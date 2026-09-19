import os
import io
import base64
import hashlib
import streamlit as st
from config import SUPPORTED_MODELS, get_active_model, get_api_key_for_model
from database.memory import MemoryManager
from agents.orchestrator import MasterOrchestrator
from tools.audio_tools import transcribe_audio_to_text
from tools.tts_tools import text_to_speech_bengali

# Page configuration
st.set_page_config(
    page_title="Personal AI Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# High-End Professional CSS with Dark & Light compatibility
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Hind Siliguri', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .main .block-container {
        max-width: 960px;
        padding-top: 1.5rem;
        padding-bottom: 5rem;
    }

    /* Executive Header Styling */
    .hero-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #111827 100%);
        border-radius: 20px;
        padding: 24px 30px;
        color: #ffffff;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.12);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
    }

    .hero-title {
        font-size: 1.65rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.01em;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .hero-subtitle {
        font-size: 0.95rem;
        color: #cbd5e1;
        margin-top: 5px;
    }

    .badge-group {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }

    .status-badge-online {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    .status-badge-model {
        background: rgba(59, 130, 246, 0.2);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.4);
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    /* Voice Console Card */
    .voice-console {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px 20px;
        margin: 14px 0 20px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }

    @media (prefers-color-scheme: dark) {
        .voice-console {
            background: #1e293b;
            border-color: #334155;
        }
    }

    /* Welcome Suggestions Card */
    .welcome-card {
        background: linear-gradient(to right, #f8fafc, #f1f5f9);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        text-align: center;
    }

    @media (prefers-color-scheme: dark) {
        .welcome-card {
            background: linear-gradient(to right, #1e293b, #0f172a);
            border-color: #334155;
        }
    }

    .welcome-title {
        font-size: 1.15rem;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .welcome-subtitle {
        font-size: 0.92rem;
        color: #64748b;
        margin-bottom: 18px;
    }

    /* Chat bubble enhancements */
    .stChatMessage {
        border-radius: 16px;
        padding: 14px 20px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }

    .audio-tag {
        font-size: 0.85rem;
        font-weight: 600;
        color: #059669;
        margin: 8px 0 4px 0;
        display: flex;
        align-items: center;
        gap: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Memory & State Initialization
if "memory" not in st.session_state:
    st.session_state.memory = MemoryManager()

if "session_id" not in st.session_state:
    sessions = st.session_state.memory.list_sessions()
    if sessions:
        st.session_state.session_id = sessions[0]["id"]
    else:
        st.session_state.session_id = st.session_state.memory.create_session("মূল অধিবেশন (Main Session)")

if "processed_audio_hashes" not in st.session_state:
    st.session_state.processed_audio_hashes = set()

if "latest_audio_bytes" not in st.session_state:
    st.session_state.latest_audio_bytes = None

if "pending_voice_command" not in st.session_state:
    st.session_state.pending_voice_command = None

# -------------------------------------------------------------
# Sidebar Configuration & Session History
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ নিয়ন্ত্রণ প্যানেল (Control Panel)")

    provider = st.selectbox("মডেল প্রোভাইডার", list(SUPPORTED_MODELS.keys()), index=0)
    models = SUPPORTED_MODELS[provider]
    selected_model = st.selectbox("সক্রিয় মডেল", models, index=0)
    os.environ["ACTIVE_MODEL"] = selected_model

    api_key_var = "GEMINI_API_KEY" if "Gemini" in provider else ("OPENAI_API_KEY" if "OpenAI" in provider else "ANTHROPIC_API_KEY")
    current_key = os.getenv(api_key_var, "")
    user_key = st.text_input(f"{provider} Key", value=current_key, type="password", help="API Key")
    if user_key and user_key.strip() != current_key:
        os.environ[api_key_var] = user_key.strip()
        st.success("API Key সফলভাবে আপডেট হয়েছে!")

    st.markdown("---")

    st.markdown("### 📝 ব্যক্তিগত পছন্দ ও নির্দেশিকা")
    saved_rules = st.session_state.memory.get_preference("assistant_rules", "")
    new_rules = st.text_area("এজেন্টকে দেওয়া বিশেষ নির্দেশনা:", value=saved_rules, height=120)
    if st.button("নির্দেশিকা সংরক্ষণ করুন", use_container_width=True):
        st.session_state.memory.set_preference("assistant_rules", new_rules)
        st.success("নির্দেশনা সংরক্ষিত হয়েছে!")

    st.markdown("---")

    st.markdown("### 💬 কথোপকথনের ইতিহাস (Sessions)")
    if st.button("➕ নতুন সেশন খুলুন", use_container_width=True):
        new_id = st.session_state.memory.create_session(f"সেশন {len(st.session_state.memory.list_sessions()) + 1}")
        st.session_state.session_id = new_id
        st.session_state.latest_audio_bytes = None
        st.session_state.pending_voice_command = None
        st.rerun()

    sessions = st.session_state.memory.list_sessions()
    session_titles = {s["id"]: f"{s['title']} ({s['created_at'][:10]})" for s in sessions}
    if sessions:
        selected_sess = st.radio(
            "পূর্বের সেশনসমূহ",
            options=list(session_titles.keys()),
            format_func=lambda x: session_titles.get(x, x),
            index=list(session_titles.keys()).index(st.session_state.session_id) if st.session_state.session_id in session_titles else 0
        )
        if selected_sess != st.session_state.session_id:
            st.session_state.session_id = selected_sess
            st.session_state.latest_audio_bytes = None
            st.session_state.pending_voice_command = None
            st.rerun()

# -------------------------------------------------------------
# Executive Header Banner
# -------------------------------------------------------------
active_model_name = get_active_model()
st.markdown(f"""
<div class="hero-container">
    <div>
        <h1 class="hero-title">🧠 Personal Master Assistant</h1>
        <div class="hero-subtitle">স্বায়ত্তশাসিত মাল্টি-এজেন্ট সিস্টেম • নির্ভুল যুক্তি, কোডিং ও বাংলা ভয়েস রিপ্লাই</div>
    </div>
    <div class="badge-group">
        <span class="status-badge-online">● অনলাইন ও প্রস্তুত</span>
        <span class="status-badge-model">⚡ {active_model_name.replace('gemini/', '')}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Message History Display with In-Bubble Audio Playback
# -------------------------------------------------------------
chat_messages = st.session_state.memory.get_messages(st.session_state.session_id)

for msg in chat_messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(msg["content"])
            
            # Show type / quality badge
            meta = msg.get("metadata", {})
            if meta.get("type") == "conversation":
                st.caption("⚡ সরাসরি কথোপকথন")
            elif meta.get("iterations"):
                st.caption(f"✨ মান যাচাইকৃত • সেলফ-কারেকশন: {meta['iterations']} বার")

            # Dedicated in-bubble Bengali audio voice playback
            audio_b64 = meta.get("audio_b64")
            if audio_b64:
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    st.markdown("<div class='audio-tag'>🔊 বাংলা অডিও রিপ্লাই শুনুন:</div>", unsafe_allow_html=True)
                    st.audio(audio_bytes, format="audio/mp3")
                except Exception:
                    pass

            # Download report button
            st.download_button(
                label="📥 উত্তর ডাউনলোড করুন (.md)",
                data=msg["content"],
                file_name=f"report_{msg['id'][:8]}.md",
                mime="text/markdown",
                key=f"dl_{msg['id']}"
            )

# -------------------------------------------------------------
# Welcome Suggestions if chat is fresh
# -------------------------------------------------------------
user_command = None

if not chat_messages:
    st.markdown("""
    <div class="welcome-card">
        <div class="welcome-title">💡 কীভাবে শুরু করবেন?</div>
        <div class="welcome-subtitle">নিচের যেকোনো একটি প্রম্পটে চাপ দিন অথবা আপনার নিজের ভাষায় কথা বলুন বা লিখুন:</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💬 তুমি আমার বাংলা কথা বোঝো?", use_container_width=True):
            user_command = "তুমি কি আমার বাংলা কথা স্পষ্টভাবে বুঝতে পারো?"
        if st.button("🔍 ২০২৬ সালের সেরা ৩টি এআই ট্রেন্ড রিসার্চ করো", use_container_width=True):
            user_command = "২০২৬ সালের সেরা ৩টি এআই ট্রেন্ড নিয়ে তথ্যবহুল রিসার্চ রিপোর্ট দাও"
    with col2:
        if st.button("💻 পাইথনে ফিবোনাচ্চি স্ক্রিপ্ট লেখো ও রান করো", use_container_width=True):
            user_command = "পাইথনে ফিবোনাচ্চি সিরিজের স্ক্রিপ্ট লেখো এবং স্যান্ডবক্সে রান করে দেখাও"
        if st.button("📊 ১ থেকে ৫০ এর মধ্যে জোড় সংখ্যার পরিসংখ্যান ও টেবিল দাও", use_container_width=True):
            user_command = "১ থেকে ৫০ এর মধ্যে জোড় সংখ্যার যোগফল এবং বিশ্লেষণধর্মী পরিসংখ্যান টেবিল দাও"

# -------------------------------------------------------------
# Unified Voice Studio (Prominent Microphone Console)
# -------------------------------------------------------------
with st.container():
    col_v1, col_v2 = st.columns([1, 4])
    with col_v1:
        st.markdown("**🎙️ ভয়েস ইনপুট:**")
    with col_v2:
        audio_val = st.audio_input("মাইক্রোফোনে বাংলায় কথা বলুন", label_visibility="collapsed")
        
        if audio_val is not None:
            raw_audio_bytes = audio_val.read()
            audio_hash = hashlib.md5(raw_audio_bytes).hexdigest()
            if audio_hash not in st.session_state.processed_audio_hashes:
                with st.spinner("🎧 আপনার কণ্ঠস্বর বিশ্লেষণ ও টেক্সটে রূপান্তর করা হচ্ছে..."):
                    try:
                        transcribed_text = transcribe_audio_to_text(
                            raw_audio_bytes,
                            mime_type=audio_val.type or "audio/wav"
                        )
                        st.session_state.processed_audio_hashes.add(audio_hash)
                        if transcribed_text and transcribed_text.strip():
                            st.success(f"🗣️ চিহ্নিত বাক্য: \"{transcribed_text}\"")
                            user_command = transcribed_text
                        else:
                            st.warning("কণ্ঠস্বর শনাক্ত করা যায়নি, অনুগ্রহ করে পুনরায় স্পষ্ট করে বলুন।")
                    except Exception as e:
                        st.error(f"ভয়েস রূপান্তরে ত্রুটি: {str(e)}")

# -------------------------------------------------------------
# Text Chat Input
# -------------------------------------------------------------
text_input = st.chat_input("অথবা এখানে আপনার যেকোনো কাজ বা প্রশ্ন লিখে পাঠান...")
if text_input and text_input.strip():
    user_command = text_input.strip()

# -------------------------------------------------------------
# Command Execution & Multi-Agent Orchestration
# -------------------------------------------------------------
if user_command:
    # 1. Immediately display user query
    with st.chat_message("user", avatar="👤"):
        st.write(user_command)

    # 2. Status & live telemetry box
    status_box = st.status("🧠 মাস্টার এজেন্ট নির্দেশ বিশ্লেষণ করছে...", expanded=True)
    live_log_container = status_box.empty()
    logs_accumulator = []

    def handle_progress(event):
        msg = f"**[{event['type'].upper()}]** {event['message']}"
        logs_accumulator.append(msg)
        live_log_container.markdown("\n\n".join(logs_accumulator))

    orchestrator = MasterOrchestrator(
        memory_manager=st.session_state.memory,
        model=selected_model
    )

    try:
        result = orchestrator.process_command(
            session_id=st.session_state.session_id,
            user_command=user_command,
            on_progress=handle_progress
        )

        status_box.update(label="✅ উত্তর প্রস্তুত ও গুণমান যাচাই সম্পন্ন!", state="complete", expanded=False)

        # 3. Render Assistant Response immediately
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(result["final_report"])

            # In-bubble audio playback for newly generated reply
            if result.get("audio_bytes"):
                st.markdown("<div class='audio-tag'>🔊 বাংলা অডিও রিপ্লাই শুনুন:</div>", unsafe_allow_html=True)
                st.audio(result["audio_bytes"], format="audio/mp3")

            st.download_button(
                label="📥 সম্পূর্ণ উত্তর ডাউনলোড করুন (.md)",
                data=result["final_report"],
                file_name="assistant_response.md",
                mime="text/markdown",
                key=f"dl_latest_{hashlib.md5(user_command.encode()).hexdigest()[:8]}"
            )

            if result.get("sub_agent_results"):
                with st.expander("🔍 সাব-এজেন্টদের কাজের ট্র্যাজেক্টরি ও কোয়ালিটি স্কোর দেখুন"):
                    for sub in result.get("sub_agent_results", []):
                        st.write(f"**টাস্ক:** {sub['task']['task_description']}")
                        st.write(f"**কর্মী:** {sub['task']['agent'].upper()}")
                        st.write(f"**চেষ্টা সংখ্যা:** {sub['attempts']}")
                        st.json(sub.get("eval", {}))
                        st.markdown("---")

    except Exception as e:
        status_box.update(label="⚠️ একটি ত্রুটি হয়েছে", state="error", expanded=True)
        st.error(f"Error: {str(e)}")
