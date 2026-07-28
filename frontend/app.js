const state = {
  currentPhrase: null,
  mediaRecorder: null,
  chunks: [],
  recordedBlob: null,
  isRecording: false,
};

const els = {
  difficultySelect: document.getElementById("difficulty-select"),
  newPhraseBtn: document.getElementById("new-phrase-btn"),
  phraseText: document.getElementById("phrase-text"),
  phraseDifficulty: document.getElementById("phrase-difficulty"),
  phraseCategory: document.getElementById("phrase-category"),
  recordBtn: document.getElementById("record-btn"),
  preview: document.getElementById("preview"),
  submitBtn: document.getElementById("submit-btn"),
  statusLine: document.getElementById("status-line"),
  resultsCard: document.getElementById("results-card"),
  overallScore: document.getElementById("overall-score"),
  feedbackWords: document.getElementById("feedback-words"),
  transcriptText: document.getElementById("transcript-text"),
  statsSummary: document.getElementById("stats-summary"),
  historyList: document.getElementById("history-list"),
  authStatus: document.getElementById("auth-status"),
};

function setStatus(message) {
  els.statusLine.textContent = message || "";
}

async function loadCurrentUser() {
  try {
    const res = await fetch("/api/me");
    if (!res.ok) return;
    const me = await res.json();
    const label = me.email || `user #${me.id}`;
    els.authStatus.textContent = "";
    els.authStatus.appendChild(document.createTextNode(`Logged in as ${label} · `));
    const logoutLink = document.createElement("a");
    logoutLink.href = "/auth/logout";
    logoutLink.textContent = "Logout";
    els.authStatus.appendChild(logoutLink);
  } catch {
    // non-fatal — leave the header blank
  }
}

async function loadRandomPhrase() {
  const difficulty = els.difficultySelect.value;
  const url = new URL("/api/phrases/random", window.location.origin);
  if (difficulty) url.searchParams.set("difficulty", difficulty);

  els.phraseText.textContent = "Loading a phrase…";
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`No phrase found (${res.status})`);
    state.currentPhrase = await res.json();
    renderPhrase(state.currentPhrase);
  } catch (err) {
    els.phraseText.textContent = "Could not load a phrase.";
    setStatus(err.message);
  }
}

function renderPhrase(phrase) {
  els.phraseText.textContent = phrase.text;
  els.phraseDifficulty.textContent = phrase.difficulty;
  els.phraseCategory.textContent = phrase.category || "";
  els.phraseCategory.hidden = !phrase.category;
  resetRecording();
  els.resultsCard.hidden = true;
}

function resetRecording() {
  state.recordedBlob = null;
  els.preview.removeAttribute("src");
  els.submitBtn.disabled = true;
  setStatus("");
}

function pickMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = pickMimeType();
    state.mediaRecorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);
    state.chunks = [];

    state.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) state.chunks.push(e.data);
    };
    state.mediaRecorder.onstop = () => {
      state.recordedBlob = new Blob(state.chunks, {
        type: state.mediaRecorder.mimeType,
      });
      els.preview.src = URL.createObjectURL(state.recordedBlob);
      els.submitBtn.disabled = false;
      stream.getTracks().forEach((track) => track.stop());
    };

    state.mediaRecorder.start();
    state.isRecording = true;
    els.recordBtn.textContent = "■ Stop";
    els.recordBtn.classList.add("recording");
    setStatus("Recording… speak the phrase above.");
  } catch (err) {
    setStatus(
      "Microphone access failed: " + err.message + ". Check browser permissions."
    );
  }
}

function stopRecording() {
  if (state.mediaRecorder && state.isRecording) {
    state.mediaRecorder.stop();
    state.isRecording = false;
    els.recordBtn.textContent = "● Record";
    els.recordBtn.classList.remove("recording");
    setStatus("Recording captured. Review it, then submit.");
  }
}

function toggleRecording() {
  if (state.isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

async function submitAttempt() {
  if (!state.currentPhrase || !state.recordedBlob) return;

  els.submitBtn.disabled = true;
  setStatus("Transcribing and scoring your pronunciation…");

  const form = new FormData();
  form.append("phrase_id", state.currentPhrase.id);
  form.append("audio", state.recordedBlob, "recording.webm");

  try {
    const res = await fetch("/api/attempts/", { method: "POST", body: form });
    if (!res.ok) throw new Error(`Scoring failed (${res.status})`);
    const result = await res.json();
    renderFeedback(result);
    setStatus("Done. Record again to try another take.");
    await Promise.all([loadHistory(), loadStats()]);
  } catch (err) {
    setStatus(err.message);
    els.submitBtn.disabled = false;
  }
}

function renderFeedback(result) {
  els.resultsCard.hidden = false;
  els.overallScore.textContent = `${result.score}/100`;
  els.transcriptText.textContent = result.transcript || "(nothing recognized)";

  els.feedbackWords.innerHTML = "";
  for (const word of result.word_feedback) {
    const span = document.createElement("span");
    span.className = `word ${word.status}`;
    span.textContent = word.expected_word || word.heard_word || "?";
    const expected = (word.expected_phonemes || []).join(" ");
    const heard = (word.heard_phonemes || []).join(" ");
    span.title = `expected: ${expected || "–"} | heard: ${heard || "–"}`;
    els.feedbackWords.appendChild(span);
    els.feedbackWords.appendChild(document.createTextNode(" "));
  }
}

async function loadHistory() {
  try {
    const res = await fetch("/api/attempts/?limit=20");
    const attempts = await res.json();
    els.historyList.innerHTML = "";
    if (attempts.length === 0) {
      els.historyList.innerHTML = "<li>No attempts yet.</li>";
      return;
    }
    for (const attempt of attempts) {
      const li = document.createElement("li");
      const phraseSpan = document.createElement("span");
      phraseSpan.className = "history-phrase";
      phraseSpan.textContent = attempt.phrase_text;
      const scoreSpan = document.createElement("span");
      scoreSpan.className = "history-score";
      scoreSpan.textContent = `${attempt.score}/100`;
      li.appendChild(phraseSpan);
      li.appendChild(scoreSpan);
      els.historyList.appendChild(li);
    }
  } catch {
    els.historyList.innerHTML = "<li>Could not load history.</li>";
  }
}

async function loadStats() {
  try {
    const res = await fetch("/api/attempts/stats");
    const stats = await res.json();
    if (stats.total_attempts === 0) {
      els.statsSummary.textContent = "No attempts yet.";
      return;
    }
    els.statsSummary.textContent =
      `${stats.total_attempts} attempt(s) so far — average score ${stats.average_score}/100.`;
  } catch {
    els.statsSummary.textContent = "Could not load stats.";
  }
}

els.newPhraseBtn.addEventListener("click", loadRandomPhrase);
els.difficultySelect.addEventListener("change", loadRandomPhrase);
els.recordBtn.addEventListener("click", toggleRecording);
els.submitBtn.addEventListener("click", submitAttempt);

loadCurrentUser();
loadRandomPhrase();
loadHistory();
loadStats();
