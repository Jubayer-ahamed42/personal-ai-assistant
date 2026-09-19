import os
import hashlib
import streamlit as st
from config import SUPPORTED_MODELS, get_active_model
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

# Custom High-End Professional CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

    * {
        font-family: 'Hind Siliguri', 'Inter', -apple-system, sans-serif;
    }

    .main .block-container {
        max-width: 950px;
        padding-top: 1.5rem;
        padding-bottom: 5rem;
    }

    /* Header banner styling */
    .hero-container {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 18px;
        padding: 22px 28px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
    }

    .hero-title {
        font-size: 1.6rem;
        font-weight: 700;
        margin: 0;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .hero-subtitle {
        font-size: 0.95rem;
        color: #94a3b8;
        margin-top: 4px;
    }

    .status-badge {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    /* Card styling */
    .stChatMessage {
        border-radius: 14px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }

    /* Voice panel clean box */
    .voice-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 18px;
    }

    /* Quick suggestion buttons */
    .suggestion-btn {
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        padding: 8px 14px;
        font-size: 0.9rem;
        color: #334155;
        cursor: pointer;
        display: inline-block;
        margin: 4px;
        transition: all 0.2s;
    }

    /* Audio player wrapper */
    .audio-wrapper {
        margin: 10px 0 14px 0;
        padding: 8px 14px;
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 10px;
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
        st.session_state.session_id = st.session_state.memory.create_session("Main Session")

if "processed_audio_hashes" not in st.session_state:
    st.session_state.processed_audio_hashes = set()

if "latest_audio_bytes" not in st.session_state:
    st.session_state.latest_audio_bytes = None

# -------------------------------------------------------------
# Sidebar Configuration
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ নিয়ন্ত্রণ প্যানেল (Settings)")

    provider = st.selectbox("মডেল প্রোভাইডার", list(SUPPORTED_MODELS.keys()), index=0)
    models = SUPPORTED_MODELS[provider]
    selected_model = st.selectbox("সক্রিয় মডেল", models, index=0)
    os.environ["ACTIVE_MODEL"] = selected_model

    api_key_var = "GEMINI_API_KEY" if "Gemini" in provider else ("OPENAI_API_KEY" if "OpenAI" in provider else "ANTHROPIC_API_KEY")
    current_key = os.getenv(api_key_var, "")
    user_key = st.text_input(f"{provider} Key", value=current_key, type="password", help="API Key")
    if user_key and user_key.strip() != current_key:
        os.environ[api_key_var] = user_key.strip()
        st.success("Key আপডেট হয়েছে!")

    st.markdown("---")

    st.markdown("### 📝 আপনার ব্যক্তিগত নির্দেশনা")
    saved_rules = st.session_state.memory.get_preference("assistant_rules", "")
    new_rules = st.text_area("এজেন্টকে যেভাবে কথা বলতে বলবেন:", value=saved_rules, height=130)
    if st.button("নিয়মাবলী সেভ করুন", use_container_width=True):
        st.session_state.memory.set_preference("assistant_rules", new_rules)
        st.success("নিয়ম সেভ হয়েছে!")

    st.markdown("---")

    st.markdown("### 💬 কথোপকথনের ইতিহাস")
    if st.button("➕ নতুন সেশন শুরু করুন", use_container_width=True):
        new_id = st.session_state.memory.create_session(f"সেশন {len(st.session_state.memory.list_sessions()) + 1}")
        st.session_state.session_id = new_id
        st.session_state.latest_audio_bytes = None
        st.rerun()

    sessions = st.session_state.memory.list_sessions()
    session_titles = {s["id"]: f"{s['title']} ({s['created_at'][:10]})" for s in sessions}
    if sessions:
        selected_sess = st.radio(
            "পূর্বের সেশনগুলো",
            options=list(session_titles.keys()),
            format_func=lambda x: session_titles.get(x, x),
            index=list(session_titles.keys()).index(st.session_state.session_id) if st.session_state.session_id in session_titles else 0
        )
        if selected_sess != st.session_state.session_id:
            st.session_state.session_id = selected_sess
            st.session_state.latest_audio_bytes = None
            st.rerun()

# -------------------------------------------------------------
# Elegant Header Banner
# -------------------------------------------------------------
st.markdown("""
<div class="hero-container">
    <div>
        <h1 class="hero-title">🧠 Personal Master Assistant</h1>
        <div class="hero-subtitle">সার্বক্ষণিক পার্সোনাল সহকারী • হাইব্রিড সেলফ-কারেকশন ইঞ্জিন</div>
    </div>
    <div>
        <span class="status-badge">● ২৪/৭ অনলাইন ও সক্রিয়</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Display Chat Messages
chat_messages = st.session_state.memory.get_messages(st.session_state.session_id)
for msg in chat_messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(msg["content"])
            if msg.get("metadata", {}).get("type") == "conversation":
                st.caption("⚡ সরাসরি কথোপকথন")
            elif msg.get("metadata", {}).get("iterations"):
                st.caption(f"✨ কোয়ালিটি যাচাইকৃত • সেলফ-কারেকশন: {msg['metadata']['iterations']} বার")

            st.download_button(
                label="📥 রিপোর্ট ডাউনলোড (.md)",
                data=msg["content"],
                file_name=f"report_{msg['id'][:8]}.md",
                mime="text/markdown",
                key=f"dl_{msg['id']}"
            )

# Show audio player for latest response if available
if st.session_state.latest_audio_bytes:
    st.markdown("🔊 **অডিও ভয়েস উত্তর শুনুন:**")
    st.audio(st.session_state.latest_audio_bytes, format="audio/mp3")

# -------------------------------------------------------------
# Input Controls (Unified Voice + Text)
# -------------------------------------------------------------
user_command = None

# Quick suggestion chips if chat is empty
if not chat_messages:
    st.markdown("**💡 কীভাবে শুরু করবেন? নিচের যেকোনো একটিতে ট্যাপ করতে পারেন:**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💬 তুমি আমার কথা বুঝতে পারো?", use_container_width=True):
            user_command = "তুমি আমার কথা বুঝতে পারো?"
        if st.button("🔍 ২০২৬ সালের সেরা ৩টি এআই ট্রেন্ড রিসার্চ করো", use_container_width=True):
            user_command = "২০২৬ সালের সেরা ৩টি এআই ট্রেন্ড নিয়ে রিসার্চ রিপোর্ট দাও"
    with col2:
        if st.button("💻 পাইথনে ফিবোনাচ্চি সিরিজের স্ক্রিপ্ট লেখো ও টেস্ট করো", use_container_width=True):
            user_command = "পাইথনে ফিবোনাচ্চি সিরিজের স্ক্রিপ্ট লেখো ও রান করে টেস্ট করো"
        if st.button("📊 ১ থেকে ৫০ এর মধ্যে জোড় সংখ্যার যোগফল ও টেবিল দাও", use_container_width=True):
            user_command = "১ থেকে ৫০ এর মধ্যে জোড় সংখ্যার যোগফল এবং বিশ্লেষণ টেবিল দাও"

# Voice input tab/panel
with st.expander("🎙️ মাইক্রোফোনে কথা বলুন (ভয়েস কমান্ড)", expanded=False):
    st.write("নিচের মাইক্রোফোনে ট্যাপ করে বাংলায় কথা বলুন:")
    audio_val = st.audio_input("ভয়েস রেকর্ডার:")
    if audio_val is not None:
        audio_bytes = audio_val.read()
        audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if audio_hash not in st.session_state.processed_audio_hashes:
            with st.spinner("🎧 আপনার কণ্ঠস্বর বিশ্লেষণ ও টেক্সটে রূপান্তর করা হচ্ছে..."):
                try:
                    transcribed_text = transcribe_audio_to_text(audio_bytes, mime_type=audio_val.type or "audio/wav")
                    st.session_state.processed_audio_hashes.add(audio_hash)
                    if transcribed_text:
                        st.success(f"🗣️ চিহ্নিত বাক্য: \"{transcribed_text}\"")
                        user_command = transcribed_text
                except Exception as e:
                    st.error(f"ভয়েস রূপান্তরে সমস্যা: {str(e)}")

# Text Chat input
text_input = st.chat_input("অথবা এখানে আপনার যেকোনো কাজ বা প্রশ্ন লিখে পাঠান...")
if text_input:
    user_command = text_input

# -------------------------------------------------------------
# Execution & Multi-Agent Workflow
# -------------------------------------------------------------
if user_command:
    with st.chat_message("user", avatar="👤"):
        st.write(user_command)

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

        status_box.update(label="✅ উত্তর প্রস্তুত ও যাচাই সম্পন্ন!", state="complete", expanded=False)

        # Store voice audio for playback
        st.session_state.latest_audio_bytes = result.get("audio_bytes")

        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(result["final_report"])

            # Render Audio player immediately
            if result.get("audio_bytes"):
                st.markdown("🔊 **অডিও ভয়েস রিপ্লাই:**")
                st.audio(result["audio_bytes"], format="audio/mp3")

            st.download_button(
                label="📥 সম্পূর্ণ রিপোর্ট ডাউনলোড করুন",
                data=result["final_report"],
                file_name="final_report.md",
                mime="text/markdown",
                key="dl_new_report"
            )

            if result.get("sub_agent_results"):
                with st.expander("🔍 সাব-এজেন্টদের কাজের ট্র্যাজেক্টরি ও কোয়ালিটি স্কোর দেখুন"):
                    for sub in result.get("sub_agent_results", []):
                        st.write(f"**টাস্ক:** {sub['task']['task_description']}")
                        st.write(f"**কর্মী:** {sub['task']['agent'].upper()}")
                        st.write(f"**চেষ্টা সংখ্যা:** {sub['attempts']}")
                        st.json(sub.get("eval", {}))
                        st.markdown("---")

        st.rerun()

    except Exception as e:
        status_box.update(label="⚠️ একটি ত্রুটি হয়েছে", state="error", expanded=True)
        st.error(f"Error: {str(e)}")
