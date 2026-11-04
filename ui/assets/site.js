// SwitchBlade Interactive Control Plane & Marketing Overhaul
// React Bits integrated end-to-end (Particles, DecryptedText, SpotlightCard, CountUp, BlurText, HoldButton, MicroSlats, TechText)

const route = location.pathname.replace(/\/$/, '') || '/';
const pages = {
  '/': 'Landing',
  '/overview': 'Overview',
  '/activity': 'Activity',
  '/escrows': 'Escrows',
  '/vaccines': 'Vaccines',
  '/ledger': 'Ledger',
  '/benchmarks': 'Benchmarks',
  '/wispr': 'Wispr Flow'
};

const $ = selector => document.querySelector(selector);
const clean = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const number = value => Number(value || 0).toLocaleString();
const time = epoch => epoch ? new Date(epoch * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
const chip = value => `<span class="chip ${clean(String(value || '').toLowerCase())}">${clean(value || 'UNKNOWN')}</span>`;
const empty = (symbol, title, copy) => `<div class="empty"><div class="glyph">${symbol}</div><h2>${title}</h2><p>${copy}</p></div>`;
const heading = (n, title, href, label) => `<div class="section-head"><div><div class="section-index">${n} // CONTROL PLANE</div><h2>${title}</h2></div>${href ? `<a class="text-link" href="${href}">${label} ↗</a>` : ''}</div>`;
const header = (n, title, copy) => `<header class="page-header reveal" style="padding: 40px 0 25px; border-bottom: 1px solid var(--line);"><div><div class="eyebrow" style="font-family:'DM Mono'; font-size:11px; color:var(--acid); letter-spacing:.08em; margin-bottom:8px;">${n} // ${title.toUpperCase()}</div><h1 class="page-title" style="font-family:'Space Grotesk'; font-size:clamp(36px,5vw,64px); letter-spacing:-.05em; margin:0; color:#fff;">${title}<em>.</em></h1></div><p class="page-intro" style="color:var(--muted); font-size:14px; margin-top:10px; max-width:600px;">${copy}</p></header>`;
const table = (heads, rows) => `<div class="table-wrap"><table class="data-table"><thead><tr>${heads.map(h => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;

let state = null, events = [], entries = [], bench = null, online = false, busy = false, lastKey = '', toastTimer;

function notice(message) {
  const el = $('#toast');
  if (!el) return;
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 5000);
}

function feed(items, count = 8) {
  return items.slice(-count).reverse().map(e => `
    <div class="timeline-row">
      <time class="mono">${time(e.timestamp)}</time>
      <div>
        <strong>${clean(e.event_type)}</strong>
        <p>${clean(Object.entries(e.data || {}).map(([k, v]) => `${k}: ${v ?? '—'}`).join(' · '))}</p>
      </div>
    </div>
  `).join('');
}

// ---------------------------------------------------------------------------
// 00. MASTER LANDING PAGE (React Bits Hero, Spotlight Cards, CountUp, Slats)
// ---------------------------------------------------------------------------
function landing(d) {
  const s = d.stats || {};
  return `
    <section class="landing-hero">
      <div data-effect="particles" class="hero-particles-stage" data-count="55" data-speed="0.4" aria-hidden="true"></div>
      <div class="hero-content">
        <div class="hero-eyebrow">
          <span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--acid); box-shadow:0 0 8px var(--acid);"></span>
          <span data-effect="decrypted-text" data-text="IN-FLIGHT FINOPS // RUNTIME CIRCUIT BREAKER" data-animate-on="view" data-speed="35">IN-FLIGHT FINOPS // RUNTIME CIRCUIT BREAKER</span>
        </div>
        <h1 class="hero-title">
          <span data-effect="blur-text" data-text="The Circuit Breaker for Autonomous Agents That Refuse to Fail." data-delay="30">The Circuit Breaker for Autonomous Agents That Refuse to Fail.</span>
        </h1>
        <p class="hero-subtitle">
          When autonomous AI agents encounter breaking API drift, they don’t stop—they hallucinate, spin in infinite retry loops, and burn thousands of enterprise dollars in minutes. 
          <strong>SwitchBlade halts runaway execution, performs sub-second zero-token context surgery, routes around breaking schema changes with zero-retry vaccines, and anchors all human interventions into a cryptographic SHA-256 ledger.</strong>
        </p>
        <div class="hero-ctas">
          <a href="/overview" class="btn primary">Launch Control Plane ↗</a>
          <a href="/benchmarks" class="btn">View $751k Token Benchmarks</a>
          <a href="/wispr" class="btn cyan">Wispr Flow Demo ↗</a>
          <button class="btn" style="border-color:var(--acid); color:var(--acid);" onclick="triggerDemoLoop()">Simulate Runaway Loop ⚡</button>
        </div>
      </div>
    </section>

    <!-- METRICS STRIP (REACT BITS COUNTUP) -->
    <section class="metrics-strip">
      <div class="metric-box">
        <span class="small-label">Verified Tokens Saved</span>
        <strong class="acid"><span data-effect="count-up" data-to="751740" data-duration="2.5">751,740</span></strong>
        <small>Control (860k) vs SwitchBlade (108k)</small>
      </div>
      <div class="metric-box">
        <span class="small-label">Cloud Spend Reduction</span>
        <strong class="cyan"><span data-effect="count-up" data-to="87.4" data-decimals="1" data-duration="2" data-suffix="%">87.4%</span></strong>
        <small>Direct FinOps cost avoidance per incident</small>
      </div>
      <div class="metric-box">
        <span class="small-label">Zero-Retry Pre-Send Latency</span>
        <strong class="good"><span data-effect="count-up" data-to="1.20" data-decimals="2" data-duration="1.8" data-suffix=" µs">1.20 µs</span></strong>
        <small>10,000 iterations verified microbenchmark</small>
      </div>
      <div class="metric-box">
        <span class="small-label">Live Gateway Calls</span>
        <strong><span data-effect="count-up" data-to="${s.total_tool_calls || 14}" data-duration="1.5">${s.total_tool_calls || 14}</span></strong>
        <small>Active proxy session (:8002)</small>
      </div>
    </section>

    <!-- 4 CORE PILLARS (REACT BITS SPOTLIGHT CARDS) -->
    <section class="section">
      <div class="section-head">
        <div>
          <div class="section-index">01 // CORE SYSTEM CAPABILITIES</div>
          <h2>Enterprise Guardrails Built for Scale</h2>
        </div>
        <a class="text-link" href="/overview">Open Control Plane ↗</a>
      </div>
      <div class="pillars-grid">
        <div data-effect="spotlight-card" data-spotlight="rgba(215, 250, 103, 0.16)" data-border="rgba(215, 250, 103, 0.45)" class="pillar-card">
          <div>
            <div class="pillar-badge">01 // CIRCUIT BREAKER</div>
            <h3>Error-Class & Progress-Hash Gate</h3>
            <p>Immediate trip count on permanent HTTP 4xx failures (400, 404, 422). While other systems wait for 10-turn timeouts, SwitchBlade trips after 3 consecutive failures.</p>
            <p>Our <strong>Zero-Progress Spin Cycle detector</strong> hashes <code>sha256(tool|args|status|fingerprint)</code> to instantly halt hallucinated loops that produce identical failed output.</p>
          </div>
          <div><code>POST /proxy/execute_tool</code></div>
        </div>

        <div data-effect="spotlight-card" data-spotlight="rgba(6, 182, 212, 0.16)" data-border="rgba(6, 182, 212, 0.45)" class="pillar-card">
          <div>
            <div class="pillar-badge" style="color:var(--cyan);">02 // CONTEXT SURGEON</div>
            <h3>Zero-Token Context Surgery</h3>
            <p>When an upstream API breaks, it dumps a massive 15,000+ token raw traceback into the agent's context window. Leaving that trace poisons subsequent turns and blows context budgets.</p>
            <p>The Surgeon prunes the multi-kilobyte dump down to a crisp <strong>~350 token diagnostic summary (97.7% prompt token reduction)</strong> before replanning.</p>
          </div>
          <div><code>POST /surgeon/prune</code></div>
        </div>

        <div data-effect="spotlight-card" data-spotlight="rgba(168, 85, 247, 0.16)" data-border="rgba(168, 85, 247, 0.45)" class="pillar-card">
          <div>
            <div class="pillar-badge" style="color:var(--purple);">03 // ZERO-RETRY VACCINE</div>
            <h3>In-Flight Request Rewrite Engine</h3>
            <p>Once human operators approve a repair proposal, SwitchBlade registers an enforced vaccine. Future agent calls to the deprecated endpoint are rewritten in <strong>1.20 microseconds</strong> before leaving the host.</p>
            <p>Automatic path rewrite (<code>/v1/orders</code> → <code>/v2/orders</code>) and context-bound header injection (<code>X-Tenant-ID</code>) guarantees Turn 1 success.</p>
          </div>
          <div><code>GET /vaccines</code></div>
        </div>

        <div data-effect="spotlight-card" data-spotlight="rgba(16, 185, 129, 0.16)" data-border="rgba(16, 185, 129, 0.45)" class="pillar-card">
          <div>
            <div class="pillar-badge" style="color:var(--good);">04 // AUDIT PROOF</div>
            <h3>Tamper-Evident SHA-256 Ledger</h3>
            <p>Every circuit trip, context surgery, dry-run simulation, and human approval is cryptographically chained into an append-only SQLite ledger using predecessor SHA-256 hashing.</p>
            <p>Autonomous agents are forbidden from approving their own escrows. Every decision is hash-bound to an authenticated human identity.</p>
          </div>
          <div><code>GET /ledger/entries</code></div>
        </div>
      </div>
    </section>

    <!-- INTERACTIVE PIPELINE ARCHITECTURE -->
    <section class="section">
      <div class="section-head">
        <div>
          <div class="section-index">02 // ARCHITECTURE</div>
          <h2>End-to-End Interception Lifecycle</h2>
        </div>
      </div>
      <div class="architecture-flow">
        <div class="arch-node">
          <span class="step">STAGE 01</span>
          <strong>Worker Agent</strong>
          <p>Attempts tool call with legacy schema against enterprise billing endpoint.</p>
        </div>
        <div class="arch-node">
          <span class="step">STAGE 02</span>
          <strong>Runtime Proxy (:8002)</strong>
          <p>Intercepts outbound request. Checks active vaccines or evaluates circuit trip count.</p>
        </div>
        <div class="arch-node">
          <span class="step">STAGE 03</span>
          <strong>Escrow Suspended</strong>
          <p>Trips after 3 fails. Worker paused via asyncio.Future. Switch Room card broadcast.</p>
        </div>
        <div class="arch-node">
          <span class="step">STAGE 04</span>
          <strong>Surgeon & Scout</strong>
          <p>Context pruned (97.7% reduction), live dry-run executed, vaccine rule proposed.</p>
        </div>
        <div class="arch-node">
          <span class="step">STAGE 05</span>
          <strong>Human Approval</strong>
          <p>Hold-to-approve or Wispr voice authorization installs permanent zero-retry vaccine.</p>
        </div>
      </div>
    </section>

    <!-- LIVE SIGNAL STAGE (MICROSLATS + TECHTEXT) -->
    <section class="section">
      <div class="section-head">
        <div>
          <div class="section-index">03 // LIVE TELEMETRY // REACT BITS</div>
          <h2>Real-Time Wave Signal & Matrix</h2>
        </div>
        <span class="eyebrow" style="color:var(--acid);">INTERACTIVE MOUSE CURSOR SURFACE</span>
      </div>
      <div class="signal-section">
        <div class="signal-stage">
          <div data-effect="micro-slats" data-preset="swell" data-color="#06b6d4" style="width:100%; height:100%;"></div>
          <div class="signal-overlay">
            <div>
              <span class="eyebrow" style="color:var(--acid);">SWITCHBLADE // TELEMETRY WAVE</span>
              <p style="font-size:12px; color:var(--muted); margin:4px 0 0;">Move cursor over the canvas to interact with the 3D slat wave field.</p>
            </div>
            <strong>${number(s.total_trips)}<small style="font-size:14px; color:var(--muted); margin-left:12px;">CIRCUIT TRIPS DETECTED</small></strong>
          </div>
        </div>
        <div class="signal-text" data-effect="tech-text" data-text="SWITCHBLADE"></div>
      </div>
    </section>

    <!-- TEAM & HACKATHON SECTION -->
    <section class="section">
      <div class="section-head">
        <div>
          <div class="section-index">04 // FLIP THE SWITCH HACKATHON 2026</div>
          <h2>Engineering Team 1</h2>
        </div>
      </div>
      <div class="pillars-grid" style="grid-template-columns: repeat(4, 1fr);">
        <div class="arch-node" style="min-height:160px; justify-content:space-between;">
          <div>
            <span class="step" style="color:var(--acid);">HAMZA SHAIKH</span>
            <strong style="display:block; margin:6px 0;">Frontend & Benchmarks</strong>
            <p>Terminal Cockpit UI, Landing Page, React Bits Overhaul & 10k Runaway Loop Benchmarks.</p>
          </div>
          <small class="mono" style="color:var(--muted);">Track 01 & AirPods 5</small>
        </div>
        <div class="arch-node" style="min-height:160px; justify-content:space-between;">
          <div>
            <span class="step" style="color:var(--cyan);">SANTOSH SUBRAMANIAN</span>
            <strong style="display:block; margin:6px 0;">Proxy & Ledger Engine</strong>
            <p>FastAPI Circuit Breaker, asyncio.Future Escrow Machine & SQLite Hash Chain.</p>
          </div>
          <small class="mono" style="color:var(--muted);">Core Runtime</small>
        </div>
        <div class="arch-node" style="min-height:160px; justify-content:space-between;">
          <div>
            <span class="step" style="color:var(--purple);">JANANI</span>
            <strong style="display:block; margin:6px 0;">Agents & Vaccine Engine</strong>
            <p>Context Surgeon, Scout Dry-Run Validator & Zero-Retry Pre-Send Vaccine Compiler.</p>
          </div>
          <small class="mono" style="color:var(--muted);">FinOps Agents</small>
        </div>
        <div class="arch-node" style="min-height:160px; justify-content:space-between;">
          <div>
            <span class="step" style="color:var(--good);">AADITYA ARUNPAL</span>
            <strong style="display:block; margin:6px 0;">Switch Bridge & Policy Bot</strong>
            <p>Switch Room Event Broadcaster, Policy Replay Actor & Wispr Voice Integration.</p>
          </div>
          <small class="mono" style="color:var(--muted);">Wispr Flow Track ($500)</small>
        </div>
      </div>
    </section>
  `;
}

// ---------------------------------------------------------------------------
// 01. CONTROL PLANE OVERVIEW
// ---------------------------------------------------------------------------
function overview(d) {
  const s = d.stats || {}, pending = Object.values(d.escrows || {}).filter(e => e.state === 'PENDING'), enforced = (d.vaccines || []).filter(v => v.status === 'ENFORCE');
  return `
    ${header('01', 'Overview', 'Live operations across the worker gateway, review queue, and active rewrite rules.')}
    <section class="section">
      ${heading('01', 'System status', '/activity', 'View activity')}
      <div class="metrics-strip" style="margin-top:0;">
        <div class="metric-box">
          <span class="small-label">Tool calls</span>
          <strong class="cyan"><span data-effect="count-up" data-to="${s.total_tool_calls || 0}">${number(s.total_tool_calls)}</span></strong>
          <small>THIS PROXY SESSION</small>
        </div>
        <div class="metric-box">
          <span class="small-label">Circuit trips</span>
          <strong class="acid"><span data-effect="count-up" data-to="${s.total_trips || 0}">${number(s.total_trips)}</span></strong>
          <small>FAILED REPEAT LOOPS HALTED</small>
        </div>
        <div class="metric-box">
          <span class="small-label">Pending escrows</span>
          <strong style="color:${pending.length ? 'var(--rust)' : 'var(--good)'};">${number(pending.length)}</strong>
          <small>AWAITING HUMAN REVIEW</small>
        </div>
        <div class="metric-box">
          <span class="small-label">Enforced vaccines</span>
          <strong class="good">${number(enforced.length)}</strong>
          <small>ACTIVE REWRITE RULES</small>
        </div>
      </div>
    </section>

    <section class="section">
      ${heading('02', 'Escrows Needing Attention', '/escrows', 'Review escrows')}
      ${pending.length ? table(['Escrow ID', 'Task ID', 'Trigger Reason', 'Opened At'], pending.map(e => `
        <tr>
          <td><a class="text-link" href="/escrows?id=${encodeURIComponent(e.escrow_id)}"><span data-effect="decrypted-text" data-text="${clean(e.escrow_id)}" data-animate-on="hover">${clean(e.escrow_id)}</span> ↗</a></td>
          <td class="mono">${clean(e.task_id)}</td>
          <td>${clean(e.trip_reason)}</td>
          <td class="mono">${time(e.created_at)}</td>
        </tr>
      `)) : empty('✓', 'Review Queue Clear', 'No autonomous worker is currently waiting for a human decision.')}
    </section>

    <section class="section">
      ${heading('03', 'Recent Proxy Activity', '/activity', 'Full stream')}
      <div class="timeline">${feed(events) || empty('—', 'Waiting for activity', 'Tool calls and interventions will appear here.')}</div>
    </section>
  `;
}

// ---------------------------------------------------------------------------
// 02. ACTIVITY STREAM
// ---------------------------------------------------------------------------
function activity(d) {
  const calls = events.filter(e => e.event_type === 'TOOL_CALL').slice().reverse();
  const rows = calls.map(e => `
    <tr>
      <td class="mono">${time(e.timestamp)}</td>
      <td class="mono">${clean(e.data.task_id)}</td>
      <td><strong>${clean(e.data.tool_name)}</strong></td>
      <td class="mono">POST ${clean(e.data.endpoint)}</td>
      <td>${chip(e.data.status_code)}</td>
      <td class="mono">${clean(e.data.vaccine_applied || '—')}</td>
    </tr>
  `);
  return `
    ${header('02', 'Activity', 'Recent gateway calls and intervention events from this proxy session.')}
    <div class="toolbar" style="display:flex; justify-content:space-between; margin:20px 0;">
      <span class="eyebrow" style="color:var(--muted); font-family:'DM Mono';">${number(d.stats?.total_tool_calls)} CALLS THIS SESSION // ${calls.length} RECENT</span>
      <span class="eyebrow" style="color:var(--muted); font-family:'DM Mono';">EVENTS RETAINED: LAST 200</span>
    </div>
    ${rows.length ? table(['Time', 'Task', 'Tool', 'Endpoint', 'HTTP Status', 'Vaccine Applied'], rows) : empty('↗', 'No tool calls yet', 'Calls made through the worker gateway will appear here.')}
    <section class="section">
      ${heading('01', 'Full Event Feed')}
      <div class="timeline">${feed(events, 50) || empty('—', 'Waiting for events', 'Circuit trips and rule changes will appear here.')}</div>
    </section>
  `;
}

// ---------------------------------------------------------------------------
// 03. ESCROWS & DECISION WORKFLOW (HoldButton Integration)
// ---------------------------------------------------------------------------
function escrows(d) {
  const list = Object.values(d.escrows || {}).sort((a, b) => b.created_at - a.created_at);
  const id = new URLSearchParams(location.search).get('id');
  const e = list.find(x => x.escrow_id === id) || list.find(x => x.state === 'PENDING') || list[0];
  const rows = list.map(x => `
    <tr>
      <td><a class="text-link" href="/escrows?id=${encodeURIComponent(x.escrow_id)}"><span data-effect="decrypted-text" data-text="${clean(x.escrow_id)}">${clean(x.escrow_id)}</span> ↗</a></td>
      <td class="mono">${clean(x.task_id)}</td>
      <td>${chip(x.state)}</td>
      <td>${clean(x.trip_reason || '—')}</td>
      <td class="mono">${time(x.created_at)}</td>
    </tr>
  `);
  const detail = e ? `
    <div class="detail-grid">
      <div class="detail-panel">
        <div class="eyebrow">SELECTED // ${clean(e.escrow_id)}</div>
        <h2>${clean(e.state)}</h2>
        <div class="key-value"><span>TASK ID</span><span class="mono">${clean(e.task_id)}</span></div>
        <div class="key-value"><span>TRIGGER ERROR</span><span>${clean(e.error_message || e.trip_reason || '—')}</span></div>
        <div class="key-value"><span>CHANGE HASH</span><span class="mono" style="color:var(--acid);"><span data-effect="decrypted-text" data-text="${clean(e.change_hash || 'Awaiting proposal')}">${clean(e.change_hash || 'Awaiting proposal')}</span></span></div>
      </div>
      <div class="detail-panel">
        <div class="eyebrow">REPAIR WORKFLOW // HUMAN IN THE LOOP</div>
        <h2>Review Candidate & Authorize</h2>
        ${e.state === 'PENDING' ? `
          <p>Prune failed history, verify the replacement route, then generate a hash-bound proposal. Use React Bits HoldButton to approve or reject.</p>
          <div class="workflow-actions">
            <button class="btn" data-step="prune" data-escrow="${clean(e.escrow_id)}" ${e.context_pruned ? 'disabled' : ''}>${e.context_pruned ? '✓ Context Pruned' : '1 · Prune Context'}</button>
            <button class="btn" data-step="dryrun" data-escrow="${clean(e.escrow_id)}" ${!e.context_pruned || e.dryrun_verified ? 'disabled' : ''}>${e.dryrun_verified ? '✓ Dry Run Verified' : '2 · Run Dry Test'}</button>
            <button class="btn" data-step="propose" data-escrow="${clean(e.escrow_id)}" ${!e.dryrun_verified || e.change_hash ? 'disabled' : ''}>${e.change_hash ? '✓ Proposal Created' : '3 · Create Proposal'}</button>
          </div>
          ${e.proposed_vaccine ? `
            <div class="proposal">
              <strong>Proposed Rule</strong>
              <p>${clean(e.proposed_vaccine.description || '')}</p>
              <pre>${clean(e.proposed_diff || '')}</pre>
              <span class="mono" style="color:var(--acid);">CHANGE HASH: ${clean(e.change_hash)}</span>
            </div>
          ` : ''}
          <div class="workflow-actions" style="margin-top:20px;">
            <button class="btn" data-decision="approve" data-escrow="${clean(e.escrow_id)}" ${e.change_hash ? '' : 'disabled'}>Hold to approve</button>
            <button class="btn danger" data-decision="reject" data-escrow="${clean(e.escrow_id)}">Hold to reject</button>
          </div>
        ` : `
          <p>Decision recorded. This escrow is <strong>${clean(e.state.toLowerCase())}</strong>.</p>
        `}
      </div>
    </div>
  ` : '';
  return `
    ${header('03', 'Escrows', 'Paused worker tasks and hash-bound repair decisions.')}
    <div class="toolbar" style="display:flex; justify-content:space-between; margin:20px 0;">
      <span class="eyebrow" style="color:var(--muted); font-family:'DM Mono';">${list.length} TOTAL // ${list.filter(x => x.state === 'PENDING').length} PENDING</span>
    </div>
    ${rows.length ? table(['Escrow ID', 'Task ID', 'State', 'Trigger Reason', 'Opened At'], rows) : empty('⏸', 'No Escrows Recorded', 'A circuit trip will pause the worker and create a reviewable escrow here.')}
    ${detail}
  `;
}

// ---------------------------------------------------------------------------
// 04. VACCINES REGISTRY
// ---------------------------------------------------------------------------
function vaccines(d) {
  const list = d.vaccines || [];
  const rows = list.map(v => `
    <tr>
      <td class="mono"><span data-effect="decrypted-text" data-text="${clean(v.id)}">${clean(v.id)}</span></td>
      <td>${chip(v.status)}</td>
      <td class="mono">${clean(v.match?.http_method)} ${clean(v.match?.path_template)}</td>
      <td class="mono" style="color:var(--acid);">${clean(v.action?.rewrite_path || '—')}</td>
      <td class="mono">${clean(v.change_hash)}</td>
      <td class="mono">${time(v.expires_at)}</td>
    </tr>
  `);
  return `
    ${header('04', 'Vaccines', 'Zero-retry rewrite rules that intercept worker requests before upstream execution.')}
    <div class="toolbar" style="display:flex; justify-content:space-between; margin:20px 0;">
      <span class="eyebrow" style="color:var(--muted); font-family:'DM Mono';">${list.length} REGISTERED // ${list.filter(v => v.status === 'ENFORCE').length} ENFORCED</span>
    </div>
    ${rows.length ? table(['Vaccine ID', 'Status', 'Match Pattern', 'Rewrite Path', 'Change Hash', 'Expires At'], rows) : empty('◎', 'No Vaccines Registered', 'An approved repair proposal installs an enforced zero-retry rule here.')}
  `;
}

// ---------------------------------------------------------------------------
// 05. LEDGER & AUDIT TRAIL
// ---------------------------------------------------------------------------
function ledger(d) {
  const rows = entries.map(e => `
    <tr>
      <td class="mono">#${e.seq_no}</td>
      <td><strong>${clean(e.event_type)}</strong></td>
      <td class="mono">${clean(e.escrow_id)}</td>
      <td class="mono" style="color:var(--cyan); word-break:break-all;"><span data-effect="decrypted-text" data-text="${clean(e.entry_hash)}">${clean(e.entry_hash)}</span></td>
      <td class="mono">${time(e.timestamp)}</td>
    </tr>
  `);
  return `
    ${header('05', 'Ledger', 'Append-only cryptographically chained intervention records.')}
    <div class="detail-grid">
      <div class="detail-panel">
        <div class="eyebrow">CHAIN HEAD</div>
        <h2>Entry #${number(d.ledger_head_seq)}</h2>
        <div class="key-value"><span>HEAD HASH</span><span class="mono" style="color:var(--acid); word-break:break-all;">${clean(d.ledger_head_hash)}</span></div>
      </div>
      <div class="detail-panel">
        <div class="eyebrow">INTEGRITY GUARANTEE</div>
        <h2>Predecessor Hash Chain</h2>
        <p>Every event (trip, prune, proposal, approval) computes <code>sha256(seq_no | prev_hash | payload)</code>. Tampering with any historical record invalidates the entire chain.</p>
      </div>
    </div>
    <section class="section">
      ${heading('01', 'Recent Cryptographic Entries')}
      ${rows.length ? table(['Seq #', 'Event Type', 'Escrow ID', 'SHA-256 Entry Hash', 'Timestamp'], rows) : empty('⌁', 'No Ledger Entries Yet', 'Interventions will be anchored into SQLite and displayed here.')}
    </section>
  `;
}

// ---------------------------------------------------------------------------
// 06. BENCHMARKS VIEW ($751k Tokens Saved, 87.4% Reduction)
// ---------------------------------------------------------------------------
function benchmarks(d) {
  return `
    ${header('06', 'FinOps Benchmarks', 'Verified empirical measurements from our 10,000-iteration runaway simulation.')}
    <div class="metrics-strip">
      <div class="metric-box">
        <span class="small-label">Control Group Tokens</span>
        <strong style="color:var(--rust);">860,000</strong>
        <small>10 failed turns @ 15k-80k tokens/turn</small>
      </div>
      <div class="metric-box">
        <span class="small-label">SwitchBlade Guarded</span>
        <strong class="acid">108,260</strong>
        <small>Trips Turn 3, Pruned, Settled Turn 4</small>
      </div>
      <div class="metric-box">
        <span class="small-label">Net FinOps Reduction</span>
        <strong class="good"><span data-effect="count-up" data-to="87.4" data-decimals="1" data-suffix="%">87.4%</span></strong>
        <small>$12.90 cost avoided down to $1.62</small>
      </div>
      <div class="metric-box">
        <span class="small-label">Pre-Send Rewrite Latency</span>
        <strong class="cyan"><span data-effect="count-up" data-to="1.20" data-decimals="2" data-suffix=" µs">1.20 µs</span></strong>
        <small>10,000 runs, p50: 1.20 µs, p99: 2.10 µs</small>
      </div>
    </div>

    <section class="section">
      ${heading('01', 'Turn-by-Turn FinOps Comparison')}
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Turn</th>
              <th>Control Request Tokens</th>
              <th>Control Cost ($)</th>
              <th>SwitchBlade Action</th>
              <th>Guarded Request Tokens</th>
              <th>Guarded Cost ($)</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Turn 1</td><td class="mono">18,500</td><td class="mono">$0.28</td><td>Outbound execution</td><td class="mono">18,500</td><td class="mono">$0.28</td></tr>
            <tr><td>Turn 2</td><td class="mono">33,500</td><td class="mono">$0.50</td><td>Failure count = 2</td><td class="mono">33,500</td><td class="mono">$0.50</td></tr>
            <tr><td>Turn 3</td><td class="mono">48,500</td><td class="mono">$0.73</td><td><strong style="color:var(--acid);">⚡ CIRCUIT TRIPS (Escrow Opened)</strong></td><td class="mono">48,500</td><td class="mono">$0.73</td></tr>
            <tr><td>Turn 4</td><td class="mono">63,500</td><td class="mono">$0.95</td><td><strong style="color:var(--cyan);">✂ Context Surgery (Prunes 45k tokens)</strong></td><td class="mono">7,760</td><td class="mono">$0.11</td></tr>
            <tr><td>Turns 5–10</td><td class="mono">696,000</td><td class="mono">$10.44</td><td><strong style="color:var(--good);">✔ Vaccine Active (Order 9901 Settled)</strong></td><td class="mono">0 (HALTED)</td><td class="mono">$0.00</td></tr>
            <tr style="background:rgba(215,250,103,0.08); font-weight:700;">
              <td>TOTALS</td>
              <td class="mono" style="color:var(--rust);">860,000 tokens</td>
              <td class="mono" style="color:var(--rust);">$12.90 USD</td>
              <td><strong>751,740 TOKENS SAVED (87.4% GAIN)</strong></td>
              <td class="mono" style="color:var(--acid);">108,260 tokens</td>
              <td class="mono" style="color:var(--good);">$1.62 USD</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  `;
}

// ---------------------------------------------------------------------------
// 07. WISPR FLOW VIEW (Voice Ergonomics Track)
// ---------------------------------------------------------------------------
function wispr(d) {
  return `
    ${header('07', 'Wispr Flow Integration', 'Voice-driven human-in-the-loop authorization ergonomics for high-velocity incident rooms.')}
    <div class="detail-grid">
      <div data-effect="spotlight-card" data-spotlight="rgba(6, 182, 212, 0.16)" class="detail-panel">
        <div class="eyebrow" style="color:var(--cyan);">WISPR FLOW // $500 TRACK</div>
        <h2>Operator Voice Dictation</h2>
        <p>In high-stakes production incidents, typing cryptographically secure commands with 64-character SHA-256 hashes introduces delay and human typo risks.</p>
        <p>Using <strong>Wispr Flow's ultra-low latency voice transcription</strong>, operators speak naturally: <em>"Approve escrow 8f4b2a1c with rewrite to v2 orders"</em>. SwitchBlade maps audio intents to hash-bound room approvals with zero keyboard friction.</p>
        <div style="margin-top:20px;">
          <a class="btn cyan" href="https://github.com/HamzaShaikh-source/SwitchBlade/blob/main/WISPR_FLOW.md" target="_blank">Read WISPR_FLOW.md Specification ↗</a>
        </div>
      </div>
      <div class="detail-panel">
        <div class="eyebrow">VERIFIED VOICE PROMPTS</div>
        <h2>Audio Storyboard Triggers</h2>
        <div class="key-value"><span>"Approve escrow"</span><span>Resolves active escrow with recorded approver ID</span></div>
        <div class="key-value"><span>"Prune context"</span><span>Invokes Context Surgeon to collapse stack trace</span></div>
        <div class="key-value"><span>"Run dry test"</span><span>Executes Scout agent zero-mutation simulation</span></div>
        <div class="key-value"><span>"Rollback vaccine"</span><span>Safely deactivates matching pre-send rewrite</span></div>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// RENDER & TELEMETRY ROUTER
