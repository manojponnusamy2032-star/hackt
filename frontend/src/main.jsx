import React, { lazy, Suspense, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, ArrowRight, AudioLines, Check, ChevronDown, Eye, EyeOff, Gauge, LockKeyhole, LogOut, Menu, Play, ShieldCheck, Sparkles, Upload, UserRoundCheck, X } from 'lucide-react';
import './styles.css';
import { supabase, supabaseConfigured } from './supabase';
import ApiDashboardWorkspace from './api-dashboard-workspace.jsx';
const SupportPage = lazy(() => import('./support-pages.jsx'));
const DashboardResourceLinks = lazy(() => import('./support-pages.jsx').then((module) => ({ default: module.DashboardResourceLinks })));
const ResourceFooter = lazy(() => import('./support-pages.jsx').then((module) => ({ default: module.ResourceFooter })));

const steps = [
  { number: '01', title: 'Detect', copy: 'AASIST models inspect every sample for synthetic patterns hidden beneath natural speech.' },
  { number: '02', title: 'Verify', copy: 'Compare the voice against a trusted speaker profile before access or action is granted.' },
  { number: '03', title: 'Prevent', copy: 'Turn a risk signal into a clear decision: allow, verify, flag, or block.' },
];

function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [mode, setMode] = useState('login');
  const [status, setStatus] = useState({ type: '', message: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  useEffect(() => {
    const handleSupportHash = () => {
      const routes = { '#forgot': '/forgot-password', '#terms': '/terms', '#privacy': '/privacy' };
      const route = routes[window.location.hash];
      if (route) window.location.replace(route);
    };
    handleSupportHash();
    window.addEventListener('hashchange', handleSupportHash);
    return () => window.removeEventListener('hashchange', handleSupportHash);
  }, []);
  const submitLogin = async (event) => {
    event.preventDefault();
    setStatus({ type: '', message: '' });
    if (!supabaseConfigured) { setStatus({ type: 'error', message: 'Supabase is not configured. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to frontend/.env.' }); return; }
    setIsSubmitting(true);
    const result = mode === 'login'
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin + '/console' } });
    setIsSubmitting(false);
    if (result.error) { setStatus({ type: 'error', message: result.error.message }); return; }
    if (mode === 'login' && result.data.session) { window.location.replace('/dashboard'); return; }
    setStatus({ type: 'success', message: 'Account created. Check your email to confirm your account.' });
  };
  return <div className="login-shell">
    <div className="login-art"><a className="landing-brand" href="/"><span className="brand-mark"><AudioLines size={20} /></span><span><strong>voiceguard</strong></span></a><div className="login-art-copy"><span className="eyebrow">SECURITY OPERATIONS</span><h1>Keep trust<br /><em>in the conversation.</em></h1><p>One secure workspace for every signal, speaker, and decision.</p><div className="login-signal"><div className="login-signal-head"><span><i /> Live protection</span><b>ACTIVE</b></div><Waveform /></div></div><span className="login-art-footer">AI-powered voice security · NEXORA</span></div>
    <main className="login-panel"><a className="back-home" href="/"><ArrowRight size={14} /> Back to website</a><div className="login-card"><div className="login-icon"><LockKeyhole size={20} /></div><span className="eyebrow">{mode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}</span><h2>{mode === 'login' ? 'Sign in to VoiceGuard' : 'Create your account'}</h2><p className="login-copy">{mode === 'login' ? 'Access your security console and keep every high-trust interaction protected.' : 'Set up your secure workspace and start protecting high-trust interactions.'}</p>{status.message && <div className={`login-notice ${status.type}`}>{status.message}</div>}<form onSubmit={submitLogin}><label>Email address<input type="email" placeholder="you@company.com" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<span className="password-field"><input type={showPassword ? 'text' : 'password'} placeholder="Enter your password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={6} required /><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></span></label>{mode === 'login' && <div className="login-options"><label className="remember"><input type="checkbox" /> <span>Remember me</span></label><a href="#forgot">Forgot password?</a></div>}<button className="login-button" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'} {!isSubmitting && <ArrowRight size={16} />}</button></form>{mode === 'login' && <><div className="login-divider"><span>or continue with</span></div><button className="sso-button" type="button" onClick={() => setStatus({ type: 'error', message: 'Google sign-in needs to be enabled in your Supabase dashboard.' })}><span className="sso-mark">G</span> Continue with Google</button></>}<p className="login-help">{mode === 'login' ? 'New to VoiceGuard?' : 'Already have an account?'} <button className="mode-toggle" type="button" onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setStatus({ type: '', message: '' }); }}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button></p></div><p className="login-legal">By continuing, you agree to VoiceGuard's Terms and Privacy Policy.</p></main>
  </div>;
}

