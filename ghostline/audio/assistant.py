import re
import time
import logging
import threading
from typing import Optional, List, Dict, Any, Callable
from collections import deque

from ghostline.core.llm_client import OllamaClient, extract_and_normalize_code, extract_code_block
from ghostline.audio.transcription import TranscriptSegment


class LiveAudioAssistant:
    """
    Context-aware conversation assistant for Ghostline.
    Maintains rolling transcript turns, detects questions, runs debounced or manual
    Ollama inference, and emits formatted technical answers.
    """

    QUESTION_INDICATORS = [
        r"\b(?:what|how|why|where|when|who|which)\b",
        r"\b(?:can you|could you|would you|should we|do you|is it|are there)\b",
        r"\b(?:explain|describe|implement|write a function|difference between)\b",
        r"\b(?:recommend|suggest|architecture|protocol|algorithm|optimize)\b",
    ]

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        model_name: str = "phi3:mini",
        max_context_turns: int = 12,
        auto_answer: bool = True,
        auto_answer_questions: Optional[bool] = None,
        debounce_sec: float = 2.0,
        on_answer: Optional[Callable[..., None]] = None,
        on_question_detected: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ):
        self.llm = ollama_client or OllamaClient(default_model=model_name)
        self.model_name = model_name
        self.max_context_turns = max_context_turns
        self.auto_answer = auto_answer_questions if auto_answer_questions is not None else auto_answer
        self.debounce_sec = max(0.05, debounce_sec)
        self.on_answer = on_answer
        self.on_question_detected = on_question_detected
        self.on_error = on_error
        self.on_status = on_status

        self.turns: deque[TranscriptSegment] = deque(maxlen=self.max_context_turns)
        self._lock = threading.Lock()

        # Debounce timer
        self._debounce_timer: Optional[threading.Timer] = None
        self._last_question_text = ""
        self.is_thinking = False

    @property
    def context_turns(self):
        return self.turns

    def add_transcript_segment(self, segment: TranscriptSegment):
        self.add_segment(segment)

    def is_question(self, text: str) -> bool:
        return self._is_question(text)

    def get_context_summary(self) -> str:
        return self.get_formatted_context()

    def add_segment(self, segment: TranscriptSegment):
        """Processes a new finalized transcript segment."""
        with self._lock:
            self.turns.append(segment)

        # Check if segment contains a question from the other participants
        if self.auto_answer and segment.source == "call":
            if self._is_question(segment.text):
                self._schedule_debounced_answer(segment.text)

    def ask(self, custom_query: Optional[str] = None):
        """
        Manually triggers AI assistance on the current conversation context.
        If custom_query is provided, answers that specific query.
        Otherwise, answers the latest question or summarizes the discussion.
        """
        # Cancel any pending debounce
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        if custom_query and self.on_question_detected:
            try:
                self.on_question_detected(custom_query)
            except Exception:
                pass

        threading.Thread(target=self._run_inference_worker, args=(custom_query,), daemon=True).start()

    def clear_context(self):
        """Clears stored conversation context."""
        with self._lock:
            self.turns.clear()
            self._last_question_text = ""
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None

    def get_formatted_context(self, max_turns: Optional[int] = None) -> str:
        """Returns clean timestamped transcript context."""
        with self._lock:
            items = list(self.turns)
        if max_turns and len(items) > max_turns:
            items = items[-max_turns:]
        return "\n".join(item.formatted_line for item in items)

    def _is_question(self, text: str) -> bool:
        """Detects whether speech text contains an interrogative question or technical prompt."""
        t_clean = text.strip().lower()
        if t_clean.endswith("?"):
            return True

        for pat in self.QUESTION_INDICATORS:
            if re.search(pat, t_clean):
                return True
        return False

    def _schedule_debounced_answer(self, question_text: str):
        """Schedules inference after debounce delay to ensure speaker finished speaking."""
        with self._lock:
            self._last_question_text = question_text
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            if self.on_question_detected:
                try:
                    self.on_question_detected(question_text)
                except Exception:
                    pass

            self._debounce_timer = threading.Timer(self.debounce_sec, self._on_debounce_timer_fired)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _on_debounce_timer_fired(self):
        with self._lock:
            q_text = self._last_question_text
            self._debounce_timer = None
        if q_text:
            self._run_inference_worker(target_question=q_text)

    def _run_inference_worker(self, target_question: Optional[str] = None):
        """Executes Ollama inference on background thread."""
        with self._lock:
            if self.is_thinking:
                return
            self.is_thinking = True

        context_str = self.get_formatted_context()
        if not context_str and not target_question:
            self._notify_status("No conversation context to analyze.")
            with self._lock:
                self.is_thinking = False
            return

        self._notify_status("Thinking...")

        # Formulate grounded prompt
        question_stem = target_question or (self.turns[-1].text if self.turns else "Recent discussion topic")
        prompt = self._construct_audio_prompt(context_str, question_stem)

        answer_text = ""
        code_snippet = None
        code_lang = ""
        is_error = False

        try:
            # Use OllamaClient to query model
            logging.info("[LiveAudioAssistant] Querying model '%s' with context (%d chars)", self.model_name, len(context_str))
            if hasattr(self.llm, "generate"):
                res = self.llm.generate(prompt=prompt, model=self.model_name)
                if hasattr(res, "response_text"):
                    raw_answer = res.response_text
                elif isinstance(res, str):
                    raw_answer = res
                elif hasattr(res, "response"):
                    raw_answer = res.response
                else:
                    raw_answer = str(res)
            elif hasattr(self.llm, "solve_question"):
                res = self.llm.solve_question(
                    question_text=prompt,
                    options=None,
                    model=self.model_name
                )
                raw_answer = res.explanation if res.explanation else res.direct_answer
            else:
                raw_answer = "No LLM interface available."


            # Check if answer contains code
            code_block, lang = extract_code_block(raw_answer)
            if code_block:
                clean_c, clean_l, clean_exp = extract_and_normalize_code(code_block, lang)
                code_snippet = clean_c
                code_lang = clean_l
                answer_text = clean_exp or raw_answer
            elif getattr(res, "code_snippet", None):
                code_snippet = res.code_snippet
                code_lang = res.code_language
                answer_text = raw_answer
            else:
                answer_text = raw_answer

            self._notify_status("Answer Ready")

        except Exception as ex:
            is_error = True
            err_str = str(ex)
            logging.warning("[LiveAudioAssistant] Ollama inference failed: %s", err_str)
            if "Cannot connect to local Ollama daemon" in err_str:
                answer_text = "Ollama is offline. Start Ollama (`ollama serve`) to enable live AI responses."
            else:
                answer_text = f"Live AI assistance error: {err_str}"
            self._notify_status("Ollama Offline / Error")
            if self.on_error is not None:
                try:
                    self.on_error(err_str)
                except Exception:
                    pass

        finally:
            with self._lock:
                self.is_thinking = False

        # Emit answer callback
        if not is_error and self.on_answer is not None:
            try:
                self.on_answer(question_stem, answer_text, code_snippet)
            except TypeError:
                try:
                    self.on_answer(answer_text, question_stem, code_snippet, code_lang, is_error)
                except Exception as cb_err:
                    logging.debug("[LiveAudioAssistant] on_answer callback error: %s", cb_err)

    def _construct_audio_prompt(self, context: str, target: str) -> str:
        return f"""You are Ghostline Live AI Assistant, a high-precision real-time technical copilot assisting in a video call.
Analyze the following live conversation transcript and provide a direct, concise, and technically rigorous answer.

Conversation Transcript:
{context}

Target Question / Inquired Topic:
{target}

Instructions:
1. Provide a direct, concise answer in 2-4 sentences or clear bullet points.
2. If code is requested or appropriate, provide clean, runnable code with a markdown code fence.
3. Ground your answer strictly in the discussion context and preserve technical terms, identifiers, architecture names, and protocols.
4. Do NOT output conversational filler or preamble like "Sure!", "Here is your answer".
"""

    def _notify_status(self, status: str):
        if self.on_status is not None:
            try:
                self.on_status(status)
            except Exception:
                pass
