import os
import hashlib
import streamlit as st
from config import SUPPORTED_MODELS, get_active_model
from database.memory import MemoryManager
from agents.orchestrator import MasterOrchestrator
from tools.audio_tools import transcribe_audio_to_text

# Configure Streamlit page with mobile-friendly viewport
st.set_page_config(
    page_title="Personal AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Mobile App Polish & PWA Feel
st.markdown("""
<style>
    /* Mobile-first clean aesthetic */
    .stApp {
        max-width: 1000px;
        margin: 0 auto;
    }
    .voice-box {
        background-color: #f0f4f9;
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 12px;
        border: 1px solid #d3e3fd;
    }
    .stStatusWidget {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize memory manager
if "memory" not in st.session_state:
    st.session_state.memory = MemoryManager()

# Session state initialization
if "session_id" not in st.session_state:
    sessions = st.session_state.memory.list_sessions()
    if sessions:
        st.session_state.session_id = sessions[0]["id"]
    else:
        st.session_state.session_id = st.session_state.memory.create_session("New Mobile Session")

if "processed_audio_hashes" not in st.session_state:
    st.session_state.processed_audio_hashes = set()

# -------------------------------------------------------------
# Sidebar: Settings, Model Config & Personal Guidelines
# -------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Agent Settings")
    
    # Model Provider Selection
    provider = st.selectbox("LLM Provider", list(SUPPORTED_MODELS.keys()), index=0)
    models = SUPPORTED_MODELS[provider]
    selected_model = st.selectbox("Active Model", models, index=0)
    os.environ["ACTIVE_MODEL"] = selected_model

    # Dynamic API Key Config
    api_key_env_var = "GEMINI_API_KEY" if "Gemini" in provider else ("OPENAI_API_KEY" if "OpenAI" in provider else "ANTHROPIC_API_KEY")
    current_key = os.getenv(api_key_env_var, "")
    user_key = st.text_input(f"{provider} API Key", value=current_key, type="password", help="Enter your key here.")
    if user_key and user_key != current_key:
        os.environ[api_key_env_var] = user_key.strip()
        st.success(f"{api_key_env_var} updated!")

    st.markdown("---")
    
    # Personal Preferences & Behavioral Guidelines (Procedural Memory)
    st.subheader("📝 Personal Assistant Rules")
    saved_rules = st.session_state.memory.get_preference("assistant_rules", "")
    new_rules = st.text_area("Custom instructions & native language tone:", value=saved_rules, height=120)
    if st.button("Save Rules", use_container_width=True):
        st.session_state.memory.set_preference("assistant_rules", new_rules)
        st.success("Rules saved to SQLite memory!")

    st.markdown("---")

    # Conversation Sessions Management
    st.subheader("💬 Chat Sessions")
    if st.button("➕ New Session", use_container_width=True):
        new_id = st.session_state.memory.create_session(f"Session {len(st.session_state.memory.list_sessions()) + 1}")
        st.session_state.session_id = new_id
        st.rerun()

    sessions = st.session_state.memory.list_sessions()
    session_titles = {s["id"]: f"{s['title']} ({s['created_at'][:10]})" for s in sessions}
    if sessions:
        selected_sess = st.radio(
            "History",
            options=list(session_titles.keys()),
            format_func=lambda x: session_titles.get(x, x),
            index=list(session_titles.keys()).index(st.session_state.session_id) if st.session_state.session_id in session_titles else 0
        )
        if selected_sess != st.session_state.session_id:
            st.session_state.session_id = selected_sess
            st.rerun()

# -------------------------------------------------------------
# Main Chat & Voice Dashboard Interface
# -------------------------------------------------------------
st.title("🤖 Personal Master Assistant")
st.caption("📱 Mobile Ready • 🎙️ Voice & Text • 🧠 Multi-Agent Factory")

# Display Conversation Messages
chat_messages = st.session_state.memory.get_messages(st.session_state.session_id)
for msg in chat_messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(msg["content"])
            if msg.get("metadata", {}).get("iterations"):
                st.caption(f"✨ Quality Verified | Self-Correction Iterations: {msg['metadata']['iterations']}")
            # One-click copy/download report
            st.download_button(
                label="📥 রিপোর্ট ডাউনলোড করুন (Markdown)",
                data=msg["content"],
                file_name=f"report_{st.session_state.session_id[:8]}.md",
                mime="text/markdown",
                key=f"dl_{msg['id']}"
            )

# -------------------------------------------------------------
# Input Controls: Voice Microphone + Text Chat
# -------------------------------------------------------------
user_command = None

# 🎙️ Native Microphone Feature
with st.expander("🎙️ ভয়েস কমান্ড দিন (কথা বলুন)", expanded=False):
    audio_val = st.audio_input("মাইক্রোফোনে ক্লিক করে বাংলায় কথা বলুন:")
    if audio_val is not None:
        audio_bytes = audio_val.read()
        audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if audio_hash not in st.session_state.processed_audio_hashes:
            with st.spinner("🎧 আপনার ভয়েস প্রসেস ও রূপান্তর করা হচ্ছে..."):
                try:
                    transcribed_text = transcribe_audio_to_text(audio_bytes, mime_type=audio_val.type or "audio/wav")
                    st.session_state.processed_audio_hashes.add(audio_hash)
                    if transcribed_text:
                        st.info(f"🗣️ আপনি বলেছেন: *\"{transcribed_text}\"*")
                        user_command = transcribed_text
                except Exception as e:
                    st.error(f"ভয়েস চিহ্নিতকরণে ত্রুটি: {str(e)}")

# ✍️ Text Chat Input
text_input = st.chat_input("অথবা এখানে আপনার নির্দেশ বা প্রশ্ন টাইপ করুন...")
if text_input:
    user_command = text_input

# -------------------------------------------------------------
# Agent Processing & Execution
# -------------------------------------------------------------
if user_command:
    with st.chat_message("user"):
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

        status_box.update(label="✅ কাজ সম্পন্ন এবং কোয়ালিটি গেট দ্বারা ভেরিফাইড!", state="complete", expanded=False)

        with st.chat_message("assistant"):
            st.markdown(result["final_report"])

            st.download_button(
                label="📥 চূড়ান্ত রিপোর্ট ডাউনলোড করুন",
                data=result["final_report"],
                file_name="final_agent_report.md",
                mime="text/markdown",
                key="dl_latest"
            )

            with st.expander("🔍 সাব-এজেন্ট ট্র্যাজেক্টরি ও কোয়ালিটি স্কোর দেখুন"):
                st.subheader("Sub-Agent Work & Evaluations")
                for sub in result.get("sub_agent_results", []):
                    st.write(f"**Task:** {sub['task']['task_description']}")
                    st.write(f"**Specialist:** {sub['task']['agent'].upper()}")
                    st.write(f"**Attempts needed:** {sub['attempts']}")
                    st.json(sub.get("eval", {}))
                    st.markdown("---")

        st.rerun()

    except Exception as e:
        status_box.update(label="⚠️ Error Occurred", state="error", expanded=True)
        st.error(f"Error during execution: {str(e)}")
