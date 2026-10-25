import sys
import json
import re
import ast
import operator
import logging
from typing import Optional, Callable, Dict, Any, List, Tuple
import requests
from pydantic import BaseModel, Field

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def normalize_tray_badge(
    badge: Optional[str],
    is_validated: bool = True,
    is_multiple_choice: bool = True,
    status: str = "normal"
) -> str:
    """
    Centralized, bulletproof badge normalizer.
    Guarantees that NO code path can EVER pass an entire answer string
    or unconstrained text into the 32x32 system tray icon.

    Rules:
    - If status == 'thinking': '' (tray renders ellipsis)
    - If status == 'ready': 'R'
    - If status == 'error' or not is_validated or badge in ('Uncertain', '?', '!', None, ''):
        returns '!' if status == 'error' else '?'
    - If is_multiple_choice is False (open-ended question):
        returns '✓' if is_validated else '?'
    - If is_multiple_choice is True:
        If badge is a short recognized option label (<= 4 chars, e.g. '1', '2', 'A', 'B', '(i)', '(iv)'):
            returns clean label
        Else (if an answer string was accidentally passed):
            returns '✓' if is_validated else '?'
    - Absolute length ceiling: 4 characters max.
    """
    if status == "thinking":
        return ""
    if status == "ready":
        return "R"
    if badge in ("?", "Uncertain", "uncertain"):
        return "?"
    if badge == "!" or status == "error":
        return "!"
    if not is_validated or badge in ("", None):
        return "?"

    # Open-ended questions ALWAYS use short status glyph '✓' (never full answer text)
    if not is_multiple_choice:
        return "✓"

    raw = str(badge).strip()

    # For multiple-choice questions, check if raw is a concise label (e.g. '1', '2', 'A', 'B', '(i)', '(iv)')
    if len(raw) <= 4 and (" " not in raw or raw.startswith("(")):
        return raw

    # Fallback safety: if full answer string was passed, represent with short status symbol
    return "✓"


class AnswerResult(BaseModel):
    source_option_label: str = Field(default="Uncertain", description="The exact validated option label (e.g. '3', 'B', '(ii)', '✓') or 'Uncertain' if unvalidated")
    option_text: str = Field(default="", description="The exact text content of the validated option")
    explanation: str = Field(default="", description="Short, concise 1-2 sentence explanation or rationale")
    is_validated: bool = Field(default=False, description="Whether the answer was successfully validated against known options or format")
    validation_status: str = Field(default="uncertain", description="Validation status: 'validated', 'uncertain', 'error', 'hallucination_rejected', 'open_ended_factual'")
    confidence_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Calibrated confidence metadata and validation telemetry")
    answer_option: str = Field(default="Uncertain", description="Backward-compatible alias for source_option_label or short open-ended answer")
    proposed_option: Optional[str] = Field(default=None, description="The raw option proposed by the model before validation")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Heuristic confidence score (not proof of factual truth)")
    raw_response: str = Field(default="", description="Complete raw text from the model")
    error: Optional[str] = Field(default=None, description="Validation or parsing error message if uncertain")
    is_multiple_choice: bool = Field(default=True, description="Whether the question was multiple-choice")
    is_unlabelled_mcq: bool = Field(default=False, description="Whether multiple-choice options were unlabelled")
    code_snippet: Optional[str] = Field(default=None, description="Extracted code solution or programming snippet")
    code_language: str = Field(default="", description="Identified language for code snippet (python, javascript, sql, etc.)")
    question_type: str = Field(default="mcq", description="Detected question type: 'mcq', 'code', 'theory', 'true_false', 'numerical', 'fill_blank', 'unknown'")
    direct_answer: str = Field(default="", description="Direct concise answer, numerical value, formula, or option value")

    @property
    def tray_badge(self) -> str:
        if self.is_validated and (not self.is_multiple_choice or self.question_type in ["code", "theory", "numerical", "fill_blank", "true_false"]):
            if self.question_type == "code":
                return "Code"
            if self.question_type == "true_false":
                return "T" if str(self.source_option_label).strip().lower().startswith(("t", "y")) else "F"
            if self.source_option_label and self.source_option_label not in ("Uncertain", "?", "!"):
                return normalize_tray_badge(self.source_option_label, is_validated=True, is_multiple_choice=False)
            return "✓"
        return normalize_tray_badge(
            self.source_option_label,
            is_validated=self.is_validated,
            is_multiple_choice=self.is_multiple_choice,
            status="error" if self.validation_status == "error" else "normal"
        )

def log_safe_code_diagnostic(stage: str, content: Any):
    """
    Logs safe diagnostic metadata for code pipeline stages without exposing private screen contents.
    Logs: Stage name, Python type, length, newline presence (ASCII 10), and literal \\n presence.
    """
    if content is None:
        logging.info("[Diagnostic Code Trace] Stage=%s | Type=None | Len=0 | has_newlines=False | has_literal_slash_n=False", stage)
        return
    text = str(content)
    has_newlines = ("\n" in text)
    has_literal_slash_n = (r"\n" in text)
    has_double_slash_n = (r"\\n" in text)
    logging.info(
        "[Diagnostic Code Trace] Stage=%s | Type=%s | Len=%d | has_newlines=%s | has_literal_slash_n=%s | has_double_slash_n=%s",
        stage, type(content).__name__, len(text), has_newlines, has_literal_slash_n, has_double_slash_n
    )

