"""
SwitchBlade Tamper-Evident Canonical Ledger
Author: Santosh Subramanian (feat/santosh-proxy-ledger)

Provides append-only SQLite storage with:
- Monotonic sequence numbers (seq_no: 1, 2, 3...)
- SQLite `BEGIN IMMEDIATE` transactions to prevent write races and chain forks
- Domain-separated cryptographic chaining: SWITCHBLADE-LEDGER-V1
- Deterministic canonical JSON serialization
- Integrity verification and room checkpoint detection (every 5 events)
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from schemas import (
    LedgerCheckpoint,
    LedgerEntry,
    LedgerEventType,
    canonical_json_dumps,
    compute_entry_hash,
)

logger = logging.getLogger("switchblade.ledger")

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "switchblade_ledger.db"
)
GENESIS_PREV_HASH = "0" * 64
CHECKPOINT_INTERVAL = 5


class LedgerManager:
    """
    Thread-safe and process-safe SQLite ledger backed by BEGIN IMMEDIATE.
    Guarantees clean connection teardown to prevent Windows file locking.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that yields a connection and strictly closes it on exit."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level=None,  # Enables manual BEGIN IMMEDIATE
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initializes ledger schema if not exists."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger (
                    seq_no INTEGER PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    escrow_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ledger_escrow
                ON ledger(escrow_id);
                """
            )

    def get_head(self) -> Optional[LedgerEntry]:
        """Fetches the latest entry in the ledger."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ledger ORDER BY seq_no DESC LIMIT 1;"
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def get_entry(self, seq_no: int) -> Optional[LedgerEntry]:
        """Fetches a specific entry by sequence number."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ledger WHERE seq_no = ?;", (seq_no,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def get_all_entries(self) -> List[LedgerEntry]:
        """Fetches all ledger entries ordered by sequence number."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ledger ORDER BY seq_no ASC;"
            )
            rows = cursor.fetchall()
            return [self._row_to_entry(r) for r in rows]

    def append_entry(
        self,
        escrow_id: str,
        event_type: Union[str, LedgerEventType],
        payload: Dict[str, Any],
        timestamp: Optional[float] = None,
    ) -> Tuple[LedgerEntry, Optional[LedgerCheckpoint]]:
        """
        Appends a new event into the ledger under an atomic BEGIN IMMEDIATE lock.
        Returns (LedgerEntry, Optional[LedgerCheckpoint]).
        If seq_no % 5 == 0, returns a LedgerCheckpoint to anchor in the Switch room.
        """
        if isinstance(event_type, LedgerEventType):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)

        now = timestamp if timestamp is not None else time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Acquire exclusive write lock immediately
                cursor.execute("BEGIN IMMEDIATE;")

                # Read current head inside transaction
                cursor.execute(
                    "SELECT seq_no, entry_hash FROM ledger ORDER BY seq_no DESC LIMIT 1;"
                )
                head_row = cursor.fetchone()

                if head_row is None:
                    seq_no = 1
                    prev_hash = GENESIS_PREV_HASH
                else:
                    seq_no = head_row["seq_no"] + 1
                    prev_hash = head_row["entry_hash"]

                canonical_payload = canonical_json_dumps(payload)
                entry_hash = compute_entry_hash(
                    seq_no=seq_no,
                    timestamp=now,
                    escrow_id=escrow_id,
                    event_type=event_type_str,
                    payload=payload,
                    prev_hash=prev_hash,
                )

                cursor.execute(
                    """
                    INSERT INTO ledger (seq_no, timestamp, escrow_id, event_type, payload, prev_hash, entry_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (seq_no, now, escrow_id, event_type_str, canonical_payload, prev_hash, entry_hash),
                )
                cursor.execute("COMMIT;")

                entry = LedgerEntry(
                    seq_no=seq_no,
                    timestamp=now,
                    escrow_id=escrow_id,
                    event_type=event_type_str,
                    payload=payload,
                    prev_hash=prev_hash,
                    entry_hash=entry_hash,
                )

                checkpoint: Optional[LedgerCheckpoint] = None
                if seq_no % CHECKPOINT_INTERVAL == 0:
                    checkpoint = LedgerCheckpoint(
                        seq=seq_no,
                        head_hash=entry_hash,
                        timestamp=now,
                    )

                return entry, checkpoint

            except Exception as e:
                try:
                    cursor.execute("ROLLBACK;")
                except Exception:
                    pass
                logger.error(f"Failed to append ledger entry: {e}")
                raise

    def verify_chain(
        self,
        expected_checkpoint_hash: Optional[str] = None,
        expected_seq: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Validates internal hash chaining and external anchor match.
        Returns (is_valid: bool, reason: str, failed_seq: Optional[int]).
        """
        entries = self.get_all_entries()
        if not entries:
            return True, "Ledger is empty", None

        # Verify internal cryptographic chaining
        prev_hash = GENESIS_PREV_HASH
        for i, entry in enumerate(entries, start=1):
            if entry.seq_no != i:
                return (
                    False,
                    f"Sequence number gap or mismatch: expected {i}, found {entry.seq_no}",
                    entry.seq_no,
                )

            if entry.prev_hash != prev_hash:
                return (
                    False,
                    f"Broken hash link at seq {entry.seq_no}: prev_hash does not match predecessor entry_hash",
                    entry.seq_no,
                )

            recomputed_hash = compute_entry_hash(
                seq_no=entry.seq_no,
                timestamp=entry.timestamp,
                escrow_id=entry.escrow_id,
                event_type=entry.event_type,
                payload=entry.payload,
                prev_hash=entry.prev_hash,
            )

            if recomputed_hash != entry.entry_hash:
                return (
                    False,
                    f"TAMPER DETECTED AT SEQ {entry.seq_no}: payload or header corrupted (computed {recomputed_hash[:8]} vs stored {entry.entry_hash[:8]})",
                    entry.seq_no,
                )

            prev_hash = entry.entry_hash

        # Verify external Switch room checkpoint if provided
        head = entries[-1]
        if expected_seq is not None:
            if head.seq_no < expected_seq:
                return (
                    False,
                    f"Tail truncation detected: head seq {head.seq_no} is less than expected checkpoint seq {expected_seq}",
                    head.seq_no,
                )

        if expected_checkpoint_hash is not None:
            target_entry = self.get_entry(expected_seq) if expected_seq else head
            if not target_entry or target_entry.entry_hash != expected_checkpoint_hash:
                return (
                    False,
                    f"Checkpoint mismatch: external room anchor does not match DB hash",
                    expected_seq or head.seq_no,
                )

        return True, "Ledger integrity verified: all cryptographic hashes and room anchors match", None

    def corrupt_row_for_demo(
        self,
        seq_no: int,
        corrupted_payload: Dict[str, Any] = {"tampered": True, "stolen_amount": 999999},
    ) -> bool:
        """Corrupts a single row to demonstrate tamper detection in verify_ledger.py."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE ledger SET payload = ? WHERE seq_no = ?;",
                (canonical_json_dumps(corrupted_payload), seq_no),
            )
            return cursor.rowcount > 0

    def _row_to_entry(self, row: sqlite3.Row) -> LedgerEntry:
        """Converts an SQLite row to a typed LedgerEntry model."""
        payload_data = json.loads(row["payload"])
        return LedgerEntry(
            seq_no=row["seq_no"],
            timestamp=row["timestamp"],
            escrow_id=row["escrow_id"],
            event_type=row["event_type"],
            payload=payload_data,
            prev_hash=row["prev_hash"],
            entry_hash=row["entry_hash"],
        )
