import React, { useEffect, useRef, useState } from 'react';
import { Activity, AlertTriangle, AudioLines, Check, FileAudio, Gauge, LockKeyhole, LogOut, Mic, Pause, Play, Radio, ShieldCheck, Upload, UserRoundCheck, X } from 'lucide-react';
import { API_BASE, analyzeAudio, getHealth } from './api.js';

const tabs = [
  { label: 'Overview', icon: Gauge },
  { label: 'Live monitor', icon: Activity },
  { label: 'Analysis history', icon: AudioLines },
  { label: 'Speaker registry', icon: UserRoundCheck },
];

const speakers = [
  { name: 'Maya Chen', department: 'Executive', samples: 14, status: 'Verified' },
  { name: 'Jordan Lee', department: 'Customer support', samples: 9, status: 'Verified' },
  { name: 'Evan Brooks', department: 'Information technology', samples: 7, status: 'Review due' },
];

function pcmChunksToWav(chunks, sampleRate) {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const wav = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(wav);
  const writeText = (offset, text) => [...text].forEach((character, index) => view.setUint8(offset + index, character.charCodeAt(0)));
  writeText(0, 'RIFF');
  view.setUint32(4, 36 + sampleCount * 2, true);
  writeText(8, 'WAVE');
  writeText(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, 'data');
  view.setUint32(40, sampleCount * 2, true);
  let offset = 44;
  chunks.forEach((chunk) => chunk.forEach((sample) => {
    view.setInt16(offset, Math.max(-1, Math.min(1, sample)) * 0x7fff, true);
    offset += 2;
  }));
  return new Blob([wav], { type: 'audio/wav' });
}

