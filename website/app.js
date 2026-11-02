/**
 * Ghostline Interactive Website Demo & Interactions
 * 100% Vanilla JS, zero dependencies, client-side only.
 */

document.addEventListener("DOMContentLoaded", () => {
  // -------------------------------------------------------------
  // 1. Tab Switching (with Keyboard ARIA support)
  // -------------------------------------------------------------
  const tabButtons = document.querySelectorAll(".demo-tab-btn");
  const tabPanels = document.querySelectorAll(".demo-tab-panel");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("aria-controls");

      tabButtons.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      tabPanels.forEach((p) => {
        p.classList.remove("active");
      });

      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      const targetPanel = document.getElementById(targetId);
      if (targetPanel) {
        targetPanel.classList.add("active");
      }
    });

    // Arrow Key Navigation for accessible tabs
    btn.addEventListener("keydown", (e) => {
      const tabList = Array.from(tabButtons);
      const index = tabList.indexOf(btn);

      if (e.key === "ArrowRight") {
        const next = tabList[(index + 1) % tabList.length];
        next.focus();
        next.click();
      } else if (e.key === "ArrowLeft") {
        const prev = tabList[(index - 1 + tabList.length) % tabList.length];
        prev.focus();
        prev.click();
      }
    });
  });

  // -------------------------------------------------------------
  // 2. Demo Tab 1: Screen Question Solve Simulation
  // -------------------------------------------------------------
  const questionData = {
    mcq1: {
      stem: "Which layer of the OSI model handles TCP segment sequencing and end-to-end flow control?",
      badge: "Option B (Transport Layer)",
      badgeBg: "var(--status-success-bg)",
      badgeColor: "var(--status-success-text)",
      explanation: `The <strong>Transport Layer (Layer 4)</strong> is responsible for end-to-end communication, session multiplexing, segment reordering, and flow control via protocols like TCP.`
    },
    mcq2: {
      stem: "What is the output of print([i**2 for i in range(4) if i % 2 == 0])?",
      badge: "[0, 4]",
      badgeBg: "var(--brand-badge-bg)",
      badgeColor: "var(--brand-text)",
      explanation: `range(4) produces [0, 1, 2, 3]. The filter (i % 2 == 0) selects [0, 2]. Squaring each element results in [0**2, 2**2] = <strong>[0, 4]</strong>.`
    },
    mcq3: {
      stem: "Which data structure provides O(1) average case lookup, insertion, and deletion?",
      badge: "Hash Table / Hash Map",
      badgeBg: "var(--status-success-bg)",
      badgeColor: "var(--status-success-text)",
      explanation: `A <strong>Hash Table</strong> maps keys to bucket indices via a hash function, achieving amortized <strong>O(1)</strong> time complexity for search, insertion, and deletion.`
    }
  };

  let currentQid = "mcq1";
  const questionButtons = document.querySelectorAll(".question-option-btn");
  const triggerSolveBtn = document.getElementById("btn-trigger-solve");
  const hudDisplay = document.getElementById("demo-hud-display");
  const hudBadge = document.getElementById("hud-badge-target");
  const hudContent = document.getElementById("hud-content-target");

  questionButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      questionButtons.forEach((b) => {
        b.classList.remove("selected");
        b.setAttribute("aria-checked", "false");
      });
      btn.classList.add("selected");
      btn.setAttribute("aria-checked", "true");
      currentQid = btn.dataset.qid;

      // Reset HUD display to ready state
      hudDisplay.classList.remove("scanning");
      hudBadge.textContent = "Scanning Required";
      hudBadge.style.backgroundColor = "rgba(255,255,255,0.06)";
      hudBadge.style.color = "var(--text-tertiary)";
      hudContent.innerHTML = `<p class="hud-explanation" style="font-style:italic;">Press "Simulate Screen Solve" to scan context and compute response.</p>`;
    });
  });

  if (triggerSolveBtn) {
    triggerSolveBtn.addEventListener("click", () => {
      const q = questionData[currentQid] || questionData.mcq1;
      hudDisplay.classList.add("scanning");
      triggerSolveBtn.disabled = true;
      triggerSolveBtn.textContent = "Scanning screen context...";

      setTimeout(() => {
        hudDisplay.classList.remove("scanning");
        triggerSolveBtn.disabled = false;
        triggerSolveBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
          Simulate Screen Solve
        `;
        hudBadge.textContent = q.badge;
        hudBadge.style.backgroundColor = q.badgeBg;
        hudBadge.style.color = q.badgeColor;
        hudContent.innerHTML = `<p class="hud-explanation">${q.explanation}</p>`;
      }, 700);
    });
  }

  // -------------------------------------------------------------
  // 3. Demo Tab 2: Live Meeting Audio Feed Simulation
  // -------------------------------------------------------------
  const toggleAudioBtn = document.getElementById("btn-toggle-audio");
  const transcriptFeed = document.getElementById("transcript-feed");
  const audioResponseTarget = document.getElementById("audio-response-target");

  const meetingScript = [
    { speaker: "[Call]", text: "Can you describe how your last system handled database read spikes during flash sales?" },
    { speaker: "[You]", text: "Sure. We introduced read replicas on PostgreSQL and fronted them with Redis cache clusters." },
    { speaker: "[Call]", text: "What cache eviction strategy did you use for inventory updates?" },
    { speaker: "[You]", text: "We used TTLs with write-through invalidation on stock depletion." },
    { speaker: "[Call]", text: "Great. Did you experience any replica replication lag issues?" }
  ];

  let audioRunning = false;
  let scriptIndex = 1;
  let audioTimer = null;

  if (toggleAudioBtn) {
    toggleAudioBtn.addEventListener("click", () => {
      audioRunning = !audioRunning;

      if (audioRunning) {
        toggleAudioBtn.classList.remove("btn-primary");
        toggleAudioBtn.classList.add("btn-secondary");
        toggleAudioBtn.textContent = "Pause Simulated Audio Feed";

        audioTimer = setInterval(() => {
          if (scriptIndex < meetingScript.length) {
            const item = meetingScript[scriptIndex];
            const div = document.createElement("div");
            div.className = "transcript-line";
            const tagClass = item.speaker === "[You]" ? "transcript-tag-you" : "transcript-tag-call";
            div.innerHTML = `<span class="${tagClass}">${item.speaker}</span> "${item.text}"`;
            transcriptFeed.appendChild(div);
            transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
            scriptIndex++;

            if (item.speaker === "[Call]" && item.text.includes("replication lag")) {
              audioResponseTarget.textContent =
`• Bottleneck: Asynchronous replication delay caused phantom reads on stock counts.
• Mitigation: Routed critical inventory decrement queries directly to primary database.
• Fallback: Cached soft-locks in Redis during payment checkout window.`;
            }
          } else {
            clearInterval(audioTimer);
            toggleAudioBtn.textContent = "Feed Completed (Click to Reset)";
          }
        }, 2200);
      } else {
        clearInterval(audioTimer);
        toggleAudioBtn.classList.remove("btn-secondary");
        toggleAudioBtn.classList.add("btn-primary");
        toggleAudioBtn.textContent = "Resume Simulated Audio Feed";

        if (scriptIndex >= meetingScript.length) {
          transcriptFeed.innerHTML = `<div class="transcript-line"><span class="transcript-tag-call">[Call]</span> "Can you describe how your last system handled database read spikes during flash sales?"</div>`;
          scriptIndex = 1;
          toggleAudioBtn.textContent = "Start Simulated Audio Feed";
        }
      }
    });
  }

  // -------------------------------------------------------------
  // 4. Demo Tab 3: Personal Profile Grounding Simulation
  // -------------------------------------------------------------
  const inputRole = document.getElementById("demo-role");
  const inputTech = document.getElementById("demo-tech");
  const inputExp = document.getElementById("demo-exp");
  const btnUpdateProfile = document.getElementById("btn-update-profile");
  const groundedAnswerBox = document.getElementById("grounded-answer-box");

  if (btnUpdateProfile) {
    btnUpdateProfile.addEventListener("click", () => {
      const role = (inputRole.value || "Software Engineer").trim();
      const tech = (inputTech.value || "Python, SQL").trim();
      const exp = (inputExp.value || "5 years").trim();

      const techs = tech.split(",").map(t => t.trim()).filter(Boolean);
      const primaryTech = techs[0] || "Python";
      const secondaryTech = techs[1] || "databases";

      groundedAnswerBox.textContent =
`As a ${role} with ${exp} of hands-on experience, I encountered a critical production issue where our ${primaryTech} services experienced severe latency spikes under peak throughput.

Using telemetry and diagnostics in ${secondaryTech}, I pinpointed connection pool saturation and excessive serialization overhead. I refactored the pipeline with asynchronous batching and optimized indexing, reducing P99 latency and restoring predictable system stability without service disruption.`;
    });
  }

  // -------------------------------------------------------------
  // 5. Demo Tab 4: Provider & Data Boundary Switcher
  // -------------------------------------------------------------
  const providerBtns = document.querySelectorAll(".demo-provider-btn");
  const boundaryStatusBadge = document.getElementById("boundary-status-badge");
  const boundaryHostBadge = document.getElementById("boundary-host-badge");
  const boundaryDetails = document.getElementById("boundary-details");

  const providerConfigs = {
    ollama: {
      status: "100% On-Device",
      statusBg: "var(--status-success-bg)",
      statusColor: "var(--status-success-text)",
      host: "Endpoint: http://127.0.0.1:11434 (Loopback)",
      network: "None. All OCR parsing and model inference run on your local machine.",
      keys: "Zero API keys needed. No external communication.",
      retention: "Captures and transcripts are stored locally in your Windows user profile."
    },
    openai: {
      status: "Cloud BYOK (Encrypted HTTPS)",
      statusBg: "var(--brand-badge-bg)",
      statusColor: "var(--brand-text)",
      host: "Endpoint: https://api.openai.com/v1",
      network: "Prompts and questions are transmitted over encrypted TLS 1.3 to OpenAI endpoints.",
      keys: "API key stored locally using Windows DPAPI (CryptProtectData). Never sent in plaintext.",
      retention: "Requests are subject to OpenAI's commercial API zero-data-retention policy."
    },
    gemini: {
      status: "Cloud BYOK (Google Cloud HTTPS)",
      statusBg: "var(--brand-badge-bg)",
      statusColor: "var(--brand-text)",
      host: "Endpoint: https://generativelanguage.googleapis.com",
      network: "Prompts are sent over HTTPS to Google Cloud Gemini endpoints.",
      keys: "Hardware-encrypted with DPAPI. Redacted from all local logs and error dumps.",
      retention: "Protected by Google Cloud data governance terms."
    },
    groq: {
      status: "Ultra-Fast Cloud BYOK",
      statusBg: "var(--brand-badge-bg)",
      statusColor: "var(--brand-text)",
      host: "Endpoint: https://api.groq.com/openai/v1",
      network: "Encrypted HTTPS communication to Groq cloud LPU inference engines.",
      keys: "Encrypted locally via Windows DPAPI. Strict HTTPS verified on every request.",
      retention: "Transcripts retained locally; provider retains data according to API terms."
    }
  };

  providerBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      providerBtns.forEach((b) => {
        b.classList.remove("active");
        b.classList.remove("btn-primary");
        b.classList.add("btn-secondary");
      });
      btn.classList.add("active");
      btn.classList.remove("btn-secondary");
      btn.classList.add("btn-primary");

      const prov = btn.dataset.prov;
      const cfg = providerConfigs[prov] || providerConfigs.ollama;

      boundaryStatusBadge.textContent = cfg.status;
      boundaryStatusBadge.style.backgroundColor = cfg.statusBg;
      boundaryStatusBadge.style.color = cfg.statusColor;
      boundaryHostBadge.textContent = cfg.host;

      boundaryDetails.innerHTML = `
        <p style="margin-bottom:0.5rem;">
          <strong>Network Destination:</strong> ${cfg.network}
        </p>
        <p style="margin-bottom:0.5rem;">
          <strong>Key Security:</strong> ${cfg.keys}
        </p>
        <p>
          <strong>Data at Rest & Retention:</strong> ${cfg.retention}
        </p>
      `;
    });
  });

  // -------------------------------------------------------------
  // 6. FAQ Accordion
  // -------------------------------------------------------------
  const faqItems = document.querySelectorAll(".faq-item");

  faqItems.forEach((item) => {
    const questionBtn = item.querySelector(".faq-question");
    if (questionBtn) {
      questionBtn.addEventListener("click", () => {
        const isOpen = item.classList.contains("open");

        // Close all others
        faqItems.forEach((other) => {
          other.classList.remove("open");
          const btn = other.querySelector(".faq-question");
          if (btn) btn.setAttribute("aria-expanded", "false");
        });

        if (!isOpen) {
          item.classList.add("open");
          questionBtn.setAttribute("aria-expanded", "true");
        }
      });
    }
  });
});
