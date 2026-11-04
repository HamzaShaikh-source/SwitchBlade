"""
SwitchBlade High-Concurrency Stress & Fuzzing Test Suite
Author: Aaditya Arunpal (feat/aaditya-switch-bridge)

Verifies zero-drift reliability under extreme load:
1. High-throughput message ingestion & deduplication (1,000 concurrent frames).
2. Memory leak check on LRU message cache.
3. Command parser fuzzing & ReDoS resistance (1,000 randomized boundary cases).
4. Concurrent proxy dispatch under fault injection (500/503/timeouts).
5. Cryptographic hash microbenchmarks (p50 & p99 latency in microseconds).
"""

import asyncio
import json
import random
import string
import time
import pytest
from switch_bridge import SwitchBridge, BridgeMode
from schemas import (
    compute_change_hash,
    compute_entry_hash,
    compute_progress_hash,
    canonical_json_dumps,
)


@pytest.fixture
def stress_bridge():
    bridge = SwitchBridge(
        mode=BridgeMode.MOCK,
        human_allowlist={"aaditya", "hamza", "santosh", "janani", "policy-bot"},
        agent_ids={"switchblade-proxy", "sb-surgeon", "sb-scout", "sb-compiler"},
    )
    bridge.max_seen_messages = 500  # small limit to verify LRU eviction under stress
    return bridge


@pytest.mark.asyncio
async def test_high_concurrency_and_deduplication(stress_bridge, monkeypatch):
    """
    Simulates 1,000 concurrent room messages:
    - 500 unique valid messages.
    - 500 duplicates of the first 500.
    Verifies that duplicates are rejected, no race conditions occur, and memory remains bounded.
    """
    dispatch_count = 0

    async def mock_dispatch(self, *args, **kwargs):
        nonlocal dispatch_count
        dispatch_count += 1
        return {"status": "success"}

    monkeypatch.setattr(SwitchBridge, "_dispatch_approval", mock_dispatch)

    start_time = time.perf_counter()

    # Generate 500 unique commands
    unique_msgs = [
        (f"msg-{i:04d}", f"APPROVE escrow-{i:04d} aabbcc{i % 100:02d}")
        for i in range(500)
    ]

    # Combine unique + duplicate interleaved
    all_tasks = []
    for msg_id, cmd in unique_msgs:
        all_tasks.append(
            stress_bridge.handle_room_message(
                sender="@aaditya",
                body=cmd,
                message_id=msg_id,
                addressed=True,
            )
        )
        # Duplicate task with same message_id
        all_tasks.append(
            stress_bridge.handle_room_message(
                sender="@aaditya",
                body=cmd,
                message_id=msg_id,
                addressed=True,
            )
        )

    # Execute all 1,000 messages concurrently
    results = await asyncio.gather(*all_tasks)
    elapsed = time.perf_counter() - start_time

    # Exactly 500 should succeed, 500 should be deduplicated (None)
    successful = [r for r in results if r is not None]
    deduplicated = [r for r in results if r is None]

    assert len(successful) == 500, f"Expected 500 successes, got {len(successful)}"
    assert len(deduplicated) == 500, f"Expected 500 deduplications, got {len(deduplicated)}"
    assert dispatch_count == 500, f"Dispatched {dispatch_count} times instead of 500"

    # Memory bounding check: seen_message_ids must never exceed max_seen_messages
    assert len(stress_bridge.seen_message_ids) <= stress_bridge.max_seen_messages

    throughput = len(all_tasks) / elapsed
    print(f"\n[Stress] 1,000 concurrent messages processed in {elapsed:.3f}s ({throughput:.1f} msg/s)")


