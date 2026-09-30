import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, ArrowUpRight, AudioLines, Check, ChevronDown, CircleHelp, FileAudio, LayoutDashboard, LockKeyhole, Menu, Mic, MoreHorizontal, Pause, Play, Plus, Radio, Search, ShieldCheck, SlidersHorizontal, Upload, UserRoundCheck, X } from 'lucide-react';
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

const historyRows = [
  { time: '09:42:18', file: 'unknown_caller_042.wav', source: 'Inbound call · +1 (415) ***-0182', result: 'Synthetic voice', risk: 92, speaker: 'Unrecognized' },
  { time: '09:31:04', file: 'maya_chen_check_018.wav', source: 'Executive line · WebRTC', result: 'Verified', risk: 8, speaker: 'Maya Chen' },
  { time: '09:16:51', file: 'finance_transfer_18.wav', source: 'Finance · +1 (212) ***-7741', result: 'Review required', risk: 67, speaker: 'Possible match' },
  { time: '08:58:27', file: 'support_call_771.wav', source: 'Support · SIP gateway', result: 'Verified', risk: 12, speaker: 'Jordan Lee' },
  { time: '08:44:09', file: 'vendor_callback_205.wav', source: 'Procurement · WebRTC', result: 'Synthetic voice', risk: 88, speaker: 'Unrecognized' },
  { time: '08:21:36', file: 'maya_chen_check_017.wav', source: 'Executive line · WebRTC', result: 'Verified', risk: 5, speaker: 'Maya Chen' },
];

const initialSpeakers = [
  { name: 'Maya Chen', role: 'Executive leadership', department: 'Executive', samples: 14, updated: 'Sep 28, 2026', status: 'Verified', initials: 'MC' },
  { name: 'Jordan Lee', role: 'Support operations', department: 'Customer support', samples: 9, updated: 'Sep 25, 2026', status: 'Verified', initials: 'JL' },
  { name: 'Priya Nair', role: 'Finance director', department: 'Finance', samples: 11, updated: 'Sep 22, 2026', status: 'Verified', initials: 'PN' },
  { name: 'Evan Brooks', role: 'IT administrator', department: 'Information technology', samples: 7, updated: 'Sep 18, 2026', status: 'Review due', initials: 'EB' },
];

function LiveMonitorPage() {
  const [paused, setPaused] = useState(false);
  const [callState, setCallState] = useState('Elevated risk detected');
  const callEnded = callState === 'Call ended';
  return <>
    <section className="page-heading"><div><p className="eyebrow">REAL-TIME PROTECTION</p><h1>Live monitor</h1><p className="heading-copy">Watch active voice interactions as they happen.</p></div><button className="outline-button" onClick={() => setPaused((value) => !value)}>{paused ? <Play size={16} /> : <Pause size={16} />}{paused ? 'Resume monitoring' : 'Pause monitoring'}</button></section>
    <section className="metrics-grid"><Metric label="Active channels" value={paused ? '0' : '12'} note={paused ? 'Monitoring paused' : 'Across 4 workspaces'} tone="blue" icon={Radio} /><Metric label="Calls screened" value="186" note="Since 9:00 AM" tone="green" icon={AudioLines} /><Metric label="Flagged this hour" value="3" note="1 requires action" tone="red" icon={AlertTriangle} /><Metric label="Average latency" value="142 ms" note="Within 200 ms target" tone="amber" icon={Activity} /></section>
    <section className="monitor-grid">
      <article className="panel live-session-panel"><div className="panel-header"><div><span className="section-kicker">ACTIVE INTERACTION</span><h2>Inbound call · Channel 04</h2></div><span className={`live-status ${paused || callEnded ? 'paused' : ''}`}><i />{callEnded ? 'Ended' : paused ? 'Paused' : 'Live'}</span></div><div className="session-meta"><span>Started 09:41:52</span><span>Caller · +1 (415) ***-0182</span><span>Gateway · SIP-West-02</span></div><div className={`waveform ${paused || callEnded ? 'waveform-paused' : ''}`} aria-label="Live audio waveform">{Array.from({ length: 48 }, (_, index) => <i key={index} style={{ '--bar-height': `${18 + ((index * 37 + 19) % 68)}%`, '--bar-delay': `${(index % 12) * -0.11}s` }} />)}</div><div className="waveform-caption"><span>00:18</span><span>Incoming audio · encrypted</span><span>{callEnded ? 'ENDED' : paused ? 'PAUSED' : 'LIVE'}</span></div><div className="session-footer"><div><span className="section-kicker">TRANSCRIPTION</span><p>“I’m calling about the urgent wire transfer approval...”</p></div><span className="transcript-confidence">96% confidence</span></div></article>
      <article className="panel live-risk-panel"><div className="panel-header"><div><span className="section-kicker">AUTHENTICITY CHECK</span><h2>{callState}</h2></div><AlertTriangle size={19} className="status-alert" /></div><div className="live-risk-score"><strong>92</strong><span>HIGH RISK · 0.8s ago</span></div><ScoreBar label="Synthetic probability" value={92} color="#d94c72" /><ScoreBar label="Speaker match" value={18} color="#c68b2f" /><div className="risk-callout"><b>{callEnded ? 'Interaction closed' : 'Unknown speaker'}</b><span>{callEnded ? 'This interaction has been ended.' : callState === 'Verification requested' ? 'A step-up verification request has been sent to the caller.' : 'Voice does not match any registered identity. Recommend step-up verification.'}</span></div><div className="session-actions"><button className="primary-button" onClick={() => setCallState('Verification requested')} disabled={callEnded || callState === 'Verification requested'}><ShieldCheck size={16} />{callState === 'Verification requested' ? 'Verification requested' : 'Request verification'}</button><button className="record-button" onClick={() => setCallState('Call ended')} disabled={callEnded}><X size={16} />{callEnded ? 'Call ended' : 'End call'}</button></div></article>
    </section>
    <section className="panel monitor-queue"><div className="panel-header"><div><span className="section-kicker">CHANNEL ACTIVITY</span><h2>Monitoring queue</h2></div><button className="text-button">All channels <ChevronDown size={15} /></button></div><div className="table-scroll"><table><thead><tr><th>CHANNEL</th><th>INTERACTION</th><th>SPEAKER</th><th>RISK</th><th>STATUS</th></tr></thead><tbody><tr><td><span className="channel-mark live-mark"><Radio size={14} />04</span></td><td><b>Inbound call</b><small>+1 (415) ***-0182 · 00:18</small></td><td>Unrecognized</td><td><span className="risk-pill high">92 / 100</span></td><td><span className="state-text alert-state">Action needed</span></td></tr><tr><td><span className="channel-mark"><Radio size={14} />02</span></td><td><b>Support callback</b><small>+1 (800) ***-4062 · 03:42</small></td><td>Jordan Lee</td><td><span className="risk-pill low">08 / 100</span></td><td><span className="state-text">Verified</span></td></tr><tr><td><span className="channel-mark"><Radio size={14} />09</span></td><td><b>Executive line</b><small>WebRTC · 01:16</small></td><td>Maya Chen</td><td><span className="risk-pill low">05 / 100</span></td><td><span className="state-text">Verified</span></td></tr></tbody></table></div></section>
  </>;
}

