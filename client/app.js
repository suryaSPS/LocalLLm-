/* ------------------------------------------------------------------ *
 * Gym Assistant — PWA client                                           *
 * ------------------------------------------------------------------ */
'use strict';

// ---------------------------------------------------------------------------
// Config — set GYM_BEARER_TOKEN in your env and rebuild, or paste directly.
// In dev mode the server accepts any token.
// ---------------------------------------------------------------------------
const API_BASE    = '';          // same origin — FastAPI serves this file
const BEARER      = localStorage.getItem('gymToken') || 'changeme';
const STT_LANG    = 'en-IN';    // works great on Indian English
const TTS_RATE    = 1.0;
const TTS_PITCH   = 1.0;

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const transcriptEl     = document.getElementById('transcript');
const micBtn           = document.getElementById('mic-btn');
const interimEl        = document.getElementById('interim-text');
const textInput        = document.getElementById('text-input');
const sendBtn          = document.getElementById('send-btn');
const statusDot        = document.getElementById('status-dot');
const logNotification  = document.getElementById('log-notification');
const logText          = document.getElementById('log-text');
const undoBtn          = document.getElementById('undo-btn');

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let history       = [];   // [{role, content}]
let isRecording   = false;
let isBusy        = false;
let wakeLock      = null;
let recognition   = null;
let pendingLog    = null;  // last LOG payload, for undo

// ---------------------------------------------------------------------------
// Wake Lock — keep screen on at the gym
// ---------------------------------------------------------------------------
async function acquireWakeLock() {
  if (!('wakeLock' in navigator)) return;
  try {
    wakeLock = await navigator.wakeLock.request('screen');
    wakeLock.addEventListener('release', () => { wakeLock = null; });
  } catch (_) {}
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') acquireWakeLock();
});

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
async function checkHealth() {
  try {
    const r = await fetch(`${API_BASE}/health`);
    const data = await r.json();
    statusDot.className = (r.ok && data.ollama) ? 'online' : 'offline';
  } catch {
    statusDot.className = 'offline';
  }
}

setInterval(checkHealth, 15_000);
checkHealth();

// ---------------------------------------------------------------------------
// Transcript helpers
// ---------------------------------------------------------------------------
function appendMsg(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = text;
  transcriptEl.appendChild(div);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
  return div;
}

function appendSystemNote(text) {
  const div = document.createElement('div');
  div.className = 'msg system-note';
  div.textContent = text;
  transcriptEl.appendChild(div);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

// ---------------------------------------------------------------------------
// TTS — speak text via on-device synthesis, skip <<LOG>> blocks
// ---------------------------------------------------------------------------
const TTS_LOG_PATTERN = /<<LOG>>[\s\S]*?<<\/LOG>>/gi;

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  const clean = text.replace(TTS_LOG_PATTERN, '').trim();
  if (!clean) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(clean);
  utt.lang  = STT_LANG;
  utt.rate  = TTS_RATE;
  utt.pitch = TTS_PITCH;
  utt.onstart = () => setMicState('speaking');
  utt.onend   = () => setMicState('idle');
  utt.onerror = () => setMicState('idle');
  window.speechSynthesis.speak(utt);
}

// ---------------------------------------------------------------------------
// Mic button state machine
// ---------------------------------------------------------------------------
function setMicState(state) {
  micBtn.className = '';
  switch (state) {
    case 'recording': micBtn.classList.add('recording'); micBtn.textContent = '⏹'; micBtn.setAttribute('aria-pressed', 'true');  break;
    case 'thinking':  micBtn.classList.add('thinking');  micBtn.textContent = '⏳'; micBtn.setAttribute('aria-pressed', 'false'); break;
    case 'speaking':  micBtn.classList.add('speaking');  micBtn.textContent = '🔊'; micBtn.setAttribute('aria-pressed', 'false'); break;
    default:          micBtn.textContent = '🎙';         micBtn.setAttribute('aria-pressed', 'false'); break;
  }
}

// ---------------------------------------------------------------------------
// Chat — stream response from FastAPI
// ---------------------------------------------------------------------------
async function sendMessage(userText) {
  if (!userText.trim() || isBusy) return;
  isBusy = true;
  setMicState('thinking');

  appendMsg('user', userText);
  history.push({ role: 'user', content: userText });

  const assistantDiv = appendMsg('assistant', '');
  let fullResponse = '';
  let logCommitted = null;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${BEARER}`,
      },
      body: JSON.stringify({ message: userText, history: history.slice(-10) }),
    });

    if (!res.ok) throw new Error(`Server error ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });

      // Check for LOG_COMMITTED sentinel
      if (chunk.includes('__LOG_COMMITTED__')) {
        const [textPart, jsonPart] = chunk.split('__LOG_COMMITTED__');
        if (textPart) {
          fullResponse += textPart;
          assistantDiv.textContent = cleanForDisplay(fullResponse);
        }
        try { logCommitted = JSON.parse(jsonPart); } catch (_) {}
      } else {
        fullResponse += chunk;
        assistantDiv.textContent = cleanForDisplay(fullResponse);
        transcriptEl.scrollTop = transcriptEl.scrollHeight;
      }
    }

    history.push({ role: 'assistant', content: fullResponse });

    if (logCommitted) {
      pendingLog = logCommitted.payload;
      showLogNotification(logCommitted.detail, logCommitted.ok);
    }

    speak(fullResponse);

  } catch (err) {
    assistantDiv.textContent = `Error: ${err.message}`;
    appendSystemNote('Check that Ollama is running and the server is reachable.');
    setMicState('idle');
  } finally {
    isBusy = false;
    if (!window.speechSynthesis?.speaking) setMicState('idle');
    interimEl.textContent = '';
  }
}