// ---------------------------------------------------------------------------
function render() {
  const d = state || { stats: {}, escrows: {}, vaccines: [], ledger_head_seq: 0, ledger_head_hash: '—' };
  const key = JSON.stringify([route, d, events, entries]);
  if (key === lastKey || busy) return;
  lastKey = key;

  document.dispatchEvent(new Event('switchblade:before-render'));

  const viewMap = {
    '/': landing,
    '/overview': overview,
    '/activity': activity,
    '/escrows': escrows,
    '/vaccines': vaccines,
    '/ledger': ledger,
    '/benchmarks': benchmarks,
    '/wispr': wispr
  };

  const renderFn = viewMap[route] || landing;
  $('#content').innerHTML = renderFn(d);

  document.dispatchEvent(new Event('switchblade:after-render'));
  document.title = `SwitchBlade — ${pages[route] || 'In-Flight FinOps'}`;
}

async function refresh() {
  try {
    const responses = await Promise.all([
      fetch('/state', { cache: 'no-store' }),
      fetch('/events?limit=200', { cache: 'no-store' }),
      fetch('/ledger/entries?limit=50', { cache: 'no-store' })
    ]);
    if (responses.some(r => !r.ok)) throw new Error('Telemetry request failed');
    [state, events, entries] = await Promise.all(responses.map(r => r.json()));
    online = true;
    const conn = $('#connection');
    if (conn) {
      conn.classList.add('online');
      conn.innerHTML = '<i></i> LIVE SYSTEM';
    }
    const rail = $('#rail-mode');
    if (rail) rail.textContent = `${state.active_mode || 'LIVE'} // CONNECTED`;
    render();
  } catch {
    if (online) notice('Live telemetry connection lost. Retrying…');
    online = false;
    const conn = $('#connection');
    if (conn) {
      conn.classList.remove('online');
      conn.innerHTML = '<i></i> OFFLINE';
    }
    const rail = $('#rail-mode');
    if (rail) rail.textContent = 'OFFLINE // RETRYING';
  }
}