function AnalysisHistoryPage() {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('All outcomes');
  const rows = historyRows.filter((row) => (filter === 'All outcomes' || row.result === filter) && `${row.file} ${row.source} ${row.speaker}`.toLowerCase().includes(query.toLowerCase()));
  return <>
    <section className="page-heading"><div><p className="eyebrow">VOICE INTELLIGENCE</p><h1>Analysis history</h1><p className="heading-copy">Review detection results and verification activity.</p></div><button className="outline-button"><ArrowUpRight size={16} />Export history</button></section>
    <section className="metrics-grid"><Metric label="Total analyses" value="1,284" note="18 in the last hour" tone="blue" icon={AudioLines} /><Metric label="Synthetic detected" value="36" note="2.8% of all samples" tone="red" icon={AlertTriangle} /><Metric label="Verified speakers" value="1,196" note="93.1% matched" tone="green" icon={UserRoundCheck} /><Metric label="Needs review" value="14" note="5 added today" tone="amber" icon={Activity} /></section>
    <section className="panel history-panel"><div className="panel-header"><div><span className="section-kicker">ALL SAMPLES</span><h2>Recent analyses <span className="result-count">{rows.length}</span></h2></div><button className="text-button"><SlidersHorizontal size={15} />Advanced filters</button></div><div className="table-tools"><label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search samples, callers, speakers" /></label><select aria-label="Filter by outcome" value={filter} onChange={(event) => setFilter(event.target.value)}><option>All outcomes</option><option>Synthetic voice</option><option>Verified</option><option>Review required</option></select><button className="date-filter"><span>Sep 30, 2026</span><ChevronDown size={15} /></button></div><div className="table-scroll"><table><thead><tr><th>TIME</th><th>SAMPLE</th><th>OUTCOME</th><th>RISK SCORE</th><th>SPEAKER</th><th></th></tr></thead><tbody>{rows.map((row) => <tr key={row.file}><td className="mono-cell">{row.time}</td><td><b>{row.file}</b><small>{row.source}</small></td><td><span className={`outcome-pill ${row.result === 'Verified' ? 'verified' : row.result === 'Review required' ? 'review' : 'synthetic'}`}><i />{row.result}</span></td><td><span className={`risk-number ${row.risk > 70 ? 'high-number' : row.risk > 40 ? 'mid-number' : ''}`}>{row.risk}<small> / 100</small></span></td><td>{row.speaker}</td><td><button className="row-action" aria-label={`Open ${row.file}`}><ArrowUpRight size={16} /></button></td></tr>)}</tbody></table>{rows.length === 0 && <div className="empty-state">No analyses match your search.</div>}</div><div className="table-pagination"><span>Showing {rows.length} of 1,284 analyses</span><div><button disabled>Previous</button><button>Next <ArrowUpRight size={13} /></button></div></div></section>
  </>;
}

