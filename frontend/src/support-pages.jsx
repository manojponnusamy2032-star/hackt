import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, ArrowLeft, ArrowRight, AudioLines, Bell, Building2, Check, CheckCircle2, ChevronRight, CircleHelp, ClipboardList, Eye, EyeOff, Fingerprint, KeyRound, LockKeyhole, Mail, Menu, Radio, ScanSearch, Send, ShieldCheck, UserRoundCheck, Workflow, X } from 'lucide-react';
import { supabase, supabaseConfigured } from './supabase';
import './support-pages.css';

const resourceLinks = [
  { href: '/about', label: 'About' },
  { href: '/security', label: 'Security' },
  { href: '/help', label: 'Help' },
  { href: '/contact', label: 'Contact' },
];

const footerLinks = [
  { href: '/about', label: 'About' },
  { href: '/security', label: 'Security' },
  { href: '/privacy', label: 'Privacy' },
  { href: '/terms', label: 'Terms' },
  { href: '/contact', label: 'Contact' },
  { href: '/help', label: 'Help' },
];

function Brand({ href = '/' }) {
  return <a className="landing-brand support-brand" href={href}><span className="brand-mark"><AudioLines size={19} /></span><span><strong>voiceguard</strong></span></a>;
}

function ResourceHeader({ minimal = false }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return <header className="support-header">
    <Brand />
    {!minimal && <>
      <button className="support-menu-button" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>{menuOpen ? <X size={19} /> : <Menu size={19} />}</button>
      <nav className={menuOpen ? 'support-nav open' : 'support-nav'} aria-label="Supporting pages">
        {resourceLinks.map((link) => <a key={link.href} href={link.href} onClick={() => setMenuOpen(false)}>{link.label}</a>)}
        <a href="/dashboard" onClick={() => setMenuOpen(false)}>Dashboard</a>
        <a className="support-nav-cta" href="/console" onClick={() => setMenuOpen(false)}>Sign in <ArrowRight size={14} /></a>
      </nav>
    </>}
  </header>;
}

export function ResourceFooter() {
  return <footer className="resource-footer"><div className="resource-footer-inner"><Brand /><p>Detect the Fake. Verify the Identity. Prevent the Threat.</p><nav aria-label="Legal and product links">{footerLinks.map((link) => <a href={link.href} key={link.href}>{link.label}</a>)}</nav><small>© 2026 NEXORA · Hackathon prototype</small></div></footer>;
}

export function DashboardResourceLinks() {
  return <footer className="dashboard-footer"><div className="dashboard-footer-inner"><a className="dashboard-footer-brand" href="/dashboard" aria-label="VoiceGuard dashboard"><span><AudioLines size={16} /></span><b>voiceguard</b></a><div className="dashboard-footer-meta"><span className="dashboard-footer-status"><i />All engines online</span><span className="dashboard-footer-copyright">© 2026 NEXORA</span></div><nav className="dashboard-footer-links" aria-label="Account and support"><a href="/security"><ShieldCheck size={14} />Security</a><a href="/help"><CircleHelp size={14} />Help</a><a href="/settings/notifications"><Bell size={14} />Settings</a><a href="/profile"><UserRoundCheck size={14} />Profile</a></nav></div></footer>;
}

function PageFrame({ children, minimal = false, className = '' }) {
  return <div className={`support-shell ${className}`}><ResourceHeader minimal={minimal} /><main className="support-main">{children}</main><ResourceFooter /></div>;
}

function PageHeading({ eyebrow, title, copy }) {
  return <header className="support-page-heading"><span className="support-eyebrow">{eyebrow}</span><h1>{title}</h1>{copy && <p>{copy}</p>}</header>;
}

function Notice({ type = 'info', children }) {
  const Icon = type === 'success' ? CheckCircle2 : type === 'error' ? AlertTriangle : ShieldCheck;
  return <div className={`support-notice ${type}`} role={type === 'error' ? 'alert' : 'status'}><Icon size={17} /><span>{children}</span></div>;
}

