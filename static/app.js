/* app.js — hash router, view loaders, pipeline trigger */

const ROUTES = ['dashboard','integrations','runs','dlq','config','audit','selectors'];
const VIEW_LABELS = {
  dashboard:'DASHBOARD', integrations:'INTEGRATIONS', runs:'RUNS',
  dlq:'DEAD-LETTER QUEUE', config:'CONFIG.YAML', audit:'AUDIT LOG',
  selectors:'SELECTOR PROPOSALS',
};

// ── HTML escaping (XSS prevention) ───────────────────────────────────────────

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Router ────────────────────────────────────────────────────────────────────

function currentRoute() {
  const h = window.location.hash.replace('#/','').split('?')[0];
  return ROUTES.includes(h) ? h : 'dashboard';
}

function navigate(route) {
  if (!ROUTES.includes(route)) route = 'dashboard';
  window.location.hash = '#/' + route;
}

function _activateView(route) {
  document.querySelectorAll('.oc-view').forEach(v => v.classList.remove('active'));
  const el = document.getElementById('view-' + route);
  if (el) el.classList.add('active');
  document.querySelectorAll('.nav-link').forEach(a =>
    a.classList.toggle('active', a.dataset.route === route)
  );
  const lbl = document.getElementById('view-label');
  if (lbl) lbl.textContent = VIEW_LABELS[route] || route.toUpperCase();
}

async function _loadRoute(route) {
  _activateView(route);
  try {
    const loaders = {
      dashboard:    loadDashboard,
      integrations: loadIntegrations,
      runs:         () => loadRuns(1),
      dlq:          () => loadDlq(1),
      config:       loadConfig,
      audit:        () => loadAudit(1),
      selectors:    loadSelectors,
    };
    if (loaders[route]) await loaders[route]();
  } catch (e) {
    if (e.status !== 401) console.error('View load error:', e);
  }
}

window.addEventListener('hashchange', () => _loadRoute(currentRoute()));

// ── Helpers ───────────────────────────────────────────────────────────────────

function _statusPill(status) {
  const cls = {
    succeeded:'ok', connected:'ok', approved:'ok',
    failed:'error', error:'error', rejected:'error',
    running:'warn', pending:'pending',
    queued:'queued', dismissed:'queued',
  }[status] || 'queued';
  return '<span class="oc-pill ' + cls + '">' + status.toUpperCase() + '</span>';
}

function _ts(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {dateStyle:'short', timeStyle:'medium'});
}

