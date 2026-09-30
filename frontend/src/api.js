// Central API helper: React -> FastAPI backend (backend/main.py)
// REST  : /api/health, /api/analyze, /api/verify, /api/telemetry, /api/freeze-log
// WS    : `${API_WS}/ws/simulator` (mic PCM), `${API_WS}/ws/dashboard` (telemetry, 200ms)
// Override with: VITE_API_URL=http://localhost:8000 npm run dev
export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
export const API_WS = API_BASE.replace(/^http/, 'ws');

export async function getHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}

export async function analyzeAudio({ audioFile, referenceFile, claimedSpeaker }) {
  const form = new FormData();
  form.append('audio', audioFile, audioFile.name || 'sample.wav');
  if (referenceFile) form.append('reference', referenceFile, referenceFile.name || 'reference.wav');
  form.append('claimed_speaker', claimedSpeaker || 'unknown');
  const res = await fetch(`${API_BASE}/api/analyze`, { method: 'POST', body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || `analyze failed (${res.status})`);
  return data;
}

export async function verifySpeakers({ audioFile, referenceFile, claimedSpeaker }) {
  const form = new FormData();
  form.append('audio', audioFile, audioFile.name || 'sample.wav');
  form.append('reference', referenceFile, referenceFile.name || 'reference.wav');
  form.append('claimed_speaker', claimedSpeaker || 'unknown');
  const res = await fetch(`${API_BASE}/api/verify`, { method: 'POST', body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || `verify failed (${res.status})`);
  return data;
}


// ---------------------------------------------------------------------------
// Live WebSockets - implemented in backend/main.py (ws_simulator / ws_dashboard)
// ---------------------------------------------------------------------------

/**
 * Subscribe to /ws/dashboard. The backend pushes one telemetry payload the
 * instant an audio window is scored (risk_score, level, fft[64], latency_ms,
 * bank freeze state) plus a 200 ms heartbeat while the stream is quiet.
 *
 * @param onTelemetry (payload: object) => void   receives {type:'telemetry'} frames
 * @param options {{onHello?: Function, onStatus?: Function, reconnect?: boolean}}
 * @returns {{close: () => void, socket: () => WebSocket|null}}
 */
export function connectDashboard(onTelemetry, options = {}) {
  const { onHello, onStatus, reconnect = true } = options;
  let socket = null;
  let timer = null;
  let closed = false;
  let attempt = 0;

  const open = () => {
    if (closed) return;
    socket = new WebSocket(`${API_WS}/ws/dashboard`);
    socket.onopen = () => { attempt = 0; onStatus?.('open'); };
    socket.onmessage = (event) => {
      let payload;
      try { payload = JSON.parse(event.data); } catch { return; }
      if (payload?.type === 'hello') onHello?.(payload);
      else if (payload?.type === 'telemetry') onTelemetry(payload);
    };
    socket.onclose = () => {
      onStatus?.('closed');
      if (reconnect && !closed) {
        attempt += 1;
        timer = setTimeout(open, Math.min(1000 * attempt, 5000));   // bounded backoff
      }
    };
    socket.onerror = () => onStatus?.('error');
  };
  open();

  return {
    close: () => {
      closed = true;
      if (timer) clearTimeout(timer);
      try { socket?.close(); } catch { /* socket already gone */ }
    },
    socket: () => socket,
  };
}



/**
 * Open /ws/simulator and stream microphone PCM to the real-time detector.
 *
 * Feed it Float32Array mono frames (AudioWorklet at 16 kHz); every frame is
 * answered with a feedback frame holding the EMA-smoothed risk score, the
 * per-stage latency breakdown and, once per critical episode, the mock bank
 * freeze payload.
 *
 * @param options {{sessionId?: string, onReady?: Function, onFeedback?: Function, onStatus?: Function}}
 * @returns {{ready: Promise<object>, send: (samples: Float32Array|ArrayBuffer) => boolean,
 *            control: (message: object) => boolean, close: () => void}}
 */
export function openMicStream(options = {}) {
  const {
    sessionId = `web-${Math.random().toString(36).slice(2, 10)}`,
    onReady, onFeedback, onStatus,
  } = options;
  const socket = new WebSocket(`${API_WS}/ws/simulator?session_id=${encodeURIComponent(sessionId)}`);
  const ready = new Promise((resolve, reject) => {
    socket.onopen = () => onStatus?.('open');
    socket.onmessage = (event) => {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (message?.type === 'ready') { resolve(message); onReady?.(message); }
      else if (message?.type === 'feedback' || message?.type === 'summary') onFeedback?.(message);
      else if (message?.type === 'error') onStatus?.(`error: ${message.error || 'unknown'}`);
      else onFeedback?.(message);                       // pong / reset / config acks
    };
    socket.onclose = () => { onStatus?.('closed'); reject(new Error('simulator closed before ready')); };
    socket.onerror = () => onStatus?.('error');
  });

  const sendBinary = (bytes) => {
    if (socket.readyState !== WebSocket.OPEN) return false;
    socket.send(bytes);
    return true;
  };

  return {
    ready,
    /** One PCM frame as little-endian float32 - the browser-native format. */
    send: (samples) => sendBinary(
      samples instanceof ArrayBuffer ? samples : new Float32Array(samples).buffer,
    ),
    /** Control channel: {type:'reset'|'stop'|'ping'|'config', ...}. */
    control: (message) => sendBinary(new TextEncoder().encode(JSON.stringify(message))),
    close: () => { try { socket.close(); } catch { /* socket already gone */ } },
  };
}

