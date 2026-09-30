import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, ArrowRight, AudioLines, Check, ChevronDown, Eye, EyeOff, Gauge, LockKeyhole, LogOut, Menu, Play, ShieldCheck, Sparkles, Upload, UserRoundCheck, X } from 'lucide-react';
import './styles.css';
import { supabase, supabaseConfigured } from './supabase';

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
    <div className="login-art"><a className="landing-brand" href="/"><span className="brand-mark"><AudioLines size={20} /></span><span><strong>voiceguard</strong><small>by nexora</small></span></a><div className="login-art-copy"><span className="eyebrow">SECURITY OPERATIONS</span><h1>Keep trust<br /><em>in the conversation.</em></h1><p>One secure workspace for every signal, speaker, and decision.</p><div className="login-signal"><div className="login-signal-head"><span><i /> Live protection</span><b>ACTIVE</b></div><Waveform /></div></div><span className="login-art-footer">AI-powered voice security · NEXORA</span></div>
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
  return <DashboardWorkspace session={session} signOut={signOut} />;
}

function Waveform() {
  const bars = [34, 62, 45, 88, 54, 75, 38, 96, 66, 43, 81, 57, 100, 70, 40, 78, 53, 91, 47, 64, 36, 73, 52, 86, 44, 68, 32, 58, 42, 76, 50, 93, 39, 65, 48, 82, 36, 71, 55, 89];
  return <div className="waveform" aria-label="Voice signal visualization">{bars.map((height, index) => <span key={index} style={{ height: `${height}%`, animationDelay: `${index * 35}ms` }} />)}</div>;
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);
  return <div className="landing-shell">
    <header className="landing-nav">
      <a className="landing-brand" href="#top" onClick={closeMenu}><span className="brand-mark"><AudioLines size={20} /></span><span><strong>voiceguard</strong><small>by nexora</small></span></a>
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
    <footer className="landing-footer"><a className="landing-brand" href="#top"><span className="brand-mark"><AudioLines size={17} /></span><span><strong>voiceguard</strong><small>by nexora</small></span></a><span>AI-powered voice security for a more trustworthy world.</span><span>© 2026 NEXORA</span></footer>
  </div>;
}

createRoot(document.getElementById('root')).render(window.location.pathname === '/console' ? <LoginPage /> : window.location.pathname === '/dashboard' ? <DashboardPage /> : <App />);
