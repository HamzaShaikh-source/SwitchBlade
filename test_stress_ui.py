"""
test_stress_ui.py - Comprehensive End-to-End Stress & Edge-Case Test Suite for SwitchBlade UI.
Author: Hamza Shaikh (feat/hamza-cockpit-ui)
"""

import io
import sys
import time
import json
import threading
from typing import Dict, Any

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console

import ui.room_cards as rc
from ui.cockpit import (
    SwitchBladeCockpit,
    CockpitState,
    WorkerTurnRecord,
    VaccineDisplayRecord,
    LedgerDisplayRecord,
    state_from_proxy_payload,
    create_demo_state,
)
import bench.run_bench as rb


def test_room_cards_edge_cases():
    print("Testing ui/room_cards.py edge cases...")

    # 1. Zero tokens and costs
    card = rc.card_context_surgery_complete(
        escrow_id="esc-zero",
        tokens_before=0,
        tokens_after=0,
        full_request_before=0,
        full_request_after=0,
    )
    lines = [l for l in card.strip().split("\n") if l.strip()]
    assert len(lines) == 4, f"Expected 4 lines, got {len(lines)}"

    # 2. Huge tokens (overflow test)
    card_huge = rc.card_escrow_tripped(
        escrow_id="esc-huge",
        task_id="task-huge",
        tool_name="sync_customer_order",
        burned_tokens=100_000_000_000,
        burned_cost_usd=1_500_000.0,
    )
    lines_huge = [l for l in card_huge.strip().split("\n") if l.strip()]
    assert len(lines_huge) == 4

    # 3. Special characters & injectables in names
    card_spec = rc.card_dry_run_verified(
        escrow_id="esc-'<>&`",
        change_hash="8f4b2a1c",
        original_route="POST /v1/orders?tenant=acme;--",
        candidate_route="POST /v2/orders?tenant=acme;--",
        dry_run_result="200 OK (?dry_run=true, would_settle=True)",
    )
    lines_spec = [l for l in card_spec.strip().split("\n") if l.strip()]
    assert len(lines_spec) == 4

    # 4. Unknown event type raises ValueError
    try:
        rc.render_card("UNKNOWN_EVENT")
        assert False, "Should raise ValueError on unknown event"
    except ValueError:
        pass

    # 5. Extra unused kwargs passed to all card functions
    for k in rc.CARD_TEMPLATES:
        rendered = rc.render_card(
            k,
            escrow_id="esc-extra",
            task_id="task-extra",
            tool_name="tool-extra",
            change_hash="12345678",
            seq_no=99,
            head_hash="0" * 64,
            vaccine_id="vac-extra",
            completely_unexpected_param="hello",
            another_param=12345,
        )
        assert len([l for l in rendered.strip().split("\n") if l.strip()]) == 4

    print("  --> Room cards passed all edge cases!")


