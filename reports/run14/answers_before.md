# Ghostline — Run 14 Part 1B Baseline Live AI Answer Path Report

**Date**: 2026-11-08  
**Scope**: Systematic empirical measurement of live question detection, AI response routing, streaming, and UI delivery across 5 core operational configurations.

---

## 1. Test Setup & Methodology

- **Test Fixture**: `tests/fixtures/question_bst.wav` (4.75s, 16kHz mono).  
  Spoken Question: *"What is the time complexity of searching in a balanced binary search tree?"*
- **Test Driver**: `tools/e2e/test_answer_path_baseline.py` driving real Win32 process HWNDs with local `FakeOllamaRunner` on port `11438`.
- **Monitored Pipeline Stages**:
  1. `transcript_shown`: Speech recognized and attributed to `[You]` or `[Call]`.
  2. `answer_trigger`: Question classified by `LiveAudioAssistant.classify_utterance`.
  3. `provider_request_sent`: Request dispatched to LLM client.
  4. `first_token`: First streamed token received and rendered.
  5. `answer_complete`: Full answer generated.
  6. `answer_rendered`: Target UI widget where the answer is rendered (`home_card` vs `hud_panel` vs `none`).
  7. `history_written`: Whether the Q&A was recorded into `history.json`.

---

## 2. Baseline Test Results Table

| Case | Configuration | Transcript Shown | Trigger Rule | Provider Request Sent | First Token Streamed | Answer Complete | Answer Rendered In UI | History Written | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **(a)** | **HUD Hidden** (`show_hud_on_solve=False`, HUD closed) | Yes | Question Classifier | Yes | **No** (blocking) | Yes | **NONE (Home window has no live answer card)** | **No** | **FAIL** |
| **(b)** | **HUD Visible** (`show_hud_on_solve=True`, HUD open) | Yes | Question Classifier | Yes | **No** (blocking) | Yes | `hud_panel` only | **No** | **PARTIAL** |
| **(c)** | **Fake AI Server UP** | Yes | Question Classifier | Yes | **No** (blocking) | Yes | `hud_panel` only | **No** | **PARTIAL** |
| **(d)** | **Fake AI Server DOWN** | Yes | None | **No** | **No** | **No** | **NONE (No error row on Home)** | **No** | **FAIL** |
| **(e1)** | **Profile Grounding OFF** | Yes | Question Classifier | Yes | **No** (blocking) | Yes | `hud_panel` only | **No** | **PARTIAL** |
| **(e2)** | **Profile Grounding ON** | Yes | Question Classifier | Yes | **No** (blocking) | Yes | `hud_panel` only | **No** | **PARTIAL** |

---

## 3. Forensic Analysis & Proven Root Causes

### 3.1 Failure 1: No Live Results or Answer Card on the Main Window (Home Screen)
- **Location**: `ghostline/app.py:865-878` (`_main_thread_audio_answer`) and `ghostline/ui/qt_main_window.py`.
- **Evidence**:
  ```python
  def _main_thread_audio_answer(self, question: str, answer: str, code: Optional[str] = None, entry_id: str = ""):
      try:
          get_history_store().add_audio_qa(question=question, answer=answer, code=code)
      except Exception:
          pass
      if hasattr(self, "audio_panel") and self.audio_panel:
          self.audio_panel.set_ai_answer(question, answer, code)
      if hasattr(self, "hud") and self.hud:
          self.hud.append_ai_answer(answer, question=question, code=code, entry_id=entry_id if entry_id else None)
  ```
  `self.main_window` is completely omitted from the answer delivery path! When the user operates Ghostline from the main window with the HUD overlay hidden or tucked away, **zero AI answers are ever displayed to the user**.

### 3.2 Failure 2: Completely Synchronous / Blocking Inference (No First-Token Streaming)
- **Location**: `ghostline/audio/assistant.py:424-455`.
- **Evidence**:
  The assistant invokes synchronous `self.llm.generate(...)` with `max_tokens=200`. It waits for the complete HTTP response before dispatching anything to the UI. There is no token-by-token streaming, no `"Thinking... (N s)"` elapsed indicator on the Home card, and no intermediate tokens.

### 3.3 Failure 3: Silent Disappearance on Provider Failures
- **Location**: `ghostline/audio/assistant.py:492-511` and `ghostline/app.py:879-887`.
- **Evidence**:
  When Ollama or a cloud provider fails (e.g. server down, 403, key invalid), the error is only routed to `self.hud.show_audio_error` or `self.audio_panel.set_ai_error`. The main Home window has no error row, no state-aware status, and no `[Fix]` button (e.g. `[Start Ollama]`, `[Open AI settings]`).

### 3.4 Failure 4: Incremental History Not Written During Live Session
- **Location**: `ghostline/audio/transcription.py` and `ghostline/app.py`.
- **Evidence**:
  `get_history_store().add_audio_qa` is only invoked inside `_main_thread_audio_answer`. If no question was asked, or if a crash occurs mid-session, transcript turns are stored only in memory (`self.turns`) and are never flushed incrementally to disk.

---

## 4. Architectural Fix Plan for Part 2 & Part 2B

1. **Build a Dedicated "Live Session" Card on the Home Screen (`qt_main_window.py`)**:
   - Real-time timestamped transcript rows labelled `You (mic)` (`#6CCB5F`) and `System audio` (`#38BDF8`).
   - Streaming partial speech text (greyed out) transitioning to crisp white upon finalization.
   - Dedicated AI Answer card displaying streamed tokens with `"Thinking... (N s)"` indicator.
   - State-aware error row with actionable `[Fix]` button (`[Start Ollama]`, `[Open AI settings]`).
2. **Synchronize Home Card and HUD Overlay through a Unified View-Model**:
   - One source of truth (`LiveSessionViewModel`) ensuring that whether HUD is visible or hidden, all content is identical and immediately visible.
3. **Stream Tokens from Live LLM Requests**:
   - Implement streaming generator in `LiveAudioAssistant` and route token chunks via Qt bridge to both Home card and HUD panel.
4. **Decouple Transcript from AI Inferences**:
   - Transcript updates must continue streaming smoothly regardless of whether an AI inference is pending, slow, or failed.
5. **Incremental Session Persistence in History**:
   - Write transcript segments and answers to `history.json` on every final segment so that history is preserved even across abrupt process termination.

