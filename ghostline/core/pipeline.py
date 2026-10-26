import time
import logging
from typing import Optional, Callable, Dict, Any, List, Tuple
from PIL import Image
from pydantic import BaseModel

from .capture import (
    capture_screen,
    get_cursor_position,
    save_diagnostic_artifacts,
    CAPTURE_MODE_FULL_SCREEN
)
from .ocr_engine import run_native_ocr, parse_question_structure, ParsedQuestion
from .llm_client import OllamaClient, AnswerResult
from .pipeline_tracer import PipelineTracer

class DuplicateQuestionError(ValueError):
    """Raised when an auto-hover solve detects the exact same question that was solved recently."""
    pass

class QuestionExtractionError(ValueError):
    """Raised when extracted OCR text cannot be reliably classified as a question."""
    def __init__(self, message: str, parsed_question: Optional[ParsedQuestion] = None, raw_text: str = ""):
        super().__init__(message)
        self.parsed_question = parsed_question
        self.raw_text = raw_text

class PipelineExecutionResult(BaseModel):
    cursor_pos: tuple
    capture_time_ms: float
    ocr_time_ms: float
    llm_time_ms: float
    total_time_ms: float
    parsed_question: ParsedQuestion
    answer_result: AnswerResult
    tracer_data: Optional[Dict[str, Any]] = None

