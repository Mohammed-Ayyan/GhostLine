import os
import sys
import json
import subprocess
import tempfile
import re
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from PIL import Image, ImageEnhance, ImageOps
from pydantic import BaseModel, Field

class ParsedQuestion(BaseModel):
    raw_text: str = ""
    lines: List[str] = Field(default_factory=list)
    question_heading: str = ""
    question_text: str = ""
    supporting_passage: str = ""
    options: Dict[str, str] = Field(default_factory=dict)
    is_multiple_choice: bool = False
    is_unlabelled_mcq: bool = False
    is_valid_question: bool = True
    validation_reason: str = ""
    question_type: str = Field(default="mcq", description="mcq, programming, true_false, numerical, theory, unknown")
    
    # Programming question structured fields
    title: str = ""
    problem_statement: str = ""
    constraints: List[str] = Field(default_factory=list)
    examples: List[Dict[str, str]] = Field(default_factory=list)
    input_format: str = ""
    output_format: str = ""
    starter_code: str = ""
    requested_language: str = ""
    
    # Confidence & Diagnostics
    confidence: float = 1.0
    diagnostic_explanation: str = ""
    warnings: List[str] = Field(default_factory=list)
    is_truncated: bool = False
    multiple_questions_detected: bool = False
    detected_questions: List[str] = Field(default_factory=list)

def get_win_ocr_binary_path() -> Path:
    # 1. Check PyInstaller bundled resource directory (_MEIPASS)
    if hasattr(sys, "_MEIPASS"):
        meipass_p = Path(sys._MEIPASS) / "bin" / "win_ocr.exe"
        if meipass_p.exists():
            return meipass_p

    # 2. Check relative to executable parent (_internal or adjacent bin)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for cand in [exe_dir / "bin" / "win_ocr.exe", exe_dir / "_internal" / "bin" / "win_ocr.exe"]:
            if cand.exists():
                return cand

    # 3. Check relative to source repository root
    base_dir = Path(__file__).resolve().parent.parent.parent
    bin_path = base_dir / "bin" / "win_ocr.exe"
    if bin_path.exists():
        return bin_path

    # 4. Check current working directory
    for cand in [
        Path.cwd() / "bin" / "win_ocr.exe",
        Path.cwd() / "ghostline" / "bin" / "win_ocr.exe",
    ]:
        if cand.exists():
            return cand

    raise FileNotFoundError(f"win_ocr.exe not found. Searched base_dir={bin_path}")

