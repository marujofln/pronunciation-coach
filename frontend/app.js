const state = {
  currentPhrase: null,
  mediaRecorder: null,
  chunks: [],
  recordedBlob: null,
  isRecording: false,
  hoverSpeakTimer: null,
};

const els = {
  difficultySelect: document.getElementById("difficulty-select"),
  categorySelect: document.getElementById("category-select"),
  newPhraseBtn: document.getElementById("new-phrase-btn"),
  phraseText: document.getElementById("phrase-text"),
  speakBtn: document.getElementById("speak-btn"),
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
  userMenu: document.getElementById("user-menu"),
  userMenuBtn: document.getElementById("user-menu-btn"),
  userTooltip: document.getElementById("user-tooltip"),
  userDropdown: document.getElementById("user-dropdown"),
  userDropdownEmail: document.getElementById("user-dropdown-email"),
  logoutLink: document.getElementById("logout-link"),
};

function setStatus(message) {
  els.statusLine.textContent = message || "";
}

// --- speech synthesis ----------------------------------------------------

// Long enough that incidental mouse travel across the feedback line doesn't
// trigger a word, short enough not to feel unresponsive when you do mean it.
// Also deliberately above Chrome's ~500ms native `title` delay, so a word's
// phoneme tooltip appears first and the audio follows it rather than racing.
const HOVER_SPEAK_DELAY_MS = 700;

// Web Speech API availability is browser/OS dependent, so every entry point
// degrades to a silent no-op rather than throwing.
function canSpeak() {
  return Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
}

// Both halves of "stop": the utterance already being spoken *and* the one a
// hover armed but hasn't fired yet. Callers only ever want both, and missing
// the timer is the subtle half — cancel() alone leaves it to fire later.
function stopSpeaking() {
  clearTimeout(state.hoverSpeakTimer);
  state.hoverSpeakTimer = null;
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

function speak(text) {
  if (!canSpeak() || !text) return;
  // Speaker output feeds straight back into getUserMedia on the laptops this
  // is built for, so speaking mid-recording would corrupt the very audio
  // about to be scored. The button is disabled too; this covers hover.
  if (state.isRecording) return;
  // Stop first, unconditionally: this is what makes a repeated click, or a
  // fast hover from one word to the next, *replace* what's playing instead
  // of queueing behind it. Every entry point gets it without remembering to.
  stopSpeaking();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  window.speechSynthesis.speak(utterance);
}

function speakCurrentPhrase() {
  if (state.currentPhrase) speak(state.currentPhrase.text);
}

// Nothing to say before the first phrase lands (or after one fails to), and
// nothing that should be said into an open microphone.
function updateSpeakButton() {
  els.speakBtn.disabled = !state.currentPhrase || state.isRecording;
}

async function loadCurrentUser() {
  try {
    const res = await fetch("/api/me");
    if (!res.ok) return;
    const me = await res.json();
    const label = me.email || `user #${me.id}`;
    els.userTooltip.textContent = label;
    els.userDropdownEmail.textContent = label;
    els.userMenu.hidden = false;
  } catch {
    // non-fatal — leave the user menu hidden
  }
}

function openUserMenu() {
  els.userDropdown.hidden = false;
  els.userMenuBtn.setAttribute("aria-expanded", "true");
}

function closeUserMenu() {
  els.userDropdown.hidden = true;
  els.userMenuBtn.setAttribute("aria-expanded", "false");
}

function toggleUserMenu() {
  if (els.userDropdown.hidden) {
    openUserMenu();
  } else {
    closeUserMenu();
  }
}

async function loadCategories() {
  try {
    const res = await fetch("/api/phrases/categories");
    if (!res.ok) return;
    for (const category of await res.json()) {
      const option = document.createElement("option");
      // The value stays the raw slug — it's what the API filters on and what
      // gets stored as a preference; only the label is prettified.
      option.value = category;
      option.textContent = categoryLabel(category);
      els.categorySelect.appendChild(option);
    }
  } catch {
    // non-fatal — the select keeps its "Any" option and filtering still works
  }
}

// "numbers-and-dates" -> "Numbers and dates". Sentence case rather than title
// case, which would capitalize the joiners ("Numbers And Dates").
function categoryLabel(category) {
  const words = category.replace(/-/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

async function loadPreferences() {
  try {
    const res = await fetch("/api/me/preferences");
    if (!res.ok) return;
    const prefs = await res.json();
    // A saved value for an option that no longer exists would silently select
    // nothing, so only apply what the select actually offers.
    if (hasOption(els.difficultySelect, prefs.difficulty)) {
      els.difficultySelect.value = prefs.difficulty;
    }
    if (hasOption(els.categorySelect, prefs.category)) {
      els.categorySelect.value = prefs.category;
    }
  } catch {
    // non-fatal — fall back to the "Any" defaults in the markup
  }
}

function hasOption(select, value) {
  if (!value) return false;
  return [...select.options].some((option) => option.value === value);
}

async function savePreferences() {
  try {
    await fetch("/api/me/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        difficulty: els.difficultySelect.value || null,
        category: els.categorySelect.value || null,
      }),
    });
  } catch {
    // non-fatal — the filter still applies to this session, it just won't stick
  }
}

