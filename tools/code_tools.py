import sys
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any
from config import SANDBOX_PATH

# Forbidden destructive patterns (Pillar 1 & 4 from Whitepaper 4)
DANGEROUS_PATTERNS = [
    "shutil.rmtree('C:",
    "os.system('del",
    "os.system('format",
    "subprocess.Popen(['rm",
    "ctypes.windll",
]

def execute_python_code(code: str, timeout: int = 15) -> Dict[str, Any]:
    """Executes Python code in an isolated sandbox environment and captures outputs.
    
    Args:
        code: Python source code to execute.
        timeout: Maximum execution time in seconds.
        
    Returns:
        Dict containing success (bool), stdout (str), stderr (str), returncode (int), execution_time_sec (float).
    """
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in code.lower():
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Security Violation: Execution blocked due to forbidden pattern '{pattern}'",
                "returncode": -1,
                "execution_time_sec": 0.0
            }

    script_path = SANDBOX_PATH / f"run_{int(time.time() * 1000)}.py"
    try:
        script_path.write_text(code, encoding="utf-8")
        start_time = time.time()

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(SANDBOX_PATH),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed = time.time() - start_time

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "execution_time_sec": round(elapsed, 3)
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds.",
            "returncode": -2,
            "execution_time_sec": float(timeout)
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"System Execution Error: {str(e)}",
            "returncode": -3,
            "execution_time_sec": 0.0
        }
    finally:
        # Keep sandbox clean
        if script_path.exists():
            try:
                script_path.unlink()
            except Exception:
                pass