function _paginationButtons(page, hasNext, fnName) {
  const prev = page > 1 ? '<button class="oc-btn oc-btn-ghost" onclick="' + fnName + '(' + (page-1) + ')">&#8592; PREV</button>' : '';
  const next = hasNext   ? '<button class="oc-btn oc-btn-ghost" onclick="' + fnName + '(' + (page+1) + ')">NEXT &#8594;</button>' : '';
  const mid  = (prev||next) ? '<span style="color:#94a3b8;font-family:\'JetBrains Mono\',monospace;font-size:.75rem;padding:.35rem .5rem">PAGE ' + page + '</span>' : '';
  return prev + mid + next;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

async function loadDashboard() {
  const [rr, dr] = await Promise.all([
    authFetch('/api/v1/runs?per_page=10'),
    authFetch('/api/v1/dlq?per_page=1'),
  ]);
  const runs = await rr.json();
  const dlq  = await dr.json();

  document.getElementById('dash-stats').innerHTML = [
    {label:'TOTAL RUNS',    value: runs.total},
    {label:'DLQ ITEMS',     value: dlq.total,   warn: dlq.total > 0},
    {label:'LATEST STATUS', value: (runs.items[0]?.status || '—').toUpperCase()},
  ].map(s =>
    '<div class="oc-stat"><div class="label">' + s.label + '</div>' +
    '<div class="value"' + (s.warn ? ' style="color:#ff4365"' : '') + '>' + _esc(String(s.value)) + '</div></div>'
  ).join('');

  document.getElementById('dash-runs').innerHTML = runs.items.length
    ? runs.items.map(r =>
        '<tr>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem;color:#38bdf8">' + _esc(r.kind) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.7rem;color:#94a3b8">' + _esc(r.correlation_id.slice(0,20)) + '&#8230;</td>' +
        '<td>' + _statusPill(r.status) + '</td>' +
        '<td style="font-size:.75rem">' + _esc(_ts(r.started_at)) + '</td>' +
        '<td style="font-size:.75rem">' + _esc(_ts(r.finished_at)) + '</td>' +
        '</tr>'
      ).join('')
    : '<tr><td colspan="5" class="oc-empty">No runs yet.</td></tr>';
}

// ── Integrations ──────────────────────────────────────────────────────────────

async function loadIntegrations() {
  const r = await authFetch('/api/v1/integrations');
  const items = await r.json();
  const byProvider = Object.fromEntries(items.map(i => [i.provider, i]));

  const KNOWN = [
    {provider:'gmail',     label:'Gmail'},
    {provider:'linkedin',  label:'LinkedIn'},
    {provider:'openai',    label:'OpenAI'},
    {provider:'anthropic', label:'Anthropic'},
  ];

  document.getElementById('integrations-list').innerHTML = KNOWN.map(k => {
    const row    = byProvider[k.provider];
    const status = row?.status || 'disconnected';
    const errHtml = row?.last_error
      ? '<div style="color:#ff4365;font-size:.75rem;margin-top:.4rem;font-family:\'JetBrains Mono\',monospace">' + _esc(row.last_error) + '</div>'
      : '';
    const isKey = ['openai','anthropic'].includes(k.provider);
    const action = isKey
      ? '<input class="oc-input" id="apikey-' + k.provider + '" type="password" placeholder="sk-..." style="width:200px">' +
        '<button class="oc-btn oc-btn-ghost" style="margin-left:.5rem" onclick="saveApiKey(\'' + k.provider + '\')">SAVE</button>'
      : '<button class="oc-btn oc-btn-ghost" disabled>' + (status === 'connected' ? 'RECONNECT' : 'CONNECT') + '</button>';
    return '<div class="oc-card">' +
      '<div class="oc-card-header"><span class="oc-card-title">' + _esc(k.label.toUpperCase()) + '</span>' + _statusPill(status) + '</div>' +
      errHtml +
      '<div style="margin-top:.75rem">' + action + '</div>' +
      '</div>';
  }).join('');
}

window.saveApiKey = function(provider) {
  const input = document.getElementById('apikey-' + provider);
  if (!input || !input.value) return;
  alert('Key noted for ' + provider + '. Persistence to DB not yet wired (W4).');
  input.value = '';
};

// ── Runs ──────────────────────────────────────────────────────────────────────

window.loadRuns = async function(page) {
  page = page || 1;
  const status = document.getElementById('runs-status-filter')?.value || '';
  const qs = new URLSearchParams({page: page, per_page: 25});
  if (status) qs.set('status', status);
  const r = await authFetch('/api/v1/runs?' + qs);
  const data = await r.json();

  document.getElementById('runs-list').innerHTML = data.items.length
    ? data.items.map(r =>
        '<tr>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem;color:#38bdf8">' + _esc(r.kind) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.7rem;color:#94a3b8">' + _esc(r.correlation_id.slice(0,24)) + '&#8230;</td>' +
        '<td>' + _statusPill(r.status) + '</td>' +
        '<td style="font-size:.75rem">' + _esc(_ts(r.started_at)) + '</td>' +
        '<td style="font-size:.75rem;text-align:right;color:#94a3b8">' + _esc(String(r.retry_count)) + '</td>' +
        '</tr>'
      ).join('')
    : '<tr><td colspan="5" class="oc-empty">No runs.</td></tr>';

  document.getElementById('runs-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadRuns');
};

// ── DLQ ───────────────────────────────────────────────────────────────────────

window.loadDlq = async function(page) {
  page = page || 1;
  const r = await authFetch('/api/v1/dlq?page=' + page + '&per_page=25');
  const data = await r.json();

  document.getElementById('dlq-list').innerHTML = data.items.length
    ? data.items.map(item =>
        '<tr>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem;color:#38bdf8">' + _esc(item.kind) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.7rem;color:#94a3b8">' + _esc(item.correlation_id.slice(0,20)) + '&#8230;</td>' +
        '<td style="font-size:.75rem;color:#ff4365">' + _esc(item.error_code || '—') + '</td>' +
        '<td style="font-size:.75rem;text-align:right;color:#94a3b8">' + _esc(String(item.retry_count)) + '</td>' +
        '<td>' +
        '<button class="oc-btn oc-btn-primary" style="font-size:.65rem;margin-right:.25rem" onclick="retryDlq(\'' + _esc(item.id) + '\')">RETRY</button>' +
        '<button class="oc-btn oc-btn-danger"  style="font-size:.65rem" onclick="dismissDlq(\'' + _esc(item.id) + '\')">DISMISS</button>' +
        '</td>' +
        '</tr>'
      ).join('')
    : '<tr><td colspan="5" class="oc-empty">DLQ is empty.</td></tr>';

  document.getElementById('dlq-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadDlq');
};

window.retryDlq = async function(id) {
  const r = await authFetch('/api/v1/dlq/' + id + '/retry', {method:'POST'});
  if (r.ok) loadDlq(1); else alert('Retry failed: ' + r.status);
};

window.dismissDlq = async function(id) {
  const r = await authFetch('/api/v1/dlq/' + id + '/dismiss', {method:'POST'});
  if (r.ok) loadDlq(1); else alert('Dismiss failed: ' + r.status);
};

// ── Config ────────────────────────────────────────────────────────────────────

let _origConfig = '';

async function loadConfig() {
  const r    = await authFetch('/api/v1/config');
  const data = await r.json();
  _origConfig = data.yaml_text;
  const editor = document.getElementById('config-editor');
  if (editor) editor.value = data.yaml_text;
  const diff = document.getElementById('config-diff');
  if (diff) diff.style.display = 'none';
  const msg = document.getElementById('config-msg');
  if (msg) msg.textContent = '';
}

function _diffHtml(oldT, newT) {
  const o = oldT.split('\n');
  const n = newT.split('\n');
  const out = [];
  for (let i = 0; i < Math.max(o.length, n.length); i++) {
    if (i >= o.length)      out.push('<span class="add">+ ' + _esc(n[i]) + '</span>');
    else if (i >= n.length) out.push('<span class="del">- ' + _esc(o[i]) + '</span>');
    else if (o[i] !== n[i]) {
      out.push('<span class="del">- ' + _esc(o[i]) + '</span>');
      out.push('<span class="add">+ ' + _esc(n[i]) + '</span>');
    } else {
      out.push('  ' + _esc(o[i]));
    }
  }
  return out.join('\n');
}

document.addEventListener('DOMContentLoaded', function() {
  var editor = document.getElementById('config-editor');
  if (editor) {
    editor.addEventListener('input', function() {
      var diff = document.getElementById('config-diff');
      if (editor.value !== _origConfig) {
        diff.style.display = 'block';
        diff.innerHTML = _diffHtml(_origConfig, editor.value);
      } else {
        diff.style.display = 'none';
      }
    });
  }

  var saveBtn = document.getElementById('config-save-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async function() {
      var yaml_text = document.getElementById('config-editor')?.value;
      var msg = document.getElementById('config-msg');
      saveBtn.disabled = true;
      try {
        var r = await authFetch('/api/v1/config', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({yaml_text: yaml_text}),
        });
        var data = await r.json();
        if (r.ok) {
          msg.style.color = '#5eead4';
          msg.textContent = 'Saved. Config reload event published.';
          _origConfig = data.yaml_text;
          document.getElementById('config-diff').style.display = 'none';
        } else {
          msg.style.color = '#ff4365';
          msg.textContent = data.detail || 'Save failed';
        }
      } catch (e) {
        msg.style.color = '#ff4365';
        msg.textContent = String(e);
      } finally {
        saveBtn.disabled = false;
      }
    });
  }
});

