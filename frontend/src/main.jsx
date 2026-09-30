import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, ArrowUpRight, AudioLines, Check, ChevronDown, CircleHelp, FileAudio, LayoutDashboard, LockKeyhole, Menu, Mic, MoreHorizontal, Play, Radio, ShieldCheck, SlidersHorizontal, Upload, UserRoundCheck, X } from 'lucide-react';
import './styles.css';

const initialEvents = [
  { time: '09:42:18', label: 'Voice sample analyzed', detail: 'unknown_caller_042.wav', level: 'high' },
  { time: '09:31:04', label: 'Speaker verified', detail: 'Executive / Maya Chen', level: 'low' },
  { time: '09:16:51', label: 'Additional verification requested', detail: 'finance_transfer_18.wav', level: 'medium' },
  { time: '08:58:27', label: 'Voice sample allowed', detail: 'support_call_771.wav', level: 'low' },
];
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
  return <div className="score-row"><div className="score-label"><span>{label}</span><b>{value}%</b></div><div className="score-track"><span style={{ width: `${value}%`, background: color }} /></div></div>;
}

function App() {
  const [activeNav, setActiveNav] = useState('Overview');
  const [file, setFile] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [lastAnalysis, setLastAnalysis] = useState('9:42:18 AM');
  const [events, setEvents] = useState(initialEvents);
  const [menuOpen, setMenuOpen] = useState(false);
  const handleFile = (event) => { const nextFile = event.target.files?.[0]; if (nextFile) setFile(nextFile); };
  const analyze = () => {
    if (isAnalyzing) return;
    setIsAnalyzing(true);
    window.setTimeout(() => {
      const now = new Date();
      const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setLastAnalysis(time);
      setEvents((current) => [{ time, label: 'Voice sample analyzed', detail: file?.name || 'live_microphone_input.wav', level: 'high' }, ...current].slice(0, 4));
      setIsAnalyzing(false);
    }, 900);
  };
  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><AudioLines size={21} /></div><div><b>voiceguard</b><span>security console</span></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav>{navItems.map(({ label, icon: Icon }) => <button className={activeNav === label ? 'nav-item active' : 'nav-item'} key={label} onClick={() => { setActiveNav(label); setMenuOpen(false); }}><Icon size={18} /><span>{label}</span>{label === 'Live monitor' && <i className="live-dot" />}</button>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item"><SlidersHorizontal size={18} /><span>Settings</span></button><div className="engine-card"><div className="engine-heading"><span className="pulse" />All engines online</div><p>Last sync <strong>just now</strong></p></div><div className="profile"><div className="avatar">AK</div><div><b>Alex Kim</b><span>Security analyst</span></div><MoreHorizontal size={18} /></div></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><button className="mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen((open) => !open)}>{menuOpen ? <X size={21} /> : <Menu size={21} />}</button><div className="breadcrumbs"><span>Workspace</span><span>/</span><b>{activeNav}</b></div><div className="topbar-actions"><span className="system-status"><span className="pulse" />System operational</span><button className="icon-button" title="Help"><CircleHelp size={19} /></button></div></header>
      <div className="content-wrap">
        <section className="page-heading"><div><p className="eyebrow">WEDNESDAY, SEPTEMBER 30, 2026</p><h1>Good morning, Alex.</h1><p className="heading-copy">Monitor voice authenticity and protect high-trust interactions.</p></div><button className="outline-button"><ArrowUpRight size={17} />Export report</button></section>
        <section className="metrics-grid"><Metric label="Risk score" value="72 / 100" note="12% from last week" tone="red" icon={AlertTriangle} /><Metric label="Samples analyzed" value="1,284" note="18 in the last hour" tone="blue" icon={AudioLines} /><Metric label="Threats blocked" value="36" note="3 today" tone="amber" icon={LockKeyhole} /><Metric label="Speaker accuracy" value="98.4%" note="0.8% from last week" tone="green" icon={ShieldCheck} /></section>
        <section className="primary-grid">
          <article className="panel analysis-panel"><div className="panel-header"><div><span className="section-kicker">ANALYSIS CENTER</span><h2>Inspect a voice sample</h2></div><span className="ready-badge"><Check size={13} /> Ready</span></div><p className="panel-copy">Upload a recording or use your microphone to run the full authenticity and speaker verification pipeline.</p><label className={`dropzone ${file ? 'has-file' : ''}`}><input type="file" accept="audio/*" onChange={handleFile} /><div className="upload-icon">{file ? <FileAudio size={25} /> : <Upload size={25} />}</div><strong>{file ? file.name : 'Drop an audio file here'}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to inspect` : 'WAV, MP3, M4A up to 25 MB'}</span>{!file && <em>or browse files</em>}</label><div className="analysis-actions"><button className="primary-button" onClick={analyze} disabled={isAnalyzing}><Play size={16} fill="currentColor" />{isAnalyzing ? 'Analyzing sample...' : 'Run analysis'}</button><button className="record-button" title="Record from microphone"><Mic size={18} /><span>Record live</span></button></div><div className="pipeline"><div className="pipeline-step done"><span>01</span><b>Preprocess</b><small>Ready</small></div><div className="pipeline-line done" /><div className="pipeline-step done"><span>02</span><b>Deepfake scan</b><small>Ready</small></div><div className="pipeline-line" /><div className="pipeline-step"><span>03</span><b>Verify speaker</b><small>Waiting</small></div></div></article>
          <article className="panel score-panel"><div className="panel-header"><div><span className="section-kicker">LATEST RESULT</span><h2>Interaction risk</h2></div><button className="more-button" title="More result options"><MoreHorizontal size={19} /></button></div><div className="risk-summary"><div className="risk-ring"><div><strong>72</strong><span>/100</span></div></div><div><span className="risk-label">HIGH RISK</span><h3>Verification required</h3><p>Potential synthetic voice detected. Do not authorize sensitive actions.</p></div></div><div className="score-bars"><ScoreBar label="Synthetic probability" value={84} color="#ef6b5f" /><ScoreBar label="Speaker match" value={62} color="#e5a93d" /><ScoreBar label="Model confidence" value={91} color="#4da7bd" /></div><div className="result-footer"><span><span className="file-dot" />{file?.name || 'unknown_caller_042.wav'}</span><span>Analyzed {lastAnalysis}</span></div></article>
        </section>
        <section className="lower-grid"><article className="panel activity-panel"><div className="panel-header"><div><span className="section-kicker">RECENT ACTIVITY</span><h2>Detection history</h2></div><button className="text-button">View all <ArrowUpRight size={15} /></button></div><div className="event-list">{events.map((event, index) => <div className="event" key={`${event.time}-${index}`}><div className={`event-icon ${event.level}`}><span /></div><div className="event-copy"><b>{event.label}</b><span>{event.detail}</span></div><time>{event.time}</time></div>)}</div></article><article className="panel status-panel"><div className="panel-header"><div><span className="section-kicker">PROTECTION LAYER</span><h2>Prevention status</h2></div><ShieldCheck size={20} className="status-shield" /></div><div className="protection-score"><strong>94%</strong><span>policy coverage</span></div><div className="protection-list"><div><span className="status-check"><Check size={13} /></span><span>High-risk calls blocked</span><b>Active</b></div><div><span className="status-check"><Check size={13} /></span><span>Step-up verification</span><b>Active</b></div><div><span className="status-check"><Check size={13} /></span><span>Security alerts</span><b>Active</b></div></div><button className="manage-button">Manage prevention rules <ChevronDown size={16} /></button></article></section>
        <footer><span>VoiceGuard AI · NEXORA</span><span>Detection models v2.4.1</span></footer>
      </div>
    </main>
  </div>;
}
createRoot(document.getElementById('root')).render(<App />);