function DashboardWorkspace({ session, signOut }) {
  const [activeTab, setActiveTab] = useState('Overview');
  const [paused, setPaused] = useState(false);
  const [query, setQuery] = useState('');
  const tabs = [
    { label: 'Overview', icon: Gauge },
    { label: 'Live monitor', icon: Activity },
    { label: 'Analysis history', icon: AudioLines },
    { label: 'Speaker registry', icon: UserRoundCheck },
  ];
  const history = [
    ['09:42:18', 'unknown_caller_042.wav', 'Synthetic voice', '92 / 100'],
    ['09:31:04', 'maya_chen_check_018.wav', 'Verified', '08 / 100'],
    ['09:16:51', 'finance_transfer_18.wav', 'Review required', '67 / 100'],
    ['08:58:27', 'support_call_771.wav', 'Verified', '12 / 100'],
  ];
  const filteredHistory = history.filter((row) => row.join(' ').toLowerCase().includes(query.toLowerCase()));
  return <div className="dashboard-shell"><header className="dashboard-nav"><a className="landing-brand" href="/"><span className="brand-mark"><AudioLines size={20} /></span><span><strong>voiceguard</strong><small>security console</small></span></a><nav className="dashboard-tabs">{tabs.map(({ label, icon: Icon }) => <button className={activeTab === label ? 'dashboard-tab active' : 'dashboard-tab'} key={label} onClick={() => setActiveTab(label)}><Icon size={16} />{label}</button>)}</nav><div className="dashboard-user"><span>{session.user.email}</span><button className="dashboard-signout" onClick={signOut}><LogOut size={15} /> Sign out</button></div></header><main className="dashboard-main"><div className="dashboard-heading"><div><span className="eyebrow">{activeTab === 'Overview' ? 'SECURITY OPERATIONS' : activeTab.toUpperCase()}</span><h1>{activeTab === 'Overview' ? 'Good morning.' : activeTab}</h1><p>{activeTab === 'Overview' ? 'Monitor voice authenticity and protect high-trust interactions.' : `Manage your VoiceGuard ${activeTab.toLowerCase()} workspace.`}</p></div><span className="dashboard-status"><i /> All engines online</span></div>{activeTab === 'Overview' && <><section className="dashboard-metrics"><article><AlertTriangle size={18} /><span>Risk score</span><strong>72 / 100</strong><small>Needs review</small></article><article><AudioLines size={18} /><span>Samples analyzed</span><strong>1,284</strong><small>18 in the last hour</small></article><article><Gauge size={18} /><span>Threats blocked</span><strong>36</strong><small>3 today</small></article><article><UserRoundCheck size={18} /><span>Speaker accuracy</span><strong>98.4%</strong><small>+0.8% this week</small></article></section><section className="dashboard-grid"><article className="dashboard-card analysis-card"><div className="dashboard-card-title"><div><span className="eyebrow">ANALYSIS CENTER</span><h2>Inspect a voice sample</h2></div><span className="ready-badge"><Check size={13} /> Ready</span></div><p>Upload an audio recording to run the authenticity and speaker verification pipeline.</p><label className="dashboard-dropzone"><input type="file" accept="audio/*" /><Upload size={25} /><strong>Drop an audio file here</strong><small>WAV, MP3, M4A up to 25 MB</small></label><button className="dashboard-action" type="button"><Play size={15} fill="currentColor" /> Run analysis</button></article><article className="dashboard-card result-card"><div className="dashboard-card-title"><div><span className="eyebrow">LATEST RESULT</span><h2>Interaction risk</h2></div><Activity size={20} /></div><div className="dashboard-risk"><div className="dashboard-ring"><strong>72</strong><small>/100</small></div><div><b>HIGH RISK</b><h3>Verification required</h3><p>Potential synthetic voice detected. Do not authorize sensitive actions.</p></div></div><div className="dashboard-bars"><span><i style={{ width: '84%' }} /><b>Synthetic probability <em>84%</em></b></span><span><i style={{ width: '62%' }} /><b>Speaker match <em>62%</em></b></span><span><i style={{ width: '91%' }} /><b>Model confidence <em>91%</em></b></span></div></article></section></>}{activeTab === 'Live monitor' && <section className="dashboard-grid"><article className="dashboard-card analysis-card"><div className="dashboard-card-title"><div><span className="eyebrow">ACTIVE INTERACTION</span><h2>Inbound call · Channel 04</h2></div><span className="ready-badge"><i /> {paused ? 'Paused' : 'Live'}</span></div><p>Caller · +1 (415) ***-0182 · Gateway SIP-West-02</p><div className="monitor-wave"><Waveform /></div><p>“I’m calling about the urgent wire transfer approval...”</p><button className="dashboard-action" type="button" onClick={() => setPaused((value) => !value)}>{paused ? <Play size={15} /> : <PauseIcon />} {paused ? 'Resume monitoring' : 'Pause monitoring'}</button></article><article className="dashboard-card result-card"><div className="dashboard-card-title"><div><span className="eyebrow">AUTHENTICITY CHECK</span><h2>Elevated risk detected</h2></div><AlertTriangle size={20} /></div><div className="dashboard-risk"><div className="dashboard-ring danger"><strong>92</strong><small>/100</small></div><div><b>HIGH RISK</b><h3>Unknown speaker</h3><p>Voice does not match a registered identity. Recommend step-up verification.</p></div></div><button className="dashboard-action" type="button"><ShieldCheck size={15} /> Request verification</button></article></section>}{activeTab === 'Analysis history' && <section className="dashboard-card dashboard-table-card"><div className="dashboard-card-title"><div><span className="eyebrow">VOICE INTELLIGENCE</span><h2>Recent analyses</h2></div><input className="dashboard-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search samples" /></div><div className="dashboard-table-wrap"><table><thead><tr><th>TIME</th><th>SAMPLE</th><th>OUTCOME</th><th>RISK</th></tr></thead><tbody>{filteredHistory.map((row) => <tr key={row[1]}><td>{row[0]}</td><td><b>{row[1]}</b></td><td><span className="dashboard-outcome">{row[2]}</span></td><td>{row[3]}</td></tr>)}</tbody></table></div></section>}{activeTab === 'Speaker registry' && <section className="dashboard-card dashboard-table-card"><div className="dashboard-card-title"><div><span className="eyebrow">IDENTITY MANAGEMENT</span><h2>Registered speakers</h2></div><button className="dashboard-action compact" type="button"><UserRoundCheck size={15} /> Add speaker</button></div><div className="dashboard-table-wrap"><table><thead><tr><th>SPEAKER</th><th>DEPARTMENT</th><th>VOICE SAMPLES</th><th>STATUS</th></tr></thead><tbody><tr><td><b>Maya Chen</b><small>Executive leadership</small></td><td>Executive</td><td>14 samples</td><td><span className="dashboard-outcome verified">Verified</span></td></tr><tr><td><b>Jordan Lee</b><small>Support operations</small></td><td>Customer support</td><td>9 samples</td><td><span className="dashboard-outcome verified">Verified</span></td></tr><tr><td><b>Evan Brooks</b><small>IT administrator</small></td><td>Information technology</td><td>7 samples</td><td><span className="dashboard-outcome review">Review due</span></td></tr></tbody></table></div></section>}</main></div>;
}