def normalize_code_newlines(code_str: str) -> str:
    """
    Decodes single and double escaped newlines outside of string literals
    while preserving:
    - Legitimate string contents (e.g. Windows paths 'C:\\notes', regexes r'\\n\\s*')
    - Indentation, blank lines, quotes, Unicode, tabs, and trailing newlines
    - Escaped quotes within string literals
    """
    if not code_str:
        return ""

    text = code_str

    # If the text already has real newlines and NO literal \n or \\n, return as-is
    if "\n" in text and r"\n" not in text and r"\\n" not in text:
        return text

    # If there are no literal \n or \\n anywhere, nothing to decode
    if r"\n" not in text and r"\\n" not in text:
        return text

    result = []
    n = len(text)
    i = 0
    in_quote = None  # None, '"', "'", '"""', "'''", '`'

    while i < n:
        # Check for start or end of triple quotes
        if in_quote is None and (text[i:i+3] == '"""' or text[i:i+3] == "'''"):
            quote_type = text[i:i+3]
            in_quote = quote_type
            result.append(quote_type)
            i += 3
            continue
        elif in_quote in ('"""', "'''") and text[i:i+3] == in_quote:
            # Check if escaped
            num_bs = 0
            k = i - 1
            while k >= 0 and text[k] == '\\':
                num_bs += 1
                k -= 1
            if num_bs % 2 == 0:
                result.append(in_quote)
                i += 3
                in_quote = None
                continue

        # Check for start or end of single/double quotes or backticks
        if in_quote is None and text[i] in ('"', "'", '`'):
            in_quote = text[i]
            result.append(text[i])
            i += 1
            continue
        elif in_quote in ('"', "'", '`') and text[i] == in_quote:
            # Check if escaped
            num_bs = 0
            k = i - 1
            while k >= 0 and text[k] == '\\':
                num_bs += 1
                k -= 1
            if num_bs % 2 == 0:
                result.append(text[i])
                i += 1
                in_quote = None
                continue

        # If we are OUTSIDE a string literal, handle \n, \\n, \t, etc.
        if in_quote is None:
            # Double-escaped newline: \\n
            if text[i:i+3] == r'\\n':
                result.append('\n')
                i += 3
                continue
            # Single-escaped newline: \n
            elif text[i:i+2] == r'\n':
                result.append('\n')
                i += 2
                continue
            # Double-escaped tab: \\t
            elif text[i:i+3] == r'\\t':
                result.append('\t')
                i += 3
                continue
            # Single-escaped tab: \t
            elif text[i:i+2] == r'\t':
                result.append('\t')
                i += 2
                continue
            # Double-escaped quote: \"
            elif text[i:i+2] == r'\"':
                result.append('"')
                i += 2
                continue
            # Escaped single quote: \'
            elif text[i:i+2] == r"\'":
                result.append("'")
                i += 2
                continue
            # Escaped carriage return
            elif text[i:i+2] == r'\r':
                i += 2
                continue

        # If INSIDE triple-quoted strings, \n also represents real newlines if encoded as \n
        elif in_quote in ('"""', "'''"):
            if text[i:i+3] == r'\\n':
                result.append('\n')
                i += 3
                continue
            elif text[i:i+2] == r'\n':
                result.append('\n')
                i += 2
                continue
        elif in_quote in ('"', "'"):
            # Check if quote is actually unclosed and transitioning to next statement
            is_escaped_nl = (text[i:i+3] == r'\\n') or (text[i:i+2] == r'\n')
            if is_escaped_nl:
                offset = 3 if text[i:i+3] == r'\\n' else 2
                remainder = text[i+offset:]
                if re.match(r'^(?:[ \t]*(?:\n|\\n)|[ \t]+(?:return|def|class|if|for|while|import|from)\b)', remainder):
                    in_quote = None
                    result.append('\n')
                    i += offset
                    continue

        # Otherwise copy character
        result.append(text[i])
        i += 1

    return "".join(result)

def decode_json_field(raw_field: str) -> str:
    """Safely decodes an extracted raw JSON string slice, handling escape sequences."""
    if not raw_field:
        return ""
    try:
        return json.loads(f'"{raw_field}"', strict=False)
    except Exception:
        # Fallback escape decoding if unescaped inner quotes prevented json.loads
        return normalize_code_newlines(raw_field)

def extract_and_normalize_code(raw: str, default_lang: str = "") -> Tuple[str, str, str]:
    """
    Extracts, normalizes, and decodes source code from model output.
    
    Returns:
        tuple of (clean_code: str, clean_lang: str, clean_explanation: str)
    
    Guarantees:
    - Never displays literal '\\n' text where actual line breaks belong.
    - Strips markdown code fences cleanly without leaking fence syntax or prose into code.
    - Preserves legitimate escapes (Windows paths C:\\..., regexes r"\\n\\s*", escaped quotes).
    - Preserves indentation, blank lines, tabs, quotes, and Unicode.
    - Separates prose explanation from code.
    """
    if not raw:
        return "", default_lang, ""

    text = str(raw).strip()
    explanation = ""
    lang = default_lang or ""
    code = ""

    # 1. Check if text contains markdown code fences: ```[lang]\n...\n```
    fence_pattern = re.compile(
        r"```([a-zA-Z0-9_\-\+]*)(?:[ \t]*\r?\n|[ \t]*\\n)(.*?)(?:```|$)",
        re.DOTALL
    )
    m = fence_pattern.search(text)
    if m:
        extracted_lang = m.group(1).strip().lower()
        if extracted_lang:
            lang = extracted_lang
        code = m.group(2).strip()
        
        prose_before = text[:m.start()].strip()
        prose_after = text[m.end():].strip()
        explanation = f"{prose_before}\n\n{prose_after}".strip()
    else:
        code = text

    # 2. Decode single and double escaped newlines cleanly
    code = normalize_code_newlines(code)

    # 3. Clean up any leftover code fences
    m_full_fence = re.match(r"^```([a-zA-Z0-9_\-\+]*)\s*\n?(.*?)\n?```$", code, re.DOTALL)
    if m_full_fence:
        if not lang and m_full_fence.group(1):
            lang = m_full_fence.group(1).strip().lower()
        code = m_full_fence.group(2).strip()
    else:
        code = re.sub(r"^```[a-zA-Z0-9_\-\+]*\s*\n?", "", code)
        code = re.sub(r"\n?\s*```$", "", code)
        code = code.strip()

    # 4. Normalize language identifier
    if not lang or lang in ("code", "text"):
        if any(tok in code for tok in ("def ", "import ", "print(", "__name__", "elif ")):
            lang = "python"
        elif any(tok in code for tok in ("function ", "const ", "let ", "console.log", "=>")):
            lang = "javascript"
        elif any(tok in code for tok in ("#include", "std::", "cout", "nullptr", "template <")):
            lang = "cpp"
        elif any(tok in code for tok in ("public class", "System.out.println", "public static void main")):
            lang = "java"
        elif any(tok in code for tok in ("SELECT ", "FROM ", "WHERE ", "INSERT INTO ")):
            lang = "sql"

    return code, lang, explanation

def extract_code_block(text: str) -> Tuple[Optional[str], str]:
    """Helper to detect and extract markdown code fence from model response."""
    if not text or "```" not in text:
        return None, ""
    clean_code, clean_lang, _ = extract_and_normalize_code(text)
    if clean_code:
        return clean_code, clean_lang or "code"
    return None, ""

def validate_code_syntax(code: str, language: str = "") -> Tuple[bool, Optional[str]]:
    """
    Validates generated source code syntax:
    - Python: AST parse validation via ast.parse
    - JavaScript / JSON: Bracket, quote, and block integrity
    - Other languages: Braces, parentheses, and string literal balancing
    Returns:
        (is_valid: bool, error_message: Optional[str])
    """
    if not code or not code.strip():
        return False, "Code snippet is empty."

    lang = (language or "").strip().lower()

    # 1. Python syntax validation via ast.parse
    if lang in ("python", "python3", "py"):
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"Python SyntaxError at line {e.lineno}: {e.msg}"
        except Exception as ex:
            return False, f"Python parse error: {str(ex)}"

    # If language was unspecified, check if it looks like Python
    if not lang and ("def " in code or "import " in code or "class " in code):
        try:
            ast.parse(code)
            return True, None
        except SyntaxError:
            pass

    # 2. Bracket, brace, parenthesis, and string balance check
    brackets = {')': '(', '}': '{', ']': '['}
    stack = []
    in_string = False
    quote_char = None
    escaped = False

    for line in code.splitlines():
        line_clean = line.strip()
        if line_clean.startswith(("//", "#", "--", ";")):
            continue

        for char in line:
            if in_string:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == quote_char:
                    in_string = False
            else:
                if char in ('"', "'", '`'):
                    in_string = True
                    quote_char = char
                elif char in brackets.values():
                    stack.append(char)
                elif char in brackets:
                    if not stack or stack[-1] != brackets[char]:
                        return False, f"Mismatched bracket '{char}' in code."
                    stack.pop()

    if in_string:
        return False, "Unclosed string literal in code."
    if stack:
        return False, f"Unclosed bracket '{stack[-1]}' in code."

    return True, None