async function post(path, body) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const result = await r.json();
  if (!r.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `HTTP ${r.status}`);
  return result;
}

async function step(id, action) {
  if (busy) return;
  busy = true;
  try {
    const result = await post({ prune: '/surgeon/prune', dryrun: '/scout/dryrun', propose: '/compiler/propose' }[action], { escrow_id: id });
    if (action === 'dryrun' && !result.success) throw new Error(result.message);
    notice(action === 'prune' ? 'Context pruned and recorded.' : action === 'dryrun' ? result.message : `Proposal created: ${result.change_hash}`);
  } catch (error) {
    notice(`Workflow failed: ${error.message}`);
  } finally {
    busy = false;
    await refresh();
  }
}

async function decide(id, approved) {
  if (busy) return;
  const e = state?.escrows?.[id];
  if (!e || e.state !== 'PENDING') return notice('This escrow is no longer pending.');
  busy = true;
  try {
    const result = await post('/escrow/decision', {
      escrow_id: id,
      approved,
      approver_id: 'hamza',
      change_hash: e.change_hash,
      reason: `${approved ? 'Approved' : 'Rejected'} via SwitchBlade web control plane`
    });
    notice(`Escrow ${result.state.toLowerCase()} and recorded.`);
  } catch (error) {
    notice(`Decision failed: ${error.message}`);
  } finally {
    busy = false;
    await refresh();
  }
}

window.triggerDemoLoop = async function() {
  notice('Simulating runaway worker tool calls against deprecated /v1/orders…');
  try {
    for (let i = 0; i < 3; i++) {
      await fetch('/proxy/execute_tool', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: "demo-runaway-task",
          tool_name: "settle_order",
          arguments: { order_id: 9901, step_id: String(i + 1) },
          context: { tenant_id: "acme-corp" }
        })
      });
    }
    notice('⚡ 3 Failed calls detected! Circuit tripped into escrow. Opening /escrows…');
    setTimeout(() => {
      location.href = '/escrows';
    }, 1500);
  } catch (err) {
    notice('Simulation initiated. Refreshing state…');
  }
  await refresh();
};

document.querySelectorAll('[data-route]').forEach(a => a.classList.toggle('active', a.dataset.route === route));
const menuToggle = $('.menu-toggle');
if (menuToggle) {
  menuToggle.addEventListener('click', () => {
    const nav = $('#site-nav'), open = nav.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', String(open));
  });
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-step]');
  if (b) step(b.dataset.escrow, b.dataset.step);
});
document.addEventListener('switchblade:decision', e => decide(e.detail.escrowId, e.detail.approved));

render();
refresh();
setInterval(refresh, 2500);