function PauseIcon() { return <span className="pause-icon">||</span>; }

function DashboardPage() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [backendStatus, setBackendStatus] = useState('checking');
  const [fileName, setFileName] = useState('');

  useEffect(() => {
    if (!supabaseConfigured) { setLoading(false); return undefined; }
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => { if (mounted) { setSession(data.session); setLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession));
    return () => { mounted = false; listener.subscription.unsubscribe(); };
  }, []);

  useEffect(() => {
    if (!loading && !session && supabaseConfigured) window.location.replace('/console');
  }, [loading, session]);

  const signOut = async () => { await supabase?.auth.signOut(); window.location.replace('/console'); };
  if (loading) return <div className="dashboard-loading">Loading your secure workspace...</div>;
  if (!supabaseConfigured) return <div className="dashboard-loading">Configure Supabase to access the dashboard.</div>;
  if (!session) return null;
  const email = session.user.email || 'Security analyst';
  return <div className="dashboard-page-frame"><ApiDashboardWorkspace session={session} signOut={signOut} onBackendStatusChange={setBackendStatus} /><DashboardResourceLinks backendStatus={backendStatus} /></div>;
}

function Waveform() {
  const bars = [34, 62, 45, 88, 54, 75, 38, 96, 66, 43, 81, 57, 100, 70, 40, 78, 53, 91, 47, 64, 36, 73, 52, 86, 44, 68, 32, 58, 42, 76, 50, 93, 39, 65, 48, 82, 36, 71, 55, 89];
  return <div className="waveform" aria-label="Voice signal visualization">{bars.map((height, index) => <span key={index} style={{ height: `${height}%`, animationDelay: `${index * 35}ms` }} />)}</div>;
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
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);
  useEffect(() => {
    document.querySelectorAll('a[href="http://localhost:5173/console"]').forEach((link) => link.setAttribute('href', '/console'));
  }, []);
  return <div className="landing-shell">
    <header className="landing-nav">
      <a className="landing-brand" href="#top" onClick={closeMenu}><span className="brand-mark"><AudioLines size={20} /></span><span><strong>voiceguard</strong></span></a>
      <button className="landing-menu" aria-label="Toggle navigation" onClick={() => setMenuOpen((open) => !open)}>{menuOpen ? <X size={21} /> : <Menu size={21} />}</button>
      <nav className={menuOpen ? 'landing-links open' : 'landing-links'}><a href="#platform" onClick={closeMenu}>Platform</a><a href="#how-it-works" onClick={closeMenu}>How it works</a><a href="#security" onClick={closeMenu}>Security</a><a className="nav-login" href="http://localhost:5173/console">Sign in <ArrowRight size={14} /></a></nav>
    </header>

    <main id="top">
      <section className="hero-section"><div className="hero-copy"><div className="eyebrow-pill"><span />REAL-TIME VOICE SECURITY</div><h1>Trust the voice.<br /><em>Verify the signal.</em></h1><p className="hero-description">VoiceGuard protects high-trust conversations from AI impersonation with deepfake detection, speaker verification, and decisions your team can act on.</p><div className="hero-actions"><a className="hero-button" href="http://localhost:5173/console">Open security console <ArrowRight size={17} /></a><a className="demo-link" href="#how-it-works"><span className="play-icon"><Play size={12} fill="currentColor" /></span>See how it works</a></div><div className="hero-trust"><ShieldCheck size={17} /><span>Built for security teams handling sensitive conversations</span></div></div><div className="hero-visual"><div className="visual-glow" /><div className="signal-card"><div className="signal-top"><div><span className="signal-label">LIVE SIGNAL ANALYSIS</span><strong>Voice authenticity</strong></div><span className="live-status"><i /> Monitoring</span></div><div className="signal-display"><div className="signal-grid" /><Waveform /><div className="signal-line" /></div><div className="signal-footer"><span><AudioLines size={14} /> incoming_call_042.wav</span><b><Check size={13} /> protected</b></div></div><div className="floating-score"><span>RISK SCORE</span><strong>08</strong><small>Low risk</small><div className="score-mini"><i /></div></div><div className="floating-chip chip-one"><Check size={13} /> Speaker verified</div><div className="floating-chip chip-two"><Sparkles size={13} /> AI scan complete</div></div></section>

      <section className="stats-strip"><div><strong>98.4%</strong><span>speaker accuracy</span></div><div><strong>1.2M+</strong><span>voice samples analyzed</span></div><div><strong>24 / 7</strong><span>continuous protection</span></div><div><strong>0.4 sec</strong><span>average response time</span></div></section>

      <section className="platform-section" id="platform"><div className="section-intro"><span className="eyebrow">ONE SIGNAL. THREE LAYERS.</span><h2>Security that listens<br /><em>between the words.</em></h2><p>Identity alone is no longer enough. VoiceGuard combines authenticity, identity, and context to make every conversation safer.</p></div><div className="feature-list"><article><span className="feature-number">01</span><div><h3>Deepfake detection</h3><p>Find the spectral fingerprints of generated speech in real time.</p></div><ArrowRight size={18} /></article><article><span className="feature-number">02</span><div><h3>Speaker verification</h3><p>Make sure the person speaking is who they claim to be.</p></div><ArrowRight size={18} /></article><article><span className="feature-number">03</span><div><h3>Risk-led prevention</h3><p>Convert model output into an action your team can trust.</p></div><ArrowRight size={18} /></article></div></section>

      <section className="workflow-section" id="how-it-works"><div className="section-intro centered"><span className="eyebrow">HOW IT WORKS</span><h2>From voice input<br /><em>to confident action.</em></h2></div><div className="steps-grid">{steps.map((step) => <article className="step-card" key={step.number}><span>{step.number}</span><h3>{step.title}</h3><p>{step.copy}</p></article>)}</div></section>

      <section className="cta-section" id="security"><div><span className="eyebrow">READY WHEN YOU ARE</span><h2>Make every voice<br /><em>verifiable.</em></h2></div><a className="hero-button" href="http://localhost:5173/console">Enter VoiceGuard <ArrowRight size={17} /></a></section>
    </main>
    <ResourceFooter />
  </div>;
}

const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
const currentPage = currentPath === '/console' || currentPath === '/login'
  ? <><LoginPage /><ResourceFooter /></>
  : currentPath === '/dashboard'
    ? <DashboardPage />
    : currentPath === '/'
        ? <App />
      : <SupportPage path={currentPath} />;

createRoot(document.getElementById('root')).render(<Suspense fallback={<div className="dashboard-loading">Loading VoiceGuard...</div>}>{currentPage}</Suspense>);