// ── Audit ─────────────────────────────────────────────────────────────────────

window.loadAudit = async function(page) {
  page = page || 1;
  var actor  = document.getElementById('audit-actor-filter')?.value  || '';
  var action = document.getElementById('audit-action-filter')?.value || '';
  var qs = new URLSearchParams({page: page, per_page: 50});
  if (actor)  qs.set('actor',  actor);
  if (action) qs.set('action', action);
  var r    = await authFetch('/api/v1/audit?' + qs);
  var data = await r.json();

  document.getElementById('audit-list').innerHTML = data.items.length
    ? data.items.map(e =>
        '<tr>' +
        '<td style="font-size:.75rem;white-space:nowrap;color:#94a3b8">' + _esc(_ts(e.at)) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem;color:#38bdf8">' + _esc(e.actor) + '</td>' +
        '<td style="font-family:\'JetBrains Mono\',monospace;font-size:.75rem">' + _esc(e.action) + '</td>' +
        '<td style="font-size:.75rem;color:#94a3b8">' + _esc(e.target) + '</td>' +
        '</tr>'
      ).join('')
    : '<tr><td colspan="4" class="oc-empty">No audit entries.</td></tr>';

  document.getElementById('audit-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadAudit');
};

document.addEventListener('DOMContentLoaded', function() {
  var btn = document.getElementById('audit-filter-btn');
  if (btn) btn.addEventListener('click', function() { loadAudit(1); });
});

