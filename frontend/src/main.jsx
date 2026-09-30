import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, ArrowUpRight, AudioLines, Check, ChevronDown, FileAudio, LayoutDashboard, LockKeyhole, Menu, Mic, MoreHorizontal, Play, Radio, ShieldCheck, SlidersHorizontal, Upload, UserRoundCheck, X } from 'lucide-react';
import { API_BASE, analyzeAudio, getHealth } from './api.js';
import './styles.css';

const API_URL = API_BASE;

const initialEvents = [];
const navItems = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Live monitor', icon: Radio },
  { label: 'Analysis history', icon: Activity },
  { label: 'Speaker registry', icon: UserRoundCheck },
];

function Metric({ label, value, note, tone, icon: Icon }) {
  return <article className={`metric metric-${tone}`}><div className="metric-top"><span>{label}</span><Icon size={17} strokeWidth={1.8} /></div><strong>{value}</strong><div className="metric-note"><span className="trend-dot" />{note}</div></article>;
}
function ScoreBar({ label, value, color }) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  return <div className="score-row"><div className="score-label"><span>{label}</span><b>{v}%</b></div><div className="score-track"><span style={{ width: `${v}%`, background: color }} /></div></div>;
}
function riskTone(level) {
  if (level === 'CRITICAL') return 'red';
  if (level === 'HIGH') return 'red';
  if (level === 'MEDIUM') return 'amber';
  return 'green';
}
function eventLevel(level) {
  const l = (level || '').toUpperCase();
  if (l === 'CRITICAL' || l === 'HIGH') return 'high';
  if (l === 'MEDIUM') return 'medium';
  return 'low';
}

