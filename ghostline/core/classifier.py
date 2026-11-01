"""
Ghostline Core Question-Type Classifier
Deterministic, multi-signal classifier for desktop AI assistance.
Classes: MCQ, CODING, SHORT_ANSWER, OUTPUT_PREDICTION, UNKNOWN.
"""

import re
from enum import Enum
from typing import Optional, Dict, Any, List


class QuestionType(str, Enum):
    MCQ = "mcq"
    CODING = "coding"
    SHORT_ANSWER = "short_answer"
    OUTPUT_PREDICTION = "output_prediction"
    UNKNOWN = "unknown"


# Option prefixes on separate lines: e.g. "A.", "A)", "(A)", "a)", "1)", "1.", "(i)"
RE_OPTION_LINE = re.compile(
    r"^\s*(?:\([A-Da-d1-4]\)|[A-Da-d1-4][\)\.\:\-]|[IVXivx]+[\)\.\:\-])\s+(?!\s*(?:input|output|example|test\s*case|constraint))\S+",
    re.IGNORECASE
)

# Imperative programming verbs & indicators
RE_CODING_VERBS = re.compile(
    r"\b(?:write\s+(?:a\s+|an\s+|the\s+)?(?:[a-zA-Z\+\#]+\s+)?(?:function|program|script|method|class|query|solution|algorithm)|"
    r"write\s+(?:code|a\s+query|an\s+algorithm)|"
    r"implement\b|"
    r"design\s+(?:a|an|the)\s+(?:[a-zA-Z\+\#]+\s+)?(?:function|class|algorithm|solution|data\s+structure)|"
    r"create\s+(?:a|an|the)\s+(?:[a-zA-Z\+\#]+\s+)?(?:function|class|method|program|script|table|view)|"
    r"complete\s+(?:the\s+)?(?:code|function|class|method)|"
    r"function\s+that\s+(?:takes|returns|computes|reverses|sorts|checks)|"
    r"return\s+the\s+(?:maximum|minimum|sum|count|index|array|list|string)|"
    r"def\s+[a-zA-Z_]\w*\s*\(|"
    r"class\s+[a-zA-Z_]\w*[:\(]|"
    r"int\s+main\s*\(|"
    r"public\s+static\s+void|"
    r"public\s+class\s+|"
    r"SELECT\s+.*?\s+FROM|"
    r"time\s+complexity\s+of\s+O\(|"
    r"space\s+complexity\s+of\s+O\()\b",
    re.IGNORECASE
)

# Output prediction query phrases
RE_OUTPUT_PREDICTION = re.compile(
    r"\b(?:what\s+is\s+the\s+output(?:\s+of)?|"
    r"what\s+(?:will|does)\s+the\s+following\s+(?:code|program|snippet|function)\s+(?:print|output|return)|"
    r"find\s+the\s+output(?:\s+of)?|"
    r"predict\s+the\s+output(?:\s+of)?|"
    r"what\s+gets\s+printed|"
    r"output\s+of\s+the\s+following)\b",
    re.IGNORECASE
)

# Short-answer / Conceptual explanation query phrases
RE_SHORT_ANSWER = re.compile(
    r"\b(?:explain\s+(?:the|what|how|why|in\s+detail)|"
    r"what\s+is\s+(?:the\s+difference\s+between|a|an|meant\s+by)|"
    r"define\s+|"
    r"describe\s+(?:the|how|why)|"
    r"why\s+does\s+|"
    r"how\s+does\s+|"
    r"differentiate\s+between|"
    r"compare\s+and\s+contrast)\b",
    re.IGNORECASE
)

# Code structure indicators (e.g. syntax, braces, def, include)
RE_CODE_STRUCTURE = re.compile(
    r"(?:#include\s*<|import\s+[a-zA-Z_]|from\s+[a-zA-Z_].*?import|def\s+\w+\(.*?\)|\bint\s+\w+\s*=|\bstd::|console\.log\(|System\.out\.print|```)",
    re.IGNORECASE
)