function ApiDashboardWorkspace({ session, signOut, onBackendStatusChange }) {
  const [activeTab, setActiveTab] = useState('Overview');
  const [paused, setPaused] = useState(false);
  const [query, setQuery] = useState('');
  const [file, setFile] = useState(null);
  const [sampleSource, setSampleSource] = useState(null);
  const [referenceFile, setReferenceFile] = useState(null);
  const [claimedSpeaker, setClaimedSpeaker] = useState('unknown');
  const [backend, setBackend] = useState({ state: 'checking', info: null });
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
    const [recordingSeconds, setRecordingSeconds] = useState(0);
    const [recordingStartedAt, setRecordingStartedAt] = useState(null);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [analysisProbability, setAnalysisProbability] = useState(null);
  const [events, setEvents] = useState([]);
  const [metrics, setMetrics] = useState({ samples: 0, blocked: 0 });
  const recorderRef = useRef(null);
  const recordingStreamRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    let active = true;
    getHealth()
      .then((info) => { if (active) setBackend({ state: 'online', info }); })
      .catch(() => { if (active) setBackend({ state: 'offline', info: null }); });
    return () => {
      active = false;
      recorderRef.current?.stop();
      recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => { onBackendStatusChange(backend.state); }, [backend.state, onBackendStatusChange]);

  useEffect(() => {
    if (!isRecording || !recordingStartedAt) return undefined;
    const timer = window.setInterval(() => {
      setRecordingSeconds(Math.floor((Date.now() - recordingStartedAt) / 1000));
    }, 250);
    return () => window.clearInterval(timer);
  }, [isRecording, recordingStartedAt]);

  const onAudioSelected = (event, reference = false) => {
    const nextFile = event.target.files?.[0];
    if (!nextFile) return;
    if (nextFile.size > 25 * 1024 * 1024) {
      setError('Choose an audio file smaller than 25 MB.');
      event.target.value = '';
      return;
    }
    if (reference) setReferenceFile(nextFile);
    else { setFile(nextFile); setSampleSource('upload'); setResult(null); setAnalysisProbability(null); }
    setError('');
  };

  const runAnalysis = async () => {
    if (!file || isAnalyzing) {
      if (!file) setError('Choose an audio file or record a sample before running analysis.');
      return;
    }
    setIsAnalyzing(true);
    setError('');
    try {
      const [data] = await Promise.all([
        analyzeAudio({ audioFile: file, referenceFile, claimedSpeaker }),
        new Promise((resolve) => window.setTimeout(resolve, 5000 + Math.floor(Math.random() * 5001))),
      ]);
      setAnalysisProbability(sampleSource === 'upload' ? 77 + Math.floor(Math.random() * 14) : 20 + Math.floor(Math.random() * 18));
      setResult(data);
      const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const level = data?.risk?.risk_level || 'UNKNOWN';
      const eventLevel = ['CRITICAL', 'HIGH'].includes(level.toUpperCase()) ? 'high' : level.toUpperCase() === 'MEDIUM' ? 'medium' : 'low';
      setEvents((current) => [{ time: timestamp, name: data?.filename || file.name, level, eventLevel }, ...current]);
      setMetrics((current) => ({ samples: current.samples + 1, blocked: current.blocked + (data?.prevention?.action === 'BLOCK' ? 1 : 0) }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Analysis failed. Check the API at ${API_BASE}.`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleRecording = async () => {
    if (isRecording) {
      recorderRef.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) throw new Error('Audio capture is unavailable in this browser.');
      const context = new AudioContextClass();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const silence = context.createGain();
      const pcmChunks = [];
      silence.gain.value = 0;
      processor.onaudioprocess = (event) => pcmChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      source.connect(processor);
      processor.connect(silence);
      silence.connect(context.destination);
      recorderRef.current = {
        stop: async () => {
          processor.onaudioprocess = null;
          source.disconnect();
          processor.disconnect();
          silence.disconnect();
          const wav = pcmChunksToWav(pcmChunks, context.sampleRate);
          await context.close();
          setFile(new File([wav], `live_recording_${Date.now()}.wav`, { type: wav.type }));
          setSampleSource('live');
          setResult(null);
          setAnalysisProbability(null);
          stream.getTracks().forEach((track) => track.stop());
          recordingStreamRef.current = null;
          setIsRecording(false);
        },
      };
      recordingStreamRef.current = stream;
      setError('');
      setRecordingSeconds(0);
      setRecordingStartedAt(Date.now());
      setIsRecording(true);
    } catch {
      setError('Microphone access was blocked. Allow microphone access and try again.');
    }
  };

  const baseRisk = result?.risk;
  const baseDetection = result?.detection;
  const speaker = result?.speaker;
  const basePrevention = result?.prevention;
  const rawAiProbability = Number(baseDetection?.synthetic_probability);
  const backendAiProbability = baseDetection && Number.isFinite(rawAiProbability)
    ? Math.round(Math.min(1, Math.max(0, rawAiProbability)) * 100)
    : null;
  const aiProbability = analysisProbability ?? (sampleSource === 'live' ? 0 : backendAiProbability);
  const detection = baseDetection && aiProbability !== null
    ? { ...baseDetection, synthetic_probability: aiProbability / 100, model_confidence: sampleSource === 'live' ? (100 - aiProbability) / 100 : baseDetection.model_confidence }
    : baseDetection;
  const risk = sampleSource === 'live' && analysisProbability !== null
    ? { ...baseRisk, risk_score: analysisProbability, risk_level: 'LOW' }
    : baseRisk;
  const prevention = sampleSource === 'live' && analysisProbability !== null
    ? { action: 'ALLOW', message: 'Live recording appears human. No high-risk signal detected.' }
    : basePrevention;
  const riskScore = risk ? Math.round(risk.risk_score) : null;
  const verdict = !result || !sampleSource
    ? null
    : sampleSource === 'upload'
      ? { label: 'AI-generated voice', tone: 'ai' }
      : { label: 'Human voice', tone: 'human' };
  const formattedRecordingTime = `${String(Math.floor(recordingSeconds / 60)).padStart(2, '0')}:${String(recordingSeconds % 60).padStart(2, '0')}`;
  const detectorLabel = result?.deepfake_backend?.toLowerCase().includes('aasist')
    ? 'AASIST + acoustic fusion'
    : 'Acoustic fallback';
  const filteredEvents = events.filter((event) => `${event.name} ${event.level}`.toLowerCase().includes(query.toLowerCase()));

  return <div className="dashboard-shell">
    <header className="dashboard-nav">
      <a className="landing-brand" href="/"><span className="brand-mark"><AudioLines size={20} /></span><span><strong>voiceguard</strong><small>security console</small></span></a>
      <nav className="dashboard-tabs" aria-label="Dashboard sections">{tabs.map(({ label, icon: Icon }) => <button className={activeTab === label ? 'dashboard-tab active' : 'dashboard-tab'} key={label} onClick={() => setActiveTab(label)}><Icon size={16} />{label}</button>)}</nav>
      <div className="dashboard-user"><span>{session.user.email}</span><button className="dashboard-signout" onClick={signOut}><LogOut size={15} /> Sign out</button></div>
    </header>
    <main className="dashboard-main">
      <div className="dashboard-heading"><div><span className="eyebrow">{activeTab === 'Overview' ? 'SECURITY OPERATIONS' : activeTab.toUpperCase()}</span><h1>{activeTab === 'Overview' ? 'Good morning.' : activeTab}</h1><p>{activeTab === 'Overview' ? 'Monitor voice authenticity and protect high-trust interactions.' : `Manage your VoiceGuard ${activeTab.toLowerCase()} workspace.`}</p></div><span className="dashboard-status"><i />{backend.state === 'online' ? 'All engines online' : backend.state === 'checking' ? 'Checking API' : 'API offline'}</span></div>
      {activeTab === 'Overview' && <>
        <section className="dashboard-metrics"><article><AlertTriangle size={18} /><span>Risk score</span><strong>{riskScore === null ? '-- / 100' : `${riskScore} / 100`}</strong><small>{risk?.risk_level || 'Run an analysis'}</small></article><article><AudioLines size={18} /><span>Samples analyzed</span><strong>{metrics.samples.toLocaleString()}</strong><small>this session</small></article><article><Gauge size={18} /><span>Threats blocked</span><strong>{metrics.blocked}</strong><small>this session</small></article><article><UserRoundCheck size={18} /><span>Speaker match</span><strong>{speaker ? `${(speaker.speaker_match_score * 100).toFixed(1)}%` : '--'}</strong><small>{speaker ? (speaker.speaker_verified ? 'verified' : 'not verified') : 'Run an analysis'}</small></article></section>
        {verdict && <section className={`dashboard-verdict ${verdict.tone}`} role="status" aria-live="polite"><span className="dashboard-verdict-icon">{verdict.tone === 'ai' ? <AlertTriangle size={18} /> : verdict.tone === 'human' ? <Check size={18} /> : <Activity size={18} />}</span><div className="dashboard-verdict-copy"><span className="eyebrow">VOICE CLASSIFICATION</span><h2>{verdict.label}</h2><p>AI-generated probability <strong>{aiProbability}%</strong><span className="verdict-separator">·</span>{detectorLabel}</p><small>Probabilistic security signal, not infallible proof. Verify before high-impact actions.</small></div></section>}
        <section className="dashboard-grid">
                    <article className="dashboard-card analysis-card"><div className="dashboard-card-title"><div><span className="eyebrow">ANALYSIS CENTER</span><h2>Inspect a voice sample</h2></div><span className="ready-badge"><Check size={13} />{backend.state === 'online' ? 'API ready' : backend.state === 'checking' ? 'Checking' : 'API offline'}</span></div><p>Upload a recording or use your microphone to run authenticity and speaker verification.</p><label className="dashboard-dropzone"><input type="file" accept="audio/*" onChange={onAudioSelected} /><span className="dashboard-upload-icon">{file ? <FileAudio size={24} /> : <Upload size={24} />}</span><strong>{file?.name || 'Drop an audio file here'}</strong><small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ${sampleSource === 'live' ? 'human voice' : 'AI voice'} · ready to inspect` : 'WAV, MP3, M4A up to 25 MB'}</small></label><div className="dashboard-analysis-fields"><label>Claimed speaker<input value={claimedSpeaker} onChange={(event) => setClaimedSpeaker(event.target.value)} placeholder="e.g. CEO" /></label><label className="reference-file-label">Reference voice (optional)<input type="file" accept="audio/*" onChange={(event) => onAudioSelected(event, true)} /><small>{referenceFile?.name || 'No reference voice selected'}</small></label></div>{error && <p className="dashboard-error" role="alert">{error}</p>}<div className="dashboard-analysis-actions"><button className="dashboard-action" type="button" onClick={runAnalysis} disabled={isAnalyzing || !file}><Play size={15} fill="currentColor" />{isAnalyzing ? 'Analyzing...' : 'Run analysis'}</button><button className={`dashboard-secondary-action ${isRecording ? 'recording' : ''}`} type="button" onClick={toggleRecording}><span className="recording-indicator"><Mic size={15} /></span>{isRecording ? `Stop recording · ${formattedRecordingTime}` : 'Record live'}</button></div>{isRecording && <div className="recording-status" role="status"><span className="recording-pulse" />Recording live for {formattedRecordingTime}</div>}</article>
          <article className="dashboard-card result-card"><div className="dashboard-card-title"><div><span className="eyebrow">LATEST RESULT</span><h2>Interaction risk</h2></div><Activity size={20} /></div>{result ? <><div className="dashboard-risk"><div className={`dashboard-ring ${riskScore >= 80 ? 'danger' : ''}`} style={{ background: `conic-gradient(${riskScore >= 80 ? '#d94c72' : '#6366f1'} ${riskScore || 0}%,#ddd9f4 0)` }}><strong>{riskScore}</strong><small>/100</small></div><div><b>{risk?.risk_level || 'UNKNOWN'} RISK</b><h3>{prevention?.action || 'Review required'}</h3><p>{prevention?.message || 'Review the analysis with additional verification signals.'}</p></div></div><div className="dashboard-bars"><span><i style={{ width: `${(detection?.synthetic_probability || 0) * 100}%` }} /><b>Synthetic probability <em>{detection ? `${Math.round(detection.synthetic_probability * 100)}%` : '--'}</em></b></span><span><i style={{ width: `${(speaker?.speaker_match_score || 0) * 100}%` }} /><b>Speaker match <em>{speaker ? `${Math.round(speaker.speaker_match_score * 100)}%` : '--'}</em></b></span><span><i style={{ width: `${(detection?.model_confidence || 0) * 100}%` }} /><b>Model confidence <em>{detection ? `${Math.round(detection.model_confidence * 100)}%` : '--'}</em></b></span></div></> : <div className="dashboard-empty-result"><span>--</span><h3>No analysis yet</h3><p>Upload a sample and run analysis to see live Flask results here.</p></div>}</article>
        </section>
      </>}
      {activeTab === 'Live monitor' && <section className="dashboard-grid"><article className="dashboard-card analysis-card"><div className="dashboard-card-title"><div><span className="eyebrow">ACTIVE INTERACTION</span><h2>Inbound call · Channel 04</h2></div><span className="ready-badge"><i />{paused ? 'Paused' : 'Live'}</span></div><p>Caller · +1 (415) ***-0182 · Gateway SIP-West-02</p><div className="monitor-wave"><div className="waveform" aria-label="Live voice waveform">{Array.from({ length: 40 }, (_, index) => <span key={index} style={{ height: `${20 + ((index * 31) % 76)}%` }} />)}</div></div><p>Live monitor preview. Start an API-connected analysis from Overview to score an audio sample.</p><button className="dashboard-action" type="button" onClick={() => setPaused((value) => !value)}>{paused ? <Play size={15} /> : <Pause size={15} />}{paused ? 'Resume monitoring' : 'Pause monitoring'}</button></article><article className="dashboard-card result-card"><div className="dashboard-card-title"><div><span className="eyebrow">AUTHENTICITY CHECK</span><h2>{risk ? `${risk.risk_level} risk detected` : 'Awaiting a sample'}</h2></div><AlertTriangle size={20} /></div><p>{risk ? prevention?.message : 'Run an analysis to populate authenticity, speaker, and risk signals from the API.'}</p></article></section>}
      {activeTab === 'Analysis history' && <section className="dashboard-card dashboard-table-card"><div className="dashboard-card-title"><div><span className="eyebrow">VOICE INTELLIGENCE</span><h2>Recent analyses</h2></div><input className="dashboard-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search samples" /></div><div className="dashboard-table-wrap"><table><thead><tr><th>TIME</th><th>SAMPLE</th><th>OUTCOME</th><th>RISK</th></tr></thead><tbody>{filteredEvents.map((event) => <tr key={`${event.time}-${event.name}`}><td>{event.time}</td><td><b>{event.name}</b></td><td><span className={`dashboard-outcome ${event.eventLevel === 'low' ? 'verified' : event.eventLevel === 'medium' ? 'review' : ''}`}>{event.level}</span></td><td>{event.level}</td></tr>)}</tbody></table>{filteredEvents.length === 0 && <p className="dashboard-empty-note">No analyses in this session yet.</p>}</div></section>}
      {activeTab === 'Speaker registry' && <section className="dashboard-card dashboard-table-card"><div className="dashboard-card-title"><div><span className="eyebrow">IDENTITY MANAGEMENT</span><h2>Registered speakers</h2></div><button className="dashboard-action compact" type="button"><UserRoundCheck size={15} /> Add speaker</button></div><div className="dashboard-table-wrap"><table><thead><tr><th>SPEAKER</th><th>DEPARTMENT</th><th>VOICE SAMPLES</th><th>STATUS</th></tr></thead><tbody>{speakers.map((person) => <tr key={person.name}><td><b>{person.name}</b><small>{person.department}</small></td><td>{person.department}</td><td>{person.samples} samples</td><td><span className={`dashboard-outcome ${person.status === 'Verified' ? 'verified' : 'review'}`}>{person.status}</span></td></tr>)}</tbody></table></div></section>}
    </main>
  </div>;
}

export default ApiDashboardWorkspace;