// ── Selectors ─────────────────────────────────────────────────────────────────

async function loadSelectors() {
  var r     = await authFetch('/api/v1/selectors');
  var items = await r.json();
  var container = document.getElementById('selectors-list');

  if (!items.length) {
    container.innerHTML = '<div class="oc-empty">No pending selector proposals.</div>';
    return;
  }

  container.innerHTML = items.map(s =>
    '<div class="oc-card" id="sel-' + _esc(s.id) + '">' +
    '<div class="oc-card-header">' +
    '<span class="oc-card-title">' + _esc(s.source.toUpperCase()) + ' &mdash; ' + _esc(s.key_path) + '</span>' +
    _statusPill(s.status) +
    '</div>' +
    '<div style="font-family:\'JetBrains Mono\',monospace;font-size:.8rem;color:#5eead4;margin-bottom:.5rem">NEW: ' + _esc(s.selector) + '</div>' +
    '<div style="font-size:.75rem;color:#94a3b8;margin-bottom:.75rem">Proposed by <strong>' + _esc(s.proposed_by) + '</strong> at ' + _esc(_ts(s.proposed_at)) + '</div>' +
    '<div style="display:flex;gap:.5rem">' +
    '<button class="oc-btn oc-btn-primary" onclick="approveSelector(\'' + _esc(s.id) + '\')">APPROVE</button>' +
    '<button class="oc-btn oc-btn-danger"  onclick="rejectSelector(\'' + _esc(s.id) + '\')">REJECT</button>' +
    '</div>' +
    '</div>'
  ).join('');
}

window.approveSelector = async function(id) {
  var r = await authFetch('/api/v1/selectors/' + id + '/approve', {method:'POST'});
  if (r.ok) loadSelectors(); else alert('Approve failed: ' + r.status);
};

window.rejectSelector = async function(id) {
  var r = await authFetch('/api/v1/selectors/' + id + '/reject', {method:'POST'});
  if (r.ok) loadSelectors(); else alert('Reject failed: ' + r.status);
};

// ── Pipeline trigger ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  var btn = document.getElementById('trigger-btn');
  if (!btn) return;
  btn.addEventListener('click', async function() {
    btn.disabled = true;
    btn.textContent = 'QUEUING…';
    try {
      var key = 'web-' + Date.now();
      var r   = await authFetch('/api/v1/pipeline/trigger', {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'Idempotency-Key': key},
        body: JSON.stringify({}),
      });
      var data = await r.json();
      btn.textContent = '✓ QUEUED (' + _esc(data.correlation_id.slice(0,8)) + '…)';
      setTimeout(function() {
        btn.textContent = '▶ TRIGGER PIPELINE';
        btn.disabled = false;
      }, 4000);
    } catch (e) {
      btn.textContent = '▶ TRIGGER PIPELINE';
      btn.disabled = false;
      alert('Trigger failed: ' + e.message);
    }
  });
});

// ── Auth UI + boot ────────────────────────────────────────────────────────────

function _showLogin() {
  document.getElementById('login-screen').style.display  = 'flex';
  document.getElementById('console-shell').style.display = 'none';
}

function _showConsole() {
  document.getElementById('login-screen').style.display  = 'none';
  document.getElementById('console-shell').style.display = 'grid';
}

document.addEventListener('DOMContentLoaded', function() {
  var logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', function(e) {
      e.preventDefault();
      clearToken();
      _showLogin();
    });
  }

  var loginBtn = document.getElementById('login-btn');
  if (loginBtn) {
    loginBtn.addEventListener('click', async function() {
      var secret = document.getElementById('bootstrap-input')?.value?.trim();
      var errEl  = document.getElementById('login-err');
      if (!secret) {
        errEl.style.display = 'block';
        errEl.textContent = 'Enter the bootstrap secret.';
        return;
      }
      loginBtn.disabled = true;
      loginBtn.textContent = 'PAIRING…';
      try {
        await pairDevice(secret);
        _showConsole();
        _loadRoute(currentRoute());
      } catch (e) {
        errEl.style.display = 'block';
        errEl.textContent = e.message || 'Pairing failed.';
        loginBtn.disabled = false;
        loginBtn.textContent = 'PAIR DEVICE';
      }
    });
  }

  if (getToken()) {
    _showConsole();
    _loadRoute(currentRoute());
  } else {
    _showLogin();
  }
});

// Runs filter
document.addEventListener('DOMContentLoaded', function() {
  var f = document.getElementById('runs-status-filter');
  if (f) f.addEventListener('change', function() { loadRuns(1); });
});
