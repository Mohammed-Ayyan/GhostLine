## RULES
- Evidence: confirm every file/class/flag exists (ls/grep) before referencing it. Verify API signatures against the installed package or official docs, not memory.
- Status labels only: VERIFIED-AUTOMATED, VERIFIED-VISUAL (you opened the PNG and described 3+ specific things you saw), MOCK-ONLY, FAILED, BLOCKED, NEEDS-USER-CHECK. You cannot see the real desktop, hear audio, or judge real LLM answer quality without keys; those are NEEDS-USER-CHECK.
- Never run reset --hard, clean, checkout -- ., stash drop. Back up before risky steps. Never print/log/commit secrets. Never click Exit/Quit/destructive buttons in test scripts.
- Do not weaken tests. If a test asserts text/nav order you legitimately changed, update only that assertion and list it with the reason.
- No GPL/commercial UI libraries. No installing drivers/services/unknown tools. No Defender exclusions or UAC bypass. If something needs the user, stop that sub-task, report it, continue with independent work.
- Pushing is allowed only in Run 3 under its conditions.
- Write reports/run<N>_<part>.md after each part; re-read reports instead of relying on memory.

