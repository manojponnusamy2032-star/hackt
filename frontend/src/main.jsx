import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowRight, AudioLines, Check, ChevronDown, Eye, EyeOff, LockKeyhole, Menu, Play, ShieldCheck, Sparkles, X } from 'lucide-react';
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
    setStatus({ type: 'success', message: mode === 'login' ? 'Signed in successfully.' : 'Account created. Check your email to confirm your account.' });
  };
  return <div className="login-shell">
    <div className="login-art"><a className="landing-brand" href="/"><span className="brand-mark"><AudioLines size={20} /></span><span><strong>voiceguard</strong><small>by nexora</small></span></a><div className="login-art-copy"><span className="eyebrow">SECURITY OPERATIONS</span><h1>Keep trust<br /><em>in the conversation.</em></h1><p>One secure workspace for every signal, speaker, and decision.</p><div className="login-signal"><div className="login-signal-head"><span><i /> Live protection</span><b>ACTIVE</b></div><Waveform /></div></div><span className="login-art-footer">AI-powered voice security · NEXORA</span></div>
    <main className="login-panel"><a className="back-home" href="/"><ArrowRight size={14} /> Back to website</a><div className="login-card"><div className="login-icon"><LockKeyhole size={20} /></div><span className="eyebrow">{mode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}</span><h2>{mode === 'login' ? 'Sign in to VoiceGuard' : 'Create your account'}</h2><p className="login-copy">{mode === 'login' ? 'Access your security console and keep every high-trust interaction protected.' : 'Set up your secure workspace and start protecting high-trust interactions.'}</p>{status.message && <div className={`login-notice ${status.type}`}>{status.message}</div>}<form onSubmit={submitLogin}><label>Email address<input type="email" placeholder="you@company.com" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<span className="password-field"><input type={showPassword ? 'text' : 'password'} placeholder="Enter your password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={6} required /><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></span></label>{mode === 'login' && <div className="login-options"><label className="remember"><input type="checkbox" /> <span>Remember me</span></label><a href="#forgot">Forgot password?</a></div>}<button className="login-button" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'} {!isSubmitting && <ArrowRight size={16} />}</button></form>{mode === 'login' && <><div className="login-divider"><span>or continue with</span></div><button className="sso-button" type="button" onClick={() => setStatus({ type: 'error', message: 'Google sign-in needs to be enabled in your Supabase dashboard.' })}><span className="sso-mark">G</span> Continue with Google</button></>}<p className="login-help">{mode === 'login' ? 'New to VoiceGuard?' : 'Already have an account?'} <button className="mode-toggle" type="button" onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setStatus({ type: '', message: '' }); }}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button></p></div><p className="login-legal">By continuing, you agree to VoiceGuard's Terms and Privacy Policy.</p></main>
  </div>;
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

createRoot(document.getElementById('root')).render(window.location.pathname === '/console' ? <LoginPage /> : <App />);