def repair_json_escapes(raw_json: str) -> str:
    r"""
    Repairs invalid backslash escapes in JSON string literals without corrupting
    valid JSON escapes (\", \\, \/, \b, \f, \n, \r, \t, \uXXXX) or multiline strings.
    """
    valid_escape_pattern = re.compile(r'^\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})$')

    def escape_replacer(match):
        s = match.group(0)
        if valid_escape_pattern.match(s):
            return s
        return '\\\\' + s[1:]

    return re.sub(r'\\(?:u[0-9a-fA-F]{4}|.)', escape_replacer, raw_json)

def sanitize_control_characters(text: str) -> str:
    r"""
    Safely escapes non-whitespace ASCII control characters (0-31 except \t, \n, \r)
    as \u00XX so that json.loads does not throw 'Invalid control character'.
    """
    if not text:
        return ""
    def _esc(m):
        val = ord(m.group(0))
        if val in (9, 10, 13):  # Preserve \t, \n, \r for strict=False
            return m.group(0)
        return f"\\u{val:04x}"
    return re.sub(r'[\x00-\x1f]', _esc, text)

def decode_json_field(val: str) -> str:
    r"""Safely decodes an escaped JSON field string, handling \n, \t, \", and unicode escapes."""
    if not val:
        return ""
    try:
        return json.loads(f'"{val}"', strict=False)
    except Exception:
        pass
    val = val.replace('\\"', '"').replace('\\\\', '\\').replace('\\/', '/')
    val = val.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
    return val

def normalize_parsed_json_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes extracted JSON fields from LLM response:
    - Joins array of code lines into multiline string
    - Promotes code from 'answer' field if 'code' is missing
    - Ensures language and explanation fields are clean strings
    """
    if not isinstance(data, dict):
        return {}
    
    # 1. Normalize code field
    raw_code = data.get("code")
    if isinstance(raw_code, list):
        data["code"] = "\n".join(str(item) for item in raw_code)
    elif raw_code is not None and not isinstance(raw_code, str):
        data["code"] = str(raw_code)
        
    # 2. If code is missing or empty, check if answer contains code
    if not data.get("code") and data.get("answer"):
        ans_str = str(data["answer"]).strip()
        if "```" in ans_str or (len(ans_str.splitlines()) > 1 and any(kw in ans_str for kw in ("def ", "class ", "function ", "return ", "public static", "SELECT "))):
            data["code"] = ans_str
            
    # 3. String normalization for other standard fields
    for field in ("language", "answer", "explanation"):
        val = data.get(field)
        if val is not None and not isinstance(val, str):
            data[field] = str(val)
            
    return data

def extract_json_block(text: str) -> str:
    """Extracts JSON payload from potential markdown fences, truncated output, or surrounding chatter."""
    if not text:
        return ""
    m_fence = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m_fence:
        candidate = m_fence.group(1).strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            return candidate

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    elif start != -1 and end == -1:
        # Truncated JSON starting with '{'
        cand = text[start:].strip()
        unescaped_quotes = len(re.findall(r'(?<!\\)"', cand))
        if unescaped_quotes % 2 == 1:
            cand += '"'
        cand += "\n}"
        return cand

    return text.strip()

def safe_parse_model_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Robust multi-tier JSON parser for LLM outputs.
    Guarantees:
    - Never raises 'Invalid control character' JSONDecodeError (strict=False natively handles unescaped newlines/tabs)
    - Escapes raw non-whitespace ASCII control characters (0-31 except \t, \n, \r)
    - Fixes unescaped code regex backslashes (\d, \s, etc.)
    - Recovers from Python single-quoted dict syntax via ast.literal_eval
    - Resilient fallback field scanner for truncated or unescaped quotes
    - Normalizes field types (lists to strings, answer promotion)
    - Safe diagnostics without leaking sensitive data
    """
    if not text or "{" not in text:
        return None

    cleaned = extract_json_block(text)
    if not cleaned or not cleaned.startswith("{"):
        return None

    # Pre-sanitize raw non-whitespace control characters (\x00-\x08, \x0b-\x0c, \x0e-\x1f)
    sanitized = sanitize_control_characters(cleaned)

    # Tier 1: strict=False natively handles unescaped control characters (ASCII 0-31: \n, \t)
    try:
        parsed = json.loads(sanitized, strict=False)
        if isinstance(parsed, dict):
            parsed = normalize_parsed_json_fields(parsed)
            log_safe_code_diagnostic("2. Structured JSON Parse (Tier 1) - code field", parsed.get("code"))
            return parsed
    except Exception as e1:
        logging.warning(
            "[LLM Client] JSON Tier 1 parse error: %s (char %s); attempting backslash escape repair",
            type(e1).__name__, getattr(e1, "pos", "unknown")
        )

    # Tier 2: Repair invalid backslash escapes in code/regex and retry
    try:
        repaired = repair_json_escapes(sanitized)
        parsed = json.loads(repaired, strict=False)
        if isinstance(parsed, dict):
            parsed = normalize_parsed_json_fields(parsed)
            log_safe_code_diagnostic("2. Structured JSON Parse (Tier 2) - code field", parsed.get("code"))
            return parsed
    except Exception as e2:
        logging.warning(
            "[LLM Client] JSON Tier 2 parse error: %s (char %s); attempting Python literal recovery",
            type(e2).__name__, getattr(e2, "pos", "unknown")
        )

    # Tier 3: Python dict single-quote recovery via ast.literal_eval
    try:
        val = ast.literal_eval(cleaned)
        if isinstance(val, dict):
            parsed = {str(k): v for k, v in val.items()}
            parsed = normalize_parsed_json_fields(parsed)
            log_safe_code_diagnostic("2. Structured JSON Parse (Tier 3 ast) - code field", parsed.get("code"))
            return parsed
    except Exception:
        pass

    # Tier 4: Resilient field scanner (handles unescaped internal quotes and truncated JSON)
    result = {}
    try:
        # 1. Code
        m_code = re.search(r'"code"\s*:\s*"(.*?)"\s*,\s*"(?:language|explanation|answer|input)"', sanitized, re.DOTALL)
        if m_code:
            result["code"] = decode_json_field(m_code.group(1))
        else:
            m_code_end = re.search(r'"code"\s*:\s*"(.*?)(?:"\s*\}|"\s*,|$)', sanitized, re.DOTALL)
            if m_code_end:
                result["code"] = decode_json_field(m_code_end.group(1))
            else:
                # Raw code block fallback within JSON
                m_code_raw = re.search(r'"code"\s*:\s*(?:"""|```)?(.*?)(?:"""|```)?\s*,\s*"(?:language|explanation|answer)"', sanitized, re.DOTALL)
                if m_code_raw:
                    result["code"] = m_code_raw.group(1).strip()

        # 2. Language
        m_lang = re.search(r'"language"\s*:\s*"([^"]+)"', sanitized)
        if m_lang:
            result["language"] = m_lang.group(1)

        # 3. Answer
        m_ans = re.search(r'"answer"\s*:\s*"([^"]+)"', sanitized)
        if m_ans:
            result["answer"] = decode_json_field(m_ans.group(1))

        # 4. Explanation
        m_exp = re.search(r'"explanation"\s*:\s*"(.*?)"(?:\s*\}|\s*,)', sanitized, re.DOTALL)
        if m_exp:
            result["explanation"] = decode_json_field(m_exp.group(1))

        result = normalize_parsed_json_fields(result)
        if result.get("code") or result.get("answer"):
            log_safe_code_diagnostic("2. Structured JSON Parse (Tier 4 scanner) - code field", result.get("code"))
            return result
    except Exception as e4:
        logging.warning("[LLM Client] JSON Tier 4 field scanner error: %s", type(e4).__name__)

    return None


