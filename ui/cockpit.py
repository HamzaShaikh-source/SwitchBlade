"""
ui/cockpit.py - Live Terminal Telemetry Cockpit for SwitchBlade.
Part of SwitchBlade: In-Flight FinOps Escrow Control Plane for Autonomous Agents.

Author: Hamza Shaikh (feat/hamza-cockpit-ui)
Role: Frontend, Live Telemetry UI & Visual Demo Lead

Displays a real-time, 4-panel split terminal UI powered by Rich:
1. Top Header: Mode Banner, active Switch Room, and Ledger Integrity badge.
2. Left Panel: Worker Stream (live turn-by-turn tokens, USD burn bar, HTTP 422/200).
3. Right Panel: Escrow & Context Surgeon View (visual compression gauge, Escrow state).
4. Bottom Panel: Vaccine Registry & Ledger Hash Feed (active vaccines, SHA-256 chain).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import time

from rich.console import Console, RenderResult
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align


@dataclass
class WorkerTurnRecord:
    turn: int
    tool: str
    endpoint: str
    status_code: int
    history_tokens: int
    full_request_tokens: int
    cost_usd: float
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass
class VaccineDisplayRecord:
    vaccine_id: str
    match_pattern: str
    rewrite_target: str
    mode: str  # "SHADOW", "ENFORCE", "INACTIVE"
    p50_us: float = 1.2
    p99_us: float = 4.8
    times_intercepted: int = 0


@dataclass
class LedgerDisplayRecord:
    seq_no: int
    event_type: str
    entry_hash: str
    room_anchored: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass
class CockpitState:
    """Holds all live telemetry state rendered by the Cockpit UI."""
    mode: str = "LIVE"  # "LIVE", "REPLAY", or "SELFTEST"
    room_name: str = "sb-switchblade"
    ledger_status: str = "VERIFIED"  # "VERIFIED", "TAMPERED", "SYNCING"
    ledger_seq: int = 15
    ledger_head_hash: str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # Worker stream
    task_id: str = "task-order-9901"
    cumulative_tokens: int = 45200
    cumulative_cost_usd: float = 0.6780
    turns: List[WorkerTurnRecord] = field(default_factory=list)

    # Escrow State
    escrow_id: Optional[str] = "esc-9901-trip"
    escrow_state: str = "PENDING"  # "IDLE", "PENDING", "APPROVED", "REJECTED", "EXPIRED"
    change_hash: str = "8f4b2a1c"
    approver_id: Optional[str] = None
    trip_reason: str = "3x repeated 422 on /v1/orders (Zero-Progress loop)"

    # Context Surgeon metrics
    surgery_performed: bool = True
    tokens_before: int = 45200
    tokens_after: int = 380
    full_before: int = 48500
    full_after: int = 3680
    reduction_pct: float = 99.2
    pair_integrity: bool = True
    thinking_stripped: bool = True

    # Vaccines
    vaccines: List[VaccineDisplayRecord] = field(default_factory=list)

    # Ledger Feed
    ledger_feed: List[LedgerDisplayRecord] = field(default_factory=list)

    # Status notification
    status_banner: str = "Escrow PENDING — Awaiting room command: APPROVE esc-9901-trip 8f4b2a1c"


class SwitchBladeCockpit:
    """Renders the 4-panel terminal cockpit layout for SwitchBlade."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.layout = Layout()
        self._setup_layout()

    def _setup_layout(self) -> None:
        """Configures the 4-panel layout hierarchy."""
        self.layout.split_column(
            Layout(name="header", size=4),
            Layout(name="body", ratio=1),
            Layout(name="bottom", size=10),
        )
        self.layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )

    # -------------------------------------------------------------------------
    # 1. Top Header Panel
    # -------------------------------------------------------------------------
    def render_header(self, state: CockpitState) -> Panel:
        mode_upper = state.mode.upper()
        if mode_upper == "LIVE":
            mode_badge = "[bold white on red] ● LIVE MODE [/]"
        elif mode_upper == "REPLAY":
            mode_badge = "[bold white on magenta] ↺ REPLAY MODE [/]"
        else:
            mode_badge = "[bold black on cyan] 🧪 SELFTEST MODE [/]"

        if state.ledger_status == "VERIFIED":
            ledger_badge = f"[bold green]🛡️ LEDGER ANCHORED (Seq #{state.ledger_seq})[/]"
        elif state.ledger_status == "TAMPERED":
            ledger_badge = "[bold white on red] ✖ TAMPER DETECTED AT SEQ [/]"
        else:
            ledger_badge = f"[bold yellow]⏳ LEDGER SYNCING (#{state.ledger_seq})[/]"

        header_table = Table.grid(expand=True)
        header_table.add_column(justify="left", ratio=1)
        header_table.add_column(justify="center", ratio=2)
        header_table.add_column(justify="right", ratio=1)

        title_text = Text()
        title_text.append("⚡ SWITCHBLADE ", style="bold bright_cyan")
        title_text.append("CONTROL PLANE ", style="bold white")
        title_text.append(f"| Room: ", style="dim")
        title_text.append(f"@{state.room_name} ", style="bold yellow")
        title_text.append(f"| Task: ", style="dim")
        title_text.append(f"{state.task_id}", style="bold white")

        sub_text = Text(f" {state.status_banner} ", style="bold black on bright_yellow")

        header_table.add_row(
            Text.from_markup(mode_badge),
            title_text,
            Text.from_markup(ledger_badge),
        )
        header_table.add_row("", Align.center(sub_text), "")

        return Panel(
            header_table,
            style="cyan",
            subtitle="In-Flight FinOps Escrow for Autonomous Background Agents",
            subtitle_align="right",
        )

    # -------------------------------------------------------------------------
    # 2. Left Panel: Worker Stream & Burn Bar
    # -------------------------------------------------------------------------
    def render_worker_stream(self, state: CockpitState) -> Panel:
        turns_table = Table(box=None, expand=True, pad_edge=False)
        turns_table.add_column("Turn", justify="center", width=5, style="bold cyan")
        turns_table.add_column("Endpoint", justify="left", style="white")
        turns_table.add_column("Status", justify="center", width=18)
        turns_table.add_column("History", justify="right", width=10)
        turns_table.add_column("Full Req", justify="right", width=10)
        turns_table.add_column("Cost", justify="right", width=9, style="yellow")

        for r in state.turns[-5:]:
            if r.status_code == 422:
                status_text = "[bold white on red] 422 LOOP [/]"
            elif r.status_code == 200:
                status_text = "[bold white on green] 200 SETTLED [/]"
            else:
                status_text = f"[bold yellow] {r.status_code} [/]"

            hist_style = "bold red" if r.history_tokens > 20000 else "green"
            turns_table.add_row(
                f"T{r.turn}",
                r.endpoint,
                status_text,
                f"[{hist_style}]{r.history_tokens:,}[/]",
                f"{r.full_request_tokens:,}",
                f"${r.cost_usd:.4f}",
            )

        # Build Visual Burn Bar
        cap = 100000
        pct = min(100.0, (state.cumulative_tokens / cap) * 100)
        bar_width = 24
        filled = int((pct / 100.0) * bar_width)
        empty = bar_width - filled

        if pct < 30:
            bar_color = "green"
        elif pct < 70:
            bar_color = "yellow"
        else:
            bar_color = "red"

        burn_bar = f"[{bar_color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

        burn_text = Text.from_markup(
            f"\n[bold]Cumulative FinOps Burn:[/]\n"
            f"Tokens: [bold {bar_color}]{state.cumulative_tokens:,}[/] / {cap:,} ({pct:.1f}% safety cap)\n"
            f"Burn Bar: {burn_bar}  Total: [bold yellow]${state.cumulative_cost_usd:.4f}[/]\n"
            f"Rate: [dim]Quadratic input accumulation arrested by circuit breaker.[/]"
        )

        stream_layout = Table.grid(expand=True)
        stream_layout.add_row(turns_table)
        stream_layout.add_row(burn_text)

        return Panel(
            stream_layout,
            title="[bold green]Worker Stream & FinOps Telemetry[/]",
            border_style="green",
        )

    # -------------------------------------------------------------------------
    # 3. Right Panel: Escrow & Context Surgeon View
    # -------------------------------------------------------------------------
    def render_escrow_surgeon(self, state: CockpitState) -> Panel:
        # Escrow status formatting
        state_upper = state.escrow_state.upper()
        if state_upper == "PENDING":
            state_markup = "[bold black on yellow] ⏸ PENDING HUMAN APPROVAL [/]"
        elif state_upper == "APPROVED":
            state_markup = "[bold white on green] ✔ APPROVED / UNLOCKED [/]"
        elif state_upper == "REJECTED":
            state_markup = "[bold white on red] ✖ REJECTED / HALTED [/]"
        else:
            state_markup = "[dim]● IDLE / MONITORING[/]"

        escrow_table = Table.grid(expand=True)
        escrow_table.add_column(ratio=1)

        escrow_info = Text.from_markup(
            f"[bold cyan]Escrow ID:[/] `{state.escrow_id or 'none'}`   State: {state_markup}\n"
            f"[bold cyan]Change Hash:[/] [bold bright_yellow]{state.change_hash}[/] (8-char SHA-256)\n"
            f"[bold cyan]Trip Trigger:[/] [dim]{state.trip_reason}[/]\n"
            f"[bold cyan]Required Room Command:[/] [bold green]APPROVE {state.escrow_id} {state.change_hash}[/]\n"
        )
        escrow_table.add_row(escrow_info)

        # Context Surgery Gauge
        if state.surgery_performed:
            reduction = state.reduction_pct
            saved_tokens = state.tokens_before - state.tokens_after

            # Visual compression bars
            b_width = 22
            before_bar = "[red]" + "█" * b_width + "[/]"
            after_ratio = max(1, int((state.tokens_after / state.tokens_before) * b_width))
            after_bar = "[green]" + "█" * after_ratio + "[/][dim]" + "░" * (b_width - after_ratio) + "[/]"

            pair_badge = "[bold green]✔ ATOMIC (tool_use, tool_result)[/]" if state.pair_integrity else "[bold red]FAIL[/]"
            thinking_badge = "[bold green]✔ STRIPPED[/]" if state.thinking_stripped else "[yellow]KEPT[/]"

            surgery_info = Text.from_markup(
                f"[bold magenta]── Context Surgery & Compaction (POST /surgeon/prune) ──[/]\n"
                f"History Before: {before_bar} [bold red]{state.tokens_before:,} tokens[/]\n"
                f"History After:  {after_bar} [bold green]{state.tokens_after:,} tokens[/] "
                f"([bold bright_green]{reduction:.1f}% reduction[/] | [green]-{saved_tokens:,}[/])\n"
                f"Full Request (count_tokens): [dim]{state.full_before:,}[/] ➔ [bold green]{state.full_after:,}[/] tokens\n"
                f"Validation: {pair_badge} | Thinking: {thinking_badge}\n"
                f"Directive: [italic dim]Closed trailing turn with failed_attempts summary.[/]"
            )
        else:
            surgery_info = Text.from_markup("[dim]No context surgery performed yet. Worker history intact.[/]")

        escrow_table.add_row(surgery_info)

        return Panel(
            escrow_table,
            title="[bold magenta]Escrow Gate & Context Surgeon View[/]",
            border_style="magenta",
        )

    # -------------------------------------------------------------------------
    # 4. Bottom Panel: Vaccine Registry & Rolling Ledger Feed
    # -------------------------------------------------------------------------
    def render_bottom_panel(self, state: CockpitState) -> Panel:
        bottom_table = Table.grid(expand=True)
        bottom_table.add_column(ratio=3)
        bottom_table.add_column(ratio=2)

        # Left Column: Vaccine Registry Table
        vaccines_table = Table(
            title="[bold cyan]Active Vaccine Registry (In-Memory Pre-Send Intercept)[/]",
            box=None,
            expand=True,
            title_justify="left",
            pad_edge=False,
        )
        vaccines_table.add_column("Vaccine ID", style="bold white", width=12)
        vaccines_table.add_column("Match Pattern", style="red", width=16)
        vaccines_table.add_column("Rewrite Target", style="green", width=16)
        vaccines_table.add_column("Mode", width=10)
        vaccines_table.add_column("Latency (p50 / p99)", style="dim", justify="right")

        if state.vaccines:
            for v in state.vaccines:
                mode_str = "[bold green]ENFORCE[/]" if v.mode == "ENFORCE" else "[bold yellow]SHADOW[/]"
                vaccines_table.add_row(
                    v.vaccine_id,
                    v.match_pattern,
                    v.rewrite_target,
                    mode_str,
                    f"{v.p50_us:.1f}μs / {v.p99_us:.1f}μs",
                )
        else:
            vaccines_table.add_row(
                "None", "No rules registered", "-", "[dim]IDLE[/]", "-"
            )

        # Right Column: Rolling Ledger Feed Table
        ledger_table = Table(
            title=f"[bold green]Anchored SQLite Ledger (Head: {state.ledger_head_hash[:8]}...)[/]",
            box=None,
            expand=True,
            title_justify="left",
            pad_edge=False,
        )
        ledger_table.add_column("Seq", style="bold cyan", width=5)
        ledger_table.add_column("Event", style="white", width=22)
        ledger_table.add_column("Entry SHA-256", style="dim", width=16)
        ledger_table.add_column("Anchor", justify="center", width=8)

        if state.ledger_feed:
            for item in state.ledger_feed[-4:]:
                anchor_badge = "[green]✔ ROOM[/]" if item.room_anchored else "[yellow]PENDING[/]"
                ledger_table.add_row(
                    f"#{item.seq_no}",
                    item.event_type,
                    f"{item.entry_hash[:12]}..",
                    anchor_badge,
                )
        else:
            ledger_table.add_row(f"#{state.ledger_seq}", "INIT_BOOTSTRAP", f"{state.ledger_head_hash[:12]}..", "[green]✔ ROOM[/]")

        bottom_table.add_row(vaccines_table, ledger_table)

        return Panel(
            bottom_table,
            title="[bold blue]Fleet Defense: Vaccine Registry & Tamper-Evident Ledger Feed[/]",
            border_style="blue",
        )

    # -------------------------------------------------------------------------
    # Render Complete Cockpit
    # -------------------------------------------------------------------------
    def update(self, state: CockpitState) -> Layout:
        """Updates and returns the complete 4-panel layout with the provided state."""
        self.layout["header"].update(self.render_header(state))
        self.layout["left"].update(self.render_worker_stream(state))
        self.layout["right"].update(self.render_escrow_surgeon(state))
        self.layout["bottom"].update(self.render_bottom_panel(state))
        return self.layout

    def render_once(self, state: CockpitState) -> None:
        """Renders a single snapshot of the cockpit to console."""
        self.console.print(self.update(state))


    def stream_live(self, duration_sec: float = 6.0, fps: int = 4) -> None:
        """
        Runs an interactive Live simulation of the 4-panel telemetry cockpit,
        demonstrating the circuit trip, context surgery, and vaccine promotion in real time.
        """
        state = CockpitState(
            mode="SELFTEST",
            room_name="sb-switchblade",
            ledger_status="VERIFIED",
            ledger_seq=10,
            ledger_head_hash="10928374aefb3829102938475610293847561029384756102938475610293847",
            task_id="task-order-9901",
            cumulative_tokens=0,
            cumulative_cost_usd=0.0,
            turns=[],
            escrow_id=None,
            escrow_state="IDLE",
            change_hash="8f4b2a1c",
            surgery_performed=False,
            status_banner="Monitoring worker stream on /v1/orders...",
        )

        steps = [
            # Step 1: Turn 1 422 error
            {
                "banner": "Turn 1: Worker calling POST /v1/orders -> HTTP 422 Unprocessable Entity",
                "turn": WorkerTurnRecord(1, "sync_customer_order", "POST /v1/orders", 422, 15000, 18500, 0.2250),
                "cum_tok": 15000,
                "cum_cost": 0.2250,
                "escrow_state": "IDLE",
                "surgery": False,
                "ledger_seq": 11,
                "event": "TOOL_ERROR_422",
            },
            # Step 2: Turn 2 422 error
            {
                "banner": "Turn 2: Agent retries without schema fix -> Cumulative input tokens doubling",
                "turn": WorkerTurnRecord(2, "sync_customer_order", "POST /v1/orders", 422, 30100, 33600, 0.4515),
                "cum_tok": 45100,
                "cum_cost": 0.6765,
                "escrow_state": "IDLE",
                "surgery": False,
                "ledger_seq": 12,
                "event": "TOOL_ERROR_422",
            },
            # Step 3: Turn 3 422 error & Escrow Trip
            {
                "banner": "Turn 3: 3x 422 Loop! CIRCUIT BREAKER TRIPPED -> Worker paused in ESCROW",
                "turn": WorkerTurnRecord(3, "sync_customer_order", "POST /v1/orders", 422, 45200, 48700, 0.6780),
                "cum_tok": 90300,
                "cum_cost": 1.3545,
                "escrow_state": "PENDING",
                "escrow_id": "esc-9901-trip",
                "surgery": False,
                "ledger_seq": 13,
                "event": "ESCROW_TRIPPED",
            },
            # Step 4: Context Surgery
            {
                "banner": "Context Surgery: @sb-surgeon prunes failed turns (45.2k -> 380 tokens, 99.2% saved)",
                "turn": None,
                "cum_tok": 90300,
                "cum_cost": 1.3545,
                "escrow_state": "PENDING",
                "escrow_id": "esc-9901-trip",
                "surgery": True,
                "ledger_seq": 14,
                "event": "CONTEXT_SURGERY_COMPLETE",
            },
            # Step 5: Room Approval & Vaccine Promotion
            {
                "banner": "Room Approval: Human posted APPROVE esc-9901-trip 8f4b2a1c -> VACCINE-042 ENFORCE",
                "turn": WorkerTurnRecord(4, "sync_customer_order", "POST /v2/orders", 200, 380, 3680, 0.0552),
                "cum_tok": 90680,
                "cum_cost": 1.4097,
                "escrow_state": "APPROVED",
                "escrow_id": "esc-9901-trip",
                "surgery": True,
                "vaccine": VaccineDisplayRecord("VACCINE-042", "POST /v1/orders", "POST /v2/orders", "ENFORCE", 1.2, 4.8, 1),
                "ledger_seq": 15,
                "event": "VACCINE_PROMOTED",
            },
        ]

        with Live(self.layout, console=self.console, refresh_per_second=fps, screen=False) as live:
            self.update(state)
            live.refresh()
            time.sleep(1.0)

            for step in steps:
                state.status_banner = step["banner"]
                if step.get("turn"):
                    state.turns.append(step["turn"])
                state.cumulative_tokens = step["cum_tok"]
                state.cumulative_cost_usd = step["cum_cost"]
                state.escrow_state = step["escrow_state"]
                if step.get("escrow_id"):
                    state.escrow_id = step["escrow_id"]
                state.surgery_performed = step["surgery"]
                if step.get("vaccine"):
                    state.vaccines = [step["vaccine"]]

                state.ledger_seq = step["ledger_seq"]
                new_hash = f"sha256_{step['ledger_seq']}_{int(time.time())}"
                state.ledger_feed.append(LedgerDisplayRecord(step["ledger_seq"], step["event"], new_hash))

                self.update(state)
                live.refresh()
                time.sleep(duration_sec / len(steps))


