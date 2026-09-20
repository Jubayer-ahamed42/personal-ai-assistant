import os
import sys
import time
import subprocess
import signal
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - [ServiceManager] - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("ServiceManager")

def main():
    logger.info("Initializing 24/7 AI Assistant Microservices...")

    processes = []

    # 1. Start Streamlit Web Dashboard
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port=8501",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ]
    logger.info("Launching Streamlit Web App on port 8501...")
    p_web = subprocess.Popen(streamlit_cmd)
    processes.append(p_web)

    # 2. Start Telegram Bot Worker (if token is configured)
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if tg_token and tg_token.strip() and tg_token != "your_telegram_bot_token_here":
        logger.info("TELEGRAM_BOT_TOKEN found! Launching Telegram Bot Worker...")
        p_tg = subprocess.Popen([sys.executable, "telegram_bot.py"])
        processes.append(p_tg)
    else:
        logger.info("TELEGRAM_BOT_TOKEN not configured yet. Telegram bot worker paused. Web UI is active.")

    def handle_shutdown(signum, frame):
        logger.info("Received termination signal. Gracefully shutting down all services...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Health loop
    try:
        while True:
            time.sleep(3)
            for p in processes:
                poll = p.poll()
                if poll is not None:
                    logger.warning(f"Process {p.args} exited with code {poll}. Restarting...")
                    # If web app died, exit so container reboots cleanly
                    if "streamlit" in " ".join(p.args):
                        sys.exit(poll)
    except KeyboardInterrupt:
        handle_shutdown(None, None)

if __name__ == "__main__":
    main()