def test_command_parser_fuzzing(stress_bridge):
    """
    Fuzzes parse_command with 1,000 random inputs:
    - Extreme string lengths (up to 50,000 chars)
    - Unicode characters, null bytes, formatting quirks
    - Injection strings (SQL, bash, path traversal)
    Asserts zero uncaught exceptions.
    """
    fuzz_samples = [
        "",
        "   ",
        None,
        12345,
        {"not": "a string"},
        "APPROVE",
        "APPROVE only_one_arg",
        "APPROVE escrow-123",
        "APPROVE escrow-123 1234567",       # 7 chars (too short)
        "APPROVE escrow-123 123456789",     # 9 chars (too long)
        "APPROVE escrow-123 1234567g",     # non-hex char
        "APPROVE " + "A" * 50000 + " 12345678",
        "```APPROVE escrow-999 12345678```",
        "```bash\nAPPROVE escrow-999 12345678\n```",
        "REJECT",
        "REJECT escrow-101",
        "REJECT escrow-101 " + "x" * 10000,
        "PROMOTE VACCINE-001 12345678",
        "ROLLBACK VACCINE-001",
        "SELECT * FROM users WHERE '1'='1'",
        "; rm -rf / ;",
        "../../../../../../etc/passwd",
        "\x00\x01\x02\xff",
        "🎉 🚀 🚨 ✂️ 💉 🔗",
    ]

    # Generate 975 additional randomized fuzz strings
    for _ in range(975):
        length = random.randint(1, 200)
        rand_str = "".join(random.choices(string.printable, k=length))
        fuzz_samples.append(rand_str)

    start = time.perf_counter()
    for sample in fuzz_samples:
        try:
            res = stress_bridge.parse_command(sample)
            if res is not None:
                assert "action" in res
        except Exception as ex:
            pytest.fail(f"parse_command crashed on input: {sample!r} with {ex}")

    elapsed = time.perf_counter() - start
    print(f"\n[Fuzzing] 1,000 inputs parsed safely in {elapsed * 1000:.2f}ms (Zero crashes)")


@pytest.mark.asyncio
async def test_fault_injection_resilience(stress_bridge, monkeypatch):
    """
    Simulates 100 concurrent room commands while the target proxy endpoint
    experiences transient network drops, 500 Internal Server Errors, and timeouts.
    Verifies that the bridge recovers cleanly and never raises uncaught exceptions.
    """
    async def faulty_post(client, url, *args, **kwargs):
        outcome = random.choice(["ok", "500", "503", "timeout", "conn_error"])
        if outcome == "ok":
            class RespOk:
                status_code = 200
                text = '{"status": "success", "state": "APPROVED"}'
                def json(self): return json.loads(self.text)
            return RespOk()
        elif outcome in ("500", "503"):
            class RespErr:
                status_code = int(outcome)
                text = f"Fault Injection {outcome}"
                def json(self): return {"error": self.text}
            return RespErr()
        elif outcome == "timeout":
            raise TimeoutError("Simulated proxy read timeout")
        else:
            raise ConnectionError("Simulated proxy connection reset")

    monkeypatch.setattr("httpx.AsyncClient.post", faulty_post)

    tasks = [
        stress_bridge.handle_room_message(
            sender="@aaditya",
            body=f"APPROVE escrow-{i:03d} 11223344",
            message_id=f"fault-msg-{i}",
            addressed=True,
        )
        for i in range(100)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no unhandled exceptions bubbled up
    for r in results:
        assert not isinstance(r, Exception), f"Unhandled exception bubbled up: {r}"
        assert isinstance(r, dict)
        assert "status" in r or "error" in r or "code" in r

    print("\n[Fault Injection] 100 concurrent requests with simulated crashes completed without bridge failure")


def test_hash_microbenchmarks():
    """
    Benchmarking canonical hash operations over 5,000 iterations:
    - compute_change_hash
    - compute_entry_hash
    - compute_progress_hash
    Measures p50 and p99 execution latency in microseconds.
    """
    iterations = 5000
    times_ns = []

    dummy_payload = {
        "escrow_id": "escrow-bench-101",
        "task_id": "task-bench-99",
        "amount": 4500.0,
        "tenant_id": "acme-corp",
        "error_class": "422_UNPROCESSABLE_ENTITY",
        "failed_attempts": 3,
    }

    for i in range(iterations):
        t0 = time.perf_counter_ns()
        _h1 = compute_change_hash({"match": "POST /v1/orders"}, "patch text")
        _h2 = compute_entry_hash(
            seq_no=i,
            timestamp=1700000000.0 + i,
            escrow_id="escrow-001",
            event_type="ESCROW_TRIPPED",
            payload=dummy_payload,
            prev_hash="0" * 64,
        )
        _h3 = compute_progress_hash("sync_orders", dummy_payload, 422, "fingerprint-xyz")
        t1 = time.perf_counter_ns()
        times_ns.append((t1 - t0) / 1000.0)  # to microseconds

    times_ns.sort()
    p50_us = times_ns[int(iterations * 0.50)]
    p90_us = times_ns[int(iterations * 0.90)]
    p99_us = times_ns[int(iterations * 0.99)]

    print(
        f"\n[Microbenchmark] 5,000 Canonical Hash Chains:\n"
        f"  p50: {p50_us:.2f} us | p90: {p90_us:.2f} us | p99: {p99_us:.2f} us"
    )

    # Guarantee sub-millisecond execution (p99 < 1000 μs)
    assert p99_us < 1000.0, f"p99 latency ({p99_us} μs) exceeded 1ms threshold"