// Strip <<LOG>> blocks from display text
function cleanForDisplay(text) {
  return text.replace(TTS_LOG_PATTERN, '').trim();
}

// ---------------------------------------------------------------------------
// Log notification + undo
// ---------------------------------------------------------------------------
function showLogNotification(detail, ok) {
  logText.textContent = ok ? `✓ ${detail}` : `⚠ ${detail}`;
  logNotification.classList.add('visible');
  setTimeout(() => logNotification.classList.remove('visible'), 8_000);
}

undoBtn.addEventListener('click', async () => {
  logNotification.classList.remove('visible');
  try {
    const r = await fetch(`${API_BASE}/log/set/last`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${BEARER}` },
    });
    if (r.ok) {
      appendSystemNote('Last set removed.');
    } else {
      appendSystemNote('Nothing to undo.');
    }
  } catch {
    appendSystemNote('Undo failed — server unreachable.');
  }
  pendingLog = null;
});

// ---------------------------------------------------------------------------
// Web Speech API — STT
// ---------------------------------------------------------------------------
function buildRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;

  const r = new SpeechRecognition();
  r.continuous     = false;
  r.interimResults = true;
  r.lang           = STT_LANG;
  r.maxAlternatives = 1;

  r.onresult = (e) => {
    let interim = '';
    let final   = '';
    for (const result of e.results) {
      if (result.isFinal) final   += result[0].transcript;
      else                interim += result[0].transcript;
    }
    interimEl.textContent = interim || final;
    if (final) r._finalTranscript = final;
  };

  r.onerror = (e) => {
    if (e.error === 'no-speech') {
      appendSystemNote('No speech detected. Try again.');
    } else {
      appendSystemNote(`STT error: ${e.error}. Use text input.`);
    }
    stopRecording(false);
  };

  r.onend = () => {
    if (isRecording) stopRecording(true);
  };

  return r;
}

function startRecording() {
  if (isBusy) return;
  window.speechSynthesis?.cancel();

  recognition = buildRecognition();
  if (!recognition) {
    appendSystemNote('Speech recognition not supported. Use text input below.');
    return;
  }

  recognition._finalTranscript = '';
  isRecording = true;
  setMicState('recording');
  try {
    recognition.start();
  } catch (_) {}
}

function stopRecording(send) {
  isRecording = false;
  try { recognition?.stop(); } catch (_) {}
  setMicState(isBusy ? 'thinking' : 'idle');

  if (send && recognition?._finalTranscript?.trim()) {
    const text = recognition._finalTranscript.trim();
    interimEl.textContent = '';
    sendMessage(text);
  }
  recognition = null;
}

// ---------------------------------------------------------------------------
// Mic button — touch + mouse events (sweaty gym hands need both)
// ---------------------------------------------------------------------------
function onMicStart(e) {
  e.preventDefault();
  acquireWakeLock();
  startRecording();
}

function onMicEnd(e) {
  e.preventDefault();
  if (isRecording) stopRecording(true);
}

micBtn.addEventListener('mousedown',  onMicStart);
micBtn.addEventListener('touchstart', onMicStart, { passive: false });
micBtn.addEventListener('mouseup',    onMicEnd);
micBtn.addEventListener('touchend',   onMicEnd,   { passive: false });
micBtn.addEventListener('mouseleave', (e) => { if (isRecording) stopRecording(true); });

// ---------------------------------------------------------------------------
// Text input fallback
// ---------------------------------------------------------------------------
sendBtn.addEventListener('click', () => {
  const text = textInput.value.trim();
  if (text) {
    textInput.value = '';
    sendMessage(text);
  }
});

textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendBtn.click();
  }
});

// ---------------------------------------------------------------------------
// Token prompt — first launch
// ---------------------------------------------------------------------------
(function promptToken() {
  const stored = localStorage.getItem('gymToken');
  if (!stored) {
    const tok = prompt('Enter your API token (leave blank for dev mode):');
    if (tok && tok.trim()) {
      localStorage.setItem('gymToken', tok.trim());
      location.reload();
    }
  }
})();

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
acquireWakeLock();
