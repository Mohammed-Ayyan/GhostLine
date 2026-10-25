import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

from ghostline.core.llm_client import AnswerResult
from ghostline.core.ocr_engine import ParsedQuestion
from ghostline.ui.code_renderer import extract_code_and_prose

# Question and presentation type taxonomy
TYPE_MCQ = "mcq"
TYPE_CODE = "code"
TYPE_THEORY = "theory"
TYPE_TRUE_FALSE = "true_false"
TYPE_NUMERICAL = "numerical"
TYPE_FILL_BLANK = "fill_blank"
TYPE_GENERIC = "generic"
TYPE_UNCERTAIN = "uncertain"
TYPE_ERROR = "error"


@dataclass
class PresentedAnswer:
    """
    Centralized, type-aware representation of validated answers for the HUD and tray.
    Guarantees deterministic presentation regardless of whether the inference source
    provided optional fields like `code_snippet`.
    """
    question_type: str                   # 'mcq', 'code', 'theory', 'true_false', 'numerical', 'fill_blank', 'generic', 'uncertain', 'error'
    badge: str                           # Short 1-4 character badge for tray and HUD pill ('A', '2', '✓', 'Code', '?', '!')
    headline: str                        # Prominent answer title (e.g. "Option B: 201 Created", "Result: x = 8")
    direct_answer: str                   # Clean direct value or choice text
    explanation: str                     # Clean prose explanation / rationale
    code: Optional[str] = None           # Monospace code block if applicable
    code_language: str = ""              # Language for syntax highlighting (e.g. "python", "sql")
    options: Dict[str, str] = field(default_factory=dict)
    selected_option_key: Optional[str] = None
    is_validated: bool = True
    error: Optional[str] = None
    confidence: float = 0.0
    raw_ocr_text: str = ""
    recovery_guidance: str = ""
    question_text: str = ""

    @property
    def has_code(self) -> bool:
        return bool(self.code and self.code.strip())

    @property
    def code_snippet(self) -> Optional[str]:
        return self.code

    @property
    def formatted_clipboard_text(self) -> str:
        """Generates clean, full-text representation for system clipboard."""
        parts = []
        if self.headline:
            parts.append(self.headline)
        if self.explanation and self.explanation != self.headline:
            parts.append(self.explanation)
        if self.has_code:
            lang = self.code_language or ""
            parts.append(f"\n```{lang}\n{self.code.strip()}\n```")
        return "\n\n".join(p for p in parts if p.strip())