function onFilterChange() {
  savePreferences();
  loadRandomPhrase();
}

async function loadRandomPhrase() {
  const difficulty = els.difficultySelect.value;
  const category = els.categorySelect.value;
  const url = new URL("/api/phrases/random", window.location.origin);
  if (difficulty) url.searchParams.set("difficulty", difficulty);
  if (category) url.searchParams.set("category", category);

  els.phraseText.textContent = "Loading a phrase…";
  // Here rather than in renderPhrase(): this is where the old phrase actually
  // goes away, and renderPhrase only runs after an unbounded await below — a
  // hover armed just before "New phrase" would otherwise fire during the
  // fetch. The failure path below never reaches renderPhrase at all.
  state.currentPhrase = null;
  stopSpeaking();
  updateSpeakButton();
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
  els.phraseCategory.textContent = phrase.category
    ? categoryLabel(phrase.category)
    : "";
  els.phraseCategory.hidden = !phrase.category;
  updateSpeakButton();
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
    // Playback into an open microphone would end up in the scored audio.
    stopSpeaking();
    updateSpeakButton();
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
    updateSpeakButton();
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

  // These spans are about to be destroyed; a hover timer armed against the
  // previous attempt's words must not outlive them.
  stopSpeaking();
  els.feedbackWords.innerHTML = "";
  for (const word of result.word_feedback) {
    const span = document.createElement("span");
    span.className = `word ${word.status}`;
    span.textContent = word.expected_word || word.heard_word || "?";
    const expected = (word.expected_phonemes || []).join(" ");
    const heard = (word.heard_phonemes || []).join(" ");
    span.title = `expected: ${expected || "–"} | heard: ${heard || "–"}`;
    // What playback should say. `expected_word` first: the point of the
    // feature is hearing the *correct* pronunciation, so a missing word
    // plays what should have been said. An `extra` word only ever has a
    // heard_word. Neither means an unpronounceable "?" — leave it unmarked.
    const speakable = word.expected_word || word.heard_word;
    if (speakable) span.dataset.speak = speakable;
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
els.difficultySelect.addEventListener("change", onFilterChange);
els.categorySelect.addEventListener("change", onFilterChange);
els.recordBtn.addEventListener("click", toggleRecording);
els.submitBtn.addEventListener("click", submitAttempt);
els.speakBtn.addEventListener("click", speakCurrentPhrase);

// Delegated onto the container rather than wired per span: renderFeedback()
// rebuilds those spans on every attempt, and mouseenter/mouseleave don't
// bubble, so mouseover/mouseout are what reach us here.
els.feedbackWords.addEventListener("mouseover", (e) => {
  const target = e.target.closest("[data-speak]");
  if (!target) return;
  stopSpeaking();
  // Delay the whole thing rather than debouncing the speech: a pointer merely
  // crossing the line should never fire at all, not fire and get cut off.
  state.hoverSpeakTimer = setTimeout(
    () => speak(target.dataset.speak),
    HOVER_SPEAK_DELAY_MS
  );
});

els.feedbackWords.addEventListener("mouseout", stopSpeaking);

// Hover doesn't exist on touch devices and isn't keyboard reachable; click
// is what makes per-word playback available there. No delay — it's deliberate.
els.feedbackWords.addEventListener("click", (e) => {
  const target = e.target.closest("[data-speak]");
  if (target) speak(target.dataset.speak);
});

// Firefox keeps speaking across a navigation, and Logout is a plain <a href>;
// don't leave a disembodied voice behind after the session ends.
window.addEventListener("pagehide", stopSpeaking);

els.userMenuBtn.addEventListener("click", (e) => {
  // Without this the document listener below sees the same click and
  // immediately closes what we just opened.
  e.stopPropagation();
  toggleUserMenu();
});

els.userMenuBtn.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") {
    e.preventDefault();
    openUserMenu();
    els.logoutLink.focus();
  }
});

document.addEventListener("click", (e) => {
  if (!els.userMenu.contains(e.target)) closeUserMenu();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !els.userDropdown.hidden) {
    closeUserMenu();
    els.userMenuBtn.focus();
  }
});

async function init() {
  loadCurrentUser();
  loadHistory();
  loadStats();
  // Sequential on purpose: the saved category can only be selected once its
  // <option> exists, and the first phrase must respect the restored filters.
  await loadCategories();
  await loadPreferences();
  loadRandomPhrase();
}

init();