class GhostlinePipeline:
    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        model_name: str = "phi3:mini",
        capture_mode: str = CAPTURE_MODE_FULL_SCREEN,
        diagnostic_mode: bool = False
    ):
        self.llm = ollama_client or OllamaClient(default_model=model_name)
        self.model_name = model_name
        self.capture_mode = capture_mode
        self.diagnostic_mode = diagnostic_mode

    def process_from_cursor(
        self,
        capture_width: int = 900,
        capture_height: int = 600,
        capture_mode: Optional[str] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        is_duplicate_fn: Optional[Callable[[str], bool]] = None,
        tracer: Optional[PipelineTracer] = None,
        excluded_rects: Optional[List[Tuple[int, int, int, int]]] = None
    ) -> PipelineExecutionResult:
        """
        Executes the full pipeline:
        1. Capture screen according to configured capture mode (full_screen, active_window, or cursor).
        2. Recognize text via Windows Native OCR with spatial line boxes.
        3. Parse question, options, constraints, and programming structure.
        4. Solve with local Ollama LLM.
        5. Validate result and verify code syntax.
        """
        if tracer is None:
            tracer = PipelineTracer()
        tracer.start_trace()
        t_start = time.perf_counter()
        
        # 1. Capture Stage
        if progress_callback:
            progress_callback("capturing")
        rec_cap = tracer.begin_stage("Screen Capture")
        effective_mode = capture_mode or self.capture_mode
        try:
            t0 = time.perf_counter()
            img, bbox, cap_diag = capture_screen(
                mode=effective_mode,
                width=capture_width,
                height=capture_height,
                diagnostic_mode=self.diagnostic_mode,
                excluded_rects=excluded_rects
            )
            t_cap = (time.perf_counter() - t0) * 1000.0
            cursor_pos = cap_diag.get("cursor", get_cursor_position())
            tracer.end_stage(rec_cap, success=True, details={
                "bbox": bbox,
                "cursor": cursor_pos,
                "capture_mode": effective_mode,
                "is_blank_frame": cap_diag.get("is_blank_frame", False),
                "is_capture_protected": cap_diag.get("is_capture_protected", False),
                "display_affinity": cap_diag.get("display_affinity", 0),
                "grab_method": cap_diag.get("grab_method", "unknown")
            })
        except Exception as e:
            tracer.end_stage(rec_cap, success=False, error=str(e))
            raise

        # 2. OCR Stage
        if progress_callback:
            progress_callback("recognizing")
        rec_ocr = tracer.begin_stage("OCR")
        try:
            t0 = time.perf_counter()
            ocr_data = run_native_ocr(img, enhance_contrast=True, deskew=True)
            t_ocr = (time.perf_counter() - t0) * 1000.0
            tracer.end_stage(rec_ocr, success=True, details={
                "lines_count": len(ocr_data.get("lines", [])),
                "line_boxes_count": len(ocr_data.get("line_boxes", [])),
                "char_count": len(ocr_data.get("text", "")),
                "text_angle": ocr_data.get("text_angle", 0.0)
            })
        except Exception as e:
            tracer.end_stage(rec_ocr, success=False, error=str(e))
            raise

        # 3. Question Extraction Stage
        rec_parse = tracer.begin_stage("Question Extraction")
        try:
            parsed_q = parse_question_structure(ocr_data, cursor_pos=cursor_pos)
            parse_details = {
                "is_valid": parsed_q.is_valid_question,
                "question_type": parsed_q.question_type,
                "is_mcq": parsed_q.is_multiple_choice,
                "is_unlabelled": parsed_q.is_unlabelled_mcq,
                "options_count": len(parsed_q.options),
                "validation_reason": parsed_q.validation_reason,
                "question_length": len(parsed_q.question_text),
                "is_truncated": parsed_q.is_truncated,
                "multiple_questions_detected": parsed_q.multiple_questions_detected,
                "warnings": parsed_q.warnings
            }
            if not parsed_q.question_text.strip() or not parsed_q.is_valid_question:
                reason = parsed_q.validation_reason or "Empty or invalid question text."
                tracer.end_stage(rec_parse, success=False, details=parse_details, error=reason)
                logging.warning("[Pipeline Tracer] Question rejected: %s", reason)
                raise QuestionExtractionError(
                    f"Unreliable question extraction: {reason}",
                    parsed_question=parsed_q,
                    raw_text=parsed_q.raw_text
                )
            tracer.end_stage(rec_parse, success=True, details=parse_details)
        except Exception as e:
            if not rec_parse.end_time:
                tracer.end_stage(rec_parse, success=False, error=str(e))
            raise

        # Save diagnostic artifacts if enabled
        if self.diagnostic_mode:
            try:
                save_diagnostic_artifacts(img, ocr_data=ocr_data, parsed_question=parsed_q, diag_info=cap_diag)
            except Exception:
                pass

        # Check duplicate question cache for auto-hover
        if is_duplicate_fn and is_duplicate_fn(parsed_q.question_text):
            logging.info("[Pipeline Tracer] Detected duplicate question within TTL. Skipping LLM.")
            raise DuplicateQuestionError(f"Duplicate question detected: {parsed_q.question_text[:50]}")

        # 4. LLM Solve Stage
        if progress_callback:
            progress_callback("thinking")
        rec_llm = tracer.begin_stage("Answer Generation", {"model": self.model_name})
        try:
            t0 = time.perf_counter()
            answer = self.llm.solve_question(
                question_text=parsed_q.question_text,
                options=parsed_q.options if parsed_q.is_multiple_choice else None,
                model=self.model_name,
                stream_callback=stream_callback,
                is_unlabelled_mcq=parsed_q.is_unlabelled_mcq,
                supporting_passage=parsed_q.supporting_passage,
                constraints=parsed_q.constraints,
                examples=parsed_q.examples,
                input_format=parsed_q.input_format,
                output_format=parsed_q.output_format,
                starter_code=parsed_q.starter_code,
                requested_language=parsed_q.requested_language,
                question_type=parsed_q.question_type
            )
            t_llm = (time.perf_counter() - t0) * 1000.0
            tracer.end_stage(rec_llm, success=True, details={
                "is_validated": answer.is_validated,
                "badge": answer.tray_badge,
                "has_code": bool(getattr(answer, "code_snippet", None)),
                "validation_status": answer.validation_status
            })
        except Exception as e:
            tracer.end_stage(rec_llm, success=False, error=str(e))
            raise

        # 5. Validation Stage
        rec_val = tracer.begin_stage("Validation")
        tracer.end_stage(rec_val, success=answer.is_validated, details={
            "is_validated": answer.is_validated,
            "tray_badge": answer.tray_badge,
            "error": answer.error,
            "validation_status": answer.validation_status
        })

        t_total = (time.perf_counter() - t_start) * 1000.0

        return PipelineExecutionResult(
            cursor_pos=cursor_pos,
            capture_time_ms=t_cap,
            ocr_time_ms=t_ocr,
            llm_time_ms=t_llm,
            total_time_ms=t_total,
            parsed_question=parsed_q,
            answer_result=answer,
            tracer_data=tracer.to_dict()
        )

    def process_from_image(
        self,
        image: Image.Image,
        cursor_pos: Optional[Tuple[int, int]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        tracer: Optional[PipelineTracer] = None
    ) -> PipelineExecutionResult:
        """Processes a static image for testing or headless pipelines."""
        if tracer is None:
            tracer = PipelineTracer()
        tracer.start_trace()
        t_start = time.perf_counter()
        
        rec_ocr = tracer.begin_stage("OCR")
        try:
            t0 = time.perf_counter()
            ocr_data = run_native_ocr(image, enhance_contrast=True, deskew=True)
            t_ocr = (time.perf_counter() - t0) * 1000.0
            tracer.end_stage(rec_ocr, success=True, details={
                "lines_count": len(ocr_data.get("lines", []))
            })
        except Exception as e:
            tracer.end_stage(rec_ocr, success=False, error=str(e))
            raise

        rec_parse = tracer.begin_stage("Question Extraction")
        try:
            parsed_q = parse_question_structure(ocr_data, cursor_pos=cursor_pos)
            if not parsed_q.question_text.strip() or not parsed_q.is_valid_question:
                reason = parsed_q.validation_reason or "No readable question detected in image."
                tracer.end_stage(rec_parse, success=False, error=reason)
                raise ValueError(f"No readable question detected in image: {reason}")
            tracer.end_stage(rec_parse, success=True, details={
                "is_mcq": parsed_q.is_multiple_choice,
                "options_count": len(parsed_q.options),
                "question_type": parsed_q.question_type
            })
        except Exception as e:
            if not rec_parse.end_time:
                tracer.end_stage(rec_parse, success=False, error=str(e))
            raise

        rec_llm = tracer.begin_stage("Answer Generation")
        try:
            t0 = time.perf_counter()
            answer = self.llm.solve_question(
                question_text=parsed_q.question_text,
                options=parsed_q.options if parsed_q.is_multiple_choice else None,
                model=self.model_name,
                stream_callback=stream_callback,
                is_unlabelled_mcq=parsed_q.is_unlabelled_mcq,
                supporting_passage=parsed_q.supporting_passage,
                constraints=parsed_q.constraints,
                examples=parsed_q.examples,
                input_format=parsed_q.input_format,
                output_format=parsed_q.output_format,
                starter_code=parsed_q.starter_code,
                requested_language=parsed_q.requested_language,
                question_type=parsed_q.question_type
            )
            t_llm = (time.perf_counter() - t0) * 1000.0
            tracer.end_stage(rec_llm, success=True, details={
                "is_validated": answer.is_validated,
                "badge": answer.tray_badge,
                "validation_status": answer.validation_status
            })
        except Exception as e:
            tracer.end_stage(rec_llm, success=False, error=str(e))
            raise

        rec_val = tracer.begin_stage("Validation")
        tracer.end_stage(rec_val, success=answer.is_validated)

        t_total = (time.perf_counter() - t_start) * 1000.0

        return PipelineExecutionResult(
            cursor_pos=(0, 0),
            capture_time_ms=0.0,
            ocr_time_ms=t_ocr,
            llm_time_ms=t_llm,
            total_time_ms=t_total,
            parsed_question=parsed_q,
            answer_result=answer,
            tracer_data=tracer.to_dict()
        )

