import re
import tkinter as tk
from typing import Tuple, Optional, List

# Common language keywords for fast offline syntax highlighting
KEYWORDS = {
    # Python
    "def", "class", "return", "import", "from", "as", "if", "elif", "else",
    "for", "while", "try", "except", "finally", "with", "yield", "lambda",
    "pass", "break", "continue", "raise", "assert", "global", "nonlocal",
    "async", "await", "None", "True", "False", "self", "cls",
    # JavaScript / TypeScript
    "function", "const", "let", "var", "new", "this", "typeof", "instanceof",
    "switch", "case", "default", "catch", "throw", "export", "interface", "type",
    "extends", "implements", "null", "undefined", "true", "false", "super",
    # Java
    "public", "private", "protected", "static", "final", "abstract", "void",
    "boolean", "byte", "char", "short", "int", "long", "float", "double",
    "package", "throws", "synchronized", "volatile", "transient", "native",
    "strictfp", "enum", "record",
    # C / C++ / C#
    "struct", "namespace", "using", "template", "typename", "auto", "nullptr",
    "constexpr", "const", "sizeof", "typedef", "virtual", "override", "inline",
    "friend", "operator", "explicit", "mutable",
    # SQL
    "select", "from", "where", "insert", "into", "update", "delete", "join",
    "left", "right", "inner", "outer", "group", "by", "order", "having",
    "limit", "create", "table", "alter", "drop", "index", "values", "primary",
    "key", "foreign", "references", "distinct", "union", "all", "when", "then",
    # Go / Rust
    "func", "fn", "mut", "impl", "trait", "pub", "match", "chan", "defer", "go"
}

TYPE_NAMES = {
    "str", "int", "float", "bool", "list", "dict", "set", "tuple", "bytes",
    "any", "object", "array", "number", "boolean", "void", "promise",
    "string", "char", "double", "long", "short", "byte", "String", "System",
    "Integer", "Boolean", "Double", "List", "Map", "Set", "vector", "std",
    "cout", "cin", "endl", "printf", "scanf", "console", "log"
}


def extract_code_and_prose(text: str) -> Tuple[str, Optional[str], str]:
    """
    Separates markdown code blocks from prose explanation text.

    Returns:
        Tuple of (clean_prose: str, code_snippet: Optional[str], language: str)
    """
    if not text:
        return "", None, ""

    from ghostline.core.llm_client import extract_and_normalize_code

    # 1. If text contains markdown code fences
    if "```" in text:
        clean_code, clean_lang, clean_prose = extract_and_normalize_code(text)
        if clean_code:
            return clean_prose or "Code Solution", clean_code, clean_lang or "code"

    # 2. Check if the entire response looks like pure code starting with language keywords
    lines = [l for l in text.splitlines() if l.strip()]
    if lines:
        first = lines[0].strip()
        first_token = first.split()[0].lower() if first.split() else ""
        code_token_langs = {
            "def": "python", "class": "python", "import": "python", "from": "python",
            "function": "javascript", "const": "javascript", "let": "javascript", "var": "javascript",
            "select": "sql", "insert": "sql", "update": "sql", "delete": "sql", "create": "sql",
            "#include": "cpp", "struct": "cpp",
            "public": "java", "package": "go", "func": "go", "fn": "rust"
        }
        if first_token in code_token_langs:
            clean_code, clean_lang, _ = extract_and_normalize_code(text, default_lang=code_token_langs[first_token])
            return "Code Solution", clean_code, clean_lang or code_token_langs[first_token]

    return text.strip(), None, ""


def apply_syntax_highlighting(text_widget: tk.Text, code: Optional[str], language: str = "", lang: str = ""):
    """
    Renders code into a Tkinter Text widget with styled syntax coloring:
    - Keywords: Emerald Green (#34d399)
    - Strings: Amber (#fbbf24)
    - Comments: Slate Gray (#64748b)
    - Numbers: Purple (#c084fc)
    - Types: Sky Blue (#38bdf8)
    """
    text_widget.configure(state="normal")
    text_widget.delete("1.0", tk.END)
    if not code:
        text_widget.configure(state="disabled")
        return

    from ghostline.core.llm_client import extract_and_normalize_code, log_safe_code_diagnostic
    normalized_code, detected_lang, _ = extract_and_normalize_code(code, language or lang)
    log_safe_code_diagnostic("6. HUD Code Widget", normalized_code)

    text_widget.insert("1.0", normalized_code)

    # Configure tag styles matching dark aesthetic (support both short and descriptive tag names)
    text_widget.tag_configure("kw", foreground="#34d399", font=("Consolas", 9, "bold"))
    text_widget.tag_configure("keyword", foreground="#34d399", font=("Consolas", 9, "bold"))
    text_widget.tag_configure("str", foreground="#fbbf24")
    text_widget.tag_configure("string", foreground="#fbbf24")
    text_widget.tag_configure("comment", foreground="#64748b", font=("Consolas", 9, "italic"))
    text_widget.tag_configure("num", foreground="#c084fc")
    text_widget.tag_configure("number", foreground="#c084fc")
    text_widget.tag_configure("type", foreground="#38bdf8")

    # Apply line-by-line highlighting
    for line_idx, line in enumerate(normalized_code.splitlines(), start=1):
        if not line:
            continue

        # 1. Comments
        comment_match = re.search(r"(#|//|--)(.*)$", line)
        comment_start = len(line)
        if comment_match:
            c_start = comment_match.start()
            comment_start = c_start
            text_widget.tag_add("comment", f"{line_idx}.{c_start}", f"{line_idx}.end")

        # 2. Strings (single and double quotes before comment)
        code_part = line[:comment_start]
        for str_match in re.finditer(r"([\"'])(?:\\.|[^\\])*?\1", code_part):
            s_start, s_end = str_match.span()
            text_widget.tag_add("str", f"{line_idx}.{s_start}", f"{line_idx}.{s_end}")
            text_widget.tag_add("string", f"{line_idx}.{s_start}", f"{line_idx}.{s_end}")

        # 3. Numbers
        for num_match in re.finditer(r"\b\d+(?:\.\d+)?\b", code_part):
            n_start, n_end = num_match.span()
            existing_tags = text_widget.tag_names(f"{line_idx}.{n_start}")
            if "str" not in existing_tags and "string" not in existing_tags:
                text_widget.tag_add("num", f"{line_idx}.{n_start}", f"{line_idx}.{n_end}")
                text_widget.tag_add("number", f"{line_idx}.{n_start}", f"{line_idx}.{n_end}")

        # 4. Words (Keywords and Types)
        for word_match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", code_part):
            w_start, w_end = word_match.span()
            word = word_match.group(0)
            existing_tags = text_widget.tag_names(f"{line_idx}.{w_start}")
            if "str" in existing_tags or "string" in existing_tags or "comment" in existing_tags:
                continue

            if word.lower() in KEYWORDS or word in KEYWORDS:
                text_widget.tag_add("kw", f"{line_idx}.{w_start}", f"{line_idx}.{w_end}")
                text_widget.tag_add("keyword", f"{line_idx}.{w_start}", f"{line_idx}.{w_end}")
            elif word.lower() in TYPE_NAMES:
                text_widget.tag_add("type", f"{line_idx}.{w_start}", f"{line_idx}.{w_end}")

    text_widget.configure(state="disabled")
