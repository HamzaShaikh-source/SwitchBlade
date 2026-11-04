---
name: switchblade-builder
description: Audited, zero-drift technical specification and phase-aware workflow for building SwitchBlade (Self-Healing Runtime & FinOps Escrow for AI Agents) for the Flip the Switch Hackathon. Use whenever generating code, configuring Switch room templates, writing proxy/circuit-breaker logic, implementing context surgery, building the terminal UI, or integrating the full repo on main.
---
# SwitchBlade Builder Skill (Antigravity Master Guardrails)

Build **SwitchBlade** strictly around **[Switch](https://www.wemakedevs.org/hackathons/switch) as the active control plane**, following the hardened v2 architecture.

## 1. Phase-Aware Branch & File Access (Flexible Across Days 1–4)

Adapt your file scope to the current Git branch or the user's explicit instruction—**never refuse to edit a file when the user asks you to integrate, debug, or polish across the repo**:

- **Phase A — Parallel Feature Branch Mode (Days 1–2)**:
  - When on a member's feature branch, prioritize that member's core files while keeping shared contracts in `schemas.py` compatible:
    - **`feat/santosh-proxy-ledger` (Santosh — Core Runtime & Ledger Lead)**: Prioritize `schemas.py`, `proxy.py`, `ledger.py`, `verify_ledger.py`.
    - **`feat/hamza-cockpit-ui` (Hamza — Frontend & Telemetry Lead)**: Prioritize `ui/cockpit.py`, `ui/room_cards.py`, `run_demo.py`, `bench/run_bench.py`, `bench/results.json`, `README.md`.
    - **`feat/aaditya-switch-bridge` (Aaditya — Switch Control Plane Lead)**: Prioritize `switchblade.template.yaml`, `switch_bridge.py`, `.env.example`.
    - **`feat/janani-agents-vaccine` (Janani — AI Agents, Vaccine & Mock API Lead)**: Prioritize `mock_billing_api.py`, `context_surgeon.py`, `vaccine_registry.py`, `vaccines.json`, `worker_agent.py`, `tools/orders_tool.py`, `test_suite.py`.
- **Phase B — Full-Repo Integration & Bugfix Mode (Days 3–4 / on `main` or when requested)**:
  - When working on `main`, an integration branch, or whenever the user asks to wire modules together, fix cross-file bugs, run end-to-end benchmarks, or prepare the demo, **you have full permission to read and edit ANY file in the repository**.

## 2. Non-Negotiable Architectural & Security Guardrails (Anti-Drift)

These rules prevent architectural drift (building the wrong product) while leaving you free to edit any file in the repo:

1. **Switch Is the Control Plane (Never a Passive Notification Sink)**:
   - Every circuit trip, context compaction, dry-run proposal, hash-bound approval (`APPROVE <escrow_id> <change_hash>`), rejection (`REJECT <escrow_id> <reason>`), vaccine promotion (`SHADOW` $\rightarrow$ `ENFORCE`), and ledger checkpoint (`LEDGER_CHECKPOINT seq=<n> head_hash=<h>`) MUST flow through the Switch room.
   - Even automated test runs (`--mode replay` or scripted room tests) must drive the Switch room via a scripted `@policy-bot` user rather than bypassing Switch locally.
   - Do not build a standalone React/Next.js web chat UI that competes with Switch; the visual interfaces are the **Switch room** (Mattermost/Slack) + the **`Rich` terminal telemetry cockpit** (`ui/cockpit.py` & `run_demo.py`).
2. **Use Current Switch WebSocket Protocol & Valid v1 Template Schema**:
   - **Template**: `switchblade.template.yaml` MUST include a top-level `params:` block and every agent MUST define `provider`, `machine` (or `location`), `directory`, and hyphenated `addressing` (`anyone`, `owner-agents`, `owner`) per [TEMPLATES.md](https://www.google.com/search?q=https://raw.githubusercontent.com/sandbox-quantum/switch/main/docs/TEMPLATES.md).
   - **Transport**: Build `switch_bridge.py` on the WebSocket endpoint `/agents/{id}/connection/ws` and HTTP operations `/agents/{id}/ops/{operation}` ([Agent connection](https://www.google.com/search?q=https://docs.switchagents.ai/switch-rooms/internals/agent-connection.md); [Agent protocol](https://docs.switchagents.ai/switch-rooms/internals/agent-protocol)), NOT legacy SSE. Deduplicate incoming events by `message_id` and check `event.addressed` ([Agent events](https://docs.switchagents.ai/switch-rooms/internals/agent-events.md)).
3. **Console Agents Call Narrow Proxy Endpoints**:
   - Because template agents (`surgeon`, `scout`, `compiler`) run in separate Switch Console PTYs ([Switch Console internals](https://docs.switchagents.ai/switch-rooms/internals/switch-console.md)), they interact with `proxy.py` (`:8002`) by calling narrow, idempotent HTTP endpoints keyed by `escrow_id`:
     - `POST /surgeon/prune`
     - `POST /scout/dryrun`
     - `POST /compiler/propose`
     - `POST /escrow/decision`
     - `GET /state` (for `ui/cockpit.py` 10 FPS live polling)
4. **Enforce All 4 Vaccine, Dry-Run & Escrow Security Controls**:
   - **Future-Based Escrow State Machine**: Never use `time.sleep()`. Hold paused worker coroutines with a strongly-referenced `Escrow` object (`escrow_id` UUID, state `PENDING` $\rightarrow$ `APPROVED` | `REJECTED` | `EXPIRED` | `CANCELLED`, and `asyncio.Future` registered *before* emitting the room event — [asyncio sync primitives](https://docs.python.org/3/library/asyncio-sync.html)).
   - **No Confused Deputy**: Never hardcode `"X-Tenant-ID": "acme-corp"` in `vaccines.json`. Use `"inject_headers_from_context": {"X-Tenant-ID": "task.tenant_id"}` ([AWS IAM confused deputy](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html)) and fail closed (`VaccineSecurityError`) if `task.tenant_id` is missing. Forbid `Authorization`, `Cookie`, `Host`, and cross-origin URL rewrites.
   - **Pre-Send Exact Matching**: Match vaccines on `(tool_name, http_method, path_template)` *before* sending the request so Turn 1 settles with 0 retries.
   - **Non-Mutating Dry-Run & Idempotency**: `POST /scout/dryrun` must call `/v2/orders?dry_run=true` (or `X-Dry-Run: true` per [KEP-576](https://www.kubernetes.dev/resources/keps/576/)) so dry-runs never double-settle an order. All real calls must attach `Idempotency-Key: sha256(task_id + step_id + canonical_body)` ([Stripe idempotency](https://docs.stripe.com/idempotency)).
   - **Hash-Bound Approval**: Verify `approver_id in HUMAN_ALLOWLIST`, `approver_id not in AGENT_IDS`, and `hmac.compare_digest(escrow.change_hash, submitted_hash)`.
5. **Strict Anthropic Message Validity in Context Surgery (`context_surgeon.py`)**:
   - Delete failed retries as atomic `(tool_use, tool_result)` pairs ([Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)).
   - Close any trailing unanswered `tool_use` with a structured error `tool_result` containing `failed_attempts` (tool, status `422`, count `3`, do-not-retry directive) and `completed_side_effects`.
   - Strip `thinking` blocks when switching model tiers ([Thinking docs](https://platform.claude.com/docs/en/build-with-claude/thinking)), and assert `tool_use_id` set equality and role alternation before every resume call.
6. **Canonical Ledger & Measured Benchmarks**:
   - **Ledger (`ledger.py`)**: Use canonical JSON (`sort_keys=True, separators=(",", ":")`), monotonic `seq_no`, domain prefix `SWITCHBLADE-LEDGER-V1`, and SQLite `BEGIN IMMEDIATE`. Post `LEDGER_CHECKPOINT seq=<n> head_hash=<h>` to the Switch room every 5 events.
   - **Benchmarks (`bench/run_bench.py` $\rightarrow$ `bench/results.json`)**: Compute all token reductions (history-only `99.2%` and full-request via `count_tokens` — [Token counting docs](https://platform.claude.com/docs/en/build-with-claude/token-counting)), USD costs (from real API `usage` fields), and rewrite latencies (`time.perf_counter_ns()` p50/p99 microseconds over 10k runs — [time docs](https://docs.python.org/3/library/time.html)) from code, never hardcoded strings.

## 3. Repository Structure & Contracts Reference

```text
switchblade/
├── .env.example                # SWITCH_API_URL, SWITCH_AGENT_TOKEN, ANTHROPIC_API_KEY, HUMAN_ALLOWLIST
├── requirements.txt            # fastapi, uvicorn, httpx, websockets, rich, pyyaml, pydantic, anthropic
├── switchblade.template.yaml   # Official v1 Switch template (params, provider, machine, directory, addressing)
├── schemas.py                  # Shared Pydantic models: TaskContext, EscrowRecord, Decision, VaccineRule, LedgerEntry
├── proxy.py                    # FastAPI (:8002): Future-based Escrow state machine + narrow agent & UI endpoints
├── ledger.py                   # Canonical-JSON, seq_no, BEGIN IMMEDIATE SQLite chain + room checkpoint post
├── verify_ledger.py            # Verifies internal hash chain + external room checkpoint + --tamper-demo
├── switch_bridge.py            # WebSocket client (/agents/{id}/connection/ws) + HTTP ops (/agents/{id}/ops/{op})
├── mock_billing_api.py         # FastAPI (:8001): seeded orders 9901 & 9902, ?dry_run=true, Idempotency-Key, /openapi.json
├── context_surgeon.py          # Atomic tool_use/tool_result pruner, thinking stripper, validator, count_tokens
├── vaccine_registry.py         # JSON Schema validator, context-bound tenant header resolver, TTL & denylist
├── vaccines.json               # Vaccine store (writable ONLY by proxy.py after hash-bound approval)
├── worker_agent.py             # Real Anthropic tool-use worker running seeded orders 9901 and 9902
├── tools/
│   └── orders_tool.py          # Tool file calling /v1/orders (patched via safe argv git branch / pr_draft.md)
├── ui/
│   ├── cockpit.py              # 4-panel Rich live terminal UI polling GET /state at 10 FPS
│   └── room_cards.py           # Scannable 4-line Markdown cards posted into the Switch room
├── bench/
│   ├── run_bench.py            # Runs unguarded control vs SwitchBlade + 10k perf_counter_ns() rewrite loop
│   └── results.json            # Committed benchmark results read by README.md and run_demo.py
├── test_suite.py               # Automated unit tests for pair validity, confused-deputy block, and ledger tamper
└── run_demo.py                 # Explicitly labeled --mode live, --mode replay, and --mode selftest
```

## 4. Verification Checklist (Run After Changes)

1. **Template Schema Check**:
   `python3 -c "import yaml; d=yaml.safe_load(open('switchblade.template.yaml')); assert 'params' in d and all('directory' in a and 'machine' in a for a in d['agents'])"`
2. **Context Surgeon & Security Unit Suite**:
   `python3 test_suite.py` (Verifies atomic `tool_use`/`tool_result` pairing, `thinking` stripping, `dry_run=true` non-mutation, and `VaccineSecurityError` on missing `task.tenant_id`).
3. **Ledger Tamper & Truncation Check**:
   `python3 verify_ledger.py --tamper-demo` (Verifies clean DB passes `100%` and tampered/truncated DB exits `1`).
4. **End-to-End Self-Test**:
   `python3 run_demo.py --mode selftest` (Verifies Order `#9901` trips at retry #3, prunes context, validates dry-run, approves with matching `change_hash`, settles `#9901`, and pre-send vaccinates Order `#9902` on Turn 1).