# Example / constraint markers typical of LeetCode / HackerRank / coding tests
RE_CODE_CONSTRAINTS_EXAMPLES = re.compile(
    r"(?:Example\s*\d*\s*:|Input\s*:|Output\s*:|Constraints\s*:|\b\d+\s*<=\s*[a-zA-Z_\.\(\)]+\s*<=)",
    re.IGNORECASE
)


def extract_option_lines(text: str) -> List[str]:
    """Finds lines that strictly match multiple-choice option patterns."""
    matched = []
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        # Exclude lines that are clearly code comments or test-case descriptions
        if line_clean.startswith(("#", "//", "/*", "*")):
            continue
        if RE_OPTION_LINE.match(line_clean):
            # Check that it is not an Input/Output example formatted like "1. Input: ..."
            if not re.search(r"\b(?:Input|Output|Example)\b\s*[:\-]", line_clean, re.IGNORECASE):
                matched.append(line_clean)
    return matched


def classify_question(ocr_text: str, parsed: Optional[Any] = None) -> QuestionType:
    """
    Classifies screen question text into:
    - QuestionType.MCQ: Multiple-choice question with >= 2 distinct answer options.
    - QuestionType.CODING: Implementation/coding challenge (function, class, algorithm, constraints).
    - QuestionType.OUTPUT_PREDICTION: Code tracing asking what the code prints/returns without MCQ options.
    - QuestionType.SHORT_ANSWER: Conceptual explanation/definition without options.
    - QuestionType.UNKNOWN: Ambiguous or insufficient signals.
    """
    raw_text = (ocr_text or "").strip()
    if not raw_text:
        return QuestionType.UNKNOWN

    # 1. Detect multiple-choice options
    parsed_opts = getattr(parsed, "options", None)
    is_unlabelled = getattr(parsed, "is_unlabelled_mcq", False)
    # Only count parsed options if they are real labelled options, not unlabelled code lines
    has_parsed_opts = bool(parsed_opts and len(parsed_opts) >= 2 and not is_unlabelled)
    
    extracted_opt_lines = extract_option_lines(raw_text)
    num_opt_lines = len(extracted_opt_lines)

    # 2. Check for Output Prediction
    has_output_pred_query = bool(RE_OUTPUT_PREDICTION.search(raw_text))
    has_code_syntax = bool(RE_CODE_STRUCTURE.search(raw_text))

    if has_output_pred_query and num_opt_lines < 2:
        return QuestionType.OUTPUT_PREDICTION

    # 3. Check for Coding Challenge Signals
    has_coding_verbs = bool(RE_CODING_VERBS.search(raw_text))
    has_code_constraints = bool(RE_CODE_CONSTRAINTS_EXAMPLES.search(raw_text))

    # Adversarial check: If both coding verbs AND option patterns appear
    if num_opt_lines >= 2 or has_parsed_opts:
        # Prefer MCQ only if options are actual answer options, not code constraints/examples
        if (has_coding_verbs or has_code_constraints) and not has_output_pred_query:
            if has_code_constraints and num_opt_lines <= 2 and not has_parsed_opts:
                return QuestionType.CODING
        return QuestionType.MCQ

    # 4. Pure Coding Challenge (no MCQ options)
    if has_coding_verbs or (has_code_constraints and has_code_syntax):
        return QuestionType.CODING

    # If it has strong code structure and asks to complete/fix without options
    if has_code_syntax and any(kw in raw_text.lower() for kw in ("function", "return", "def ", "class ", "int main", "find", "code")):
        if has_output_pred_query:
            return QuestionType.OUTPUT_PREDICTION
        return QuestionType.CODING

    # 5. Short-Answer / Conceptual Explanation
    if RE_SHORT_ANSWER.search(raw_text):
        return QuestionType.SHORT_ANSWER

    # 6. Fallback based on question indicators
    if raw_text.endswith("?") and num_opt_lines < 2:
        return QuestionType.SHORT_ANSWER

    return QuestionType.UNKNOWN