ALLOWED_MATH_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _safe_eval_ast(node: ast.AST):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Non-numeric constant")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_MATH_OPERATORS:
            raise ValueError(f"Operator {op_type} not allowed")
        left = _safe_eval_ast(node.left)
        right = _safe_eval_ast(node.right)
        return ALLOWED_MATH_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_MATH_OPERATORS:
            raise ValueError(f"Operator {op_type} not allowed")
        operand = _safe_eval_ast(node.operand)
        return ALLOWED_MATH_OPERATORS[op_type](operand)
    else:
        raise ValueError(f"Node type {type(node)} not allowed")

def try_solve_deterministic_math(text: str) -> Tuple[Optional[str], Optional[float]]:
    """
    Deterministically and safely solves standard arithmetic expressions and simple linear equations.
    Only allows basic arithmetic AST evaluation (pure math, zero risk of code injection).
    """
    if not text:
        return None, None

    # 1. Linear equation: e.g. "3x + 15 = 42" or "2y - 6 = 12"
    m_lin = re.search(r"\b([+-]?\s*\d*)\s*([a-zA-Z])\s*([+-]\s*\d+)\s*=\s*([+-]?\s*\d+)\b", text)
    if m_lin:
        a_str, var, b_str, c_str = m_lin.groups()
        a_str = a_str.replace(" ", "")
        if not a_str or a_str == "+":
            a = 1.0
        elif a_str == "-":
            a = -1.0
        else:
            try:
                a = float(a_str)
            except ValueError:
                a = 0.0
        try:
            b = float(b_str.replace(" ", ""))
            c = float(c_str.replace(" ", ""))
            if a != 0:
                sol = (c - b) / a
                sol_num = int(sol) if sol.is_integer() else round(sol, 4)
                return f"{var} = {sol_num}", float(sol_num)
        except Exception:
            pass

    # 2. Arithmetic expression: e.g. "25 * 4 - 30 / 2" or "17 % 5 + 2 * 3^2"
    m_arith = re.search(r"(\d+(?:\.\d+)?(?:\s*[\+\-\*\/\%\^]\s*\d+(?:\.\d+)?)+)", text)
    if m_arith:
        expr = m_arith.group(1).strip()
        expr = re.sub(r"\s+", "", expr)
        expr = re.sub(r"[\+\-\*\/\%\^]+$", "", expr)
        py_expr = expr.replace("^", "**")
        try:
            tree = ast.parse(py_expr, mode='eval')
            val = _safe_eval_ast(tree.body)
            if isinstance(val, (int, float)):
                val_num = int(val) if float(val).is_integer() else round(float(val), 4)
                return str(val_num), float(val_num)
        except Exception:
            pass

    return None, None