function App() {
  const [activeNav, setActiveNav] = useState('Overview');
  const [file, setFile] = useState(null);
  const [refFile, setRefFile] = useState(null);
  const [claimed, setClaimed] = useState('unknown');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [lastAnalysis, setLastAnalysis] = useState('not yet analyzed');
  const [events, setEvents] = useState(initialEvents);
  const [menuOpen, setMenuOpen] = useState(false);
  const [backend, setBackend] = useState({ state: 'checking', info: null });
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [metrics, setMetrics] = useState({ samples: 0, blocked: 0 });
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    let alive = true;
    getHealth().then((info) => { if (alive) setBackend({ state: 'online', info }); }).catch(() => { if (alive) setBackend({ state: 'offline', info: null }); });
    return () => { alive = false; };
  }, []);

  const handleFile = (event) => { const nextFile = event.target.files?.[0]; if (nextFile) { setFile(nextFile); setError(''); } };
  const handleRef = (event) => { const nextFile = event.target.files?.[0]; if (nextFile) setRefFile(nextFile); };

  const analyze = async () => {
    if (isAnalyzing || !file) { if (!file) setError('Choose an audio file (or record live) before running analysis.'); return; }
    setIsAnalyzing(true); setError('');
    try {
      const data = await analyzeAudio({ audioFile: file, referenceFile: refFile, claimedSpeaker: claimed });
      setResult(data);
      const now = new Date();
      const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setLastAnalysis(time);
      setMetrics((m) => ({ samples: m.samples + 1, blocked: m.blocked + (data?.prevention?.action === 'BLOCK' ? 1 : 0) }));
      setEvents((current) => [{ time, label: `Voice sample analyzed (${data?.risk?.risk_level || '?'})`, detail: data?.filename || file.name, level: eventLevel(data?.risk?.risk_level) }, ...current].slice(0, 6));
    } catch (err) {
      setError(err.message || 'Analysis failed. Is the Flask API running on :5000?');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleRecord = async () => {
    if (isRecording) {
      mediaRef.current?.mediaRecorder?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mr.mimeType || 'audio/webm' });
        const f = new File([blob], `live_recording_${Date.now()}.webm`, { type: blob.type });
        setFile(f); setError('');
        stream.getTracks().forEach((t) => t.stop());
        setIsRecording(false);
      };
      mediaRef.current = { mediaRecorder: mr };
      mr.start();
      setIsRecording(true);
    } catch (e) {
      setError('Microphone blocked by the browser. Allow mic access and retry.');
    }
  };

  const risk = result?.risk || null;
  const det = result?.detection || null;
  const spk = result?.speaker || null;
  const prev = result?.prevention || null;
  const hasResult = !!result;
  const riskScore = risk ? Math.round(risk.risk_score) : null;
  const riskLabel = risk?.risk_level ? `${risk.risk_level} RISK` : 'NO RESULT YET';
  const actionMsg = prev ? `${prev.action} - ${prev.message}` : 'Upload a sample and press Run analysis. Nothing has been scored yet.';
  const synthPct = det ? det.synthetic_probability * 100 : null;
  const spkPct = spk ? spk.speaker_match_score * 100 : null;
  const confPct = det ? det.model_confidence * 100 : null;

  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><AudioLines size={21} /></div><div><b>voiceguard</b><span>security console</span></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav>{navItems.map(({ label, icon: Icon }) => <button className={activeNav === label ? 'nav-item active' : 'nav-item'} key={label} onClick={() => { setActiveNav(label); setMenuOpen(false); }}><Icon size={18} /><span>{label}</span>{label === 'Live monitor' && <i className="live-dot" />}</button>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item"><SlidersHorizontal size={18} /><span>Settings</span></button><div className="engine-card"><div className="engine-heading"><span className="pulse" />{backend.state === 'online' ? `API online (${result?.deepfake_backend || backend.info?.deepfake_backend || 'ready'})` : backend.state === 'checking' ? 'Checking API...' : 'API offline - start Flask :5000'}</div><p>Last sync <strong>just now</strong> · <strong>{API_URL}</strong></p></div><div className="profile"><div className="avatar">AK</div><div><b>Alex Kim</b><span>Security analyst</span></div><MoreHorizontal size={18} /></div></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><button className="mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen((open) => !open)}>{menuOpen ? <X size={21} /> : <Menu size={21} />}</button><div className="breadcrumbs"><span>Workspace</span><span>/</span><b>{activeNav}</b></div><div className="topbar-actions"><span className="system-status"><span className="pulse" />{backend.state === 'online' ? 'System operational' : 'Backend unreachable'}</span></div></header>
      <div className="content-wrap">
        <section className="page-heading"><div><p className="eyebrow">VOICEGUARD · REACT + FLASK</p><h1>Good morning, Alex.</h1><p className="heading-copy">Monitor voice authenticity and protect high-trust interactions.</p></div><button className="outline-button" onClick={() => window.print()}><ArrowUpRight size={17} />Export report</button></section>
        <section className="metrics-grid"><Metric label="Risk score" value={hasResult ? `${riskScore} / 100` : '-- / 100'} note={risk ? `level ${risk.risk_level}` : 'no analysis yet'} tone={risk ? riskTone(risk.risk_level) : 'blue'} icon={AlertTriangle} /><Metric label="Samples analyzed" value={metrics.samples.toLocaleString()} note={metrics.samples ? 'this session' : 'no analysis yet'} tone="blue" icon={AudioLines} /><Metric label="Threats blocked" value={String(metrics.blocked)} note={metrics.blocked ? 'blocked this session' : 'no blocks yet'} tone="amber" icon={LockKeyhole} /><Metric label="Speaker match" value={spk ? `${(spk.speaker_match_score * 100).toFixed(1)}%` : '--'} note={spk ? (spk.speaker_verified ? 'speaker verified' : 'not verified') : 'no analysis yet'} tone="green" icon={ShieldCheck} /></section>
        <section className="primary-grid">
          <article className="panel analysis-panel"><div className="panel-header"><div><span className="section-kicker">ANALYSIS CENTER</span><h2>Inspect a voice sample</h2></div><span className="ready-badge"><Check size={13} /> {backend.state === 'online' ? 'API ready' : 'API offline'}</span></div><p className="panel-copy">Upload a recording or use your microphone to run the full authenticity and speaker verification pipeline.</p><label className={`dropzone ${file ? 'has-file' : ''}`}><input type="file" accept="audio/*" onChange={handleFile} /><div className="upload-icon">{file ? <FileAudio size={25} /> : <Upload size={25} />}</div><strong>{file ? file.name : 'Drop an audio file here'}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB - ready to inspect` : 'WAV, MP3, M4A up to 25 MB'}</span>{!file && <em>or browse files</em>}</label><div className="verify-row"><label className="verify-input">Claimed speaker<input type="text" value={claimed} onChange={(e) => setClaimed(e.target.value)} placeholder="e.g. CEO" /></label><label className="verify-input">Reference voice (optional)<input type="file" accept="audio/*" onChange={handleRef} /><span>{refFile ? refFile.name : 'no reference - neutral 0.5 used'}</span></label></div>{error && <p className="error-line">{error}</p>}{result?.deepfake_backend && <p className="backend-line">Scored by <b>{result.deepfake_backend}</b> · {result.duration_s}s audio</p>}<div className="analysis-actions"><button className="primary-button" onClick={analyze} disabled={isAnalyzing || !file}><Play size={16} fill="currentColor" />{isAnalyzing ? 'Analyzing sample...' : 'Run analysis'}</button><button className={`record-button ${isRecording ? 'recording' : ''}`} onClick={toggleRecord} title="Record from microphone"><Mic size={18} /><span>{isRecording ? 'Stop recording' : 'Record live'}</span></button></div><div className="pipeline"><div className="pipeline-step done"><span>01</span><b>Preprocess</b><small>{result ? `${result.duration_s}s @16kHz` : 'Ready'}</small></div><div className="pipeline-line done" /><div className="pipeline-step done"><span>02</span><b>Deepfake scan</b><small>{det ? `${(det.synthetic_probability * 100).toFixed(1)}% synthetic` : 'Ready'}</small></div><div className="pipeline-line" /><div className="pipeline-step"><span>03</span><b>Verify speaker</b><small>{spk && !spk.note ? `${(spk.speaker_match_score * 100).toFixed(1)}% match` : 'Waiting'}</small></div></div></article>
          <article className="panel score-panel"><div className="panel-header"><div><span className="section-kicker">LATEST RESULT</span><h2>Interaction risk</h2></div><button className="more-button" title="More result options"><MoreHorizontal size={19} /></button></div>{hasResult ? <><div className="risk-summary"><div className="risk-ring"><div><strong>{riskScore}</strong><span>/100</span></div></div><div><span className="risk-label">{riskLabel}</span><h3>{prev?.action || '--'}</h3><p>{actionMsg}</p></div></div><div className="score-bars"><ScoreBar label="Synthetic probability" value={synthPct} color="#ef6b5f" /><ScoreBar label="Speaker match" value={spkPct} color="#e5a93d" /><ScoreBar label="Model confidence" value={confPct} color="#4da7bd" /></div><div className="result-footer"><span><span className="file-dot" />{result.filename || file?.name}</span><span>Analyzed {lastAnalysis}</span></div></> : <div className="empty-result"><div className="empty-ring"><span>--</span></div><h3>No analysis yet</h3><p>Upload a voice sample above and press <b>Run analysis</b>. Live Flask scores will appear here — no placeholder numbers.</p></div>}</article>
        </section>
        <section className="lower-grid"><article className="panel activity-panel"><div className="panel-header"><div><span className="section-kicker">RECENT ACTIVITY</span><h2>Detection history</h2></div><button className="text-button">View all <ArrowUpRight size={15} /></button></div><div className="event-list">{events.length ? events.map((event, index) => <div className="event" key={`${event.time}-${index}`}><div className={`event-icon ${event.level}`}><span /></div><div className="event-copy"><b>{event.label}</b><span>{event.detail}</span></div><time>{event.time}</time></div>) : <p className="empty-note">No detections yet — history from this session will appear here.</p>}</div></article><article className="panel status-panel"><div className="panel-header"><div><span className="section-kicker">PROTECTION LAYER</span><h2>Prevention status</h2></div><ShieldCheck size={20} className="status-shield" /></div><div className="protection-score"><strong>94%</strong><span>policy coverage</span></div><div className="protection-list"><div><span className="status-check"><Check size={13} /></span><span>High-risk calls blocked</span><b>Active</b></div><div><span className="status-check"><Check size={13} /></span><span>Step-up verification</span><b>Active</b></div><div><span className="status-check"><Check size={13} /></span><span>Security alerts</span><b>Active</b></div></div><button className="manage-button">Manage prevention rules <ChevronDown size={16} /></button></article></section>
        <footer><span>VoiceGuard AI - NEXORA · Flask {API_URL}</span><span>Detection models v2.4.1</span></footer>
      </div>
    </main>
  </div>;
}
createRoot(document.getElementById('root')).render(<App />);