def preprocess_image_for_ocr(
    image: Image.Image,
    enhance_contrast: bool = True,
    target_min_width: int = 1200
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Applies configurable, intelligent preprocessing:
    - Upscaling small images to ensure high OCR glyph clarity
    - Contrast enhancement only when dynamic range / contrast is low
    - Ensures clean RGB mode for Windows.Media.Ocr
    """
    diag: Dict[str, Any] = {"scaled": False, "contrast_enhanced": False, "original_size": image.size}
    w, h = image.size
    img = image

    # 1. Scale up small images for superior OCR accuracy
    if w < target_min_width and w > 0:
        scale = 2 if w < (target_min_width // 2) else 1.5
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        diag["scaled"] = True
        diag["scale_factor"] = scale

    # 2. Convert to RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    # 3. Check contrast dynamically
    if enhance_contrast:
        try:
            gray = img.convert("L")
            extrema = gray.getextrema()
            # If dynamic range is compressed (difference between min and max < 140)
            if extrema[1] - extrema[0] < 140 and extrema[1] > extrema[0]:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.4)
                diag["contrast_enhanced"] = True
        except Exception:
            pass

    diag["processed_size"] = img.size
    return img, diag

def safe_parse_ocr_json(stdout_text: str) -> Dict[str, Any]:
    """
    Robust JSON parser for win_ocr stdout.
    Guarantees that unescaped control characters (e.g. \\x07, nulls)
    never crash with 'Invalid control character' JSONDecodeError.
    """
    if not stdout_text or not stdout_text.strip():
        return {"text": "", "lines": [], "line_boxes": [], "text_angle": 0.0}
    try:
        return json.loads(stdout_text, strict=False)
    except Exception:
        # Sanitize stray ASCII control characters (0-31 except \\t, \\n, \\r)
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', stdout_text)
        try:
            return json.loads(sanitized, strict=False)
        except Exception as e:
            logging.warning("[OCR Engine] Fallback JSON parse on OCR stdout: %s", e)
            text_m = re.search(r'"text"\s*:\s*"(.*?)"', sanitized)
            text_val = text_m.group(1) if text_m else ""
            lines = [l for l in text_val.split("\n") if l.strip()]
            return {
                "text": text_val,
                "lines": lines,
                "line_boxes": [],
                "text_angle": 0.0
            }

def run_native_ocr(
    image: Image.Image,
    enhance_contrast: bool = True,
    deskew: bool = True
) -> Dict[str, Any]:
    """
    Executes native Windows.Media.Ocr on the provided PIL Image.
    Returns:
        {
            "text": str,
            "text_angle": float,
            "lines": List[str],
            "line_boxes": List[Dict[str, Any]],
            "image_size": [width, height]
        }
    """
    ocr_bin = get_win_ocr_binary_path()
    
    # Preprocess image
    processed_img, prep_diag = preprocess_image_for_ocr(image, enhance_contrast=enhance_contrast)
    orig_w, orig_h = image.size
    proc_w, proc_h = processed_img.size
    scale_x = proc_w / orig_w if orig_w > 0 else 1.0
    scale_y = proc_h / orig_h if orig_h > 0 else 1.0

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
        
    try:
        processed_img.save(tmp_path, format="PNG")
        
        creationflags = 0
        startupinfo = None
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

        t0_sub = time.perf_counter()
        proc = subprocess.run(
            [str(ocr_bin), tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
        t_sub = (time.perf_counter() - t0_sub) * 1000.0
        
        if proc.returncode != 0:
            raise RuntimeError(f"OCR binary exited with code {proc.returncode}: {proc.stderr}")
            
        data = safe_parse_ocr_json(proc.stdout)
        data["image_size"] = [orig_w, orig_h]
        data["prep_diag"] = prep_diag

        # If image was scaled, map bounding boxes back to original coordinate space
        if (scale_x != 1.0 or scale_y != 1.0) and "line_boxes" in data:
            for box in data["line_boxes"]:
                box["x"] = round(box.get("x", 0) / scale_x, 1)
                box["y"] = round(box.get("y", 0) / scale_y, 1)
                box["width"] = round(box.get("width", 0) / scale_x, 1)
                box["height"] = round(box.get("height", 0) / scale_y, 1)
                for w in box.get("words", []):
                    w["x"] = round(w.get("x", 0) / scale_x, 1)
                    w["y"] = round(w.get("y", 0) / scale_y, 1)
                    w["width"] = round(w.get("width", 0) / scale_x, 1)
                    w["height"] = round(w.get("height", 0) / scale_y, 1)

        # Deskewing support: if significant skew is reported by OCR engine and deskew enabled
        angle = data.get("text_angle", 0.0)
        if deskew and abs(angle) >= 1.5:
            logging.info("[OCR Deskew] Detected text skew angle of %.1f deg; rotating to deskew.", angle)
            # Re-run once with deskewed rotation
            deskewed_img = image.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)
            deskewed_data = run_native_ocr(deskewed_img, enhance_contrast=False, deskew=False)
            deskewed_data["deskewed_angle"] = angle
            return deskewed_data

        return data
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

# UI Chrome / Noise patterns to filter from assessment content
UI_NOISE_REGEX = re.compile(
    r"^(?:"
    # Ghostline HUD overlay elements and controls
    r"(?:Ghostline|Answer\s*⌘.*|Screenshot\s*⌘.*|Chat\s*⌘.*|Ask a follow-up.*|Copy Answer|Copy Code|Live Audio HUD|⭐ Answer.*|💬 Question.*|Waveform|Clear\s*⌘.*|End(?:\s*session)?|Pause|Resume|Choice\s+[A-D]|Verified\s+Local\s+AI)[\s\.\!]*$|"
    # Browser assistant & AI overlays (Gemini, Copilot, ChatGPT, etc.)
    r"(?:Ask\s+Gemini|Gemini|Ask\s+Copilot|Copilot|Ask\s+AI|Search\s+with\s+Google|Google\s+Search|New\s+Tab|Extensions?)\b.*|"
    # Browser URL bars and navigation
    r"(?:https?:\/\/|[a-zA-Z0-9_\-]+\.[a-zA-Z]{2,}\/|chrome:\/\/|edge:\/\/).*|"
    # General evaluation / instructions text
    r"(?:Move through all scenarios.*)|"
    # Test suite chrome, evaluation fixtures, instructions, and diagnostic panels (excluding Test Case headers which are block boundaries)
    r"(?:Ghostline Pipeline Diagnostic|Pipeline Diagnostic & Verification Suite|Local Controlled Page|Controlled evaluation fixture|Pipeline Tracker|\d+\.\s*(?:Hotkey|Screen Capture|Native OCR|Question Extraction|Local AI Reasoning|Validation|Scrollable HUD)|Expected:\s*Badge.*|Operating System & Assessment Platform Diagnostic Notes|Windows Display Affinity|User Interface Privilege Isolation|Scrollable HUD:.*|Dedicated Canvas viewport.*).*|"
    # Assessment buttons and navigation
    r"^(?:Submit(?:\s*answer)?|Next(?:\s*question)?|Previous|Back|Finish(?:\s*test)?|Review|Flag|Clear(?:\s*selection|\s*answer)?|Mark for Review|Exit Exam|Save\s*&\s*Next|Run\s*Code|Submit\s*Code|Reset(?:\s*code)?|Test\s*Cases?|Page\s*\d+\s*of\s*\d+)[\s\.\!\>]*$|"
    # Assessment progress indicators (e.g. Question 4 of 50)
    r"^Question\s*\d+\s*of\s*\d+.*$|"
    # Standalone percentage indicators (e.g. 100%, 75%)
    r"^\s*\d{1,3}%\s*$|"
    # Assessment instructions and hints
    r"^(?:Expected\s*[:\-]|Expected\s*Result|Note\s*[:\-]|Hint\s*[:\-]|Instructions?\s*[:\-]?).*|"
    # Timers and clocks
    r"time\s*(?:remaining|left)?\s*[:\-]?\s*[\d]{1,2}:[\d]{2}(?::[\d]{2})?\s*(?:am|pm)?|"
    r"[\d]{1,2}:[\d]{2}(?::[\d]{2})?\s*(?:am|pm|remaining|left)?|"
    r"timer\s*[:\-]?\s*[\d]{1,2}:[\d]{2}|"
    # Action and navigation buttons
    r"(?:submit(?:\s*answer)?|next(?:\s*question)?|previous|back|finish(?:\s*test)?|review|flag|clear(?:\s*selection|\s*answer)?|save\s*&\s*next|run\s*code|submit\s*code|reset(?:\s*code)?|test\s*cases?)\b[\s\.\!\>]*$|"
    # Test section / metadata banners
    r"section\s*[\d\w]+(?:\s*:\s*.*)?|"
    r"marks?\s*:\s*\+?[\d\.]+\s*(?:,\s*\-?[\d\.]+)?|"
    r"negative\s*marks?\s*:\s*[\d\.]+|"
    r"proctored\s*exam.*|"
    r"webcam\s*active.*|"
    r"microphone\s*active.*|"
    r"page\s*\d+\s*of\s*\d+|"
    # IDE menu bars and window titles
    r"(?:File|Edit|Selection|View|Go|Run|Terminal|Help|Window)(?:\s+(?:File|Edit|Selection|View|Go|Run|Terminal|Help|Window))+(?:\s*.*)?|"
    r"(?:Visual\s+Studio\s+Code|Visual\s+Studio|Sublime\s+Text|IntelliJ\s+IDEA|Android\s+Studio|PyCharm|Eclipse)(?:\s*[\-\–]\s*.*)?|"
    # IDE sidebars and bottom panels
    r"(?:EXPLORER|OUTLINE|TIMELINE|SEARCH|SOURCE\s+CONTROL|EXTENSIONS|PROBLEMS|OUTPUT|DEBUG\s+CONSOLE|TERMINAL|PORTS|GIT\s+LENS)\b(?:\s*\d+)?$|"
    # Breadcrumb navigation: e.g. "ghostline > ui > qt_hud_overlay.py"
    r"[a-zA-Z0-9_\-\.]+(?:\s*[>\/]\s*[a-zA-Z0-9_\-\.]+){2,}(?:\s*.*)?$|"
    # Status bar lines
    r".*(?:Ln\s*\d+,\s*Col\s*\d+|Spaces:\s*\d+|UTF-8|CRLF|Python\s*[\d\.]+\b.*).*$|"
    # File tree / explorer noise
    r"^\s*(?:>|\^|v)?\s*(?:OPEN EDITORS|EXPLORER)\s*$|"
    # Shell prompts
    r"(?:PS\s+[a-zA-Z]:\\.*>|[a-zA-Z]:\\.*>|bash-[\d\.]+\$|[$#%]\s*|>>>\s*|\.\.\.\s*|user@[^:]+:.*[$#]|git\s+(?:status|commit|push|pull|diff|branch|checkout)\b.*)$|"
    # Standalone filenames
    r"^[a-zA-Z0-9_\-]+\.(?:py|js|ts|jsx|tsx|html|css|json|md|c|cpp|h|java|go|rs|sql|sh|bat|yml|yaml|toml|lock)$|"
    # Taskbar artifacts: date (e.g. 26-10-2026), language indicators (e.g. ENG), search bar placeholders, clocks
    r"^\s*\d{1,2}[-\/\.]\d{1,2}[-\/\.]\d{2,4}\s*$|"
    r"^\s*(?:ENG|ESP|FRA|DEU|ITA|JPN|KOR|CHS|CHT)\s*$|"
    r"^(?:Ask\s+anything|Type\s+here\s+to\s+search|Search\s+the\s+web)\b.*$|"
    r"^\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?\s*$"
    r")$",
    re.IGNORECASE
)

def _is_ui_noise(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned:
        return True
    return bool(UI_NOISE_REGEX.match(cleaned))

def _detect_multi_column_order(line_boxes: List[Dict[str, Any]], image_width: int) -> List[Dict[str, Any]]:
    """
    Detects if the lines are distributed in two columns (e.g. left column: question,
    right column: code editor or option list).
    If a clear two-column partition exists, orders lines column-by-column rather than
    interleaving across columns horizontally.
    """
    if len(line_boxes) < 4 or image_width <= 0:
        return line_boxes

    midpoint = image_width / 2.0
    col1 = []
    col2 = []
    spanning = []

    for box in line_boxes:
        bx = box.get("x", 0)
        bw = box.get("width", 0)
        br = bx + bw
        # If line clearly stays in left half
        if br < midpoint + 40:
            col1.append(box)
        # If line clearly starts in right half
        elif bx > midpoint - 40:
            col2.append(box)
        else:
            spanning.append(box)

    # If substantial elements exist on both sides without excessive spanning lines
    if len(col1) >= 2 and len(col2) >= 2 and len(spanning) <= (len(col1) + len(col2)) * 0.35:
        # Sort each column top-to-bottom
        col1_sorted = sorted(col1, key=lambda b: b.get("y", 0))
        col2_sorted = sorted(col2, key=lambda b: b.get("y", 0))
        return col1_sorted + col2_sorted + spanning

    # Default: sort primarily by Y (top-to-bottom) with slight X threshold
    return sorted(line_boxes, key=lambda b: (round(b.get("y", 0) / 12) * 12, b.get("x", 0)))

def _check_boundary_truncation(line_boxes: List[Dict[str, Any]], image_size: List[int]) -> Tuple[bool, List[str]]:
    """
    Detects if text extends directly to capture boundaries (top, bottom, left, right),
    which signals that relevant question or option content may be cut off.
    """
    if not line_boxes or not image_size or len(image_size) < 2:
        return False, []

    w, h = image_size[0], image_size[1]
    warnings = []
    is_truncated = False

    margin = 8  # pixels from edge
    for box in line_boxes:
        bx, by = box.get("x", 0), box.get("y", 0)
        bw, bh = box.get("width", 0), box.get("height", 0)
        br, bb = bx + bw, by + bh

        if by <= margin:
            warnings.append("Text detected near top boundary; earlier lines may be cut off.")
            is_truncated = True
            break
        if bb >= h - margin:
            warnings.append("Text detected near bottom boundary; options or problem end may be cut off.")
            is_truncated = True
            break

    return is_truncated, warnings

def _is_meaningful_question(text: str, options: Dict[str, str]) -> Tuple[bool, str]:
    """
    Validates whether the extracted text and options represent a legitimate question.
    Rejects arbitrary UI chrome, file tabs, and isolated word lists while supporting:
    - Multiple-choice questions (labelled, unlabelled, bulleted)
    - Interrogative questions with '?'
    - Imperative problem stems ('Solve for', 'Evaluate', 'Determine', 'Find', 'Select', 'Consider', 'Given')
    - Programming / code-based assessment problems
    - Multi-line technical stems
    """
    cleaned = text.strip()
    if not cleaned:
        return False, "Empty text detected from screen capture."
        
    words = cleaned.split()
    if len(words) < 2 or len(cleaned) < 8:
        return False, f"Extracted text is too short ({len(words)} words, {len(cleaned)} chars) to be a valid question."

    # 1. Multiple-choice questions (at least 2 options detected)
    if len(options) >= 2 and len(words) >= 3:
        return True, "Valid multiple-choice question."

    # 2. Interrogative question mark
    if "?" in cleaned:
        return True, "Valid question with interrogative question mark."

    # 3. Question numbering or problem prefixes (e.g. Question 1:, Q1., Problem:, Task:)
    if re.match(r"^(?:Question\b|Q\s*[\d\.\:]|Problem\b|Exercise\b|Task\b|Example\b|\d+[\.\)])", cleaned, re.IGNORECASE):
        if len(words) >= 3:
            return True, "Valid question with problem prefix."

    # 4. Assessment verbs and interrogative phrases (covers standard, coding, and online proctored tests)
    assessment_pattern = re.compile(
        r"\b("
        r"which\s+(?:of\s+the\s+following|one|choice|statement|option)|"
        r"what\s+(?:is|are|does|will|would|can|should|was|were)|"
        r"how\s+(?:many|much|do|does|can|could|is|are|to)|"
        r"why\s+(?:is|are|do|does|did)|"
        r"solve\s+(?:for|the|this)|"
        r"evaluate\s+(?:the|each|all|following)|"
        r"calculate\s+(?:the|all|each|following)|"
        r"determine\s+(?:the|all|whether|which|if|following)|"
        r"find\s+(?:the|all|each|value|out|which|what)|"
        r"select\s+(?:the|all|one|which|correct|following)|"
        r"choose\s+(?:the|all|one|which|correct|following)|"
        r"identify\s+(?:the|all|each|which|following)|"
        r"explain\s+(?:the|how|why|what|following)|"
        r"define\s+(?:the|what|how)|"
        r"describe\s+(?:the|how|why)|"
        r"simplify\s+(?:the|each|following)|"
        r"consider\s+(?:the|a|an|following)|"
        r"given\s+(?:that|the|a|an|an?\s+array|an?\s+string|an?\s+integer|an?\s+list|an?\s+tree|following)|"
        r"suppose\s+(?:that|a|an)|"
        r"assume\s+(?:that|a|an)|"
        r"match\s+(?:the|column|each)|"
        r"complete\s+(?:the|following)|"
        r"fill\s+in\s+the\s+blank|"
        r"true\s+or\s+false|"
        r"output\s+of\s+(?:the|following)|"
        r"what\s+will\s+be\s+the\s+output|"
        r"predict\s+the\s+output|"
        r"state\s+whether|"
        r"implement\s+(?:a|an|the|this|following)|"
        r"write\s+(?:a|an|the|code|program|function|query|script|solution)|"
        r"construct\s+(?:a|an|the|following)|"
        r"create\s+(?:a|an|the|function|class|table|query)|"
        r"design\s+(?:a|an|the|class|algorithm|system|data\s+structure)|"
        r"analyze\s+(?:the|this|all|following)|"
        r"compute\s+(?:the|all|each|following)|"
        r"derive\s+(?:the|an|a|following)|"
        r"prove\s+(?:that|the|following)|"
        r"show\s+that|"
        r"check\s+(?:if|whether|that)|"
        r"verify\s+(?:if|whether|that)|"
        r"convert\s+(?:the|each|all|following)|"
        r"transform\s+(?:the|each|all|following)|"
        r"optimize\s+(?:the|this|all|following)|"
        r"count\s+(?:the|number\s+of|occurrences)|"
        r"reverse\s+(?:the|a|an)|"
        r"sort\s+(?:the|a|an)|"
        r"return\s+(?:true|false|the|a|an|all)|"
        r"you\s+are\s+given|"
        r"there\s+(?:is|are)\s+(?:a|an|\d+)"
        r")\b",
        re.IGNORECASE
    )
    if assessment_pattern.search(cleaned) and len(words) >= 3:
        return True, "Valid question with assessment verb or interrogative stem."

    # 5. Programming / code question detection
    code_indicators = ["def ", "class ", "int main", "public static", "SELECT ", "console.log", "return ", "#include", "import "]
    if any(ind in cleaned for ind in code_indicators) and len(words) >= 5:
        return True, "Valid programming question with code keywords."

    # 6. Competitive programming / structured specs (e.g. constraints, sample input, time complexity)
    if any(re.search(pat, cleaned, re.IGNORECASE) for pat in [r"\b(?:sample\s*input|example\s*\d+|constraints|time\s*complexity|space\s*complexity)\b"]) and len(words) >= 4:
        return True, "Valid competitive programming / coding problem specifications."

    # 7. Technical problem statement ending in a colon or containing mathematical relation
    if len(words) >= 8 and (cleaned.rstrip().endswith(":") or re.search(r"\b[a-zA-Z]\s*=\s*[\d\w]", cleaned)):
        return True, "Valid technical problem statement."

    return False, "Captured text does not contain question indicators or multiple-choice options."

def parse_programming_question(lines: List[str], raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Identifies and parses programming/coding challenges into structured components:
    - title
    - problem_statement
    - constraints
    - examples (input, output, explanation)
    - input_format
    - output_format
    - starter_code
    - requested_language
    """
    prog_keywords = ["function ", "def ", "class ", "return ", "time limit:", "memory limit:",
                     "input format", "output format", "constraints", "sample input", "example 1",
                     "example 2", "starter code", "write a program", "write a function", "given an array",
                     "given a string", "return the number of", "return true if", "determine if"]
    
    joined_lower = "\n".join(lines).lower()
    matches = sum(1 for kw in prog_keywords if kw in joined_lower)
    if matches < 2:
        return None

    title = ""
    problem_statement_lines = []
    constraints = []
    examples = []
    input_format_lines = []
    output_format_lines = []
    starter_code_lines = []
    requested_language = ""

    current_section = "statement"
    current_example: Dict[str, str] = {}
    current_example_field = "input"

    # Detect requested language if explicitly stated
    lang_patterns = {
        "python": r"\b(python\s*3?|py)\b",
        "javascript": r"\b(javascript|typescript|js|ts|node\.?js)\b",
        "cpp": r"\b(c\+\+|cpp)\b",
        "java": r"\b(java)(?!\s*script)\b",
        "c": r"\b(c\s+program|ansi\s+c)\b",
        "sql": r"\b(sql|mysql|postgresql)\b",
        "go": r"\b(golang|go\s+language)\b",
        "rust": r"\b(rust)\b"
    }
    for lang, pat in lang_patterns.items():
        if re.search(pat, joined_lower):
            requested_language = lang
            break

    # Look for title on line 1 or 2
    if lines and len(lines) > 0:
        first = lines[0].strip()
        m_title = re.match(r"^(?:Problem|Question|Task)\s*[\d\w]*[\:\-]?\s*(.+)$", first, re.IGNORECASE)
        if m_title:
            cand_title = m_title.group(1).strip()
            if len(cand_title.split()) <= 8:
                title = cand_title
        elif re.match(r"^[A-Z][\w\s]{2,40}$", first) and len(first.split()) <= 6:
            title = first

    for idx, line in enumerate(lines):
        if idx == 0 and title:
            continue
        cleaned = line.strip()
        lower = cleaned.lower()

        # Section header detection
        if re.match(r"^constraints\s*[\:\-]?$", lower):
            current_section = "constraints"
            continue
        elif re.match(r"^(?:sample|example)\s*(?:input|1|\d+)[\:\-]?$", lower):
            current_section = "examples"
            if current_example and (current_example.get("input") or current_example.get("output")):
                examples.append(current_example)
            current_example = {"input": "", "output": "", "explanation": ""}
            current_example_field = "input"
            continue
        elif re.match(r"^input\s*format\s*[\:\-]?$", lower):
            current_section = "input_format"
            continue
        elif re.match(r"^output\s*format\s*[\:\-]?$", lower):
            current_section = "output_format"
            continue
        elif re.match(r"^(?:starter|initial|template)\s*code\s*[\:\-]?$", lower) or (current_section != "starter_code" and re.match(r"^(?:class\s+\w+|def\s+\w+|public\s+class)", cleaned)):
            current_section = "starter_code"
            starter_code_lines.append(line)
            continue

        # Section content routing
        if current_section == "constraints":
            if cleaned:
                # Handle bulleted or comma separated constraints
                c_clean = re.sub(r"^[•\-\*]\s*", "", cleaned)
                constraints.append(c_clean)
        elif current_section == "examples":
            if re.match(r"^(?:sample\s*)?input\s*[\:\-]?\s*(.*)$", lower):
                current_example_field = "input"
                val = re.sub(r"^(?:sample\s*)?input\s*[\:\-]?\s*", "", cleaned, flags=re.IGNORECASE)
                if val:
                    current_example["input"] = val
            elif re.match(r"^(?:sample\s*)?output\s*[\:\-]?\s*(.*)$", lower):
                current_example_field = "output"
                val = re.sub(r"^(?:sample\s*)?output\s*[\:\-]?\s*", "", cleaned, flags=re.IGNORECASE)
                if val:
                    current_example["output"] = val
            elif re.match(r"^explanation\s*[\:\-]?\s*(.*)$", lower):
                current_example_field = "explanation"
                val = re.sub(r"^explanation\s*[\:\-]?\s*", "", cleaned, flags=re.IGNORECASE)
                if val:
                    current_example["explanation"] = val
            else:
                if current_example_field in current_example:
                    if current_example[current_example_field]:
                        current_example[current_example_field] += "\n" + cleaned
                    else:
                        current_example[current_example_field] = cleaned
        elif current_section == "input_format":
            input_format_lines.append(cleaned)
        elif current_section == "output_format":
            output_format_lines.append(cleaned)
        elif current_section == "starter_code":
            starter_code_lines.append(line)
        else:  # statement
            problem_statement_lines.append(cleaned)

    if current_example and (current_example.get("input") or current_example.get("output")):
        examples.append(current_example)

    statement = "\n".join(problem_statement_lines).strip()
    starter_code = "\n".join(starter_code_lines).strip()

    if not requested_language and starter_code:
        if "def " in starter_code or "import " in starter_code or "class " in starter_code:
            requested_language = "python"
        elif "function " in starter_code or "const " in starter_code or "let " in starter_code:
            requested_language = "javascript"
        elif "#include" in starter_code or "std::" in starter_code or "cout" in starter_code:
            requested_language = "cpp"
        elif "public class" in starter_code or "System.out" in starter_code:
            requested_language = "java"
        elif "SELECT " in starter_code.upper() and "FROM " in starter_code.upper():
            requested_language = "sql"

    return {
        "title": title or "Programming Problem",
        "problem_statement": statement if statement else raw_text,
        "constraints": constraints,
        "examples": examples,
        "input_format": "\n".join(input_format_lines).strip(),
        "output_format": "\n".join(output_format_lines).strip(),
        "starter_code": starter_code,
        "requested_language": requested_language
    }

def _detect_multiple_questions(lines: List[str]) -> List[int]:
    """
    Detects boundaries where distinct question cards or stems exist on screen.
    Includes:
    - 'Test Case 1', 'Test Case 2', 'Question 1', 'Problem 1'
    - '1. What is...', '2. Which of...', '3. Solve for...'
    """
    stem_start_indices = []
    card_pattern = re.compile(
        r"^(?:"
        r"(?:Test\s*Case|Question|Problem|Task|Scenario|Exercise)\s*\d+[\:\.\-]?"
        r"|Q\s*[\d\.\:]"
        r"|\b\d{1,2}\s*[\.\)]\s+(?:which|what|how|why|solve|calculate|evaluate|determine|find|select|consider|given|suppose|a\s+|in\s+)"
        r")",
        re.IGNORECASE
    )
    for idx, line in enumerate(lines):
        if card_pattern.match(line.strip()):
            stem_start_indices.append(idx)

    return stem_start_indices

def _split_inline_options(line: str) -> List[str]:
    """
    Splits multi-option lines (e.g. 'A) Apple  B) Banana  C) Orange') while preserving
    card and question headers (e.g. 'Test Case 1: ...', 'Question 2: ...').
    """
    if re.match(r"^(?:Test\s*Case|Question|Problem|Task|Scenario|Exercise)\s*\d+", line, re.IGNORECASE):
        return [line]

    inline_split_regex = re.compile(
        r"(?<=\S)(?:\s{2,}|\s+(?=[A-J1-9][\.\:\)\]\-]\s+))(?=(?:"
        r"[\(\[]\s*(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\s*[\)\]\-]\s+"
        r"|\(\s*(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\s*\)\s+"
        r"|\[\s*(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\s*\]\s+"
        r"|(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\s*[\.\:](?!\d|[-\/\.])\s+"
        r"|(?:[A-Za-z]|[1-9]\d?)\s*[\)\]\-](?!\d|[-\/\.])\s+"
        r"))"
    )
    subparts = inline_split_regex.split(line)
    return [p.strip() for p in subparts if p.strip()]

def parse_question_structure(ocr_data: Any, cursor_pos: Optional[Tuple[int, int]] = None) -> ParsedQuestion:
    """
    Robust Document Structure & Question Extraction Parser:
    - Filters out UI noise, timers, navigation, and buttons
    - Multi-column layout awareness
    - Explicit MCQ labels (A/B/C/D, 1/2/3/4, Roman numerals (i)-(iv))
    - Genuinely unlabelled options (preserves exact order and alignment)
    - Disambiguates question numbering from option labels
    - Handles large vertical gaps and intervening notes
    - Detects programming problems with separate structured fields
    - Detects truncation and multiple questions without silent merging
    - Calculates confidence score and diagnostic telemetry
    """
    if isinstance(ocr_data, str):
        ocr_data = {
            "text": ocr_data,
            "lines": [l.strip() for l in ocr_data.splitlines() if l.strip()],
            "line_boxes": []
        }

    raw_text = ocr_data.get("text", "") or ""
    line_boxes = ocr_data.get("line_boxes", []) or []
    image_size = ocr_data.get("image_size", [1920, 1080])

    # Check boundary truncation
    is_truncated, truncation_warnings = _check_boundary_truncation(line_boxes, image_size)

    # 1. Multi-column and spatial layout ordering
    if line_boxes and len(line_boxes) >= 4 and image_size and image_size[0] > 0:
        sorted_boxes = _detect_multi_column_order(line_boxes, image_size[0])
        initial_lines = [b.get("text", "").strip() for b in sorted_boxes if b.get("text", "").strip()]
    else:
        initial_lines = [l.strip() for l in ocr_data.get("lines", []) if l.strip()]
        if not initial_lines and raw_text:
            initial_lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    # 2. Filter UI noise (timers, proctoring chrome, buttons)
    filtered_lines = [l for l in initial_lines if not _is_ui_noise(l)]

    # 3. Disambiguate multi-option lines (e.g. "A) Apple  B) Banana  C) Orange")
    lines: List[str] = []
    for l in filtered_lines:
        for p in _split_inline_options(l):
            lines.append(p)

    # 4. Check for multiple distinct questions (prevent silent merging)
    multiple_q_indices = _detect_multiple_questions(lines)
    multiple_questions_detected = len(multiple_q_indices) > 1
    detected_questions: List[str] = []
    warnings: List[str] = list(truncation_warnings)

    if multiple_questions_detected:
        warnings.append(f"Detected {len(multiple_q_indices)} distinct question cards; isolated targeted question.")
        for q_idx in multiple_q_indices:
            detected_questions.append(lines[q_idx][:60] + "...")
        # Isolate the targeted question block (by cursor position or block 0)
        target_block_idx = 0
        if cursor_pos:
            cx, cy = cursor_pos[0], cursor_pos[1]
            best_idx = 0
            best_dist = float("inf")
            if line_boxes and image_size and image_size[1] > 0:
                for k in range(len(multiple_q_indices)):
                    s_idx = multiple_q_indices[k]
                    e_idx = multiple_q_indices[k + 1] if k + 1 < len(multiple_q_indices) else len(lines)
                    block_line_texts = set(lines[s_idx:e_idx])
                    matched_boxes = [b for b in line_boxes if b.get("text", "").strip() in block_line_texts]
                    if matched_boxes:
                        min_y = min(b.get("y", 0) for b in matched_boxes)
                        max_y = max(b.get("y", 0) + b.get("height", 0) for b in matched_boxes)
                        min_x = min(b.get("x", 0) for b in matched_boxes)
                        max_x = max(b.get("x", 0) + b.get("width", 0) for b in matched_boxes)
                        if (min_x - 40 <= cx <= max_x + 40) and (min_y - 25 <= cy <= max_y + 25):
                            best_idx = k
                            break
                        center_y = (min_y + max_y) / 2.0
                        dist = abs(cy - center_y)
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = k
                target_block_idx = best_idx
            else:
                total_h = image_size[1] if (image_size and image_size[1] > 0) else 1080
                card_fraction = cy / max(1.0, float(total_h))
                target_block_idx = min(len(multiple_q_indices) - 1, max(0, int(card_fraction * len(multiple_q_indices))))
        q_start = multiple_q_indices[target_block_idx]
        q_end = multiple_q_indices[target_block_idx + 1] if target_block_idx + 1 < len(multiple_q_indices) else len(lines)
        lines = lines[q_start:q_end]

    # Option parsing patterns
    opt_prefix_regex = re.compile(
        r"^(?:"
        r"[\(\[]\s*([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\s*[\)\]\-]\s*"
        r"|\(\s*([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\s*\)\s*"
        r"|\[\s*([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\s*\]\s*"
        r"|([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\s*[\.\:](?!\d|[-\/\.])\s*"
        r"|([A-Za-z]|[1-9]\d?)\s*[\)\]\-](?!\d|[-\/\.])\s*"
        r"|(?:○|●|◯|🔘|\[\s*\]|\[\s*x\s*\]|\[\s*\*\s*\]|\(\s*\)|\(\s*\*\s*\))\s*"
        r")(.*)$"
    )
    bullet_regex = re.compile(r"^[•\-\*▪▫◦]\s*(.+)$")

    # 5. Check for programming question structure (only if NOT an MCQ with choices)
    has_mcq_options = len([l for l in lines if opt_prefix_regex.match(l.strip())]) >= 2
    if not has_mcq_options:
        prog_data = parse_programming_question(lines, raw_text)
        if prog_data and (prog_data.get("constraints") or prog_data.get("examples") or prog_data.get("starter_code")):
            return ParsedQuestion(
                raw_text=raw_text,
                lines=lines,
                question_text=prog_data["problem_statement"],
                options={},
                is_multiple_choice=False,
                is_unlabelled_mcq=False,
                is_valid_question=True,
                validation_reason="Valid programming problem with structured specifications.",
                question_type="programming",
                title=prog_data.get("title", "Programming Problem"),
                problem_statement=prog_data.get("problem_statement", ""),
                constraints=prog_data.get("constraints", []),
                examples=prog_data.get("examples", []),
                input_format=prog_data.get("input_format", ""),
                output_format=prog_data.get("output_format", ""),
                starter_code=prog_data.get("starter_code", ""),
                requested_language=prog_data.get("requested_language", ""),
                confidence=0.95,
                diagnostic_explanation="Successfully extracted structured programming question.",
                warnings=warnings,
                is_truncated=is_truncated,
                multiple_questions_detected=multiple_questions_detected,
                detected_questions=detected_questions
            )

    candidates: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines):
        m = opt_prefix_regex.match(line)
        if m:
            raw_key = m.group(1) or m.group(2) or m.group(3) or m.group(4) or m.group(5)
            val = m.group(6).strip()
            # Normalize key
            if raw_key is None:
                # Radio button without explicit text label
                candidates.append({"idx": idx, "key": None, "raw_key": None, "val": val, "line": line, "is_bullet": True})
            elif line.startswith("(") and (raw_key.lower() in ["i", "ii", "iii", "iv", "v", "x"] or raw_key.isdigit()):
                key = f"({raw_key})"
                candidates.append({"idx": idx, "key": key, "raw_key": raw_key, "val": val, "line": line})
            elif raw_key.isalpha() and len(raw_key) == 1:
                key = raw_key.upper()
                candidates.append({"idx": idx, "key": key, "raw_key": raw_key, "val": val, "line": line})
            else:
                key = raw_key
                candidates.append({"idx": idx, "key": key, "raw_key": raw_key, "val": val, "line": line})
        else:
            m_bullet = bullet_regex.match(line)
            if m_bullet:
                candidates.append({"idx": idx, "key": None, "raw_key": None, "val": m_bullet.group(1).strip(), "line": line, "is_bullet": True})
            else:
                candidates.append({"idx": idx, "key": None, "raw_key": None, "val": line, "line": line, "is_text": True})

    # Disambiguate leading question numbering (e.g. "3. Which of the following...")
    option_entries = [c for c in candidates if c.get("key") is not None]
    if option_entries:
        first = option_entries[0]
        val_lower = first["val"].lower()
        raw_k = str(first.get("raw_key") or "")
        is_numeric_key = raw_k.isdigit() or raw_k.lower().startswith("q")

        is_stem_like = False
        if is_numeric_key:
            if "?" in first["line"] or any(val_lower.startswith(w) for w in [
                "which", "what", "how", "why", "explain", "find", "determine", "identify",
                "calculate", "state", "select", "a company", "in python", "consider", "given", "solve"
            ]) or (raw_k.isdigit() and int(raw_k) > 4 and len(first["val"].split()) >= 3):
                is_stem_like = True
        elif len(option_entries) > 1:
            if "?" in first["val"] and any(val_lower.startswith(w) for w in ["which", "what", "how", "why", "solve", "consider", "given"]):
                next_key = option_entries[1].get("key")
                if next_key in ["A", "a", "(A)", "1", "(1)"]:
                    is_stem_like = True

        if is_stem_like and len(option_entries) > 1:
            first["is_stem"] = True
            first["key"] = None
            first["line"] = re.sub(r"^(?:Q\s*\d+[\.\:]|\d+\s*[\.\:]|Question\s*\d+[\.\:])\s*", "", first["line"], flags=re.IGNORECASE).strip()
            first["val"] = re.sub(r"^(?:Q\s*\d+[\.\:]|\d+\s*[\.\:]|Question\s*\d+[\.\:])\s*", "", first["val"], flags=re.IGNORECASE).strip()

    # Identify question stem start index to prune preceding IDE chrome or file headers
    q_start_idx = 0
    q_stem_regex = re.compile(
        r"^(?:"
        r"(?:Question|Problem|Task|Exercise|Q|Test\s*Case)\s*[\d\w]*(?:\s+of\s+\d+)?(?:\b|[\:\.\-])|"
        r"\d{1,3}\s*[\.\)]\s+|"
        r"(?:which|what|how|why|solve|calculate|evaluate|determine|find|select|choose|identify|explain|define|describe|simplify|consider|given|suppose|assume|predict|implement|write)\b"
        r")",
        re.IGNORECASE
    )
    for idx, c in enumerate(candidates):
        l_text = c.get("line", "").strip()
        if q_stem_regex.search(l_text) or "?" in l_text or c.get("is_stem"):
            q_start_idx = idx
            break

    options: Dict[str, str] = {}
    question_lines: List[str] = []
    is_unlabelled = False
    confidence = 1.0

    non_stem_candidates = [c for c in candidates if not c.get("is_stem")]
    labeled_candidates = [c for c in non_stem_candidates if c.get("key") is not None]
    bullet_candidates = [c for c in non_stem_candidates if c.get("is_bullet")]

    if len(labeled_candidates) >= 2:
        # Check if first key is an outlier before a standard sequence (e.g. question '3' before '1', '2', '3', '4')
        keys = [c["key"] for c in labeled_candidates]
        if len(keys) >= 3 and keys[0] in ["1", "2", "3", "4", "5", "6", "7", "8", "9"] and keys[1] == "1":
            labeled_candidates[0]["is_stem"] = True
            labeled_candidates = labeled_candidates[1:]
        elif len(keys) >= 3 and keys[0] in ["1", "2", "3", "4", "5", "6", "7", "8", "9"] and keys[1] in ["A", "(i)", "i"]:
            labeled_candidates[0]["is_stem"] = True
            labeled_candidates = labeled_candidates[1:]

        options_started = False
        options_ended = False
        current_k = None
        for idx, c in enumerate(candidates):
            if idx < q_start_idx and not c.get("is_stem"):
                line_text = c.get("line", "").strip()
                if len(line_text.split()) >= 4 and not _is_ui_noise(line_text):
                    question_lines.append(c["line"])
                continue

            if not options_started:
                if c.get("key") is not None and c in labeled_candidates:
                    options_started = True
                    current_k = c["key"]
                    options[current_k] = c["val"]
                else:
                    question_lines.append(c["line"])
            elif not options_ended:
                if c.get("key") is not None and c in labeled_candidates:
                    current_k = c["key"]
                    options[current_k] = c["val"]
                else:
                    line_val = c.get("line", "").strip()
                    if _is_ui_noise(line_val) or re.match(
                        r"^(?:PS\s+[a-zA-Z]:|[a-zA-Z]:\\|Ln\s*\d+|Spaces:|Submit|Next|Previous|Question\s*\d+|Test\s*Case\s*\d+|Expected|Note|Hint|Instructions?|Diagnostic|Operating|Windows|Caps Lock|\d+\.\s*Hotkey|Which|What|How|Why|Solve|Consider|Explain)",
                        line_val, re.IGNORECASE
                    ):
                        options_ended = True
                        current_k = None
                    elif c.get("val") and not c.get("key"):
                        if not re.match(r"^(?:Expected|Note|Hint|Instructions?|Diagnostic|Operating|Windows|Test\s*Case)\b", line_val, re.IGNORECASE):
                            options[current_k] += " " + c["line"]
                        else:
                            options_ended = True
                            current_k = None
            else:
                # Options section finished; do NOT leak footers or trailing text into question_lines
                pass
    elif len(bullet_candidates) >= 2:
        is_unlabelled = True
        for idx, b in enumerate(bullet_candidates, 1):
            options[str(idx)] = b["val"]
        for idx, c in enumerate(candidates):
            if idx < q_start_idx:
                line_text = c.get("line", "").strip()
                if len(line_text.split()) >= 4 and not _is_ui_noise(line_text):
                    question_lines.append(c["line"])
                continue
            if not c.get("is_bullet"):
                question_lines.append(c["line"])
    else:
        # Genuinely unlabelled multiple choice options (plain list of choices following question stem)
        stem_end_idx = -1
        interrogative_regex = re.compile(
            r"\b(which|what|how|why|explain|define|calculate|determine|find|select|identify|state)\b",
            re.IGNORECASE
        )
        for i, c in enumerate(candidates):
            c_text = c["val"].strip()
            words_count = len(c_text.split())
            if "?" in c_text:
                stem_end_idx = i
            elif c_text.endswith(":") and words_count >= 2:
                stem_end_idx = i
            elif interrogative_regex.search(c_text) and words_count >= 4 and any(c_text.lower().startswith(w) for w in ["which", "what", "how", "why", "select", "choose", "identify"]):
                stem_end_idx = i

        if stem_end_idx >= 0 and len(candidates) - (stem_end_idx + 1) >= 2:
            potential_opts = candidates[stem_end_idx + 1:]
            # Filter intervening instructions (e.g. "Select one:", "Choose correct answer:", "Please choose...", "Note: ...")
            cleaned_opts = []
            for opt_cand in potential_opts:
                opt_str = opt_cand["val"].strip()
                if opt_str.endswith(":") or re.match(r"^(?:please\s+)?(?:choose|select|pick|mark)\b", opt_str, re.IGNORECASE) or opt_str.lower().startswith("note:"):
                    question_lines.append(opt_cand["line"])
                    continue
                # Stop if hitting another card or expected badge footer
                if re.match(r"^(?:Expected|Test\s*Case|Question\s*\d+|Operating|Windows)\b", opt_str, re.IGNORECASE):
                    break
                cleaned_opts.append(opt_cand)

            valid_unlabelled = True
            for opt_cand in cleaned_opts:
                opt_str = opt_cand["val"].strip()
                if not opt_str or "?" in opt_str:
                    valid_unlabelled = False
                    break

            if valid_unlabelled and 2 <= len(cleaned_opts) <= 8:
                is_unlabelled = True
                for idx, opt_cand in enumerate(cleaned_opts, 1):
                    options[str(idx)] = opt_cand["val"].strip()
                for c in candidates[:stem_end_idx + 1]:
                    question_lines.append(c["line"])
                confidence = 0.90

        if not options:
            for idx, c in enumerate(candidates):
                if idx < q_start_idx:
                    continue
                question_lines.append(c["line"])

    # Separate heading, supporting passage / code block, and question stem
    question_heading = ""
    supporting_passage = ""
    stem_lines = []
    passage_lines = []

    clean_q_lines = [ql.strip() for ql in question_lines if ql.strip()]
    heading_pattern = re.compile(r"^(?:(?:\d+[\.\:\-]\s*)?(?:Question|Problem|Task|Exercise|Q|Test\s*Case)|\d+[\.\:\-]\s+[A-Za-z])[\d\w]*(?:\s+of\s+\d+)?[\:\.\-]?.*$", re.IGNORECASE)
    if clean_q_lines and heading_pattern.match(clean_q_lines[0]):
        question_heading = clean_q_lines[0]
        clean_q_lines = clean_q_lines[1:]

    # Identify question stem vs supporting passage (whether passage is before stem or between stem and choices)
    code_pattern = re.compile(
        r"(?:def\s+\w+|class\s+\w+|return\b|result\s*=|print\(|function\s+\w+|console\.log|SELECT\s+|FROM\s+|#include|import\s+\w+|public\s+static|int\s+main|\bnums\b)",
        re.IGNORECASE
    )

    stem_idx = -1
    for idx, ql in enumerate(clean_q_lines):
        if "?" in ql or re.match(r"^(?:which|what|how|why|solve\s+for|evaluate|determine|calculate|explain|consider)\b", ql, re.IGNORECASE):
            stem_idx = idx
            break

    if stem_idx >= 0:
        before_stem = clean_q_lines[:stem_idx]
        stem_and_after = clean_q_lines[stem_idx:]

        actual_before = []
        for line in before_stem:
            if not heading_pattern.match(line):
                actual_before.append(line)

        actual_stem_lines = [stem_and_after[0]]
        trailing_passage = []
        in_trailing_passage = False

        for idx, line in enumerate(stem_and_after[1:], 1):
            is_code_line = bool(code_pattern.search(line) or line.startswith(("    ", "\t", "```")))
            if is_code_line or in_trailing_passage:
                trailing_passage.append(line)
                in_trailing_passage = True
            else:
                actual_stem_lines.append(line)

        passage_lines = actual_before + trailing_passage
        stem_lines = actual_stem_lines
    else:
        for ql in clean_q_lines:
            is_code_line = bool(code_pattern.search(ql) or ql.startswith(("    ", "\t", "```")))
            if is_code_line:
                passage_lines.append(ql)
            else:
                stem_lines.append(ql)

    if passage_lines:
        supporting_passage = "\n".join(passage_lines).strip()
        stem_text = " ".join(stem_lines).strip()
        if not stem_text:
            stem_text = supporting_passage
            supporting_passage = ""
        question_text = stem_text
    else:
        question_text = " ".join(clean_q_lines).strip()

    is_mcq = len(options) >= 2

    # Structural validity verification using _is_meaningful_question
    is_valid, reason = _is_meaningful_question(question_text if question_text else raw_text, options)
    if not is_valid:
        confidence = 0.0

    # Question type classification
    if not is_valid:
        q_type = "uncertain" if ("does not contain question indicators" in reason or "Unreliable" in reason or "Empty" in reason) else "error"
    elif is_mcq:
        q_type = "mcq"
    else:
        q_lower = (question_text if question_text else raw_text).lower()
        if any(k in q_lower for k in ["def ", "class ", "int main", "return ", "function"]):
            q_type = "programming"
        elif any(k in q_lower for k in ["calculate", "solve for", "evaluate", "value of"]):
            q_type = "numerical"
        elif "true or false" in q_lower or "state whether true" in q_lower:
            q_type = "true_false"
        else:
            q_type = "theory"

    diag_exp = f"Parsed as {q_type.upper()} ({len(options)} options, confidence {confidence:.2f})"
    if warnings:
        diag_exp += " | Warnings: " + "; ".join(warnings)

    return ParsedQuestion(
        raw_text=raw_text,
        lines=lines,
        question_heading=question_heading,
        question_text=question_text if question_text else raw_text,
        supporting_passage=supporting_passage,
        options=options,
        is_multiple_choice=is_mcq,
        is_unlabelled_mcq=is_unlabelled,
        is_valid_question=is_valid,
        validation_reason=reason,
        question_type=q_type,
        confidence=confidence,
        diagnostic_explanation=diag_exp,
        warnings=warnings,
        is_truncated=is_truncated,
        multiple_questions_detected=multiple_questions_detected,
        detected_questions=detected_questions
    )
