const route = location.pathname.replace(/\/$/, '') || '/';
const pages = {'/':'Overview','/activity':'Activity','/escrows':'Escrows','/vaccines':'Vaccines','/ledger':'Ledger'};
const $ = selector => document.querySelector(selector);
const clean = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => Number(value || 0).toLocaleString();
const time = epoch => epoch ? new Date(epoch * 1000).toLocaleString() : '—';
const chip = value => `<span class="chip ${clean(String(value || '').toLowerCase())}">${clean(value || 'UNKNOWN')}</span>`;
const empty = (symbol, title, copy) => `<div class="empty"><div class="glyph">${symbol}</div><h2>${title}</h2><p>${copy}</p></div>`;
const heading = (n, title, href, label) => `<div class="section-head"><div><div class="section-index">${n} / CONTROL PLANE</div><h2>${title}</h2></div>${href ? `<a class="text-link" href="${href}">${label} ↗</a>` : ''}</div>`;
const header = (n, title, copy) => `<header class="page-header reveal"><div><div class="eyebrow"><span>${n}</span> SWITCHBLADE / ${title.toUpperCase()}</div><h1 class="page-title">${title}<em>.</em></h1></div><p class="page-intro">${copy}</p></header>`;
const table = (heads, rows) => `<div class="table-wrap"><table class="data-table"><thead><tr>${heads.map(h => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
let state = null, events = [], entries = [], online = false, busy = false, lastKey = '', toastTimer;
function notice(message) { const el = $('#toast'); el.textContent = message; el.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 5000); }
function feed(items, count = 8) { return items.slice(-count).reverse().map(e => `<div class="timeline-row"><time class="mono">${time(e.timestamp)}</time><div><strong>${clean(e.event_type)}</strong><p>${clean(Object.entries(e.data || {}).map(([k,v]) => `${k}: ${v ?? '—'}`).join(' · '))}</p></div></div>`).join(''); }
function overview(d) {
  const s = d.stats || {}, pending = Object.values(d.escrows || {}).filter(e => e.state === 'PENDING'), enforced = (d.vaccines || []).filter(v => v.status === 'ENFORCE');
  return `${header('01','Overview','Live operations across the worker gateway, review queue, and active repair rules.')}
  <section class="section">${heading('01','System status','/activity','View activity')}<div class="stat-grid"><div class="stat"><span class="small-label">Tool calls</span><strong>${number(s.total_tool_calls)}</strong><small>THIS PROXY SESSION</small></div><div class="stat"><span class="small-label">Circuit trips</span><strong>${number(s.total_trips)}</strong><small>THIS PROXY SESSION</small></div><div class="stat"><span class="small-label">Pending escrows</span><strong>${number(pending.length)}</strong><small>NEED HUMAN REVIEW</small></div><div class="stat"><span class="small-label">Enforced vaccines</span><strong>${number(enforced.length)}</strong><small>ACTIVE REWRITE RULES</small></div></div></section>
  <section class="section">${heading('02','Needs attention','/escrows','Review escrows')}${pending.length ? table(['Escrow','Task','Trigger','Opened'],pending.map(e => `<tr><td><a class="text-link" href="/escrows?id=${encodeURIComponent(e.escrow_id)}">${clean(e.escrow_id)} ↗</a></td><td>${clean(e.task_id)}</td><td>${clean(e.trip_reason)}</td><td>${time(e.created_at)}</td></tr>`)) : empty('✓','Review queue clear','No worker is currently waiting for a human decision.')}</section>
  <section class="section">${heading('03','Recent activity','/activity','Full stream')}<div class="timeline">${feed(events) || empty('—','Waiting for activity','Tool calls and interventions will appear here.')}</div></section><section class="section signal-section"><div class="signal-stage"><div data-effect="micro-slats" class="micro-surface" aria-hidden="true"></div><div class="signal-overlay"><span class="eyebrow">LIVE SYSTEM / INTERACTIVE SIGNAL</span><strong>${number(s.total_trips)}<small> CIRCUIT TRIPS</small></strong></div></div><div class="signal-text" data-effect="tech-text" aria-hidden="true"><span class="tech-fallback">SWITCHBLADE</span></div></section>`;
}
function activity(d) {
  const calls = events.filter(e => e.event_type === 'TOOL_CALL').slice().reverse();
  const rows = calls.map(e => `<tr><td>${time(e.timestamp)}</td><td class="mono">${clean(e.data.task_id)}</td><td>${clean(e.data.tool_name)}</td><td class="mono">POST ${clean(e.data.endpoint)}</td><td>${chip(e.data.status_code)}</td><td>${clean(e.data.vaccine_applied || '—')}</td></tr>`);
  return `${header('02','Activity','Recent gateway calls and intervention events from this proxy session.')}<div class="toolbar"><span class="eyebrow">${number(d.stats?.total_tool_calls)} CALLS THIS SESSION / ${calls.length} RECENT</span><span class="eyebrow">EVENTS RETAINED: LAST 200</span></div>${rows.length ? table(['Time','Task','Tool','Endpoint','HTTP','Vaccine'],rows) : empty('↗','No tool calls yet','Calls made through the worker gateway will appear here.')}<section class="section">${heading('01','Event feed')}<div class="timeline">${feed(events, 50) || empty('—','Waiting for events','Circuit trips and rule changes will appear here.')}</div></section>`;
}
function escrows(d) {
  const list = Object.values(d.escrows || {}).sort((a,b) => b.created_at - a.created_at);
  const id = new URLSearchParams(location.search).get('id');
  const e = list.find(x => x.escrow_id === id) || list.find(x => x.state === 'PENDING') || list[0];
  const rows = list.map(x => `<tr><td><a class="text-link" href="/escrows?id=${encodeURIComponent(x.escrow_id)}">${clean(x.escrow_id)} ↗</a></td><td>${clean(x.task_id)}</td><td>${chip(x.state)}</td><td>${clean(x.trip_reason || '—')}</td><td>${time(x.created_at)}</td></tr>`);
  const detail = e ? `<div class="detail-grid"><div class="detail-panel dark"><div class="eyebrow">SELECTED / ${clean(e.escrow_id)}</div><h2>${clean(e.state)}</h2><div class="key-value"><span>TASK</span><span>${clean(e.task_id)}</span></div><div class="key-value"><span>TRIGGER</span><span>${clean(e.error_message || e.trip_reason || '—')}</span></div><div class="key-value"><span>CHANGE HASH</span><span>${clean(e.change_hash || 'Awaiting proposal')}</span></div></div><div class="detail-panel"><div class="eyebrow">REPAIR WORKFLOW</div><h2>Review the candidate.</h2>${e.state === 'PENDING' ? `<p>Prune failed history, verify the replacement route, then generate a hash-bound proposal. Hold to approve or reject.</p><div class="workflow-actions"><button class="btn secondary" data-step="prune" data-escrow="${clean(e.escrow_id)}" ${e.context_pruned ? 'disabled' : ''}>${e.context_pruned ? '✓ Context pruned' : '1 · Prune context'}</button><button class="btn secondary" data-step="dryrun" data-escrow="${clean(e.escrow_id)}" ${!e.context_pruned || e.dryrun_verified ? 'disabled' : ''}>${e.dryrun_verified ? '✓ Dry run verified' : '2 · Run dry test'}</button><button class="btn secondary" data-step="propose" data-escrow="${clean(e.escrow_id)}" ${!e.dryrun_verified || e.change_hash ? 'disabled' : ''}>${e.change_hash ? '✓ Proposal created' : '3 · Create proposal'}</button></div>${e.proposed_vaccine ? `<div class="proposal"><strong>Proposed rule</strong><p>${clean(e.proposed_vaccine.description || '')}</p><pre>${clean(e.proposed_diff || '')}</pre><span class="mono">CHANGE HASH · ${clean(e.change_hash)}</span></div>` : ''}<div class="workflow-actions"><button class="btn" data-decision="approve" data-escrow="${clean(e.escrow_id)}" ${e.change_hash ? '' : 'disabled'}>Hold to approve</button><button class="btn danger" data-decision="reject" data-escrow="${clean(e.escrow_id)}">Hold to reject</button></div>` : `<p>Decision recorded. This escrow is ${clean(e.state.toLowerCase())}.</p>`}</div></div>` : '';
  return `${header('03','Escrows','Paused worker tasks and hash-bound repair decisions.')}<div class="toolbar"><span class="eyebrow">${list.length} TOTAL / ${list.filter(x => x.state === 'PENDING').length} PENDING</span></div>${rows.length ? table(['Escrow','Task','State','Trigger','Opened'],rows) : empty('⏸','No escrows','A circuit trip creates a reviewable escrow here.')}${detail}`;
}
function vaccines(d) {
  const list = d.vaccines || [];
  const rows = list.map(v => `<tr><td class="mono">${clean(v.id)}</td><td>${chip(v.status)}</td><td class="mono">${clean(v.match?.http_method)} ${clean(v.match?.path_template)}</td><td class="mono">${clean(v.action?.rewrite_path || '—')}</td><td class="mono">${clean(v.change_hash)}</td><td>${time(v.expires_at)}</td></tr>`);
  return `${header('04','Vaccines','Rules that rewrite matching worker requests before the upstream API.')}<div class="toolbar"><span class="eyebrow">${list.length} REGISTERED / ${list.filter(v => v.status === 'ENFORCE').length} ENFORCED</span></div>${rows.length ? table(['Rule','Mode','Match','Rewrite','Change hash','Expires'],rows) : empty('◎','No vaccines registered','An approved repair proposal installs an enforced rule.')}`;
}
function ledger(d) {
  const rows = entries.map(e => `<tr><td class="mono">#${e.seq_no}</td><td>${clean(e.event_type)}</td><td class="mono">${clean(e.escrow_id)}</td><td class="mono hash-cell" title="${clean(e.entry_hash)}">${clean(e.entry_hash)}</td><td>${time(e.timestamp)}</td></tr>`);
  return `${header('05','Ledger','Persisted intervention records linked by SHA-256 hashes.')}<div class="detail-grid"><div class="detail-panel dark"><div class="eyebrow">CURRENT HEAD</div><h2>Entry #${number(d.ledger_head_seq)}</h2><div class="key-value"><span>HEAD HASH</span><span class="mono">${clean(d.ledger_head_hash)}</span></div></div><div class="detail-panel"><div class="eyebrow">INTEGRITY</div><h2>Append-only history.</h2><p>Each entry stores its predecessor hash. Verify the chain with the ledger verification command.</p></div></div><section class="section">${heading('01','Recent records')}<div class="toolbar"><span class="eyebrow">${entries.length} MOST RECENT ENTRIES</span></div>${rows.length ? table(['Sequence','Event','Escrow','Entry hash','Time'],rows) : empty('⌁','No entries yet','Interventions will be recorded here.')}</section>`;
}
function render() {
  const d = state || {stats:{},escrows:{},vaccines:[],ledger_head_seq:0,ledger_head_hash:'—'};
  const key = JSON.stringify([route,d,events,entries]);
  if (key === lastKey || busy) return;
  lastKey = key;
  document.dispatchEvent(new Event('switchblade:before-render'));
  $('#content').innerHTML = ({'/':overview,'/activity':activity,'/escrows':escrows,'/vaccines':vaccines,'/ledger':ledger}[route] || overview)(d);
  document.dispatchEvent(new Event('switchblade:after-render'));
  document.title = `SwitchBlade — ${pages[route] || 'Overview'}`;
}
async function refresh() {
  try {
    const responses = await Promise.all(['/state','/events?limit=200','/ledger/entries?limit=50'].map(path => fetch(path,{cache:'no-store'})));
    if (responses.some(r => !r.ok)) throw new Error('Telemetry request failed');
    [state,events,entries] = await Promise.all(responses.map(r => r.json()));
    online = true;
    $('#connection').classList.add('online'); $('#connection').innerHTML = '<i></i> LIVE SYSTEM';
    $('#rail-mode').textContent = `${state.active_mode || 'LIVE'} / CONNECTED`;
    render();
  } catch {
    if (online) notice('Live telemetry connection lost. Retrying…');
    online = false; $('#connection').classList.remove('online'); $('#connection').innerHTML = '<i></i> OFFLINE';
    $('#rail-mode').textContent = 'OFFLINE / RETRYING';
  }
}
async function post(path, body) {
  const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result = await r.json();
  if (!r.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `HTTP ${r.status}`);
  return result;
}
async function step(id, action) {
  if (busy) return; busy = true;
  try {
    const result = await post({prune:'/surgeon/prune',dryrun:'/scout/dryrun',propose:'/compiler/propose'}[action],{escrow_id:id});
    if (action === 'dryrun' && !result.success) throw new Error(result.message);
    notice(action === 'prune' ? 'Context pruned and recorded.' : action === 'dryrun' ? result.message : `Proposal created: ${result.change_hash}`);
  } catch (error) { notice(`Workflow failed: ${error.message}`); }
  finally { busy = false; await refresh(); }
}
async function decide(id, approved) {
  if (busy) return;
  const e = state?.escrows?.[id];
  if (!e || e.state !== 'PENDING') return notice('This escrow is no longer pending.');
  busy = true;
  try {
    const result = await post('/escrow/decision',{escrow_id:id,approved,approver_id:'hamza',change_hash:e.change_hash,reason:`${approved ? 'Approved' : 'Rejected'} via SwitchBlade web control plane`});
    notice(`Escrow ${result.state.toLowerCase()} and recorded.`);
  } catch (error) { notice(`Decision failed: ${error.message}`); }
  finally { busy = false; await refresh(); }
}
document.querySelectorAll('[data-route]').forEach(a => a.classList.toggle('active',a.dataset.route === route));
$('.menu-toggle').addEventListener('click',() => { const nav = $('#site-nav'), open = nav.classList.toggle('open'); $('.menu-toggle').setAttribute('aria-expanded',String(open)); });
document.addEventListener('click',e => { const b = e.target.closest('[data-step]'); if (b) step(b.dataset.escrow,b.dataset.step); });
document.addEventListener('switchblade:decision',e => decide(e.detail.escrowId,e.detail.approved));
render(); refresh(); setInterval(refresh,3000);
