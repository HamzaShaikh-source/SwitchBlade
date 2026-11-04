"""
SwitchBlade Localhost Launcher
Starts both the Mock Billing API (:8001) and the Control Plane / Web Cockpit (:8002).
"""

import os
import subprocess
import sys
import time
import urllib.request

def check_url(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    python_exe = sys.executable

    print("=" * 65)
    print("  SWITCHBLADE LOCALHOST LAUNCHER")
    print("=" * 65)

    # 1. Check Mock Billing API (:8001)
    if not check_url("http://localhost:8001/orders/9901"):
        print("[*] Starting Mock Enterprise Billing API on :8001...")
        subprocess.Popen(
            [python_exe, os.path.join(root, "mock_billing_api.py")],
            cwd=root,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        time.sleep(1.5)
    else:
        print("[+] Mock Enterprise Billing API already active on :8001")

    # 2. Check Proxy Control Plane (:8002)
    if not check_url("http://localhost:8002/health"):
        print("[*] Starting SwitchBlade Control Plane & Web Cockpit on :8002...")
        subprocess.Popen(
            [python_exe, os.path.join(root, "proxy.py")],
            cwd=root,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        time.sleep(2.0)
    else:
        print("[+] SwitchBlade Control Plane already active on :8002")

    print("\n" + "=" * 65)
    print("  SWITCHBLADE IS LIVE ON LOCALHOST:")
    print("  • Landing Page:    http://localhost:8002/")
    print("  • Control Plane:   http://localhost:8002/overview")
    print("  • Activity Stream: http://localhost:8002/activity")
    print("  • Escrows Queue:   http://localhost:8002/escrows")
    print("  • Vaccine Rules:   http://localhost:8002/vaccines")
    print("  • SHA-256 Ledger:  http://localhost:8002/ledger")
    print("  • Benchmarks:      http://localhost:8002/benchmarks")
    print("  • Wispr Flow:      http://localhost:8002/wispr")
    print("  • API Docs:        http://localhost:8002/docs")
    print("=" * 65)

if __name__ == "__main__":
    main()