def classify_question_type(question_text: str, options: Optional[Dict[str, str]] = None) -> str:
    """Classifies question into one of: 'mcq', 'true_false', 'numerical', 'programming', 'theory'."""
    text_clean = (question_text or "").strip().lower()
    
    if options and len(options) >= 2:
        opt_keys_clean = set(k.strip("().:- ").lower() for k in options.keys())
        opt_vals_clean = set(v.strip("().:- ").lower() for v in options.values())
        if opt_keys_clean.issubset({"true", "false", "t", "f"}) or opt_vals_clean.issubset({"true", "false", "t", "f"}):
            return "true_false"
        return "mcq"

    # Open-ended
    # 1. True / False indicators
    if re.search(r"\b(?:true\s+or\s+false|state\s+whether\s+true|is\s+true\s+or\s+false|is\s+this\s+true)\b", text_clean):
        return "true_false"
    if text_clean.startswith("state whether") or text_clean.startswith("true or false:"):
        return "true_false"

    # 2. Programming / Code
    code_indicators = [
        "def ", "class ", "int main", "public static", "select ", "console.log", "return ",
        "import ", "function ", "```", "len(", "dereferencing", "pointer",
        "write a function", "write a python", "write a program", "implement a", "implement the",
        "time complexity", "space complexity", "algorithm", "binary search", "linked list",
        "c++", "cpp", "javascript", "python", "java", "sql query", "method", "stdin", "stdout"
    ]
    if any(ind in text_clean for ind in code_indicators):
        return "programming"

    # 3. Numerical / Math
    math_indicators = ["solve for", "calculate", "evaluate", "derivative", "hit ratio", "amat", "what is the result of", "ip addresses", "usable hosts"]
    if any(ind in text_clean for ind in math_indicators) or re.search(r"\d+\s*[\+\-\*\/\%\^]\s*\d+", text_clean) or re.search(r"\b[a-zA-Z]\s*=\s*\d+", text_clean):
        return "numerical"

    return "theory"


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", default_model: str = "phi3:mini"):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def is_available(self) -> bool:
        """Verifies if the local Ollama daemon is reachable on localhost."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Returns list of installed local models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def check_health(self) -> Tuple[bool, List[str]]:
        """Returns (is_available, list_of_models) with short timeout."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                return True, models
        except Exception:
            pass
        return False, []

    def pull_model(self, model_name: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> Tuple[bool, str]:
        """Pulls model from Ollama daemon with real progress tracking."""
        try:
            resp = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": True},
                stream=True,
                timeout=600.0
            )
            if resp.status_code != 200:
                return False, f"Ollama HTTP error {resp.status_code}"
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line.decode("utf-8"))
                    status = data.get("status", "")
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    pct = (completed / total * 100.0) if total > 0 else 0.0
                    if progress_callback:
                        progress_callback(status, pct)
                except Exception:
                    pass
            return True, f"Model '{model_name}' successfully installed."
        except Exception as e:
            return False, str(e)

    def generate(self, prompt: str, model: Optional[str] = None, system: Optional[str] = None) -> str:
        """General text generation endpoint for live conversation copilot and direct prompts."""
        selected_model = model or self.default_model
        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 400}
        }
        if system:
            payload["system"] = system
        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


    def solve_question(
        self,
        question_text: str,
        options: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        is_unlabelled_mcq: bool = False,
        constraints: Optional[List[str]] = None,
        examples: Optional[List[Dict[str, str]]] = None,
        input_format: str = "",
        output_format: str = "",
        starter_code: str = "",
        requested_language: str = "",
        question_type: Optional[str] = None
    ) -> AnswerResult:
        """
        Submits question and options to local Ollama LLM and validates structured output.
        """
        selected_model = model or self.default_model

        # 1. Classify question type
        q_type = question_type or classify_question_type(question_text, options)

        # 2. Build structured, question-type-tailored prompt
        prompt = self._construct_prompt(
            question_text,
            options,
            is_unlabelled_mcq=is_unlabelled_mcq,
            question_type=q_type,
            constraints=constraints,
            examples=examples,
            input_format=input_format,
            output_format=output_format,
            starter_code=starter_code,
            requested_language=requested_language
        )

        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": stream_callback is not None,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 750 if q_type == "programming" else 250
            }
        }

        # For programming questions, prefer structured JSON output schema
        if q_type == "programming":
            payload["format"] = {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string"},
                    "answer": {"type": "string"},
                    "explanation": {"type": "string"}
                },
                "required": ["code", "language", "answer", "explanation"]
            }

        full_response = ""

        try:
            if stream_callback:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    stream=True,
                    timeout=60.0
                )
                if resp.status_code == 400 and isinstance(payload.get("format"), dict):
                    # Fallback to string format for older Ollama versions
                    payload["format"] = "json"
                    resp = requests.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        stream=True,
                        timeout=60.0
                    )
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode("utf-8", errors="replace") if isinstance(line, (bytes, bytearray)) else str(line)
                        line_str = line_str.strip()
                        if not line_str:
                            continue
                        try:
                            chunk = json.loads(line_str, strict=False)
                        except Exception:
                            sanitized_line = sanitize_control_characters(line_str)
                            try:
                                chunk = json.loads(sanitized_line, strict=False)
                            except Exception:
                                m_resp = re.search(r'"response"\s*:\s*"(.*?)"', line_str)
                                chunk = {"response": m_resp.group(1)} if m_resp else {}
                        token = chunk.get("response", "")
                        full_response += token
                        stream_callback(token)
            else:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=60.0
                )
                if resp.status_code == 400 and isinstance(payload.get("format"), dict):
                    payload["format"] = "json"
                    resp = requests.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        timeout=60.0
                    )
                resp.raise_for_status()
                text_content = getattr(resp, "text", None)
                if isinstance(text_content, str) and text_content.strip():
                    try:
                        full_response = json.loads(text_content, strict=False).get("response", "")
                    except Exception:
                        sanitized_text = sanitize_control_characters(text_content)
                        try:
                            full_response = json.loads(sanitized_text, strict=False).get("response", "")
                        except Exception:
                            m_resp = re.search(r'"response"\s*:\s*"(.*?)"', text_content, re.DOTALL)
                            full_response = m_resp.group(1) if m_resp else text_content
                elif callable(getattr(resp, "json", None)):
                    try:
                        full_response = resp.json().get("response", "")
                    except Exception:
                        full_response = ""

            log_safe_code_diagnostic("1. Raw Ollama Response", full_response)

            result = self._parse_and_validate_response(
                full_response,
                options,
                is_unlabelled_mcq=is_unlabelled_mcq,
                question_text=question_text,
                question_type=q_type,
                requested_language=requested_language
            )

            # If programming question produced malformed output or missing code, attempt ONE controlled retry
            if q_type == "programming" and not getattr(result, "code_snippet", None):
                logging.info("[LLM Client] Structured code extraction empty. Executing 1 controlled retry with correction prompt...")
                try:
                    retry_prompt = (
                        f"Previous answer did not produce a parseable code solution.\n\n"
                        f"Question:\n{question_text}\n\n"
                        f"Return ONLY a valid JSON object with keys: \"code\", \"language\", \"answer\", \"explanation\".\n"
                        f"Escape all newlines in code as \\n and double quotes as \\\".\n"
                        f'{{"code": "SOURCE_CODE_HERE", "language": "{requested_language or "python"}", "answer": "Direct Answer", "explanation": "Brief explanation"}}'
                    )
                    retry_payload = {
                        "model": selected_model,
                        "prompt": retry_prompt,
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 1024}
                    }
                    if isinstance(payload.get("format"), dict):
                        retry_payload["format"] = payload["format"]
                    else:
                        retry_payload["format"] = "json"

                    retry_resp = requests.post(f"{self.base_url}/api/generate", json=retry_payload, timeout=45.0)
                    if retry_resp.status_code == 200:
                        try:
                            retry_text = json.loads(retry_resp.text, strict=False).get("response", "")
                        except Exception:
                            retry_text = retry_resp.text
                        if retry_text:
                            retry_result = self._parse_and_validate_response(
                                retry_text,
                                options,
                                is_unlabelled_mcq=is_unlabelled_mcq,
                                question_text=question_text,
                                question_type=q_type,
                                requested_language=requested_language
                            )
                            if getattr(retry_result, "code_snippet", None):
                                result = retry_result
                                full_response = retry_text
                except Exception as retry_err:
                    logging.warning("[LLM Client] Controlled retry encountered error: %s", retry_err)
            
            # Diagnostic logging (redacting screen content, logging structured tokens)
            try:
                print(f"[*] [LLM Diagnostic] Model: {selected_model} | Output Length: {len(full_response)} chars")
                print(f"[*] [LLM Diagnostic] Proposed: {result.proposed_option} | Validated: {result.is_validated} | Final Badge: {result.tray_badge} | Answer: {result.answer_option}")
                if result.error:
                    print(f"[!] [LLM Diagnostic] Validation Warning: {result.error}")
            except Exception:
                pass

            return result

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to local Ollama daemon at {self.base_url}. "
                "Ensure Ollama is started locally (`ollama serve`)."
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Ollama inference timed out after 60s at {self.base_url}.")
        except requests.exceptions.HTTPError as http_err:
            raise RuntimeError(f"Ollama HTTP communication error: {str(http_err)}")
        except Exception as ex:
            raise RuntimeError(f"Local AI inference failed: {str(ex)}")

    def _construct_prompt(
        self,
        question: str,
        options: Optional[Dict[str, str]],
        is_unlabelled_mcq: bool = False,
        question_type: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        examples: Optional[List[Dict[str, str]]] = None,
        input_format: str = "",
        output_format: str = "",
        starter_code: str = "",
        requested_language: str = ""
    ) -> str:
        q_type = question_type or classify_question_type(question, options)

        if options and len(options) >= 2:
            options_list = ", ".join(options.keys())
            formatted_opts = []
            for k, v in options.items():
                if k.endswith((")", ".", ":", "-", "]")):
                    formatted_opts.append(f"{k} {v}")
                else:
                    formatted_opts.append(f"{k}) {v}")
            options_text = "Options:\n" + "\n".join(formatted_opts)

            math_hint = ""
            if any(sym in question for sym in ("^", "%", "*", "/", "+", "-")):
                math_hint = "\nNote: In mathematical expressions, '^' denotes exponentiation (e.g. 3^2 = 9), NOT bitwise XOR. Follow standard mathematical order of operations (PEMDAS).\n"

            if is_unlabelled_mcq:
                instruction_1 = f"1. On the very first line, state ONLY the single correct option number ({options_list}), formatted exactly as:\nANSWER: [OPTION_NUMBER]\n(For example: 'ANSWER: 1' or 'ANSWER: 2')"
            else:
                instruction_1 = f"1. On the very first line, state ONLY the single correct option label, formatted exactly as:\nANSWER: [OPTION_LABEL]\n(For example: 'ANSWER: 2' or 'ANSWER: B' or 'ANSWER: (ii)')"

            return f"""You are Ghostline, a high-precision question-answering assistant.
Analyze the following multiple-choice question and determine the single correct answer option.

Question:
{question}

{options_text}
{math_hint}
Instructions:
{instruction_1}
2. On line 2, provide a clear, concise 1-2 sentence explanation justifying why this option is correct.
3. You MUST choose strictly from the provided options ({options_list}). Never invent or assume an option that is not listed.
"""

        # Non-MCQ / Open-ended prompt tailored by question type
        if q_type == "true_false":
            return f"""You are Ghostline, a high-precision question-answering assistant.
Analyze the following statement and determine if it is True or False.

Statement:
{question}

Instructions:
1. On line 1, state ONLY 'True' or 'False'.
2. On line 2, provide a concise 1-sentence explanation justifying why it is True or False.
"""

        elif q_type == "numerical":
            return f"""You are Ghostline, a high-precision mathematician and computer engineer.
Solve the following numerical problem carefully.

Problem:
{question}

Note: In mathematical expressions, '^' denotes exponentiation (e.g. 3x^3 is 3 times x cubed; 3^2 = 9), NOT bitwise XOR. Follow standard mathematical order of operations (PEMDAS).

Instructions:
1. On line 1, state ONLY the final concise numerical answer or value (e.g. '20' or 'x = 9' or '31').
2. On line 2, provide the concise step-by-step calculation or derivation.
"""

        elif q_type == "programming":
            lang_req = requested_language or "python"
            sections = [f"Problem Statement:\n{question}"]
            if constraints:
                sections.append("Constraints:\n" + "\n".join(f"- {c}" for c in constraints))
            if input_format:
                sections.append(f"Input Format:\n{input_format}")
            if output_format:
                sections.append(f"Output Format:\n{output_format}")
            if examples:
                ex_lines = []
                for idx, ex in enumerate(examples, 1):
                    ex_lines.append(f"Example {idx}:")
                    if ex.get("input"):
                        ex_lines.append(f"  Input: {ex['input']}")
                    if ex.get("output"):
                        ex_lines.append(f"  Output: {ex['output']}")
                    if ex.get("explanation"):
                        ex_lines.append(f"  Explanation: {ex['explanation']}")
                sections.append("Examples:\n" + "\n".join(ex_lines))
            if starter_code:
                sections.append(f"Starter Code:\n{starter_code}")

            sections.append(f"Requested Programming Language: {lang_req}")
            prompt_body = "\n\n".join(sections)

            return f"""You are Ghostline, a high-precision software engineer.
Analyze and solve the following programming problem in {lang_req}.

{prompt_body}

Instructions:
Respond strictly in JSON format with the following fields:
{{
  "code": "The complete, clean, runnable source code solution in {lang_req} (preserve all indentation and newlines)",
  "language": "{lang_req}",
  "answer": "Short 1-line summary or function signature",
  "explanation": "Clear, concise 1-2 sentence explanation of the approach and time/space complexity"
}}
"""

        else:  # theory
            return f"""You are Ghostline, a high-precision technical instructor.
Analyze the following technical question and provide a direct, factual explanation.

Question:
{question}

Instructions:
1. On line 1, state a direct, concise, factual explanation answering the question in 2-3 sentences.
2. Directly mention the core architectural and technical terms (e.g. mechanisms, protocols, components, definitions).
"""

    def _parse_and_validate_response(
        self,
        text: str,
        options: Optional[Dict[str, str]],
        is_unlabelled_mcq: bool = False,
        question_text: str = "",
        question_type: Optional[str] = None,
        requested_language: str = ""
    ) -> AnswerResult:
        cleaned = text.strip()
        code_snip, code_lang = extract_code_block(cleaned)

        # Check for structured JSON response (Ollama JSON schema or manual JSON)
        parsed_json = None
        if "{" in cleaned:
            parsed_json = safe_parse_model_json(cleaned)

        if not cleaned:
            return AnswerResult(
                source_option_label="Uncertain",
                option_text="",
                answer_option="Uncertain",
                proposed_option=None,
                is_validated=False,
                validation_status="uncertain",
                confidence=0.0,
                confidence_metadata={"calibrated": False, "score": 0.0, "status": "empty_response"},
                explanation="Model returned an empty response.",
                raw_response=text,
                error="Empty model response",
                is_multiple_choice=bool(options and len(options) >= 2),
                is_unlabelled_mcq=is_unlabelled_mcq,
                code_snippet=None,
                code_language="",
                question_type="unknown",
                direct_answer=""
            )

        # CASE 1: Multiple Choice Question with extracted options
        if options and len(options) >= 2:
            # Deterministic arithmetic cross-validation check for MCQs
            det_math_ans, det_math_num = try_solve_deterministic_math(question_text)
            opt_math_match = None
            if det_math_ans or det_math_num is not None:
                for k, v in options.items():
                    v_clean = v.strip().lower()
                    if (det_math_ans and det_math_ans.lower() == v_clean) or (
                        det_math_num is not None and str(int(det_math_num) if float(det_math_num).is_integer() else det_math_num) == v_clean
                    ):
                        opt_math_match = k
                        break

            # Build normalized lookup table: maps normalized keys to the exact source key
            lookup: Dict[str, str] = {}
            for k in options.keys():
                lookup[k] = k
                lookup[k.lower()] = k
                lookup[k.upper()] = k
                clean = k.strip("()[]:.- ")
                if clean:
                    lookup[clean] = k
                    lookup[clean.lower()] = k
                    lookup[clean.upper()] = k

            lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
            first_line = lines[0] if lines else ""

            proposed = None
            
            # Pattern 0: Structured JSON answer field
            if parsed_json and isinstance(parsed_json, dict):
                cand_ans = str(parsed_json.get("answer") or parsed_json.get("option") or "").strip()
                if cand_ans:
                    proposed = cand_ans

            # Pattern 1: Explicit "ANSWER: [TOKEN]"
            if not proposed:
                m_ans = re.search(r"ANSWER\s*[:\-]?\s*(\([^\)]+\)|\[[^\]]+\]|[^\s,;]+)", first_line, re.IGNORECASE)
                if m_ans:
                    proposed = m_ans.group(1).strip()

            # Pattern 2: Option prefix on line 1, e.g. "B) ...", "3. ...", "(ii) ..."
            if not proposed:
                m_prefix = re.match(r"^(\([^\)]+\)|\[[^\]]+\]|[^\s\)\.\:\-]+)[\)\]\.\:\-]\s*", first_line)
                if m_prefix:
                    candidate = m_prefix.group(1).strip()
                    if candidate in lookup or candidate.strip("()[]:.- ") in lookup:
                        proposed = candidate

            # Pattern 3: "Option X" or "Choice X"
            if not proposed:
                m_opt = re.search(r"(?:Correct\s+Option|Option|Choice|Answer)\s*[:\-]?\s*(\([^\)]+\)|\[[^\]]+\]|[^\s,;]+)", first_line, re.IGNORECASE)
                if m_opt:
                    proposed = m_opt.group(1).strip()

            # Pattern 4: Global search for explicit "ANSWER: [TOKEN]" anywhere in text
            if not proposed:
                m_global = re.search(r"\bANSWER\s*[:\-]?\s*(\([^\)]+\)|\[[^\]]+\]|[^\s,;]+)", cleaned, re.IGNORECASE)
                if m_global:
                    proposed = m_global.group(1).strip()

            # Pattern 5: Content match — check if model responded directly with option text
            if not proposed:
                for k, v in options.items():
                    if v and len(v) >= 3 and v.lower() in first_line.lower():
                        proposed = k
                        break

            # STRICT VALIDATION: Resolve proposed token against exact source options
            matched_key = None
            if proposed:
                matched_key = lookup.get(proposed) or lookup.get(proposed.strip("()[]:.- ")) or lookup.get(proposed.upper()) or lookup.get(proposed.lower())

            # Fallback: if proposed was not an option key, check if model answered with the option VALUE
            if not matched_key:
                if proposed:
                    proposed_clean = proposed.strip("()[]:.- ").lower()
                    for k, v in options.items():
                        v_clean = v.strip().lower()
                        if proposed_clean == v_clean or proposed.lower() == v.lower():
                            matched_key = k
                            break

                if not matched_key:
                    for k, v in options.items():
                        v_clean = v.strip().lower()
                        if len(v_clean) >= 2 and (f" {v_clean} " in f" {first_line.lower()} " or first_line.lower().endswith(v_clean)):
                            matched_key = k
                            break

            # Deterministic math match fallback: if model was unparseable or made arithmetic error, but math matched an option
            if not matched_key and opt_math_match:
                matched_key = opt_math_match
                proposed = opt_math_match

            is_tf = bool(set(k.strip("().:- ").lower() for k in options.keys()).issubset({"true", "false", "t", "f"}))
            mcq_type = "true_false" if is_tf else "mcq"

            if matched_key and matched_key in options:
                validated_label = matched_key
                opt_content = options[validated_label]
                
                # Extract explanation lines
                explanation_lines = lines[1:] if (len(lines) > 1 and lines[0].startswith(("ANSWER", proposed or "", validated_label))) else lines
                explanation = "\n".join(explanation_lines).strip()
                if not explanation:
                    explanation = f"Option {validated_label}: {opt_content}"
                if opt_math_match and opt_math_match == validated_label:
                    explanation = f"[Verified by deterministic calculation: {det_math_ans}]\n{explanation}"

                return AnswerResult(
                    source_option_label=validated_label,
                    option_text=opt_content,
                    answer_option=validated_label,
                    proposed_option=proposed,
                    is_validated=True,
                    validation_status="validated",
                    confidence=0.98 if opt_math_match == validated_label else 0.95,
                    confidence_metadata={
                        "score": 0.98 if opt_math_match == validated_label else 0.95,
                        "calibrated": False,
                        "validation_type": "exact_option_match",
                        "matched_key": validated_label,
                        "disclaimer": "Schema validation confirms deterministic alignment with extracted options, not factual ground truth."
                    },
                    explanation=explanation,
                    raw_response=cleaned,
                    is_multiple_choice=True,
                    is_unlabelled_mcq=is_unlabelled_mcq,
                    code_snippet=code_snip,
                    code_language=code_lang,
                    question_type=mcq_type,
                    direct_answer=opt_content
                )
            else:
                err_msg = (
                    f"Model proposed option '{proposed}', which does not exist in valid choices {list(options.keys())}."
                    if proposed else
                    f"Model output could not be deterministically parsed into an option in {list(options.keys())}."
                )
                return AnswerResult(
                    source_option_label="Uncertain",
                    option_text="",
                    answer_option="Uncertain",
                    proposed_option=proposed,
                    is_validated=False,
                    validation_status="hallucination_rejected" if proposed else "uncertain",
                    confidence=0.0,
                    confidence_metadata={
                        "score": 0.0,
                        "calibrated": False,
                        "validation_type": "rejected",
                        "disclaimer": "Schema validation rejected model output as ungrounded or absent."
                    },
                    explanation=f"Uncertain: {err_msg}\n\nRaw output:\n{cleaned}",
                    raw_response=cleaned,
                    error=err_msg,
                    is_multiple_choice=True,
                    is_unlabelled_mcq=is_unlabelled_mcq,
                    code_snippet=code_snip,
                    code_language=code_lang,
                    question_type="unknown",
                    direct_answer=""
                )

        # CASE 2: Open-ended question without multiple-choice options
        if parsed_json and isinstance(parsed_json, dict):
            json_code = parsed_json.get("code")
            json_ans = str(parsed_json.get("answer") or parsed_json.get("direct_answer") or "").strip()
            json_lang = str(parsed_json.get("language") or parsed_json.get("lang") or "").strip()
            json_exp = str(parsed_json.get("explanation") or parsed_json.get("rationale") or "").strip()

            # If json_code was empty, but json_ans has code (e.g. small models putting code in answer)
            if not json_code and json_ans and ("```" in json_ans or any(k in json_ans for k in ("def ", "function ", "#include", "public class", "int main", "SELECT "))):
                c_extracted, l_extracted, p_extracted = extract_and_normalize_code(json_ans, json_lang)
                if c_extracted:
                    json_code = c_extracted
                    if not json_lang:
                        json_lang = l_extracted
                    if p_extracted and not json_exp:
                        json_exp = p_extracted

            if json_code:
                final_code, final_lang, p_extracted = extract_and_normalize_code(
                    str(json_code), json_lang or code_lang or requested_language
                )
                exp_text = json_exp or p_extracted or "Code solution generated by model."
                disp_ans = json_ans or (final_code.splitlines()[0] if final_code else "Code Solution")
                if disp_ans.startswith("```"):
                    disp_ans = "Code Solution"

                # Validate syntax
                is_syntax_valid, syntax_err = validate_code_syntax(final_code, final_lang)
                val_status = "open_ended_factual" if is_syntax_valid else "syntax_error"
                badge = "Code" if is_syntax_valid else "?"
                confidence = 0.95 if is_syntax_valid else 0.40
                err_msg = syntax_err if not is_syntax_valid else None
                if not is_syntax_valid:
                    exp_text = f"Code syntax warning: {syntax_err}\n\n{exp_text}"

                log_safe_code_diagnostic("3. AnswerResult construction - code_snippet", final_code)

                return AnswerResult(
                    source_option_label=badge,
                    option_text=disp_ans[:100],
                    answer_option=badge,
                    proposed_option=disp_ans[:100],
                    is_validated=is_syntax_valid,
                    validation_status=val_status,
                    confidence=confidence,
                    confidence_metadata={
                        "score": confidence,
                        "calibrated": False,
                        "validation_type": "structured_code_json",
                        "syntax_validated": is_syntax_valid,
                        "syntax_error": syntax_err,
                        "disclaimer": "Structured programming output validated via syntax analyzer."
                    },
                    explanation=exp_text,
                    raw_response=cleaned,
                    error=err_msg,
                    is_multiple_choice=False,
                    is_unlabelled_mcq=False,
                    code_snippet=final_code,
                    code_language=final_lang,
                    question_type="code",
                    direct_answer=disp_ans
                )
            elif (question_type == "programming" or classify_question_type(question_text) == "programming"):
                err_msg = "Model did not provide a valid source code solution."
                log_safe_code_diagnostic("3. AnswerResult construction - error (no code)", None)
                return AnswerResult(
                    source_option_label="!",
                    option_text="",
                    answer_option="!",
                    proposed_option=None,
                    is_validated=False,
                    validation_status="error",
                    confidence=0.0,
                    confidence_metadata={"score": 0.0, "calibrated": False, "status": "no_code_produced"},
                    explanation=f"{err_msg} Click 'Retry' to re-query the model.",
                    raw_response=cleaned,
                    error=err_msg,
                    is_multiple_choice=False,
                    is_unlabelled_mcq=False,
                    code_snippet=None,
                    code_language="",
                    question_type="error",
                    direct_answer="",
                    tray_badge="!"
                )
            elif json_ans or json_exp:
                # Structured non-code response
                disp_ans = json_ans if json_ans else ""
                exp_text = json_exp if json_exp else disp_ans
                q_type = question_type or "theory"
                # Check deterministic math
                det_ans, det_num = try_solve_deterministic_math(question_text)
                if det_ans:
                    disp_ans = det_ans
                    exp_text = f"Calculated: {det_ans}\n{exp_text}"
                    q_type = "numerical"

                return AnswerResult(
                    source_option_label="✓",
                    option_text=disp_ans[:100],
                    answer_option=disp_ans[:100],
                    proposed_option=disp_ans[:100],
                    is_validated=True,
                    validation_status="open_ended_factual",
                    confidence=0.9,
                    confidence_metadata={
                        "score": 0.9,
                        "calibrated": False,
                        "validation_type": "structured_text_json",
                        "disclaimer": "Structured output validated via JSON schema."
                    },
                    explanation=exp_text,
                    raw_response=cleaned,
                    is_multiple_choice=False,
                    is_unlabelled_mcq=False,
                    code_snippet=None,
                    code_language="",
                    question_type=q_type,
                    direct_answer=disp_ans
                )

        lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
        if lines:
            short_ans = lines[0]
            short_ans = re.sub(r"^(?:ANSWER|Answer)\s*[:\-]?\s*", "", short_ans).strip()
            explanation = "\n".join(lines[1:]).strip() if len(lines) > 1 else short_ans
            
            # Detect question type
            m_tf = re.match(r"^(true|false|yes|no)\b", short_ans, re.IGNORECASE)
            if code_snip:
                clean_c, clean_l, clean_p = extract_and_normalize_code(code_snip, code_lang)
                log_safe_code_diagnostic("3. Fallback Markdown Parse - code_snippet", clean_c)
                return AnswerResult(
                    source_option_label="Code",
                    option_text=clean_c.splitlines()[0][:100] if clean_c else "Code Solution",
                    answer_option="Code",
                    proposed_option="Code",
                    is_validated=True,
                    validation_status="open_ended_factual",
                    confidence=0.9,
                    confidence_metadata={"score": 0.9, "calibrated": False, "validation_type": "markdown_code_fence"},
                    explanation=clean_p or explanation,
                    raw_response=cleaned,
                    is_multiple_choice=False,
                    is_unlabelled_mcq=False,
                    code_snippet=clean_c,
                    code_language=clean_l,
                    question_type="code",
                    direct_answer="Code Solution"
                )
            elif (question_type == "programming" or classify_question_type(question_text) == "programming"):
                err_msg = "Model did not provide a valid source code solution."
                log_safe_code_diagnostic("3. Fallback Markdown Parse - error (no code)", None)
                return AnswerResult(
                    source_option_label="!",
                    option_text="",
                    answer_option="!",
                    proposed_option=None,
                    is_validated=False,
                    validation_status="error",
                    confidence=0.0,
                    confidence_metadata={"score": 0.0, "calibrated": False, "status": "no_code_produced"},
                    explanation=f"{err_msg} Click 'Retry' to re-query the model.",
                    raw_response=cleaned,
                    error=err_msg,
                    is_multiple_choice=False,
                    is_unlabelled_mcq=False,
                    code_snippet=None,
                    code_language="",
                    question_type="error",
                    direct_answer="",
                    tray_badge="!"
                )
            elif m_tf or question_type == "true_false":
                q_type = "true_false"
                val_tf = "True" if ((m_tf and m_tf.group(1).lower() in ("true", "yes")) or ("true" in short_ans.lower() and "false" not in short_ans.lower())) else "False"
                short_ans = val_tf
                source_label = val_tf
            elif question_type == "numerical" or re.search(r"^\s*([a-zA-Z]\s*=\s*|[-+]?\d*\.?\d+)", short_ans):
                q_type = "numerical"
                source_label = "✓"
                # Check deterministic math calculation
                det_ans, det_num = try_solve_deterministic_math(question_text)
                if det_ans:
                    short_ans = det_ans
                    explanation = f"Calculated: {det_ans}\n{explanation}"
            elif "fill in" in cleaned.lower() or "blank" in cleaned.lower():
                q_type = "fill_blank"
                source_label = "✓"
            else:
                q_type = "theory"
                source_label = "✓"

            return AnswerResult(
                source_option_label=source_label,
                option_text=short_ans[:100],
                answer_option=short_ans[:100],
                proposed_option=short_ans[:100],
                is_validated=True,
                validation_status="open_ended_factual",
                confidence=0.85,
                confidence_metadata={
                    "score": 0.85,
                    "calibrated": False,
                    "validation_type": "open_ended_heuristic",
                    "disclaimer": "Factual heuristic without multiple-choice verification."
                },
                explanation=explanation,
                raw_response=cleaned,
                is_multiple_choice=False,
                is_unlabelled_mcq=False,
                code_snippet=code_snip,
                code_language=code_lang,
                question_type=q_type,
                direct_answer=short_ans
            )

        return AnswerResult(
            source_option_label="Uncertain",
            option_text="",
            answer_option="Uncertain",
            proposed_option=None,
            is_validated=False,
            validation_status="uncertain",
            confidence=0.0,
            confidence_metadata={"score": 0.0, "calibrated": False},
            explanation="Could not extract an answer from model response.",
            raw_response=cleaned,
            error="Empty parsed lines",
            is_multiple_choice=False,
            is_unlabelled_mcq=False,
            code_snippet=None,
            code_language="",
            question_type="unknown",
            direct_answer=""
        )