function AuthPanel({ children, eyebrow, title, copy }) {
  return <div className="auth-support-layout"><section className="auth-support-aside"><span className="auth-aside-mark"><AudioLines size={25} /></span><span className="support-eyebrow">VOICEGUARD AI · SECURITY OPERATIONS</span><h1>Trust the voice.<br /><em>Verify the signal.</em></h1><p>Protect every high-trust interaction with clear security signals and identity checks.</p><div className="auth-aside-status"><i /> Security console · encrypted connection</div></section><section className="auth-support-content"><a className="back-link" href="/console"><ArrowLeft size={15} /> Back to Sign In</a><div className="auth-support-card"><span className="support-eyebrow">{eyebrow}</span><h2>{title}</h2><p className="auth-support-copy">{copy}</p>{children}</div><div className="auth-legal-links"><a href="/terms">Terms of Service</a><a href="/privacy">Privacy Policy</a></div></section></div>;
}

function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    setStatus(null);
    if (!supabaseConfigured) {
      setStatus({ type: 'error', text: 'Password recovery is unavailable in this demo. Configure Supabase to send reset instructions.' });
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/reset-password` });
    setLoading(false);
    if (error) setStatus({ type: 'error', text: error.message });
    else setStatus({ type: 'success', text: 'Reset instructions sent. If an account exists for this address, check its inbox.' });
  };
  return <PageFrame minimal className="auth-support-shell"><AuthPanel eyebrow="ACCOUNT RECOVERY" title="Reset your password" copy="Enter the email associated with your VoiceGuard account and we'll send instructions to reset your password.">
    {status && <Notice type={status.type}>{status.text}</Notice>}
    <form className="support-form" onSubmit={submit}><label htmlFor="recovery-email">Email address</label><span className="support-input-wrap"><Mail size={17} /><input id="recovery-email" type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(event) => setEmail(event.target.value)} required /></span><button className="support-primary-button" type="submit" disabled={loading}>{loading ? 'Sending...' : 'Send reset link'} {!loading && <ArrowRight size={16} />}</button></form>
    <p className="prototype-note">For privacy, a successful response does not reveal whether an address has an account.</p>
  </AuthPanel></PageFrame>;
}

const passwordRules = [
  { label: 'At least 8 characters', test: (value) => value.length >= 8 },
  { label: 'One uppercase letter', test: (value) => /[A-Z]/.test(value) },
  { label: 'One lowercase letter', test: (value) => /[a-z]/.test(value) },
  { label: 'One number', test: (value) => /\d/.test(value) },
  { label: 'One special character', test: (value) => /[^A-Za-z0-9]/.test(value) },
];

function ResetPasswordPage() {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const passedRules = passwordRules.filter((rule) => rule.test(password)).length;
  const submit = async (event) => {
    event.preventDefault();
    setStatus(null);
    if (passedRules !== passwordRules.length) { setStatus({ type: 'error', text: 'Meet every password requirement before continuing.' }); return; }
    if (password !== confirm) { setStatus({ type: 'error', text: 'The passwords do not match.' }); return; }
    if (!supabaseConfigured) { setStatus({ type: 'error', text: 'Password updates are unavailable in this demo. Configure Supabase to update an account password.' }); return; }
    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password });
    setLoading(false);
    if (error) setStatus({ type: 'error', text: error.message });
    else { setStatus({ type: 'success', text: 'Password successfully updated.' }); setPassword(''); setConfirm(''); }
  };
  return <PageFrame minimal className="auth-support-shell"><AuthPanel eyebrow="SECURE YOUR ACCOUNT" title="Choose a new password" copy="Create a strong password for your VoiceGuard account.">
    {status && <Notice type={status.type}>{status.text}</Notice>}
    <form className="support-form" onSubmit={submit}>
      <label htmlFor="new-password">New password</label><span className="support-input-wrap"><KeyRound size={17} /><input id="new-password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><button className="password-visibility" type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></span>
      <div className="password-strength" aria-label={`Password strength ${passedRules} of 5`}><span style={{ width: `${passedRules * 20}%` }} /><small>{password ? `${passedRules}/5 requirements met` : 'Password strength'}</small></div>
      <ul className="password-rules">{passwordRules.map((rule) => <li key={rule.label} className={rule.test(password) ? 'met' : ''}><Check size={13} />{rule.label}</li>)}</ul>
      <label htmlFor="confirm-password">Confirm password</label><span className="support-input-wrap"><LockKeyhole size={17} /><input id="confirm-password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} required /></span>
      <button className="support-primary-button" type="submit" disabled={loading}>{loading ? 'Updating...' : 'Reset Password'} {!loading && <ArrowRight size={16} />}</button>
    </form>
    {status?.type === 'success' && <a className="support-secondary-button" href="/console">Return to Sign In <ArrowRight size={15} /></a>}
    <p className="prototype-note">Passwords are sent directly to the configured authentication provider and are not saved in browser storage.</p>
  </AuthPanel></PageFrame>;
}

const termsSections = [
  ['1. Introduction', 'VoiceGuard AI is a hackathon prototype developed to demonstrate layered voice-security workflows. These terms describe use of the prototype and are not a substitute for a negotiated enterprise agreement.'],
  ['2. Use of VoiceGuard', 'Use the service only for lawful security evaluation and authorized voice interactions. You are responsible for obtaining the permissions and notices required to analyze a voice sample.'],
  ['3. User Accounts', 'Keep account credentials confidential and notify the workspace administrator if access may have been compromised. Account functions depend on the configured authentication provider.'],
  ['4. Acceptable Use', 'Do not use the prototype to impersonate people, make consequential decisions without human review, unlawfully surveil individuals, or upload content you are not authorized to process.'],
  ['5. Voice Data and Security', 'Voice data can be sensitive biometric information. Only submit samples when you have a lawful basis and necessary consent. The prototype may process or retain data according to its active configuration; do not assume a retention or deletion guarantee.'],
  ['6. AI Detection Limitations', 'AI results are security signals, not infallible proof that a voice is synthetic or belongs to a particular person. Models may produce false positives and false negatives. Use additional verification and human judgment for high-impact decisions.'],
  ['7. Third-Party Integrations', 'Authentication and other integrations may be provided by third parties, including Supabase when configured. Their services are governed by their own terms and privacy policies.'],
  ['8. Security Responsibilities', 'Apply appropriate access controls, limit access to audio and event data, and avoid placing production secrets or sensitive recordings in the demo environment.'],
  ['9. Service Availability', 'The prototype is provided for demonstration and may change, become unavailable, or lose data without notice. No service-level commitment is offered.'],
  ['10. Intellectual Property', 'The VoiceGuard name, interface, and project materials remain with their respective owners. You receive no rights beyond permitted evaluation of the prototype.'],
  ['11. Limitation of Liability', 'To the extent permitted by law, the prototype is provided without warranties. Do not rely on it as the sole control for financial, identity, safety, or access decisions.'],
  ['12. Changes to Terms', 'These terms may be updated as the prototype evolves. The displayed update date identifies the current version.'],
  ['13. Contact', 'Questions about these terms can be sent through the Contact page. The contact form is a local prototype interaction and does not deliver email.'],
];

const privacySections = [
  ['1. Information We Collect', 'Depending on configuration, the prototype can receive account details, audio files or short-lived audio segments, analysis outputs, and operational metadata such as timestamps and integration identifiers.'],
  ['2. Voice Data', 'Voice recordings and derived voice features can identify a person and may be legally regulated. Submit only data you are authorized to process, and avoid real sensitive recordings in demonstrations.'],
  ['3. Audio Processing', 'The existing project includes audio-processing and inference components. Actual processing and retention depend on which frontend, API, and model services are connected. The demo does not guarantee that uploaded raw audio is never stored.'],
  ['4. AI Analysis', 'Detection and speaker-verification outputs are probabilistic security signals. They may be inaccurate and should not be treated as conclusive identity proof.'],
  ['5. Metadata', 'Security events may include risk levels, model confidence, speaker-match results, timestamps, and source identifiers for investigation. Avoid putting unnecessary personal information in metadata.'],
  ['6. Data Retention', 'Prototype retention behavior depends on the active app and deployment configuration and may not provide automated deletion. The intended production architecture minimizes raw-audio retention and may process short-lived segments, subject to validation and deployment controls.'],
  ['7. Data Security', 'Use access controls and secure deployment settings appropriate to the sensitivity of voice data. A hackathon prototype is not a certification or guarantee of production-grade security.'],
  ['8. Third-Party Services', 'When configured, Supabase may handle authentication. Other connected services may process data under their own policies. Review those terms before using real voice data.'],
  ['9. User Rights', 'Requests to access, correct, or delete data must be handled through the operator of the deployment and its configured storage providers. This prototype does not provide a complete rights-request workflow.'],
  ['10. Cookies', 'The authentication provider may use browser storage for session management. Notification preferences in this demo are saved locally in the browser. Do not store passwords or secrets in local storage.'],
  ["11. Children's Privacy", 'VoiceGuard is not designed for children. Do not submit children’s voice data to the prototype.'],
  ['12. Policy Changes', 'This policy may change as the project evolves. Review the displayed date before using the prototype with sensitive data.'],
  ['13. Contact', 'Use the Contact page to prepare a demo inquiry. Its success state is local and does not send a message to an operator.'],
];

function LegalPage({ privacy = false }) {
  const sections = privacy ? privacySections : termsSections;
  return <PageFrame><PageHeading eyebrow={privacy ? 'DATA & PRIVACY' : 'SERVICE TERMS'} title={privacy ? 'Privacy Policy' : 'Terms of Service'} copy={privacy ? 'How VoiceGuard handles voice, account, and security information.' : 'Terms for evaluating the VoiceGuard AI hackathon prototype.'} />
    <div className="legal-layout"><aside className="legal-aside"><span className="legal-date">Last updated: September 2026</span><div className="legal-callout"><ShieldCheck size={18} /><b>Prototype notice</b><p>{privacy ? 'Current data handling depends on the active deployment. Intended privacy controls are not a guarantee of current behavior.' : 'VoiceGuard results are security signals and should not be treated as infallible proof.'}</p></div><a href={privacy ? '/terms' : '/privacy'}>{privacy ? 'Read Terms of Service' : 'Read Privacy Policy'} <ArrowRight size={14} /></a></aside><article className="legal-document">{sections.map(([title, text]) => <section key={title}><h2>{title}</h2><p>{text}</p></section>)}</article></div>
  </PageFrame>;
}

const securityLayers = [
  { icon: Radio, title: 'REAL-TIME ANALYSIS', copy: 'Short-lived audio processing supports continuous risk analysis, subject to the connected deployment and its retention settings.' },
  { icon: Fingerprint, title: 'PRIVACY-FIRST PROCESSING', copy: 'Minimize unnecessary raw-voice storage. The current prototype does not guarantee raw audio is never retained.' },
  { icon: ScanSearch, title: 'MULTI-LAYER DETECTION', copy: 'Combine synthetic voice detection with speaker verification to assess authenticity and claimed identity separately.' },
  { icon: Activity, title: 'RISK-BASED RESPONSE', copy: 'Convert multiple security signals into an actionable risk level and recommend allow, verify, flag, or block.' },
  { icon: ClipboardList, title: 'AUDITABLE INCIDENTS', copy: 'Security event metadata can support investigation, with fields and retention determined by deployment configuration.' },
  { icon: Workflow, title: 'SECURE INTEGRATIONS', copy: 'Designed to connect with enterprise, banking, and communication systems through controlled integration points.' },
];

function SecurityPage() {
  return <PageFrame><PageHeading eyebrow="TRUST IS A SYSTEM" title="Security by Design" copy="A layered voice-security workflow built to make risk visible and response deliberate." />
    <section className="security-grid">{securityLayers.map(({ icon: Icon, title, copy }, index) => <article className="security-card" key={title}><span className="security-card-index">0{index + 1}</span><span className="security-card-icon"><Icon size={20} /></span><h2>{title}</h2><p>{copy}</p></article>)}</section>
    <section className="architecture-panel"><div><span className="support-eyebrow">SIGNAL FLOW</span><h2>From live voice to security action</h2><p>Each stage adds context. No single model score should act as conclusive proof.</p></div><ol className="architecture-flow">{['Live Voice', 'Audio Processing', 'AI Detection', 'Speaker Verification', 'Risk Engine', 'Security Action'].map((stage, index) => <li key={stage}><span>{String(index + 1).padStart(2, '0')}</span><b>{stage}</b>{index < 5 && <ChevronRight size={16} />}</li>)}</ol></section>
    <Notice>Prototype implementation and data-retention behavior vary by deployment. See the <a href="/privacy">Privacy Policy</a> for the distinction between current behavior and intended architecture.</Notice>
  </PageFrame>;
}

const sectors = ['Banking', 'Financial services', 'Enterprise', 'Telecom', 'Government', 'Customer support'];

function AboutPage() {
  return <PageFrame><PageHeading eyebrow="ABOUT VOICEGUARD" title="VoiceGuard AI" copy="Detect the Fake. Verify the Identity. Prevent the Threat." />
    <section className="about-intro"><div className="about-visual"><div className="about-orbit orbit-one" /><div className="about-orbit orbit-two" /><span><AudioLines size={39} /></span><i className="about-node node-one" /><i className="about-node node-two" /><i className="about-node node-three" /></div><div><span className="support-eyebrow">VOICE IS AN ATTACK SURFACE</span><h2>Trust needs more than a familiar voice.</h2><p>VoiceGuard is an AI-powered security platform designed to detect synthetic voice impersonation and help organizations respond to suspicious voice interactions.</p></div></section>
    <section className="about-pillars">{[['The problem', 'Voice cloning can make a fabricated voice sound like a trusted person, weakening voice-only checks.'], ['The solution', 'Combine synthetic-audio detection, speaker verification, risk assessment, and policy-based response.'], ['How it works', 'Process an audio sample, evaluate authenticity and identity signals, then surface a risk recommendation.'], ['Who it protects', 'Security teams handling high-trust conversations, account recovery, approvals, and customer support.']].map(([title, text], index) => <article key={title}><span>0{index + 1}</span><h2>{title}</h2><p>{text}</p></article>)}</section>
    <section className="sectors-panel"><div><span className="support-eyebrow">BUILT FOR HIGH-TRUST WORKFLOWS</span><h2>Who we protect</h2></div><div className="sector-tags">{sectors.map((sector) => <span key={sector}><Check size={13} />{sector}</span>)}</div></section>
    <section className="future-note"><SparkleIcon /><div><span className="support-eyebrow">FUTURE VISION</span><h2>Security that adapts with the voice threat.</h2><p>Move toward validated, privacy-preserving analysis, clear operator controls, and integrations that fit existing incident workflows.</p></div></section>
  </PageFrame>;
}

function SparkleIcon() { return <span className="future-icon"><Activity size={22} /></span>; }

function ContactPage() {
  const [sent, setSent] = useState(false);
  const submit = (event) => { event.preventDefault(); event.currentTarget.reset(); setSent(true); };
  return <PageFrame><PageHeading eyebrow="CONTACT & SUPPORT" title="How can we help?" copy="Send a note to the VoiceGuard team. This prototype does not send email; submissions stay in this browser session." />
    <div className="contact-layout"><form className="contact-form" onSubmit={submit}>{sent && <Notice type="success">Demo submission received in this browser only. No email was sent.</Notice>}<div className="form-grid"><label>Name<input name="name" autoComplete="name" required /></label><label>Email<input name="email" type="email" autoComplete="email" required /></label><label>Organization<input name="organization" autoComplete="organization" /></label><label>Subject<select name="subject" defaultValue=""><option value="" disabled>Select a topic</option><option>Security issue</option><option>Technical support</option><option>Partnership</option><option>General question</option></select></label></div><label>Message<textarea name="message" rows="5" required /></label><button className="support-primary-button" type="submit">Send Message <Send size={15} /></button></form><aside className="contact-topics"><span className="support-eyebrow">DIRECT TOPICS</span>{[['Security Issues', 'Report a suspected security weakness or data concern.'], ['Technical Support', 'Questions about the prototype and integrations.'], ['Partnerships', 'Discuss a potential collaboration or evaluation.'], ['General Questions', 'Anything else about VoiceGuard AI.']].map(([title, text], index) => <article key={title}><span className="contact-topic-icon">{index === 0 ? <ShieldCheck size={17} /> : index === 1 ? <CircleHelp size={17} /> : index === 2 ? <Building2 size={17} /> : <Mail size={17} />}</span><div><h2>{title}</h2><p>{text}</p></div></article>)}</aside></div>
  </PageFrame>;
}

const helpTopics = [
  ['Getting Started', 'Use the overview to inspect a sample, then review the result and recommended next step. The public demo uses illustrative data unless connected to a configured backend.'],
  ['Live Call Analysis', 'The live monitor page demonstrates channel status and risk presentation. Actual live-stream analysis requires an integration with a configured audio source.'],
  ['Understanding Risk Scores', 'A risk score combines available security signals. Higher scores indicate that additional verification may be appropriate; the score is not proof of fraud.'],
  ['Speaker Verification', 'Speaker verification compares a voice sample with an enrolled profile. Performance depends on audio quality, sample coverage, and the configured model.'],
  ['Deepfake Detection', 'Detection models look for artifacts associated with synthetic audio. Results can be wrong and should be reviewed with other signals.'],
  ['Security Alerts', 'Alerts can represent unusual authenticity, identity, or policy signals. Review the details and follow your organization’s verification procedure.'],
  ['Incident Management', 'Capture the relevant metadata, document operator decisions, and follow established escalation policy. Full incident workflows depend on the connected deployment.'],
  ['API Integration', 'Integration adapters are present in the repository. Configure and validate access controls, transport security, and data-retention behavior before production use.'],
  ['Privacy', 'Voice data can be sensitive. See the Privacy Policy for prototype limitations and the intended privacy-by-design direction.'],
];

function HelpPage() {
  const [query, setQuery] = useState('');
  const topics = helpTopics.filter(([title, text]) => `${title} ${text}`.toLowerCase().includes(query.toLowerCase()));
  return <PageFrame><PageHeading eyebrow="DOCUMENTATION" title="VoiceGuard Help Center" copy="Guidance for reviewing signals, profiles, and response workflows." />
    <label className="help-search"><CircleHelp size={17} /><input type="search" placeholder="Search help topics" value={query} onChange={(event) => setQuery(event.target.value)} /></label><section className="help-topic-grid">{topics.map(([title, text]) => <details className="help-topic" key={title}><summary><span>{title}</span><ChevronRight size={16} /></summary><p>{text}</p></details>)}</section>
    <section className="faq-band"><span className="support-eyebrow">QUICK ANSWERS</span><article><h2>What does the risk score mean?</h2><p>The risk score is a combined security signal generated from available detection and verification signals. A higher score indicates that additional verification may be appropriate.</p></article><article><h2>What happens when a call is suspicious?</h2><p>VoiceGuard can generate an alert and recommend additional verification depending on the configured security policy.</p></article><a className="support-text-link" href="/contact">Still need help? Contact support <ArrowRight size={14} /></a></section>
  </PageFrame>;
}

function ProfilePage() {
  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(supabaseConfigured);
  useEffect(() => {
    if (!supabaseConfigured) return undefined;
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      if (!data.session) window.location.replace('/console');
      else setAccount(data.session.user);
      setLoading(false);
    });
    return () => { active = false; };
  }, []);
  if (loading) return <PageFrame><div className="profile-loading">Loading account information...</div></PageFrame>;
  const demo = !supabaseConfigured;
  const fullName = account?.user_metadata?.full_name || (demo ? 'Alex Kim' : 'VoiceGuard user');
  return <PageFrame><PageHeading eyebrow="ACCOUNT" title="Profile" copy="Review account details and security settings." />
    {demo && <Notice>Demo profile only. No account service is configured; displayed identity and preferences are illustrative.</Notice>}
    <div className="profile-grid"><section className="profile-card"><div className="profile-card-title"><span className="profile-avatar">{fullName.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</span><div><h2>{fullName}</h2><p>{account?.email || 'alex.kim@example.com'}</p></div></div><dl className="profile-details"><div><dt>Name</dt><dd>{fullName}</dd></div><div><dt>Email</dt><dd>{account?.email || 'alex.kim@example.com'}</dd></div><div><dt>Organization</dt><dd>{account?.user_metadata?.organization || (demo ? 'Nexora Demo' : 'Not provided')}</dd></div><div><dt>Role</dt><dd>{account?.user_metadata?.role || 'Security analyst'}</dd></div></dl></section><section className="profile-card"><span className="support-eyebrow">SECURITY</span><div className="profile-setting"><span className="profile-setting-icon"><KeyRound size={17} /></span><div><h3>Change password</h3><p>Use the account recovery flow to update credentials.</p></div><a href="/forgot-password" aria-label="Change password"><ArrowRight size={16} /></a></div><div className="profile-setting"><span className="profile-setting-icon"><Fingerprint size={17} /></span><div><h3>Two-factor authentication</h3><p>{demo ? 'Not connected in demo mode.' : 'Check your authentication provider for enrolled factors.'}</p></div><span className="demo-tag">Provider managed</span></div><div className="profile-setting"><span className="profile-setting-icon"><Activity size={17} /></span><div><h3>Active session</h3><p>{demo ? 'Browser-only demo session.' : 'Current authenticated browser session.'}</p></div><span className="session-tag"><i /> Current</span></div></section></div>
    <div className="profile-preferences"><span className="support-eyebrow">PREFERENCES</span><p>Notification preferences can be managed separately. In this prototype, they are stored locally in this browser.</p><a className="support-secondary-button" href="/settings/notifications">Notification settings <ArrowRight size={15} /></a></div>
  </PageFrame>;
}

const notificationDefaults = {
  highRisk: true,
  suspiciousSpeaker: true,
  incidents: true,
  system: false,
  email: false,
};
const notificationOptions = [
  ['highRisk', 'High-risk voice alerts', 'When an interaction crosses your configured risk threshold.'],
  ['suspiciousSpeaker', 'Suspicious speaker alerts', 'When a voice does not match an enrolled identity.'],
  ['incidents', 'Incident notifications', 'Updates when an incident is created or escalated.'],
  ['system', 'System notifications', 'Maintenance, availability, and model-status notices.'],
  ['email', 'Email notifications', 'Send enabled alerts to the account email, when a backend is configured.'],
];

function NotificationSettingsPage() {
  const [settings, setSettings] = useState(() => {
    try { return { ...notificationDefaults, ...JSON.parse(window.localStorage.getItem('voiceguard-notifications') || '{}') }; }
    catch { return notificationDefaults; }
  });
  const [saved, setSaved] = useState(false);
  const toggle = (key) => { setSettings((current) => ({ ...current, [key]: !current[key] })); setSaved(false); };
  const save = (event) => {
    event.preventDefault();
    try { window.localStorage.setItem('voiceguard-notifications', JSON.stringify(settings)); setSaved(true); }
    catch { setSaved(false); }
  };
  return <PageFrame><PageHeading eyebrow="PREFERENCES" title="Notification settings" copy="Choose which security events appear in this browser's demo preferences." />
    <Notice>Demo behavior: these preferences are saved to this browser only. No email or server notifications are sent.</Notice>
    <form className="notification-settings" onSubmit={save}><div className="notification-list">{notificationOptions.map(([key, title, copy]) => <label className="notification-option" key={key}><span><b>{title}</b><small>{copy}</small></span><input type="checkbox" role="switch" checked={settings[key]} onChange={() => toggle(key)} aria-label={title} /></label>)}</div><div className="notification-save"><span>{saved ? <><Check size={15} /> Preferences saved in this browser</> : 'Changes apply to this browser demo.'}</span><button className="support-primary-button" type="submit">Save settings <Check size={15} /></button></div></form>
  </PageFrame>;
}

function NotFoundPage() {
  return <PageFrame className="not-found-shell"><section className="not-found-panel"><div className="not-found-signal"><div className="not-found-orbit" /><ShieldCheck size={53} /><div className="not-found-wave"><i /><i /><i /><i /><i /><i /><i /><i /><i /></div></div><span className="support-eyebrow">404 · SIGNAL LOST</span><h1>Signal Lost.</h1><p>The page you're looking for could not be found.</p><div className="not-found-actions"><a className="support-primary-button" href="/dashboard">Return to Dashboard <ArrowRight size={15} /></a><a className="support-secondary-button" href="/">Go Home</a></div></section></PageFrame>;
}

export default function SupportPage({ path }) {
  const route = path.replace(/\/$/, '') || '/';
  if (route === '/forgot-password') return <ForgotPasswordPage />;
  if (route === '/reset-password') return <ResetPasswordPage />;
  if (route === '/terms') return <LegalPage />;
  if (route === '/privacy') return <LegalPage privacy />;
  if (route === '/security') return <SecurityPage />;
  if (route === '/about') return <AboutPage />;
  if (route === '/contact') return <ContactPage />;
  if (route === '/help') return <HelpPage />;
  if (route === '/profile') return <ProfilePage />;
  if (route === '/settings' || route === '/settings/notifications') return <NotificationSettingsPage />;
  return <NotFoundPage />;
}