def build_answer_presentation(
    parsed_q: Optional[ParsedQuestion],
    ans: AnswerResult
) -> PresentedAnswer:
    """
    Builds a type-aware PresentedAnswer from a ParsedQuestion and AnswerResult.
    Safely inspects optional fields and applies intelligent heuristics so that
    no consumer ever crashes if `code_snippet` or other fields are missing.
    """
    if not isinstance(ans, AnswerResult):
        # Fallback for mock or unexpected objects
        raw_badge = getattr(ans, "tray_badge", None) or getattr(ans, "source_option_label", None) or getattr(ans, "answer_option", "✓")
        raw_exp = getattr(ans, "explanation", str(ans))
        raw_head = getattr(ans, "headline", f"Option {raw_badge}" if str(raw_badge) in ["A", "B", "C", "D", "1", "2", "3", "4", "I", "II"] else "Answer Received")
        return PresentedAnswer(
            question_type=getattr(ans, "question_type", TYPE_GENERIC),
            badge=str(raw_badge) if raw_badge else "✓",
            headline=raw_head,
            direct_answer=str(getattr(ans, "answer_option", ans)),
            explanation=raw_exp,
            is_validated=getattr(ans, "is_validated", True),
            question_text=getattr(ans, "question_text", "")
        )

    # 1. Error and Uncertainty Handling
    is_valid = getattr(ans, "is_validated", False)
    val_status = getattr(ans, "validation_status", "uncertain")
    badge_raw = getattr(ans, "tray_badge", getattr(ans, "source_option_label", "?"))

    if not is_valid or val_status in ["error", "hallucination_rejected"] or badge_raw == "!":
        is_err = (val_status == "error" or badge_raw == "!")
        err_badge = "!" if is_err else "?"
        err_msg = getattr(ans, "error", None) or getattr(ans, "explanation", "") or "Uncertain result."
        
        # Check for question extraction failure
        raw_ocr = getattr(parsed_q, "raw_text", "") or getattr(ans, "raw_ocr_text", "")
        recovery_guidance = ""
        
        if "Unreliable question extraction" in err_msg or "does not contain question indicators" in err_msg:
            headline = "Uncertain Question Extraction"
            err_badge = "?"
            is_err = False
            clean_reason = err_msg.replace("Unreliable question extraction:", "").strip()
            
            ocr_snippet = raw_ocr.strip()
            if len(ocr_snippet) > 300:
                ocr_snippet = ocr_snippet[:300] + "..."
            
            explanation_parts = [
                f"Validation note: {clean_reason}",
                f"Captured screen text:\n\"{ocr_snippet}\"" if ocr_snippet else "Captured screen text was empty or blurred.",
                "How to recover:\n• Hover cursor directly over the question prompt or press [Alt+/]\n• Ensure question text is not obstructed by menus\n• Or enter/paste the question manually in the input bar below"
            ]
            exp_text = "\n\n".join(explanation_parts)
            recovery_guidance = "Hover over question body or use manual entry below."
        else:
            headline = "Inference Pipeline Error" if is_err else "Could Not Reliably Validate Answer"
            exp_text = err_msg

        return PresentedAnswer(
            question_type=TYPE_ERROR if is_err else TYPE_UNCERTAIN,
            badge=err_badge,
            headline=headline,
            direct_answer="",
            explanation=exp_text,
            is_validated=False,
            error=err_msg,
            confidence=getattr(ans, "confidence", 0.0),
            raw_ocr_text=raw_ocr,
            recovery_guidance=recovery_guidance,
            question_text=getattr(parsed_q, "question_text", "") if parsed_q else ""
        )

    # 2. Extract code snippet safely
    code_snippet = getattr(ans, "code_snippet", None)
    code_language = getattr(ans, "code_language", "") or ""
    explanation_raw = getattr(ans, "explanation", "") or ""

    # If code_snippet is not explicitly set, check if explanation contains markdown fences
    if not code_snippet and "```" in explanation_raw:
        prose, code, lang = extract_code_and_prose(explanation_raw)
        if code:
            code_snippet = code
            code_language = lang
            explanation_raw = prose

    # Normalize code snippet to guarantee real line breaks
    if code_snippet:
        from ghostline.core.llm_client import extract_and_normalize_code, log_safe_code_diagnostic
        norm_code, norm_lang, norm_prose = extract_and_normalize_code(code_snippet, code_language)
        code_snippet = norm_code
        if norm_lang:
            code_language = norm_lang
        if norm_prose and not explanation_raw:
            explanation_raw = norm_prose
        log_safe_code_diagnostic("5. Presentation Layer - code", code_snippet)

    # Append question extraction warnings (e.g. boundary truncation or multiple questions)
    warnings_list = getattr(parsed_q, "warnings", []) if parsed_q else []
    if warnings_list:
        warning_str = "\n[Notice: " + "; ".join(warnings_list) + "]"
        if warning_str not in explanation_raw:
            explanation_raw = (explanation_raw + "\n" + warning_str).strip()

    # 3. Detect Question Type from Question Structure + Answer Result
    is_mcq = getattr(ans, "is_multiple_choice", True)
    q_options = getattr(parsed_q, "options", {}) if parsed_q else {}
    q_text = getattr(parsed_q, "question_text", "") if parsed_q else getattr(ans, "question_text", "")

    # Check for Binary True/False
    is_true_false = False
    if q_options and len(q_options) in (2, 3):
        opt_keys_clean = {k.strip("().:- ").lower() for k in q_options.keys()}
        opt_vals_clean = {v.strip().lower() for v in q_options.values() if v.strip()}
        if (opt_keys_clean and opt_keys_clean.issubset({"true", "false", "t", "f", "yes", "no"})) or \
           (opt_vals_clean and opt_vals_clean.issubset({"true", "false", "yes", "no"})):
            is_true_false = True
    elif ans.option_text and ans.option_text.strip().lower() in ["true", "false", "yes", "no"] and not (q_options and len(q_options) > 2):
        is_true_false = True

    if is_true_false:
        choice = ans.option_text.strip().capitalize() if ans.option_text else ans.source_option_label
        badge = "T" if choice.lower().startswith(("t", "y")) else "F"
        return PresentedAnswer(
            question_type=TYPE_TRUE_FALSE,
            badge=badge,
            headline=f"Answer: {choice}",
            direct_answer=choice,
            explanation=explanation_raw,
            code=code_snippet,
            code_language=code_language,
            options=q_options,
            selected_option_key=ans.source_option_label,
            is_validated=True,
            confidence=getattr(ans, "confidence", 0.95)
        )

    # Check for Multiple-Choice Questions (MCQ)
    if (q_options and len(q_options) >= 2) or (ans.source_option_label and ans.source_option_label in q_options) or (not code_snippet and is_mcq and getattr(ans, "question_type", "") in ("mcq", "true_false")):
        selected_key = ans.source_option_label or ""
        opt_text = ans.option_text or (q_options.get(selected_key, "") if selected_key else "")
        badge = getattr(ans, "tray_badge", None) or selected_key or "✓"

        # Format Headline: "Option A: [text]" or "Option 1: [text]"
        clean_opt = opt_text.strip() if opt_text else ""
        if clean_opt and badge:
            # Strip redundant "Option A: " or "A) " prefix from opt_text
            clean_opt = re.sub(
                r'^(?:option\s+)?' + re.escape(badge) + r'[\s.:\)-]+\s*',
                '',
                clean_opt,
                flags=re.IGNORECASE
            ).strip()
            if selected_key and selected_key != badge:
                clean_opt = re.sub(
                    r'^(?:option\s+)?' + re.escape(selected_key) + r'[\s.:\)-]+\s*',
                    '',
                    clean_opt,
                    flags=re.IGNORECASE
                ).strip()

        display_opt = clean_opt or opt_text
        if display_opt:
            headline = f"Option {badge}: {display_opt}"
        else:
            headline = f"Option {badge}"

        # Clean explanation to remove duplicate headline prefix
        clean_exp = explanation_raw
        if clean_exp.startswith(f"Option {badge}:"):
            clean_exp = clean_exp[len(f"Option {badge}:"):].strip()
        elif clean_exp.startswith(f"Option {badge}"):
            clean_exp = clean_exp[len(f"Option {badge}"):].strip(" :.-")

        return PresentedAnswer(
            question_type=TYPE_MCQ,
            badge=badge,
            headline=headline,
            direct_answer=opt_text or f"Option {badge}",
            explanation=clean_exp or f"Option {badge} selected based on question parameters.",
            code=code_snippet,
            code_language=code_language,
            options=q_options,
            selected_option_key=selected_key,
            is_validated=True,
            confidence=getattr(ans, "confidence", 0.95),
            question_text=q_text
        )

    # Check for Programming / Code Solution
    has_code_stem = bool(
        code_snippet or
        any(k in q_text for k in ["def ", "class ", "int main", "public static", "SELECT ", "function "]) or
        getattr(ans, "question_type", "") == "code"
    )
    if has_code_stem and code_snippet:
        direct = getattr(ans, "direct_answer", "") or getattr(ans, "option_text", "") or "Code Solution"
        headline = f"Code Solution: {direct}" if direct and direct != "Code Solution" else "Code Solution"
        return PresentedAnswer(
            question_type=TYPE_CODE,
            badge="Code",
            headline=headline,
            direct_answer=direct,
            explanation=explanation_raw,
            code=code_snippet,
            code_language=code_language,
            is_validated=True,
            confidence=getattr(ans, "confidence", 0.9),
            question_text=q_text
        )

    # Check for Numerical / Mathematical Answers
    direct_val = getattr(ans, "direct_answer", "") or getattr(ans, "option_text", "") or getattr(ans, "answer_option", "")
    is_num = bool(
        "solve for" in q_text.lower() or
        "calculate" in q_text.lower() or
        re.search(r"^\s*([a-zA-Z]\s*=\s*|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", direct_val) or
        getattr(ans, "question_type", "") == "numerical"
    )
    if is_num and direct_val:
        return PresentedAnswer(
            question_type=TYPE_NUMERICAL,
            badge="✓",
            headline=f"Result: {direct_val}" if not direct_val.lower().startswith("result:") else direct_val,
            direct_answer=direct_val,
            explanation=explanation_raw,
            code=code_snippet,
            code_language=code_language,
            is_validated=True,
            confidence=getattr(ans, "confidence", 0.9),
            question_text=q_text
        )

    # Check for Fill in the Blank
    if "fill in" in q_text.lower() or "blank" in q_text.lower() or getattr(ans, "question_type", "") == "fill_blank":
        return PresentedAnswer(
            question_type=TYPE_FILL_BLANK,
            badge="✓",
            headline=f"Missing Term: {direct_val}" if direct_val else "Fill in the Blank",
            direct_answer=direct_val,
            explanation=explanation_raw,
            code=code_snippet,
            code_language=code_language,
            is_validated=True,
            confidence=getattr(ans, "confidence", 0.85),
            question_text=q_text
        )

    # Open-ended / Theory / Conceptual Questions
    direct_ans = direct_val or getattr(ans, "answer_option", "") or "Answer"
    headline = f"Answer: {direct_ans}" if direct_ans and not direct_ans.lower().startswith("answer:") else direct_ans
    return PresentedAnswer(
        question_type=TYPE_THEORY,
        badge="✓",
        headline=headline,
        direct_answer=direct_ans,
        explanation=explanation_raw,
        code=code_snippet,
        code_language=code_language,
        is_validated=True,
        confidence=getattr(ans, "confidence", 0.85),
        question_text=q_text
    )
