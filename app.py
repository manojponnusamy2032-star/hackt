import os
import tempfile
import io
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np
import streamlit as st
import streamlit.components.v1 as components

from deepfake_detection.detector import detect_voice


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="VoiceGuard | NEXORA",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# SESSION STATE
# ============================================================
defaults = {
    "theme": "Dark",
    "voice_bytes": None,
    "voice_name": "voice_sample.wav",
    "analysis_result": None,
    "reference_bytes": None,
    "reference_name": "reference_voice.wav",
    "speaker_result": None,
    "risk_score": 0.0,
    "risk_level": "NOT ANALYZED",
    "action": "WAITING",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:

    st.markdown("## 🎨 Appearance")

    theme = st.selectbox(
        "Dashboard Theme",
        ["Dark", "Dim", "Light"],
        index=["Dark", "Dim", "Light"].index(
            st.session_state.theme
        ),
    )

    st.session_state.theme = theme

    st.markdown("---")

    st.markdown("### 🛡️ System Status")

    st.success("● AI Detection Engine Ready")
    st.success("● Speaker Verification Ready")
    st.success("● Risk Engine Ready")
    st.success("● Prevention Layer Ready")


# ============================================================
# THEME
# ============================================================
if theme == "Dark":

    BG = "#070B14"
    CARD = "#0D1422"
    CARD2 = "#111B2D"
    TEXT = "#F8FAFC"
    MUTED = "#94A3B8"
    BORDER = "#243247"
    ACCENT = "#38BDF8"

elif theme == "Dim":

    BG = "#171717"
    CARD = "#222222"
    CARD2 = "#2A2A2A"
    TEXT = "#F5F5F5"
    MUTED = "#A3A3A3"
    BORDER = "#3F3F46"
    ACCENT = "#60A5FA"

else:

    BG = "#F5F7FB"
    CARD = "#FFFFFF"
    CARD2 = "#F1F5F9"
    TEXT = "#0F172A"
    MUTED = "#64748B"
    BORDER = "#CBD5E1"
    ACCENT = "#0284C7"


# ============================================================
# CSS
# ============================================================
st.markdown(
    f"""
<style>

html, body, [class*="css"] {{
    font-family: Inter, Arial, sans-serif;
}}

.stApp {{
    background: {BG};
    color: {TEXT};
}}

.block-container {{
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}}

section[data-testid="stSidebar"] {{
    background: {CARD};
    border-right: 1px solid {BORDER};
}}

section[data-testid="stSidebar"] * {{
    color: {TEXT};
}}

.hero {{
    background: linear-gradient(
        135deg,
        {CARD} 0%,
        {CARD2} 100%
    );
    border: 1px solid {BORDER};
    border-radius: 24px;
    padding: 42px;
    margin-bottom: 25px;
    box-shadow: 0 10px 35px rgba(0,0,0,0.15);
}}

.badge {{
    display: inline-block;
    padding: 7px 14px;
    border-radius: 999px;
    background: rgba(56,189,248,0.12);
    color: {ACCENT};
    border: 1px solid rgba(56,189,248,0.3);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1.4px;
}}

.hero-title {{
    font-size: 52px;
    font-weight: 800;
    margin-top: 18px;
    color: {TEXT};
}}

.hero-subtitle {{
    font-size: 22px;
    line-height: 1.5;
    color: {MUTED};
    max-width: 900px;
    margin-top: 8px;
}}

.small-text {{
    color: {ACCENT};
    font-size: 14px;
    font-weight: 600;
    margin-top: 15px;
}}

.section {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 20px;
    padding: 28px;
    margin-top: 22px;
    margin-bottom: 22px;
}}

.section-title {{
    font-size: 25px;
    font-weight: 750;
    color: {TEXT};
    margin-bottom: 5px;
}}

.section-subtitle {{
    color: {MUTED};
    font-size: 14px;
    margin-bottom: 20px;
}}

.metric-card {{
    background: {CARD2};
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 20px;
    text-align: center;
    min-height: 120px;
}}

.metric-label {{
    color: {MUTED};
    font-size: 13px;
    font-weight: 600;
}}

.metric-value {{
    color: {TEXT};
    font-size: 28px;
    font-weight: 800;
    margin-top: 7px;
}}

.pipeline {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 15px;
}}

.pipeline-item {{
    flex: 1;
    min-width: 120px;
    background: {CARD2};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 15px 10px;
    text-align: center;
    color: {TEXT};
    font-size: 13px;
    font-weight: 700;
}}

.arrow {{
    color: {ACCENT};
    font-size: 20px;
}}

.status-box {{
    padding: 18px;
    border-radius: 14px;
    border: 1px solid {BORDER};
    background: {CARD2};
    margin-top: 10px;
}}

.footer {{
    text-align: center;
    color: {MUTED};
    padding: 30px 10px 10px 10px;
    font-size: 13px;
}}

div.stButton > button {{
    border-radius: 12px;
    font-weight: 700;
    min-height: 45px;
}}

</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# VOICEGUARD VISUAL SYSTEM
# ============================================================
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');

:root {{
    --vg-bg: {BG};
    --vg-card: {CARD};
    --vg-card-2: {CARD2};
    --vg-text: {TEXT};
    --vg-muted: {MUTED};
    --vg-line: {BORDER};
    --vg-cyan: #62e4f3;
    --vg-violet: #9987ff;
    --vg-lime: #bdf56e;
    --vg-amber: #f4c86d;
    --vg-red: #ff6f7b;
}}

html, body, [class*="css"] {{ font-family: 'Manrope', sans-serif; }}
.stApp {{
    background-color: var(--vg-bg);
    background-image: radial-gradient(circle at 83% 0%, rgba(98,228,243,.12), transparent 26%), linear-gradient(rgba(98,228,243,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(98,228,243,.035) 1px, transparent 1px);
    background-size: auto, 42px 42px, 42px 42px;
}}
.block-container {{ max-width: 1480px; padding: 2.2rem 3rem 4rem; }}
section[data-testid="stSidebar"] {{ background: rgba(8,14,25,.93); border-right: 1px solid var(--vg-line); }}
section[data-testid="stSidebar"] * {{ color: var(--vg-text) !important; }}
section[data-testid="stSidebar"] hr {{ border-color: var(--vg-line); }}

.hero {{
    position: relative; overflow: hidden; display: flex; justify-content: space-between; gap: 28px;
    min-height: 300px; background: linear-gradient(130deg, rgba(13,20,34,.96), rgba(16,27,49,.84));
    border: 1px solid rgba(98,228,243,.28); border-radius: 10px; padding: 38px 42px; margin-bottom: 22px;
    box-shadow: 0 24px 75px rgba(0,0,0,.22), inset 0 0 60px rgba(98,228,243,.035);
}}
.hero:before {{ content: ''; position: absolute; inset: 0; background: linear-gradient(110deg, transparent 20%, rgba(153,135,255,.07) 50%, transparent 78%); pointer-events: none; }}
.hero-copy {{ position: relative; z-index: 1; max-width: 720px; align-self: center; }}
.badge {{ background: rgba(98,228,243,.08); color: var(--vg-cyan); border-color: rgba(98,228,243,.35); font: 500 10px 'DM Mono', monospace; letter-spacing: .16em; }}
.hero-title {{ font-size: clamp(42px, 6vw, 76px); line-height: .96; letter-spacing: -.065em; margin-top: 20px; }}
.hero-subtitle {{ font-size: clamp(16px, 2vw, 22px); max-width: 650px; line-height: 1.45; }}
.small-text {{ color: var(--vg-cyan); font: 500 11px 'DM Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }}
.hero-core {{ position: relative; width: 260px; height: 260px; flex: 0 0 260px; align-self: center; display: grid; place-items: center; }}
.core-shell, .core-ring, .core-ring:before {{ position: absolute; border-radius: 50%; }}
.core-shell {{ inset: 35px; border: 1px solid rgba(98,228,243,.6); background: radial-gradient(circle at 35% 28%, rgba(255,255,255,.36), rgba(98,228,243,.13) 22%, rgba(10,18,34,.25) 62%, rgba(153,135,255,.18)); box-shadow: 0 0 36px rgba(98,228,243,.26), inset -18px -12px 25px rgba(153,135,255,.25); animation: corePulse 4s ease-in-out infinite; }}
.core-shell:after {{ content: ''; position: absolute; inset: 34%; border-radius: 50%; background: var(--vg-cyan); box-shadow: 0 0 22px 8px rgba(98,228,243,.55); }}
.core-ring {{ border: 1px solid rgba(153,135,255,.58); inset: 17px; transform: rotateX(66deg) rotateZ(18deg); animation: orbit 10s linear infinite; }}
.core-ring:before {{ content: ''; inset: -1px 28%; border-top: 2px solid var(--vg-cyan); border-bottom: 2px solid var(--vg-violet); }}
.core-ring.outer {{ inset: 0; transform: rotateY(68deg) rotateZ(-22deg); animation-duration: 14s; border-color: rgba(98,228,243,.35); }}
.core-label {{ position: absolute; bottom: -8px; color: var(--vg-muted); font: 500 10px 'DM Mono', monospace; letter-spacing: .15em; }}
@keyframes orbit {{ to {{ transform: rotateX(66deg) rotateZ(378deg); }} }}
@keyframes corePulse {{ 50% {{ transform: scale(1.04); box-shadow: 0 0 58px rgba(98,228,243,.4), inset -18px -12px 25px rgba(153,135,255,.28); }} }}

.telemetry {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px; background: var(--vg-line); border: 1px solid var(--vg-line); margin: 0 0 24px; }}
.telemetry-item {{ background: rgba(13,20,34,.92); padding: 15px 16px; }}
.telemetry-label {{ color: var(--vg-muted); font: 500 9px 'DM Mono', monospace; letter-spacing: .12em; text-transform: uppercase; }}
.telemetry-value {{ color: var(--vg-text); font-size: 13px; font-weight: 700; margin-top: 6px; }}
.online-dot {{ color: var(--vg-lime); }}
.section {{ background: rgba(13,20,34,.86); border: 1px solid var(--vg-line); border-radius: 7px; padding: 26px; margin: 20px 0; box-shadow: 0 15px 50px rgba(0,0,0,.12); }}
.section-title {{ font-size: 21px; letter-spacing: -.035em; }}
.section-subtitle {{ color: var(--vg-muted); font-size: 13px; }}
.metric-card {{ background: rgba(17,27,45,.82); border: 1px solid var(--vg-line); border-top: 2px solid var(--vg-cyan); border-radius: 5px; text-align: left; min-height: 112px; transition: transform .2s ease, border-color .2s ease; }}
.metric-card:hover {{ transform: translateY(-3px); border-color: rgba(98,228,243,.65); }}
.metric-label {{ font: 500 10px 'DM Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }}
.metric-value {{ font: 700 28px 'DM Mono', monospace; letter-spacing: -.06em; }}
.pipeline {{ gap: 5px; }}
.pipeline-item {{ background: rgba(17,27,45,.74); border-color: var(--vg-line); border-radius: 4px; font: 600 11px 'DM Mono', monospace; letter-spacing: .04em; text-transform: uppercase; }}
.arrow {{ color: var(--vg-cyan); }}
.risk-layout {{ display: grid; grid-template-columns: 250px 1fr; align-items: center; gap: 28px; }}
.risk-gauge {{ position: relative; width: 210px; height: 210px; border-radius: 50%; display: grid; place-items: center; background: conic-gradient(var(--risk-color) calc(var(--risk-score) * 1%), rgba(255,255,255,.07) 0); box-shadow: 0 0 38px color-mix(in srgb, var(--risk-color) 24%, transparent); }}
.risk-gauge:after {{ content: ''; width: 164px; height: 164px; border-radius: 50%; background: var(--vg-card); position: absolute; }}
.risk-gauge-content {{ position: relative; z-index: 1; text-align: center; }}
.risk-number {{ font: 700 38px 'DM Mono', monospace; letter-spacing: -.08em; }}
.risk-level {{ color: var(--risk-color); font: 500 10px 'DM Mono', monospace; letter-spacing: .14em; }}
.wave-panel {{ border: 1px solid var(--vg-line); background: rgba(7,11,20,.62); padding: 12px; border-radius: 5px; margin-top: 18px; }}
.wave-panel svg {{ display: block; width: 100%; height: 100px; }}
.event-feed {{ border-left: 1px solid rgba(98,228,243,.35); padding-left: 18px; }}
.event {{ position: relative; padding: 0 0 16px; color: var(--vg-text); font-size: 13px; }}
.event:before {{ content: ''; position: absolute; width: 7px; height: 7px; border-radius: 50%; background: var(--vg-cyan); left: -22px; top: 6px; box-shadow: 0 0 11px var(--vg-cyan); }}
.event-time {{ color: var(--vg-muted); font: 500 10px 'DM Mono', monospace; margin-right: 10px; }}
.footer {{ border-top: 1px solid var(--vg-line); margin-top: 42px; font: 500 10px 'DM Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }}
div.stButton > button {{ border-radius: 4px; min-height: 46px; font: 700 11px 'DM Mono', monospace; letter-spacing: .08em; }}
@media (max-width: 850px) {{ .block-container {{ padding: 1.2rem 1rem 3rem; }} .hero {{ padding: 26px; min-height: 0; }} .hero-core {{ width: 180px; height: 180px; flex-basis: 180px; }} .telemetry {{ grid-template-columns: repeat(2, 1fr); }} .risk-layout {{ grid-template-columns: 1fr; }} .risk-gauge {{ margin: 0 auto; }} }}
@media (prefers-reduced-motion: reduce) {{ *, *:before, *:after {{ animation-duration: .01ms !important; transition-duration: .01ms !important; }} }}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def create_temp_audio(audio_bytes, filename):

    suffix = Path(filename).suffix.lower()

    if suffix not in [
        ".wav",
        ".mp3",
        ".m4a",
        ".ogg",
        ".flac",
    ]:
        suffix = ".wav"

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    )

    temp_file.write(audio_bytes)
    temp_file.close()

    return temp_file.name


def safe_percentage(value):

    try:

        value = float(value)

        if value <= 1:
            value *= 100

        return max(
            0.0,
            min(100.0, value)
        )

    except Exception:

        return 0.0


def extract_result_value(
    result,
    keys,
    default=0.0
):

    if not isinstance(result, dict):
        return default

    for key in keys:

        if key in result:

            try:
                return float(result[key])

            except Exception:
                pass

    return default


def build_waveform_svg(audio_bytes, sample_count=180):
    """Render the uploaded/recorded signal itself, never generated telemetry."""
    try:
        waveform, _ = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)
        if waveform.size == 0:
            return ""

        indexes = np.linspace(0, waveform.size - 1, sample_count).astype(int)
        samples = waveform[indexes]
        peak = max(float(np.max(np.abs(samples))), 1e-6)
        points = []
        for index, sample in enumerate(samples):
            x = 2 + (index / max(len(samples) - 1, 1)) * 996
            y = 50 - (float(sample) / peak) * 39
            points.append(f"{x:.1f},{y:.1f}")

        return (
            '<div class="wave-panel">'
            '<div class="telemetry-label">CAPTURED SIGNAL / 16 KHZ</div>'
            '<svg viewBox="0 0 1000 100" preserveAspectRatio="none" '
            'role="img" aria-label="Captured voice waveform">'
            '<line x1="0" y1="50" x2="1000" y2="50" '
            'stroke="rgba(98,228,243,.18)" stroke-width="1"/>'
            f'<polyline points="{" ".join(points)}" fill="none" '
            'stroke="#62e4f3" stroke-width="2" vector-effect="non-scaling-stroke" '
            'filter="drop-shadow(0 0 5px rgba(98,228,243,.8))"/>'
            '</svg></div>'
        )
    except Exception:
        return ""


# ============================================================
# SPEAKER SIMILARITY
# ============================================================
def calculate_speaker_similarity(
    file1,
    file2
):

    try:

        audio1, sr1 = librosa.load(
            file1,
            sr=16000,
            mono=True
        )

        audio2, sr2 = librosa.load(
            file2,
            sr=16000,
            mono=True
        )

        if len(audio1) == 0 or len(audio2) == 0:
            return 0.0

        mfcc1 = librosa.feature.mfcc(
            y=audio1,
            sr=sr1,
            n_mfcc=20
        )

        mfcc2 = librosa.feature.mfcc(
            y=audio2,
            sr=sr2,
            n_mfcc=20
        )

        vector1 = np.mean(
            mfcc1,
            axis=1
        )

        vector2 = np.mean(
            mfcc2,
            axis=1
        )

        denominator = (
            np.linalg.norm(vector1)
            *
            np.linalg.norm(vector2)
        )

        if denominator == 0:
            return 0.0

        similarity = (
            np.dot(
                vector1,
                vector2
            )
            /
            denominator
        )

        similarity = (
            similarity + 1
        ) / 2

        return float(
            max(
                0.0,
                min(
                    1.0,
                    similarity
                )
            )
        )

    except Exception as e:

        st.error(
            f"Speaker verification error: {e}"
        )

        return 0.0


# ============================================================
# RISK ENGINE
# ============================================================
def calculate_risk(
    synthetic_probability,
    speaker_similarity=None
):

    deepfake_score = float(
        synthetic_probability
    )

    # Before speaker verification:
    # use ONLY the deepfake detection result.
    if speaker_similarity is None:

        risk_score = deepfake_score

    else:

        speaker_mismatch = (
            1.0 -
            float(speaker_similarity)
        ) * 100

        # Combined security score
        risk_score = (
            deepfake_score * 0.70
        ) + (
            speaker_mismatch * 0.30
        )

    # Risk classification
    if risk_score >= 70:

        level = "CRITICAL"
        action = "BLOCK / ESCALATE"

    elif risk_score >= 40:

        level = "HIGH"
        action = "SECURITY ALERT"

    elif risk_score >= 20:

        level = "MEDIUM"
        action = "VERIFY / MONITOR"

    else:

        level = "LOW"
        action = "ALLOW"

    return (
        float(risk_score),
        level,
        action
    )


# ============================================================
# HERO
# ============================================================
components.html(
    Path(__file__).with_name("voiceguard_hero.html").read_text(encoding="utf-8"),
    height=420,
    scrolling=False,
)

st.markdown(
    f"""
<div class="telemetry" aria-label="VoiceGuard system telemetry">
    <div class="telemetry-item"><div class="telemetry-label">Audio input</div><div class="telemetry-value"><span class="online-dot">●</span> READY</div></div>
    <div class="telemetry-item"><div class="telemetry-label">AI engine</div><div class="telemetry-value"><span class="online-dot">●</span> AASIST ACTIVE</div></div>
    <div class="telemetry-item"><div class="telemetry-label">Risk engine</div><div class="telemetry-value"><span class="online-dot">●</span> LOCAL</div></div>
    <div class="telemetry-item"><div class="telemetry-label">Privacy</div><div class="telemetry-value"><span class="online-dot">●</span> ON DEVICE</div></div>
    <div class="telemetry-item"><div class="telemetry-label">Session</div><div class="telemetry-value"><span class="online-dot">●</span> {"ANALYZED" if st.session_state.analysis_result is not None else "STANDBY"}</div></div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SECURITY PIPELINE
# ============================================================
st.markdown(
    """
<div class="section">

<div class="section-title">
🔐 Security Pipeline
</div>

<div class="section-subtitle">
Multi-layer protection against AI-generated voice impersonation.
</div>

<div class="pipeline">

<div class="pipeline-item">
🎙️<br>
Live Voice
</div>

<div class="arrow">→</div>

<div class="pipeline-item">
🤖<br>
AI Detection
</div>

<div class="arrow">→</div>

<div class="pipeline-item">
👤<br>
Speaker Verification
</div>

<div class="arrow">→</div>

<div class="pipeline-item">
📊<br>
Risk Score
</div>

<div class="arrow">→</div>

<div class="pipeline-item">
🛡️<br>
Prevention
</div>

<div class="arrow">→</div>

<div class="pipeline-item">
🚨<br>
Alert
</div>

</div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# VOICE ANALYSIS
# ============================================================
st.markdown(
    """
<div class="section">

<div class="section-title">
🎙️ Voice Analysis
</div>

<div class="section-subtitle">
Provide a voice sample to determine whether the speech
is authentic or potentially AI-generated.
</div>

</div>
""",
    unsafe_allow_html=True,
)


voice_col1, voice_col2 = st.columns(2)


# ============================================================
# RECORD VOICE
# ============================================================
with voice_col1:

    st.markdown("### 🎤 Record Voice")

    recorded_audio = st.audio_input(
        "Record a short voice sample",
        key="main_voice_recorder"
    )

    if recorded_audio is not None:

        st.session_state.voice_bytes = (
            recorded_audio.getvalue()
        )

        st.session_state.voice_name = (
            "recorded_voice.wav"
        )

        # Reset old verification when new voice is selected
        st.session_state.analysis_result = None
        st.session_state.speaker_result = None

        st.audio(
            st.session_state.voice_bytes,
            format="audio/wav"
        )


# ============================================================
# UPLOAD VOICE
# ============================================================
with voice_col2:

    st.markdown("### 📁 Upload Audio")

    uploaded_audio = st.file_uploader(
        "Upload a voice sample",
        type=[
            "wav",
            "mp3",
            "m4a",
            "ogg",
            "flac"
        ],
        key="main_voice_uploader"
    )

    if uploaded_audio is not None:

        st.session_state.voice_bytes = (
            uploaded_audio.getvalue()
        )

        st.session_state.voice_name = (
            uploaded_audio.name
        )

        # Reset old verification when new voice is selected
        st.session_state.analysis_result = None
        st.session_state.speaker_result = None

        st.audio(
            st.session_state.voice_bytes
        )


# ============================================================
# ANALYZE VOICE
# ============================================================
if st.session_state.voice_bytes is not None:

    st.markdown("")

    analyze_button = st.button(
        "🔍 ANALYZE VOICE",
        use_container_width=True,
        type="primary",
        key="analyze_voice_button"
    )

    if analyze_button:

        temp_path = None

        try:

            with st.spinner(
                "Running AI voice authenticity analysis..."
            ):

                temp_path = create_temp_audio(
                    st.session_state.voice_bytes,
                    st.session_state.voice_name
                )

                result = detect_voice(
                    temp_path
                )

                st.session_state.analysis_result = result

                synthetic_probability = safe_percentage(
                    extract_result_value(
                        result,
                        [
                            "synthetic_probability",
                            "synthetic_prob",
                            "fake_probability",
                            "deepfake_probability"
                        ]
                    )
                )

                authentic_probability = safe_percentage(
                    extract_result_value(
                        result,
                        [
                            "authentic_probability",
                            "authentic_prob",
                            "real_probability"
                        ]
                    )
                )

                model_confidence = safe_percentage(
                    extract_result_value(
                        result,
                        [
                            "model_confidence",
                            "confidence"
                        ],
                        synthetic_probability / 100
                    )
                )

                if authentic_probability == 0:

                    authentic_probability = (
                        100 -
                        synthetic_probability
                    )

                if model_confidence == 0:

                    model_confidence = (
                        max(
                            synthetic_probability,
                            authentic_probability
                        )
                    )

                # IMPORTANT:
                # Speaker verification has not happened yet,
                # so only AI detection is used here.
                (
                    risk_score,
                    risk_level,
                    action
                ) = calculate_risk(
                    synthetic_probability
                )

                st.session_state.risk_score = risk_score
                st.session_state.risk_level = risk_level
                st.session_state.action = action

            st.success(
                "Voice analysis completed successfully."
            )

        except Exception as e:

            st.error(
                f"AI Detection Error: {e}"
            )

        finally:

            if (
                temp_path is not None
                and os.path.exists(temp_path)
            ):

                try:
                    os.remove(temp_path)

                except Exception:
                    pass


# ============================================================
# AI DETECTION RESULT
# ============================================================
if st.session_state.analysis_result is not None:

    result = st.session_state.analysis_result

    synthetic_probability = safe_percentage(
        extract_result_value(
            result,
            [
                "synthetic_probability",
                "synthetic_prob",
                "fake_probability",
                "deepfake_probability"
            ]
        )
    )

    authentic_probability = safe_percentage(
        extract_result_value(
            result,
            [
                "authentic_probability",
                "authentic_prob",
                "real_probability"
            ]
        )
    )

    model_confidence = safe_percentage(
        extract_result_value(
            result,
            [
                "model_confidence",
                "confidence"
            ],
            synthetic_probability / 100
        )
    )

    if authentic_probability == 0:

        authentic_probability = (
            100 -
            synthetic_probability
        )

    if model_confidence == 0:

        model_confidence = (
            max(
                synthetic_probability,
                authentic_probability
            )
        )

    st.markdown(
        """
<div class="section">

<div class="section-title">
🤖 AI Detection Result
</div>

<div class="section-subtitle">
Deepfake detection engine output.
</div>

</div>
""",
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown(
            f"""
<div class="metric-card">
<div class="metric-label">
Synthetic Probability
</div>
<div class="metric-value">
{synthetic_probability:.2f}%
</div>
</div>
""",
            unsafe_allow_html=True
        )

    with c2:

        st.markdown(
            f"""
<div class="metric-card">
<div class="metric-label">
Authentic Probability
</div>
<div class="metric-value">
{authentic_probability:.2f}%
</div>
</div>
""",
            unsafe_allow_html=True
        )

    with c3:

        st.markdown(
            f"""
<div class="metric-card">
<div class="metric-label">
Model Confidence
</div>
<div class="metric-value">
{model_confidence:.2f}%
</div>
</div>
""",
            unsafe_allow_html=True
        )

    if synthetic_probability >= 70:

        st.error(
            "🚨 HIGH PROBABILITY OF AI-GENERATED / SYNTHETIC VOICE"
        )

    elif synthetic_probability >= 40:

        st.warning(
            "⚠️ Suspicious voice characteristics detected."
        )

    else:

        st.success(
            "✅ Voice appears predominantly authentic."
        )

    waveform_markup = build_waveform_svg(st.session_state.voice_bytes)
    if waveform_markup:
        st.markdown(waveform_markup, unsafe_allow_html=True)


# ============================================================
# SPEAKER VERIFICATION
# ============================================================
if st.session_state.analysis_result is not None:

    st.markdown(
        """
<div class="section">

<div class="section-title">
👤 Speaker Verification
</div>

<div class="section-subtitle">
Verify whether the analyzed voice matches a trusted reference speaker.
</div>

</div>
""",
        unsafe_allow_html=True
    )

    st.markdown(
        "### 📁 Upload Trusted Reference Voice"
    )

    reference_upload = st.file_uploader(
        "Select the trusted reference voice",
        type=[
            "wav",
            "mp3",
            "m4a",
            "ogg",
            "flac"
        ],
        key="reference_uploader",
        help="Upload a clear recording of the genuine speaker."
    )

    if reference_upload is not None:

        st.session_state.reference_bytes = (
            reference_upload.getvalue()
        )

        st.session_state.reference_name = (
            reference_upload.name
        )

        st.success(
            f"Reference voice loaded: {reference_upload.name}"
        )

        st.audio(
            st.session_state.reference_bytes
        )

        st.markdown("")

        verify_button = st.button(
            "🔐 VERIFY SPEAKER",
            use_container_width=True,
            type="primary",
            key="verify_speaker_button"
        )

        if verify_button:

            analysis_temp = None
            reference_temp = None

            try:

                with st.spinner(
                    "Comparing speaker characteristics..."
                ):

                    analysis_temp = create_temp_audio(
                        st.session_state.voice_bytes,
                        st.session_state.voice_name
                    )

                    reference_temp = create_temp_audio(
                        st.session_state.reference_bytes,
                        st.session_state.reference_name
                    )

                    similarity = calculate_speaker_similarity(
                        analysis_temp,
                        reference_temp
                    )

                    st.session_state.speaker_result = (
                        similarity
                    )

                    synthetic_probability = safe_percentage(
                        extract_result_value(
                            st.session_state.analysis_result,
                            [
                                "synthetic_probability",
                                "synthetic_prob",
                                "fake_probability",
                                "deepfake_probability"
                            ]
                        )
                    )

                    (
                        risk_score,
                        risk_level,
                        action
                    ) = calculate_risk(
                        synthetic_probability,
                        similarity
                    )

                    st.session_state.risk_score = (
                        risk_score
                    )

                    st.session_state.risk_level = (
                        risk_level
                    )

                    st.session_state.action = (
                        action
                    )

                st.success(
                    "✅ Speaker verification completed successfully."
                )

            except Exception as e:

                st.error(
                    f"Speaker verification failed: {e}"
                )

            finally:

                for path in [
                    analysis_temp,
                    reference_temp
                ]:

                    if (
                        path is not None
                        and os.path.exists(path)
                    ):

                        try:
                            os.remove(path)

                        except Exception:
                            pass

    else:

        st.info(
            "👆 Upload a trusted reference voice to enable Speaker Verification."
        )


# ============================================================
# SPEAKER RESULT
# ============================================================
if st.session_state.speaker_result is not None:

    similarity_percentage = (
        st.session_state.speaker_result *
        100
    )

    st.markdown(
        f"""
<div class="status-box">

<b>👤 Speaker Verification Completed</b><br><br>

<b>Speaker Similarity:</b>
{similarity_percentage:.2f}%

</div>
""",
        unsafe_allow_html=True
    )

    if similarity_percentage >= 70:

        st.success(
            "✅ Speaker characteristics appear consistent with the reference voice."
        )

    else:

        st.error(
            "🚨 Speaker mismatch detected."
        )


# ============================================================
# FINAL RISK ASSESSMENT
# ============================================================
if st.session_state.analysis_result is not None:

    st.markdown(
        """
<div class="section">

<div class="section-title">
📊 Final Risk Assessment
</div>

<div class="section-subtitle">
Combined AI detection and speaker verification assessment.
</div>

</div>
""",
        unsafe_allow_html=True
    )

    risk_score = st.session_state.risk_score
    risk_level = st.session_state.risk_level
    action = st.session_state.action

    risk_color = {
        "LOW": "#bdf56e",
        "MEDIUM": "#f4c86d",
        "HIGH": "#ff995f",
        "CRITICAL": "#ff6f7b",
    }.get(risk_level, "#62e4f3")

    st.markdown(
        f"""
<div class="risk-layout">
    <div class="risk-gauge" style="--risk-score:{max(0, min(100, risk_score))}; --risk-color:{risk_color}">
        <div class="risk-gauge-content"><div class="risk-number">{risk_score:.0f}</div><div class="risk-level">{risk_level}</div></div>
    </div>
    <div>
        <div class="section-title">CURRENT RISK <span style="color:{risk_color}">/ {risk_level}</span></div>
        <div class="section-subtitle">Decision surface assembled from the current synthetic probability and speaker signal.</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    r1, r2, r3 = st.columns(3)

    with r1:

        st.markdown(
            f"""
<div class="metric-card">
<div class="metric-label">
Overall Risk Score
</div>
<div class="metric-value">
{risk_score:.2f}%
</div>
</div>
""",
            unsafe_allow_html=True
        )

    with r2:

        st.markdown(
            f"""
<div class="metric-card">
<div class="metric-label">
Risk Level
</div>
<div class="metric-value">
{risk_level}
</div>
</div>
""",
            unsafe_allow_html=True
        )

    with r3:

        st.markdown(
            f"""
<div class="metric-card">
<div class="metric-label">
Recommended Action
</div>
<div class="metric-value">
{action}
</div>
</div>
""",
            unsafe_allow_html=True
        )


# ============================================================
# SECURITY EVENTS
# ============================================================
if st.session_state.analysis_result is not None:
    event_time = datetime.now().strftime("%H:%M:%S")
    events = [
        "Voice sample accepted for analysis",
        "AASIST authenticity inference completed",
    ]
    if st.session_state.speaker_result is not None:
        events.append("Reference speaker comparison completed")
    events.append(f"Risk engine classified signal as {st.session_state.risk_level}")
    event_markup = "".join(
        f'<div class="event"><span class="event-time">{event_time}</span>{event}</div>'
        for event in events
    )
    st.markdown(
        f"""
<div class="section">
    <div class="section-title">SECURITY EVENTS</div>
    <div class="section-subtitle">State changes from this analysis session.</div>
    <div class="event-feed">{event_markup}</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# PREVENTION & RESPONSE
# ============================================================
if st.session_state.analysis_result is not None:

    st.markdown(
        """
<div class="section">

<div class="section-title">
🛡️ Prevention & Response
</div>

<div class="section-subtitle">
Security action generated from the final risk assessment.
</div>

</div>
""",
        unsafe_allow_html=True
    )

    level = st.session_state.risk_level

    if level == "CRITICAL":

        st.error(
            "🚫 THREAT BLOCKED — High-risk voice impersonation detected. "
            "Interaction should be blocked and escalated."
        )

    elif level == "HIGH":

        st.error(
            "🚨 SECURITY ALERT — Suspicious voice detected. "
            "Additional verification is recommended."
        )

    elif level == "MEDIUM":

        st.warning(
            "⚠️ VERIFICATION REQUIRED — Voice characteristics "
            "show suspicious behavior."
        )

    else:

        st.success(
            "✅ LOW RISK — Interaction can proceed under normal monitoring."
        )


# ============================================================
# SYSTEM RESPONSE
# ============================================================
st.markdown(
    """
<div class="section">

<div class="section-title">
⚡ System Response
</div>

<div class="section-subtitle">
VoiceGuard's automated response workflow.
</div>

</div>
""",
    unsafe_allow_html=True
)

response1, response2, response3 = st.columns(3)

with response1:

    st.markdown(
        """
<div class="metric-card">
<div class="metric-label">
Detection
</div>
<div class="metric-value">
🤖 AI Scan
</div>
</div>
""",
        unsafe_allow_html=True
    )

with response2:

    st.markdown(
        """
<div class="metric-card">
<div class="metric-label">
Verification
</div>
<div class="metric-value">
👤 Identity
</div>
</div>
""",
        unsafe_allow_html=True
    )

with response3:

    st.markdown(
        """
<div class="metric-card">
<div class="metric-label">
Protection
</div>
<div class="metric-value">
🛡️ Prevention
</div>
</div>
""",
        unsafe_allow_html=True
    )


# ============================================================
# FOOTER
# ============================================================
st.markdown(
    """
<div class="footer">
<b>VoiceGuard • NEXORA</b><br>
AI-powered voice impersonation defence
</div>
""",
    unsafe_allow_html=True
)