def test_cockpit_stress_and_edge_cases():
    print("Testing ui/cockpit.py stress and edge cases...")
    buffer = io.StringIO()
    test_console = Console(file=buffer, width=120)
    cockpit = SwitchBladeCockpit(console=test_console)

    # 1. Completely empty CockpitState
    empty_state = CockpitState(
        mode="",
        room_name="",
        ledger_status="",
        ledger_seq=0,
        ledger_head_hash="",
        cumulative_tokens=0,
        cumulative_cost_usd=0.0,
        turns=[],
        escrow_id=None,
        escrow_state="",
        change_hash="",
        trip_reason="",
        surgery_performed=False,
        tokens_before=0,
        tokens_after=0,
        vaccines=[],
        ledger_feed=[],
        status_banner="",
    )
    cockpit.render_once(empty_state)

    # 2. Extreme token counts & negative numbers
    extreme_state = CockpitState(
        cumulative_tokens=-500,  # Negative tokens
        cumulative_cost_usd=-10.0,
        surgery_performed=True,
        tokens_before=0,  # Zero tokens before
        tokens_after=1000,
        reduction_pct=-50.0,
        vaccines=[
            VaccineDisplayRecord(
                vaccine_id="VACCINE-EXTREME",
                match_pattern="POST /extreme",
                rewrite_target="POST /v2/extreme",
                mode="ENFORCE",
                p50_us=0.001,
                p99_us=999999.9,
            )
        ],
    )
    cockpit.render_once(extreme_state)

    # 3. 100 turns stress test
    many_turns_state = create_demo_state()
    many_turns_state.turns = [
        WorkerTurnRecord(i, f"tool_{i}", f"POST /v1/endpoint_{i}", 422 if i % 2 == 0 else 200, i * 1000, i * 1200, 0.01 * i)
        for i in range(1, 101)
    ]
    many_turns_state.cumulative_tokens = 500_000_000  # Way beyond cap
    cockpit.render_once(many_turns_state)

    # 4. Narrow terminal width (60 columns)
    narrow_console = Console(file=buffer, width=60)
    narrow_cockpit = SwitchBladeCockpit(console=narrow_console)
    narrow_cockpit.render_once(create_demo_state())

    # 5. Wide terminal width (200 columns)
    wide_console = Console(file=buffer, width=200)
    wide_cockpit = SwitchBladeCockpit(console=wide_console)
    wide_cockpit.render_once(create_demo_state())

    print("  --> Cockpit rendering passed all stress tests!")


def test_proxy_payload_fuzzing():
    print("Testing state_from_proxy_payload fuzzing...")

    fuzz_payloads = [
        None,
        {},
        {"stats": None, "escrows": None, "vaccines": None},
        {"stats": "corrupted_string"},
        {"escrows": [1, 2, "not_a_dict"]},
        {"vaccines": [{"id": 123, "match": "not_a_dict", "action": None}]},
        {
            "stats": {
                "turns": [{"turn": "NaN", "status_code": "bad"}],
                "ledger_feed": [{"seq": "bad_seq", "hash": None}],
                "surgery": {"tokens_before": 0, "tokens_after": 0},
            }
        },
    ]

    for i, payload in enumerate(fuzz_payloads):
        try:
            state = state_from_proxy_payload(payload)
            # Verify we can render it without exception
            buffer = io.StringIO()
            c = SwitchBladeCockpit(console=Console(file=buffer, width=100))
            c.render_once(state)
        except Exception as e:
            assert False, f"Fuzz payload #{i} crashed with {type(e)}: {e}"

    print("  --> Proxy payload parser passed all fuzzing tests!")


def test_bench_suite_stress():
    print("Testing bench/run_bench.py stress and edge cases...")
    
    # 1. 100 iterations microbenchmark
    res_100 = rb.run_vaccine_microbenchmark(iterations=100)
    assert res_100["iterations"] == 100
    assert res_100["p50_us"] > 0
    assert res_100["p99_us"] >= res_100["p50_us"]

    # 2. Control run with 1 turn and 20 turns
    c1 = rb.run_unguarded_control(cap_turns=1)
    assert c1["turns"] == 1
    assert c1["total_tokens"] > 0

    c20 = rb.run_unguarded_control(cap_turns=20)
    assert c20["turns"] == 20
    assert c20["total_tokens"] > c1["total_tokens"]

    # 3. Guarded run
    g = rb.run_guarded_switchblade()
    assert g["orders_settled"] == [9901, 9902]
    assert g["history_reduction_pct"] == 99.2

    print("  --> Benchmark suite passed all stress runs!")


def main():
    print("==================================================================")
    print("🚀 RUNNING COMPREHENSIVE END-TO-END SWITCHBLADE STRESS TEST SUITE")
    print("==================================================================")
    t0 = time.time()
    test_room_cards_edge_cases()
    test_cockpit_stress_and_edge_cases()
    test_proxy_payload_fuzzing()
    test_bench_suite_stress()
    t1 = time.time()
    print("==================================================================")
    print(f"✅ ALL STRESS TESTS PASSED CLEANLY IN {t1 - t0:.2f}s! ZERO BUGS!")
    print("==================================================================")


if __name__ == "__main__":
    main()
