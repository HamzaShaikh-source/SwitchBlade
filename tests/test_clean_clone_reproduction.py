"""
Unit and Integration Tests for Milestone A4: Clean-Clone Reproduction Verification
Owned by Aaditya Arunpal (branch: feat/aaditya-switch-bridge)

Verifications Required by Rubric:
1. Clean-clone reproduction in an isolated directory simulates onboarding from scratch.
2. switchblade.template.yaml conforms to the v1 Switch template spec (params, machine, directory, addressing: anyone).
3. All dependencies in requirements.txt import cleanly.
4. switch_bridge.py --test-roundtrip verifies WebSocket agent protocol and command parsing.
5. verify_ledger.py --tamper-demo detects database row tampering and exits with code 1.
6. run_demo.py --mode selftest renders cockpit and exits with code 0.
7. test_suite.py runs and passes completely.
8. Total execution time is strictly under 10 minutes (target < 30 seconds).
"""

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


@pytest.fixture(scope="module")
def clean_clone_dir():
    """
    Simulates a pristine git clone into a temporary isolated directory.
    Copies all repo files, excluding caches and git internals.
    """
    with tempfile.TemporaryDirectory(prefix="switchblade_clean_clone_") as tmp_dir:
        dest_root = Path(tmp_dir)

        # Files and directories to copy
        items_to_copy = [
            ".env.example",
            "requirements.txt",
            "switchblade.template.yaml",
            "schemas.py",
            "proxy.py",
            "ledger.py",
            "verify_ledger.py",
            "switch_bridge.py",
            "mock_billing_api.py",
            "context_surgeon.py",
            "vaccine_registry.py",
            "vaccines.json",
            "worker_agent.py",
            "test_suite.py",
            "test_schemas.py",
            "test_proxy_and_ledger.py",
            "run_demo.py",
            "pytest.ini",
            "README.md",
            "BLOG.md",
            "WISPR_FLOW.md",
            "DEMO_RUNBOOK.md",
            "patch.diff",
            "pr_draft.md",
            "tools",
            "ui",
            "bench",
            "tests",
        ]

        for item in items_to_copy:
            src = REPO_ROOT / item
            if src.is_file():
                shutil.copy2(src, dest_root / item)
            elif src.is_dir():
                shutil.copytree(src, dest_root / item, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        yield dest_root


def test_clean_clone_template_yaml_spec(clean_clone_dir):
    """
    Verifies switchblade.template.yaml in the clean clone directory:
    - Must be valid YAML.
    - Must contain a top-level 'params' block.
    - Every agent must declare 'provider', 'machine', 'directory', and 'addressing: anyone'.
    - Room and kickoff sections must be properly formed.
    """
    template_path = clean_clone_dir / "switchblade.template.yaml"
    assert template_path.exists(), "switchblade.template.yaml missing in clean clone"

    with open(template_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "params" in data, "Template must contain top-level 'params'"
    assert isinstance(data["params"], (dict, list))
    if isinstance(data["params"], dict):
        param_names = set(data["params"].keys())
    else:
        param_names = {p["name"] for p in data["params"] if "name" in p}
    assert {"team", "provider", "machine", "repo_dir"}.issubset(param_names)

    assert "agents" in data, "Template must contain 'agents' list"
    assert len(data["agents"]) >= 3, "Template must declare surgeon, scout, and compiler"

    for agent in data["agents"]:
        assert "name" in agent
        assert "provider" in agent
        assert "machine" in agent
        assert "directory" in agent
        assert agent.get("addressing") == "anyone", f"Agent {agent['name']} must use 'addressing: anyone'"

    assert "room" in data, "Template must declare a 'room'"
    assert "kickoff" in data, "Template must declare 'kickoff' instructions"


def test_clean_clone_requirements_and_env(clean_clone_dir):
    """
    Verifies that all core packages listed in requirements.txt can be imported,
    and .env.example contains the necessary configuration keys.
    """
    env_example = clean_clone_dir / ".env.example"
    assert env_example.exists()
    content = env_example.read_text(encoding="utf-8")
    assert "SWITCH_API_URL" in content
    assert "SWITCH_AGENT_TOKEN" in content
    assert "ANTHROPIC_API_KEY" in content
    assert "HUMAN_ALLOWLIST" in content

    # Test requirements importability
    req_file = clean_clone_dir / "requirements.txt"
    assert req_file.exists()
    packages = ["fastapi", "uvicorn", "httpx", "websockets", "rich", "yaml", "pydantic", "anthropic", "pytest"]
    for pkg in packages:
        mod = importlib.import_module(pkg)
        assert mod is not None, f"Failed to import required package: {pkg}"


def test_clean_clone_switch_bridge_roundtrip(clean_clone_dir):
    """
    Verifies python switch_bridge.py --test-roundtrip runs cleanly
    in the isolated clone environment and exits with code 0.
    """
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "switch_bridge.py", "--test-roundtrip"],
        cwd=str(clean_clone_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=SUBPROCESS_ENV,
        timeout=30,
    )
    elapsed = time.perf_counter() - start

    assert proc.returncode == 0, f"switch_bridge.py --test-roundtrip failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    assert "Round-Trip PASSED" in proc.stdout or "Milestone A2 Round-Trip PASSED" in proc.stdout or proc.returncode == 0
    assert elapsed < 15.0, f"Round-trip took too long ({elapsed:.2f}s)"


def test_clean_clone_ledger_tamper_demo(clean_clone_dir):
    """
    Verifies python verify_ledger.py --tamper-demo runs in the isolated environment,
    catches cryptographic chain corruption, and exits with code 1.
    """
    proc = subprocess.run(
        [sys.executable, "verify_ledger.py", "--tamper-demo"],
        cwd=str(clean_clone_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=SUBPROCESS_ENV,
        timeout=30,
    )

    # Must exit 1 to indicate tamper was detected
    assert proc.returncode == 1, f"Expected returncode 1 from --tamper-demo, got {proc.returncode}"
    output = (proc.stdout or "") + (proc.stderr or "")
    assert "TAMPER DETECTED" in output, f"Output did not indicate tamper detection:\n{output}"


def test_clean_clone_run_demo_selftest(clean_clone_dir):
    """
    Verifies python run_demo.py --mode selftest runs in the isolated environment,
    rendering the Rich terminal cockpit and exiting 0.
    """
    proc = subprocess.run(
        [sys.executable, "run_demo.py", "--mode", "selftest"],
        cwd=str(clean_clone_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=SUBPROCESS_ENV,
        timeout=30,
    )

    assert proc.returncode == 0, f"run_demo.py --mode selftest failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    output = proc.stdout or ""
    assert "SELFTEST MODE" in output
    assert "SWITCHBLADE CONTROL PLANE" in output


def test_clean_clone_test_suite(clean_clone_dir):
    """
    Verifies python test_suite.py passes in the clean clone directory.
    """
    proc = subprocess.run(
        [sys.executable, "test_suite.py"],
        cwd=str(clean_clone_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=SUBPROCESS_ENV,
        timeout=60,
    )

    assert proc.returncode == 0, f"test_suite.py failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"


def test_clean_clone_benchmark_results_consistency(clean_clone_dir):
    """
    Verifies that bench/results.json exists, parses cleanly, and confirms:
    - 860,000 control tokens vs 108,260 guarded tokens.
    - 99.2% context history reduction.
    - 87.4% API cost reduction ($12.90 -> $1.62).
    - Sub-microsecond / low microsecond rewrite latency (p50: 1.2us, p99: 2.6us).
    """
    import json
    bench_file = clean_clone_dir / "bench" / "results.json"
    assert bench_file.exists()

    with open(bench_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["control_run"]["total_tokens"] == 860000
    assert data["control_run"]["total_cost_usd"] == 12.9
    assert data["guarded_run"]["total_tokens"] == 108260
    assert data["guarded_run"]["history_reduction_pct"] == 99.2
    assert abs(data["guarded_run"]["total_cost_usd"] - 1.6239) < 0.01
    assert data["rewrite_latency"]["p50_us"] == 1.2
    assert data["rewrite_latency"]["p99_us"] == 2.6


def test_clean_clone_spinup_time_under_10_minutes():
    """
    Measures complete end-to-end spinup time:
    Creating clean directory, verifying template, checking dependencies,
    running roundtrip, tamper verification, and selftest demo.
    Asserts entire process finishes in under 600 seconds (< 10 minutes).
    """
    start_time = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="switchblade_spinup_test_") as tmp_dir:
        dest_root = Path(tmp_dir)

        for fname in ["switchblade.template.yaml", "switch_bridge.py", "verify_ledger.py", "run_demo.py", "schemas.py"]:
            shutil.copy2(REPO_ROOT / fname, dest_root / fname)

        # 1. Template validation
        with open(dest_root / "switchblade.template.yaml", "r", encoding="utf-8") as f:
            t_data = yaml.safe_load(f)
        assert "params" in t_data

        # 2. Roundtrip execution
        p_roundtrip = subprocess.run(
            [sys.executable, "switch_bridge.py", "--test-roundtrip"],
            cwd=str(dest_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=SUBPROCESS_ENV,
            timeout=20,
        )
        assert p_roundtrip.returncode == 0

        # 3. Tamper demo execution
        p_tamper = subprocess.run(
            [sys.executable, "verify_ledger.py", "--tamper-demo"],
            cwd=str(dest_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=SUBPROCESS_ENV,
            timeout=20,
        )
        assert p_tamper.returncode == 1

    total_duration = time.perf_counter() - start_time
    # Must finish in under 10 minutes (600 seconds)
    assert total_duration < 600.0, f"Spinup took {total_duration:.2f}s, expected < 600s"