def create_demo_state() -> CockpitState:
    """Builds a realistic default demonstration state for testing the cockpit."""
    state = CockpitState(
        mode="SELFTEST",
        room_name="sb-switchblade",
        ledger_status="VERIFIED",
        ledger_seq=15,
        ledger_head_hash="a37f81b2c90e14589d71b3e9447a112048cd4f91048e920d9124159f81a7b8e1",
        task_id="task-order-9901",
        cumulative_tokens=45200,
        cumulative_cost_usd=0.6780,
        turns=[
            WorkerTurnRecord(1, "sync_customer_order", "POST /v1/orders", 422, 15000, 18500, 0.2250),
            WorkerTurnRecord(2, "sync_customer_order", "POST /v1/orders", 422, 30100, 33600, 0.4515),
            WorkerTurnRecord(3, "sync_customer_order", "POST /v1/orders", 422, 45200, 48700, 0.6780),
        ],
        escrow_id="esc-9901-trip",
        escrow_state="PENDING",
        change_hash="8f4b2a1c",
        trip_reason="3x 422 loop on /v1/orders (Missing X-Tenant-ID / Deprecated API)",
        surgery_performed=True,
        tokens_before=45200,
        tokens_after=380,
        full_before=48500,
        full_after=3680,
        reduction_pct=99.2,
        pair_integrity=True,
        thinking_stripped=True,
        vaccines=[
            VaccineDisplayRecord(
                vaccine_id="VACCINE-042",
                match_pattern="POST /v1/orders",
                rewrite_target="POST /v2/orders",
                mode="ENFORCE",
                p50_us=1.2,
                p99_us=4.8,
                times_intercepted=1,
            )
        ],
        ledger_feed=[
            LedgerDisplayRecord(12, "CIRCUIT_BREAKER_TRIPPED", "3a91c10d54ef"),
            LedgerDisplayRecord(13, "CONTEXT_SURGERY_PRUNED", "9f82bc01481e"),
            LedgerDisplayRecord(14, "DRY_RUN_VERIFIED", "e710bca3810d"),
            LedgerDisplayRecord(15, "LEDGER_CHECKPOINT", "a37f81b2c90e"),
        ],
        status_banner="Escrow PENDING — Awaiting room command: APPROVE esc-9901-trip 8f4b2a1c",
    )
    return state


if __name__ == "__main__":
    import sys
    cockpit = SwitchBladeCockpit()
    if "--animate" in sys.argv:
        cockpit.stream_live(duration_sec=3.0, fps=5)
    else:
        demo_state = create_demo_state()
        cockpit.render_once(demo_state)
