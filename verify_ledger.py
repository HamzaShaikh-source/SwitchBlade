#!/usr/bin/env python3
"""
SwitchBlade Ledger Verifier CLI
Author: Santosh Subramanian (feat/santosh-proxy-ledger)

Verifies the cryptographic integrity of the SQLite ledger and room checkpoints:
- Validates internal SHA-256 chain links
- Recomputes domain-prefixed entry hashes: SWITCHBLADE-LEDGER-V1
- Detects row mutations, payload tampering, sequence gaps, and tail truncation
- Supports --tamper-demo to corrupt a temporary DB copy and prove detection exits 1
"""

import argparse
import os
import shutil
import sys
import tempfile

from ledger import DEFAULT_DB_PATH, LedgerManager


def parse_args():
    parser = argparse.ArgumentParser(
        description="Verify cryptographic integrity of the SwitchBlade SQLite ledger."
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite ledger database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--checkpoint-hash",
        type=str,
        default=None,
        help="Expected SHA-256 head hash anchored in the Switch Room",
    )
    parser.add_argument(
        "--expected-seq",
        type=int,
        default=None,
        help="Expected head sequence number anchored in the Switch Room",
    )
    parser.add_argument(
        "--tamper-demo",
        action="store_true",
        help="Corrupt a copy of the DB to demonstrate tamper detection",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.tamper_demo:
        print("[!] Running Tamper Demonstration...")
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_db_path = tmp.name
        tmp.close()

        try:
            mgr = LedgerManager(db_path=tmp_db_path)
            if os.path.exists(args.db) and os.path.getsize(args.db) > 0:
                shutil.copyfile(args.db, tmp_db_path)
                mgr = LedgerManager(db_path=tmp_db_path)

            if not mgr.get_head():
                # Seed demo entries if DB was empty
                for i in range(1, 6):
                    mgr.append_entry(
                        escrow_id=f"esc-demo-{i}",
                        event_type="ESCROW_TRIPPED" if i == 1 else "LEDGER_CHECKPOINT",
                        payload={"order_id": 9900 + i, "step": i, "demo": True},
                    )

            head = mgr.get_head()
            if not head:
                print("[-] Could not create or read demo ledger.")
                sys.exit(1)

            target_seq = max(1, head.seq_no // 2)
            print(f"[*] Corrupting payload at sequence {target_seq} in isolated copy...")
            mgr.corrupt_row_for_demo(seq_no=target_seq)

            print("[*] Running verification on corrupted ledger...")
            is_valid, reason, failed_seq = mgr.verify_chain()
            if not is_valid:
                print(f"\n[+] SUCCESS: TAMPER DETECTED!")
                print(f"    Sequence: {failed_seq}")
                print(f"    Reason:   {reason}\n")
                sys.exit(0)
            else:
                print("[-] ERROR: Tamper was NOT detected!")
                sys.exit(1)
        finally:
            if os.path.exists(tmp_db_path):
                try:
                    os.remove(tmp_db_path)
                except Exception:
                    pass

    # Standard verification mode
    if not os.path.exists(args.db):
        print(f"[-] Ledger database not found at: {args.db}")
        sys.exit(1)

    ledger = LedgerManager(db_path=args.db)
    is_valid, reason, failed_seq = ledger.verify_chain(
        expected_checkpoint_hash=args.checkpoint_hash,
        expected_seq=args.expected_seq,
    )

    if not is_valid:
        print(f"[FAIL] TAMPER DETECTED AT SEQ {failed_seq}")
        print(f"       Details: {reason}")
        sys.exit(1)

    head = ledger.get_head()
    seq_display = head.seq_no if head else 0
    hash_display = head.entry_hash[:16] + "..." if head else "None"
    print(f"[PASS] Ledger integrity verified. Head Seq: {seq_display}, Hash: {hash_display}")
    sys.exit(0)


if __name__ == "__main__":
    main()