function SpeakerRegistryPage() {
  const [speakers, setSpeakers] = useState(initialSpeakers);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('All statuses');
  const [adding, setAdding] = useState(false);
  const filteredSpeakers = speakers.filter((speaker) => (status === 'All statuses' || speaker.status === status) && `${speaker.name} ${speaker.role} ${speaker.department}`.toLowerCase().includes(query.toLowerCase()));
  const addSpeaker = (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = form.get('name').trim();
    const department = form.get('department').trim();
    if (!name || !department) return;
    const initials = name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
    setSpeakers((current) => [{ name, department, role: `${department} team`, samples: 0, updated: 'Just added', status: 'Enrollment needed', initials }, ...current]);
    setAdding(false);
  };
  return <>
    <section className="page-heading"><div><p className="eyebrow">IDENTITY MANAGEMENT</p><h1>Speaker registry</h1><p className="heading-copy">Manage trusted voice profiles used for speaker verification.</p></div><button className="primary-button" onClick={() => setAdding((value) => !value)}><Plus size={16} />Add speaker</button></section>
    <section className="metrics-grid"><Metric label="Registered speakers" value={`${speakers.length.toString().padStart(2, '0')}`} note="Across 6 departments" tone="blue" icon={UserRoundCheck} /><Metric label="Verified profiles" value={`${speakers.filter((speaker) => speaker.status === 'Verified').length}`} note="Voiceprints active" tone="green" icon={ShieldCheck} /><Metric label="Enrollment needed" value={`${speakers.filter((speaker) => speaker.status !== 'Verified').length}`} note="Complete voice samples" tone="amber" icon={Mic} /><Metric label="Registry accuracy" value="98.4%" note="Updated Sep 30" tone="red" icon={Activity} /></section>
    {adding && <section className="panel add-speaker-panel"><div className="panel-header"><div><span className="section-kicker">NEW VOICE PROFILE</span><h2>Add a trusted speaker</h2></div><button className="row-action" onClick={() => setAdding(false)} aria-label="Close form"><X size={17} /></button></div><form className="speaker-form" onSubmit={addSpeaker}><label>Full name<input name="name" placeholder="e.g. Taylor Morgan" required /></label><label>Department<input name="department" placeholder="e.g. Legal" required /></label><div><button className="primary-button" type="submit"><Plus size={15} />Create profile</button><button className="text-button" type="button" onClick={() => setAdding(false)}>Cancel</button></div></form></section>}
    <section className="panel registry-panel"><div className="panel-header"><div><span className="section-kicker">TRUSTED IDENTITIES</span><h2>Registered speakers <span className="result-count">{speakers.length}</span></h2></div><button className="text-button"><SlidersHorizontal size={15} />Manage fields</button></div><div className="table-tools"><label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name or department" /></label><select aria-label="Filter by verification status" value={status} onChange={(event) => setStatus(event.target.value)}><option>All statuses</option><option>Verified</option><option>Enrollment needed</option><option>Review due</option></select></div><div className="table-scroll"><table><thead><tr><th>SPEAKER</th><th>DEPARTMENT</th><th>VOICE SAMPLES</th><th>LAST UPDATED</th><th>STATUS</th><th></th></tr></thead><tbody>{filteredSpeakers.map((speaker) => <tr key={speaker.name}><td><div className="speaker-cell"><span className="speaker-avatar">{speaker.initials}</span><span><b>{speaker.name}</b><small>{speaker.role}</small></span></div></td><td>{speaker.department}</td><td><span className="sample-count">{speaker.samples} <small>samples</small></span></td><td>{speaker.updated}</td><td><span className={`outcome-pill ${speaker.status === 'Verified' ? 'verified' : 'review'}`}><i />{speaker.status}</span></td><td><button className="row-action" aria-label={`Open ${speaker.name} profile`}><MoreHorizontal size={17} /></button></td></tr>)}</tbody></table>{filteredSpeakers.length === 0 && <div className="empty-state">No speakers match your search.</div>}</div><div className="table-pagination"><span>Showing {filteredSpeakers.length} of {speakers.length} speakers</span><div><button disabled>Previous</button><button>Next <ArrowUpRight size={13} /></button></div></div></section>
  </>;
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
        {activeNav === 'Overview' ? <>
        <section className="page-heading"><div><p className="eyebrow">WEDNESDAY, SEPTEMBER 30, 2026</p><h1>Good morning, Alex.</h1><p className="heading-copy">Monitor voice authenticity and protect high-trust interactions.</p></div><button className="outline-button"><ArrowUpRight size={17} />Export report</button></section>
        <section className="metrics-grid"><Metric label="Risk score" value="72 / 100" note="12% from last week" tone="red" icon={AlertTriangle} /><Metric label="Samples analyzed" value="1,284" note="18 in the last hour" tone="blue" icon={AudioLines} /><Metric label="Threats blocked" value="36" note="3 today" tone="amber" icon={LockKeyhole} /><Metric label="Speaker accuracy" value="98.4%" note="0.8% from last week" tone="green" icon={ShieldCheck} /></section>
        <section className="primary-grid">
          <article className="panel analysis-panel"><div className="panel-header"><div><span className="section-kicker">ANALYSIS CENTER</span><h2>Inspect a voice sample</h2></div><span className="ready-badge"><Check size={13} /> Ready</span></div><p className="panel-copy">Upload a recording or use your microphone to run the full authenticity and speaker verification pipeline.</p><label className={`dropzone ${file ? 'has-file' : ''}`}><input type="file" accept="audio/*" onChange={handleFile} /><div className="upload-icon">{file ? <FileAudio size={25} /> : <Upload size={25} />}</div><strong>{file ? file.name : 'Drop an audio file here'}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to inspect` : 'WAV, MP3, M4A up to 25 MB'}</span>{!file && <em>or browse files</em>}</label><div className="analysis-actions"><button className="primary-button" onClick={analyze} disabled={isAnalyzing}><Play size={16} fill="currentColor" />{isAnalyzing ? 'Analyzing sample...' : 'Run analysis'}</button><button className="record-button" title="Record from microphone"><Mic size={18} /><span>Record live</span></button></div><div className="pipeline"><div className="pipeline-step done"><span>01</span><b>Preprocess</b><small>Ready</small></div><div className="pipeline-line done" /><div className="pipeline-step done"><span>02</span><b>Deepfake scan</b><small>Ready</small></div><div className="pipeline-line" /><div className="pipeline-step"><span>03</span><b>Verify speaker</b><small>Waiting</small></div></div></article>
          <article className="panel score-panel"><div className="panel-header"><div><span className="section-kicker">LATEST RESULT</span><h2>Interaction risk</h2></div><button className="more-button" title="More result options"><MoreHorizontal size={19} /></button></div><div className="risk-summary"><div className="risk-ring"><div><strong>72</strong><span>/100</span></div></div><div><span className="risk-label">HIGH RISK</span><h3>Verification required</h3><p>Potential synthetic voice detected. Do not authorize sensitive actions.</p></div></div><div className="score-bars"><ScoreBar label="Synthetic probability" value={84} color="#ef6b5f" /><ScoreBar label="Speaker match" value={62} color="#e5a93d" /><ScoreBar label="Model confidence" value={91} color="#4da7bd" /></div><div className="result-footer"><span><span className="file-dot" />{file?.name || 'unknown_caller_042.wav'}</span><span>Analyzed {lastAnalysis}</span></div></article>
        </section>
        <section className="lower-grid"><article className="panel activity-panel"><div className="panel-header"><div><span className="section-kicker">RECENT ACTIVITY</span><h2>Detection history</h2></div><button className="text-button">View all <ArrowUpRight size={15} /></button></div><div className="event-list">{events.map((event, index) => <div className="event" key={`${event.time}-${index}`}><div className={`event-icon ${event.level}`}><span /></div><div className="event-copy"><b>{event.label}</b><span>{event.detail}</span></div><time>{event.time}</time></div>)}</div></article><article className="panel status-panel"><div className="panel-header"><div><span className="section-kicker">PROTECTION LAYER</span><h2>Prevention status</h2></div><ShieldCheck size={20} className="status-shield" /></div><div className="protection-score"><strong>94%</strong><span>policy coverage</span></div><div className="protection-list"><div><span className="status-check"><Check size={13} /></span><span>High-risk calls blocked</span><b>Active</b></div><div><span className="status-check"><Check size={13} /></span><span>Step-up verification</span><b>Active</b></div><div><span className="status-check"><Check size={13} /></span><span>Security alerts</span><b>Active</b></div></div><button className="manage-button">Manage prevention rules <ChevronDown size={16} /></button></article></section>
        </> : activeNav === 'Live monitor' ? <LiveMonitorPage /> : activeNav === 'Analysis history' ? <AnalysisHistoryPage /> : <SpeakerRegistryPage />}
        <footer><span>VoiceGuard AI · NEXORA</span><span>Detection models v2.4.1</span></footer>
      </div>
    </main>
  </div>;
}
createRoot(document.getElementById('root')).render(<App />);
