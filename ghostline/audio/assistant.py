import re
import time
import logging
import threading
import uuid
from typing import Optional, List, Dict, Any, Callable, Tuple
from collections import deque

from ghostline.core.llm_client import OllamaClient, extract_and_normalize_code, extract_code_block
from ghostline.audio.transcription import TranscriptSegment
from ghostline.audio.timing import record_timing_mark


class LiveAudioAssistant:
    """
    Context-aware conversation assistant for Ghostline.
    Features:
    - Multi-stage question detection that filters acknowledgements ('okay', 'right', 'thanks')
    - Distinguishes genuine questions, imperative prompts, statements, and incomplete phrases
    - Correlation of inference with session ID and entry ID to prevent delayed overwrites
    - Immediate cancellation upon End button or session close
    - Rolling transcript turns and configurable auto-answering
    """

    ACKNOWLEDGEMENT_SET = {
        "okay", "ok", "k", "yes", "yeah", "yep", "yup", "aye", "right", "alright",
        "thanks", "thank you", "got it", "sure", "cool", "great", "awesome",
        "no problem", "makes sense", "understood", "i see", "sounds good",
        "perfect", "good", "fine", "no worries", "uh-huh", "mm-hmm", "yep right",
        "okay thanks", "okay thank you", "okay got it", "all right", "gotcha",
        "indeed", "exactly", "definitely", "absolutely", "fair enough", "true"
    }

    PHATIC_PATTERNS = [
        r"^(?:can you hear me|am i audible|can you see my screen|are you there|hello\??)$",
        r"^(?:hold on|one second|give me a moment|let me know|check \d+|test test)\b",
    ]

    QUESTION_INDICATORS = [
        r"\b(?:what|how|why|where|when|who|which)\b",
        r"\b(?:can you|could you|would you|should we|do you|is it|are there|have you)\b",
        r"\b(?:explain|describe|implement|write a function|difference between|compare)\b",
        r"\b(?:recommend|suggest|architecture|protocol|algorithm|optimize|solve)\b",
        r"\b(?:how would you|what happens if|walk me through|tell me about|tell us about)\b",
        r"\b(?:introduce yourself|what did you study|your background|your experience|your projects?)\b",
        r"\b(?:what are your strengths?|tell me about one of your)\b",
    ]

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        model_name: str = "phi3:mini",
        max_context_turns: int = 12,
        auto_answer: bool = True,
        auto_answer_questions: Optional[bool] = None,
        when_to_answer: str = "questions",
        debounce_sec: float = 2.0,
        session_id: Optional[str] = None,
        on_answer: Optional[Callable[..., None]] = None,
        on_token: Optional[Callable[[str, str], None]] = None,
        on_question_detected: Optional[Callable[..., None]] = None,
        on_error: Optional[Callable[..., None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ):
        self.llm = ollama_client or OllamaClient(default_model=model_name)
        self.model_name = model_name
        self.max_context_turns = max_context_turns
        self.auto_answer = auto_answer_questions if auto_answer_questions is not None else auto_answer
        self.when_to_answer = when_to_answer  # 'questions', 'every_pause', 'manual'
        self.debounce_sec = max(0.05, debounce_sec)
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.is_session_active = True
        self.is_paused = False

        self.on_answer = on_answer
        self.on_token = on_token
        self.on_question_detected = on_question_detected
        self.on_error = on_error
        self.on_status = on_status

        self.turns: deque[TranscriptSegment] = deque(maxlen=self.max_context_turns)
        self._lock = threading.RLock()

        # Debounce timer & target request tracking
        self._debounce_timer: Optional[threading.Timer] = None
        self._pending_question_text = ""
        self._pending_entry_id = ""
        self._pending_session_id = ""
        self.is_thinking = False
        self._last_answered_question = ""
        self._last_answered_time = 0.0
        self._last_answered_norm = ""
        self.provider_name = getattr(self.llm, "id", getattr(self.llm, "provider_name", "ollama"))

    @property
    def context_turns(self):
        return self.turns

    @property
    def transcript_history(self) -> List[TranscriptSegment]:
        with self._lock:
            return list(self.turns)

    @transcript_history.setter
    def transcript_history(self, segments: List[TranscriptSegment]):
        with self._lock:
            self.turns.clear()
            for s in segments:
                self.turns.append(s)

    def set_session(self, session_id: str):
        """Starts a fresh session context and cancels any pending work from prior session."""
        with self._lock:
            self.session_id = session_id
            self.is_session_active = True
            self.is_paused = False
            self.turns.clear()
            self._cancel_debounce()
            self.is_thinking = False

    def end_session(self):
        """Cleanly terminates the session and drops pending inference requests."""
        with self._lock:
            self.is_session_active = False
            self._cancel_debounce()
            self._pending_question_text = ""
            self._pending_entry_id = ""
            self._pending_session_id = ""
        self._notify_status("Session Ended")

    def pause(self):
        with self._lock:
            self.is_paused = True
            self._cancel_debounce()
        self._notify_status("Paused")

    def resume(self):
        with self._lock:
            self.is_paused = False
        self._notify_status("Listening")

    def warmup(self):
        """Pre-warms the active LLM provider (especially local Ollama) with keep_alive: 5m and num_thread: 4."""
        def _do_warmup():
            try:
                if hasattr(self.llm, "warmup"):
                    self.llm.warmup()
                elif hasattr(self.llm, "providers") and "ollama" in self.llm.providers:
                    ollama = self.llm.providers["ollama"]
                    if hasattr(ollama, "warmup"):
                        ollama.warmup()
            except Exception as ex:
                logging.debug("[LiveAudioAssistant] Warmup non-fatal error: %s", ex)
        threading.Thread(target=_do_warmup, daemon=True, name="Ghostline-LLM-Warmup").start()

    def add_transcript_segment(self, segment: TranscriptSegment, entry_id: Optional[str] = None):
        self.add_segment(segment, entry_id=entry_id)

    def is_question(self, text: str) -> bool:
        """Public API: returns True only if text is a genuine question or technical prompt."""
        is_q, _, _ = self.classify_utterance(text)
        return is_q

    def is_acknowledgement(self, text: str) -> bool:
        """Returns True if the utterance is an acknowledgement or short conversational filler."""
        t_clean = re.sub(r"[^\w\s]", "", text.strip().lower())
        words = t_clean.split()
        if not words:
            return True
        if t_clean in self.ACKNOWLEDGEMENT_SET:
            return True
        if len(words) <= 3 and all(w in self.ACKNOWLEDGEMENT_SET for w in words):
            return True
        for pat in self.PHATIC_PATTERNS:
            if re.search(pat, text.strip().lower()):
                return True
        return False

    def classify_utterance(self, text: str) -> Tuple[bool, str, float]:
        """
        Classifies speech utterance into:
        - (is_question: bool, category: str, confidence: float)
        Categories: 'question', 'acknowledgement', 'incomplete', 'statement'
        """
        raw = text.strip()
        if not raw:
            return False, "incomplete", 0.0

        # 1. Filter pure acknowledgements and short filler phrases
        if self.is_acknowledgement(raw):
            return False, "acknowledgement", 0.95

        t_lower = raw.lower()
        words = t_lower.split()

        # 2. Check for trailing fragments and incomplete thoughts
        if len(words) < 4:
            trailing_fragment = re.match(
                r"^(?:so|and|but|or|because|what if|like|such as|for instance|if we|we can|you know)\b",
                t_lower
            )
            if trailing_fragment:
                return False, "incomplete", 0.85

        # 3. Interrogative and technical question indicators
        has_indicator = any(re.search(pat, t_lower) for pat in self.QUESTION_INDICATORS)
        ends_with_qmark = raw.endswith("?")

        # Clear substantive question with '?'
        if ends_with_qmark and (len(words) >= 3 or has_indicator):
            return True, "question", 0.98

        # Substantive question with interrogative or imperative verb without '?'
        # (e.g. "Explain the difference between TCP and UDP", "Implement binary search")
        if has_indicator and len(words) >= 4:
            return True, "question", 0.92

        # Short question without '?' but starting with clear question stem or interview prompt
        if any(t_lower.startswith(prefix) for prefix in [
            "what is", "how do", "why is", "can you", "could you", "explain", "describe", "implement",
            "tell me about", "walk me through", "introduce yourself", "tell us about"
        ]) and len(words) >= 2:
            return True, "question", 0.90

        # General statement
        return False, "statement", 0.70

    def add_segment(self, segment: TranscriptSegment, entry_id: Optional[str] = None):
        """Processes a new finalized transcript segment."""
        with self._lock:
            if not self.is_session_active or self.is_paused:
                return
            self.turns.append(segment)

        # Respect When to Answer policy: 'manual', 'questions', or 'every_pause'
        if not self.auto_answer or getattr(self, "when_to_answer", "questions") == "manual":
            return

        if segment.source in ("call", "mic"):
            should_answer = False
            category = "statement"
            if getattr(self, "when_to_answer", "questions") == "every_pause":
                if not self.is_acknowledgement(segment.text) and len(segment.text.strip().split()) >= 3:
                    should_answer = True
                    category = "pause"
            else:
                is_q, category, conf = self.classify_utterance(segment.text)
                should_answer = is_q

            if should_answer:
                norm_q = re.sub(r"[^\w\s]", "", segment.text.strip().lower())
                now = time.time()
                if self._last_answered_norm == norm_q and (now - self._last_answered_time < 12.0):
                    logging.debug("[LiveAudioAssistant] Utterance is recent duplicate; skipping auto-answer.")
                    return
                eid = entry_id or str(getattr(segment, "id", uuid.uuid4()))
                self._schedule_debounced_answer(segment.text, entry_id=eid)
            else:
                logging.debug("[LiveAudioAssistant] Utterance classified as '%s' (not triggering AI): '%s'",
                              category, segment.text)

    def _find_recent_question_stem(self) -> str:
        """Finds the most recent question or substantive technical utterance from stored turns."""
        with self._lock:
            turns_list = list(self.turns)
        if not turns_list:
            return "Recent discussion topic"

        # Search backwards (up to 8 turns) for a classified question
        recent_window = turns_list[-8:]
        for turn in reversed(recent_window):
            text = getattr(turn, "text", "").strip()
            if not text:
                continue
            is_q, cat, _ = self.classify_utterance(text)
            if is_q:
                return text

        # If no classified question, find the most recent non-acknowledgement / non-filler utterance
        for turn in reversed(recent_window):
            text = getattr(turn, "text", "").strip()
            if text and not self.is_acknowledgement(text):
                return text

        return turns_list[-1].text if turns_list else "Recent discussion topic"

    def ask(self, custom_query: Optional[str] = None, entry_id: Optional[str] = None):
        """
        Manually triggers AI assistance on the current conversation context.
        Bypasses automatic classification.
        """
        with self._lock:
            if not self.is_session_active:
                logging.info("[LiveAudioAssistant] Cannot ask: session is inactive.")
                return
            if self.is_thinking:
                logging.info("[LiveAudioAssistant] Inference already in progress; ignoring overlapping ask request.")
                return
            self._cancel_debounce()
            sess_id = self.session_id
            eid = entry_id or str(uuid.uuid4())[:8]

        # Determine target question to display in thinking state
        display_q = custom_query or self._find_recent_question_stem()

        if self.on_question_detected:
            try:
                self.on_question_detected(display_q, eid)
            except TypeError:
                try:
                    self.on_question_detected(display_q)
                except Exception:
                    pass

        threading.Thread(
            target=self._run_inference_worker,
            args=(custom_query, eid, sess_id),
            daemon=True
        ).start()

    def clear_context(self):
        """Clears stored conversation turns."""
        with self._lock:
            self.turns.clear()
            self._cancel_debounce()
            self._pending_question_text = ""
            self._pending_entry_id = ""

    def get_formatted_context(self, max_turns: Optional[int] = None) -> str:
        """Returns clean timestamped transcript context."""
        with self._lock:
            items = list(self.turns)
        if max_turns and len(items) > max_turns:
            items = items[-max_turns:]
        return "\n".join(item.formatted_line for item in items)

    get_context_summary = get_formatted_context

    def _cancel_debounce(self):
        if self._debounce_timer is not None:
            try:
                self._debounce_timer.cancel()
            except Exception:
                pass
            self._debounce_timer = None

    def _schedule_debounced_answer(self, question_text: str, entry_id: str):
        """Schedules inference after debounce delay to ensure speaker finished speaking."""
        with self._lock:
            if not self.is_session_active or self.is_paused:
                return

            self._pending_question_text = question_text
            self._pending_entry_id = entry_id
            self._pending_session_id = self.session_id
            self._cancel_debounce()

            if self.on_question_detected:
                try:
                    self.on_question_detected(question_text, entry_id)
                except TypeError:
                    try:
                        self.on_question_detected(question_text)
                    except Exception:
                        pass

            self._debounce_timer = threading.Timer(self.debounce_sec, self._on_debounce_timer_fired)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _on_debounce_timer_fired(self):
        with self._lock:
            if not self.is_session_active or self.is_paused:
                return
            q_text = self._pending_question_text
            eid = self._pending_entry_id
            sess_id = self._pending_session_id
            self._debounce_timer = None

        if q_text and sess_id == self.session_id and self.is_session_active:
            self._run_inference_worker(target_question=q_text, entry_id=eid, target_session_id=sess_id)

    def _run_inference_worker(
        self,
        target_question: Optional[str] = None,
        entry_id: Optional[str] = None,
        target_session_id: Optional[str] = None
    ):
        """Executes Ollama inference on background thread with session safety."""
        with self._lock:
            if not self.is_session_active:
                return
            if target_session_id and target_session_id != self.session_id:
                logging.info("[LiveAudioAssistant] Stale inference worker dropped (session mismatch).")
                return
            if self.is_thinking:
                return
            self.is_thinking = True
            active_session = self.session_id

        context_str = self.get_formatted_context()
        if not context_str and not target_question:
            err_msg = "No audio transcript recorded yet. Press Alt+A to start listening, then speak or play audio."
            self._notify_status("No conversation context to analyze.")
            logging.info("[LiveAudioAssistant] %s", err_msg)
            if self.on_error is not None:
                try:
                    self.on_error(err_msg, entry_id)
                except TypeError:
                    try:
                        self.on_error(err_msg)
                    except Exception:
                        pass
            with self._lock:
                self.is_thinking = False
            return

        self._notify_status("Thinking...")

        # Formulate grounded interview prompt using centralized ProfileContextBuilder
        question_stem = target_question or self._find_recent_question_stem()

        from ghostline.core.profile import get_profile_context_builder
        
        builder = get_profile_context_builder()
        provider_id = getattr(self.llm, "get_active_provider_id", lambda: "ollama")() if hasattr(self.llm, "get_active_provider_id") else getattr(self, "provider_name", "ollama")
        is_cloud = (str(provider_id).lower().strip() != 'ollama')

        with self._lock:
            recent_turns = list(self.turns)[-5:] if self.turns else []

        system_prompt, user_query = builder.build_interview_prompt(
            question=question_stem,
            recent_turns=recent_turns,
            is_cloud=is_cloud
        )

        answer_text = ""
        code_snippet = None
        code_lang = ""
        is_error = False

        try:
            # Check session still active before contacting LLM
            with self._lock:
                if not self.is_session_active or self.session_id != active_session:
                    logging.info("[LiveAudioAssistant] Session ended before querying LLM; aborting.")
                    return

            eff_model = getattr(self.llm, "model_name", self.model_name)
            logging.info("[LiveAudioAssistant] Querying model '%s' (provider: %s) for [%s]",
                         eff_model, provider_id, entry_id)

            record_timing_mark("provider_request_sent", {"provider": provider_id, "entry_id": entry_id})
            t_start = time.perf_counter()
            first_token_received = False
            accumulated_text = ""

            def _stream_token_handler(tok: str):
                nonlocal first_token_received, accumulated_text
                accumulated_text += tok
                if not first_token_received and tok.strip():
                    first_token_received = True
                    lat_ms = (time.perf_counter() - t_start) * 1000.0
                    record_timing_mark("first_token", {"entry_id": entry_id, "latency_ms": round(lat_ms, 1)})
                if self.on_token is not None:
                    try:
                        self.on_token(tok, entry_id)
                    except Exception as ex_t:
                        logging.debug("[LiveAudioAssistant] on_token error: %s", ex_t)

            if hasattr(self.llm, "generate"):
                try:
                    res = self.llm.generate(
                        prompt=user_query,
                        model=eff_model,
                        system=system_prompt,
                        stream_callback=_stream_token_handler,
                        max_tokens=250,
                        temperature=0.3
                    )
                except TypeError:
                    try:
                        res = self.llm.generate(
                            prompt=user_query,
                            model=eff_model,
                            system=system_prompt,
                            max_tokens=200,
                            temperature=0.3
                        )
                    except TypeError:
                        combined_prompt = f"{system_prompt}\n\n{user_query}"
                        res = self.llm.generate(prompt=combined_prompt, model=eff_model)

                if hasattr(res, "response_text"):
                    raw_answer = res.response_text
                elif isinstance(res, str):
                    raw_answer = res
                elif hasattr(res, "response"):
                    raw_answer = res.response
                else:
                    raw_answer = str(res)

                if not first_token_received and raw_answer:
                    _stream_token_handler(raw_answer)
            elif hasattr(self.llm, "generate_stream"):
                try:
                    res = self.llm.generate_stream(
                        prompt=user_query,
                        stream_callback=_stream_token_handler,
                        model=eff_model,
                        system=system_prompt,
                        max_tokens=250,
                        temperature=0.3
                    )
                    raw_answer = res or accumulated_text
                except Exception as stream_err:
                    logging.warning("[LiveAudioAssistant] generate_stream failed: %s", stream_err)
                    raw_answer = accumulated_text
            elif hasattr(self.llm, "solve_question"):
                combined_prompt = f"{system_prompt}\n\n{user_query}"
                res = self.llm.solve_question(
                    question_text=combined_prompt,
                    options=None,
                    model=self.model_name
                )
                raw_answer = res.explanation if res.explanation else res.direct_answer
                if not first_token_received and raw_answer:
                    _stream_token_handler(raw_answer)
            else:
                raw_answer = "No LLM interface available."

            t_infer = time.perf_counter()
            total_infer_ms = (t_infer - t_start) * 1000.0
            record_timing_mark("answer_finished", {"entry_id": entry_id, "total_ms": round(total_infer_ms, 1)})
            logging.info("[LiveAudioAssistant] Inference completed in %.2f ms", total_infer_ms)

            # Record deduplication
            norm_q = re.sub(r"[^\w\s]", "", question_stem.strip().lower())
            self._last_answered_question = question_stem
            self._last_answered_norm = norm_q
            self._last_answered_time = time.time()

            # Strip missing profile data sentinel if emitted by grounded models
            if "[[NO_PROFILE_DATA]]" in raw_answer:
                raw_answer = raw_answer.replace("[[NO_PROFILE_DATA]]", "").strip()

            raw_answer = raw_answer.strip()
            if (raw_answer.startswith('"') and raw_answer.endswith('"')) or (raw_answer.startswith("'") and raw_answer.endswith("'")):
                raw_answer = raw_answer[1:-1].strip()
            for preamble in ["Candidate response:", "Candidate:", "Response:", "Here is the response:", "Here's the response:"]:
                if raw_answer.lower().startswith(preamble.lower()):
                    raw_answer = raw_answer[len(preamble):].strip()

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
            logging.warning("[LiveAudioAssistant] AI inference failed: %s", err_str)
            fix_label = "Retry"
            fix_action = "retry"
            if "Cannot connect" in err_str or "11434" in err_str or "Ollama" in err_str:
                answer_text = "Ollama is offline. Start Ollama (`ollama serve`) to enable live AI responses."
                fix_label = "Start Ollama"
                fix_action = "start_ollama"
            elif "401" in err_str or "403" in err_str or "key" in err_str.lower():
                answer_text = f"API authentication failed: {err_str}"
                fix_label = "Check Settings"
                fix_action = "open_settings"
            else:
                answer_text = f"Live AI assistance error: {err_str}"

            self._notify_status("AI Error")
            error_info = {
                "error": err_str,
                "message": answer_text,
                "fix_label": fix_label,
                "fix_action": fix_action,
                "provider": provider_id
            }
            if self.on_error is not None:
                with self._lock:
                    if self.is_session_active and self.session_id == active_session:
                        try:
                            self.on_error(err_str, entry_id, error_info)
                        except TypeError:
                            try:
                                self.on_error(err_str, entry_id)
                            except TypeError:
                                self.on_error(err_str)

        finally:
            with self._lock:
                self.is_thinking = False

        # Guard: Check that session did not end or change while Ollama was thinking
        with self._lock:
            if not self.is_session_active or self.session_id != active_session:
                logging.info("[LiveAudioAssistant] Dropping delayed Ollama answer because session was ended or changed.")
                return

        # Emit answer callback
        if not is_error and self.on_answer is not None:
            try:
                self.on_answer(question_stem, answer_text, code_snippet, entry_id=entry_id)
            except TypeError:
                try:
                    self.on_answer(question_stem, answer_text, code_snippet)
                except TypeError:
                    try:
                        self.on_answer(answer_text, question_stem, code_snippet, code_lang, is_error)
                    except Exception as cb_err:
                        logging.debug("[LiveAudioAssistant] on_answer callback error: %s", cb_err)

    def _construct_audio_prompt(self, context: str, target: str) -> str:
        try:
            from ghostline.core.profile import get_profile_context_builder
            builder = get_profile_context_builder()
            provider_id = getattr(self.llm, "get_active_provider_id", lambda: "ollama")() if hasattr(self.llm, "get_active_provider_id") else getattr(self, "provider_name", "ollama")
            is_cloud = (str(provider_id).lower().strip() != 'ollama')
            sys_p, u_q = builder.build_interview_prompt(question=target, is_cloud=is_cloud)
            return f"{sys_p}\n\nConversation Transcript:\n{context}\n\n{u_q}"
        except Exception:
            return f"Conversation Transcript:\n{context}\n\nInterviewer asks: \"{target}\"\n\nCandidate response (spoken aloud):" 

    def _notify_status(self, status: str):
        if self.on_status is not None:
            try:
                self.on_status(status)
            except Exception:
                pass
