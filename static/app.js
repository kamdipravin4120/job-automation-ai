/* app.js — hash router, view loaders, pipeline trigger */

const ROUTES = ['dashboard','integrations','jobs','runs','dlq','config','audit','selectors','profile','resume','credentials'];
const VIEW_LABELS = {
  dashboard:    'DASHBOARD',
  integrations: 'INTEGRATIONS',
  jobs:         'JOBS',
  runs:         'RUNS',
  dlq:          'DEAD-LETTER QUEUE',
  config:       'CONFIG.YAML',
  audit:        'AUDIT LOG',
  selectors:    'SELECTOR PROPOSALS',
  profile:      'PROFILE',
  resume:       'RESUME & ARTIFACTS',
  credentials:  'CREDENTIALS',
};

// ── XSS prevention ────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Toast notifications ───────────────────────────────────────────────────────

function _toast(msg, type, duration) {
  type = type || 'info';
  duration = duration == null ? 3500 : duration;
  var container = document.getElementById('oc-toast-container');
  if (!container) return;

  var toast = document.createElement('div');
  toast.className = 'oc-toast ' + type;
  toast.innerHTML =
    '<span class="oc-toast-dot"></span>' +
    '<span>' + _esc(String(msg)) + '</span>';

  container.appendChild(toast);

  var remove = function() {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(12px)';
    toast.style.transition = 'opacity .15s, transform .15s';
    setTimeout(function() { toast.remove(); }, 160);
  };

  if (duration > 0) setTimeout(remove, duration);
  toast.addEventListener('click', remove);
}

// ── Skeleton rows ─────────────────────────────────────────────────────────────

function _skeletonRows(count, cols) {
  var widths = [60, 90, 45, 70, 55, 80];
  var rows = '';
  for (var i = 0; i < count; i++) {
    var cells = '';
    for (var j = 0; j < cols; j++) {
      var w = widths[(i + j) % widths.length];
      cells += '<td><span class="oc-skel oc-skel-anim" style="width:' + w + '%"></span></td>';
    }
    rows += '<tr>' + cells + '</tr>';
  }
  return rows;
}

// ── Router ────────────────────────────────────────────────────────────────────

function currentRoute() {
  var h = window.location.hash.replace('#/','').split('?')[0];
  return ROUTES.includes(h) ? h : 'dashboard';
}

function navigate(route) {
  if (!ROUTES.includes(route)) route = 'dashboard';
  window.location.hash = '#/' + route;
}

function _activateView(route) {
  document.querySelectorAll('.oc-view').forEach(function(v) { v.classList.remove('active'); });
  var el = document.getElementById('view-' + route);
  if (el) el.classList.add('active');
  document.querySelectorAll('.nav-link').forEach(function(a) {
    a.classList.toggle('active', a.dataset.route === route);
  });
  var lbl = document.getElementById('view-label');
  if (lbl) lbl.textContent = VIEW_LABELS[route] || route.toUpperCase();
}

async function _loadRoute(route) {
  _activateView(route);
  try {
    var loaders = {
      dashboard:    loadDashboard,
      integrations: loadIntegrations,
      jobs:         function() { return loadJobs(1); },
      runs:         function() { return loadRuns(1); },
      dlq:          function() { return loadDlq(1); },
      config:       loadConfig,
      audit:        function() { return loadAudit(1); },
      selectors:    loadSelectors,
      profile:      loadProfile,
      resume:       loadResume,
      credentials:  loadCredentials,
    };
    if (loaders[route]) await loaders[route]();
  } catch (e) {
    if (e.status !== 401) console.error('View load error:', e);
  }
}

window.addEventListener('hashchange', function() { _loadRoute(currentRoute()); });

// ── Clock ─────────────────────────────────────────────────────────────────────

function _startClock() {
  var el = document.getElementById('topbar-clock');
  if (!el) return;
  var tick = function() {
    var now = new Date();
    el.textContent = now.toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  };
  tick();
  setInterval(tick, 1000);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _statusPill(status) {
  var cls = {
    succeeded: 'ok',  connected: 'ok',  approved: 'ok',
    failed:    'error', error: 'error',  rejected: 'error',
    running:   'warn',
    pending:   'pending',
    queued:    'queued', dismissed: 'queued',
  }[status] || 'queued';
  return '<span class="oc-pill ' + cls + '">' + _esc(status.toUpperCase()) + '</span>';
}

function _ts(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {dateStyle:'short', timeStyle:'medium'});
}

function _paginationButtons(page, hasNext, fnName) {
  var prev = page > 1
    ? '<button class="oc-btn oc-btn-ghost oc-btn-sm" onclick="' + fnName + '(' + (page-1) + ')">&#8592; PREV</button>'
    : '';
  var next = hasNext
    ? '<button class="oc-btn oc-btn-ghost oc-btn-sm" onclick="' + fnName + '(' + (page+1) + ')">NEXT &#8594;</button>'
    : '';
  var mid = (prev || next)
    ? '<span class="oc-page-num">PAGE ' + page + '</span>'
    : '';
  return prev + mid + next;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

async function loadDashboard() {
  var runsBody = document.getElementById('dash-runs');
  var statsEl  = document.getElementById('dash-stats');
  if (runsBody) runsBody.innerHTML = _skeletonRows(5, 5);

  var rr = await authFetch('/api/v1/runs?per_page=10');
  var dr = await authFetch('/api/v1/dlq?per_page=1');
  var runs = await rr.json();
  var dlq  = await dr.json();

  statsEl.innerHTML = [
    {label:'TOTAL RUNS',    value: runs.total},
    {label:'DLQ ITEMS',     value: dlq.total,  cls: dlq.total > 0 ? 'danger' : ''},
    {label:'LATEST STATUS', value: (runs.items[0]?.status || '—').toUpperCase(), cls: ''},
  ].map(function(s) {
    return '<div class="oc-stat">' +
      '<div class="label">' + s.label + '</div>' +
      '<div class="value' + (s.cls ? ' ' + s.cls : '') + '">' + _esc(String(s.value)) + '</div>' +
      '</div>';
  }).join('');

  runsBody.innerHTML = runs.items.length
    ? runs.items.map(function(r) {
        return '<tr>' +
          '<td style="font-family:var(--mono);font-size:.73rem;color:var(--accent)">' + _esc(r.kind) + '</td>' +
          '<td style="font-family:var(--mono);font-size:.7rem;color:var(--t-mid)">' + _esc(r.correlation_id.slice(0,22)) + '&#8230;</td>' +
          '<td>' + _statusPill(r.status) + '</td>' +
          '<td style="font-size:.75rem;color:var(--t-mid);white-space:nowrap">' + _esc(_ts(r.started_at)) + '</td>' +
          '<td style="font-size:.75rem;color:var(--t-mid);white-space:nowrap">' + _esc(_ts(r.finished_at)) + '</td>' +
          '</tr>';
      }).join('')
    : '<tr><td colspan="5" class="oc-empty">No runs yet.</td></tr>';
}

// ── Integrations ──────────────────────────────────────────────────────────────

async function loadIntegrations() {
  var container = document.getElementById('integrations-list');
  container.innerHTML = '<div class="oc-spinner-wrap"><div class="oc-spinner"></div></div>';

  var r     = await authFetch('/api/v1/integrations');
  var items = await r.json();
  var byProvider = Object.fromEntries(items.map(function(i) { return [i.provider, i]; }));

  var KNOWN = [
    {provider:'gmail',     label:'Gmail'},
    {provider:'linkedin',  label:'LinkedIn'},
    {provider:'openai',    label:'OpenAI'},
    {provider:'anthropic', label:'Anthropic'},
  ];

  container.innerHTML = KNOWN.map(function(k) {
    var row    = byProvider[k.provider];
    var status = row?.status || 'disconnected';
    var errHtml = row?.last_error
      ? '<div style="color:var(--err);font-size:.72rem;margin-top:.4rem;font-family:var(--mono)">' + _esc(row.last_error) + '</div>'
      : '';
    var isKey = k.provider === 'openai' || k.provider === 'anthropic';
    var action = isKey
      ? '<input class="oc-input" id="apikey-' + k.provider + '" type="text" autocomplete="off" spellcheck="false" placeholder="sk-…" style="width:200px">' +
        '<button class="oc-btn oc-btn-ghost oc-btn-sm" style="margin-left:.5rem" onclick="saveApiKey(\'' + k.provider + '\')">SAVE</button>'
      : '<button class="oc-btn oc-btn-ghost oc-btn-sm" disabled>' + (status === 'connected' ? 'RECONNECT' : 'CONNECT') + '</button>';
    return '<div class="oc-card">' +
      '<div class="oc-card-header">' +
        '<span class="oc-card-title">' + _esc(k.label.toUpperCase()) + '</span>' +
        _statusPill(status) +
      '</div>' +
      errHtml +
      '<div style="margin-top:.75rem;display:flex;align-items:center">' + action + '</div>' +
      '</div>';
  }).join('');
}

window.saveApiKey = function(provider) {
  var input = document.getElementById('apikey-' + provider);
  if (!input || !input.value) return;
  _toast('Key noted for ' + provider + '. Persistence not yet wired (W4).', 'info');
  input.value = '';
};

// ── Runs ──────────────────────────────────────────────────────────────────────

window.loadRuns = async function(page) {
  page = page || 1;
  var tbody = document.getElementById('runs-list');
  if (tbody) tbody.innerHTML = _skeletonRows(6, 5);

  var status = document.getElementById('runs-status-filter')?.value || '';
  var qs = new URLSearchParams({page: page, per_page: 25});
  if (status) qs.set('status', status);
  var r    = await authFetch('/api/v1/runs?' + qs);
  var data = await r.json();

  tbody.innerHTML = data.items.length
    ? data.items.map(function(r) {
        return '<tr>' +
          '<td style="font-family:var(--mono);font-size:.73rem;color:var(--accent)">' + _esc(r.kind) + '</td>' +
          '<td style="font-family:var(--mono);font-size:.7rem;color:var(--t-mid)">' + _esc(r.correlation_id.slice(0,24)) + '&#8230;</td>' +
          '<td>' + _statusPill(r.status) + '</td>' +
          '<td style="font-size:.75rem;color:var(--t-mid);white-space:nowrap">' + _esc(_ts(r.started_at)) + '</td>' +
          '<td style="font-size:.75rem;text-align:right;color:var(--t-mid)">' + _esc(String(r.retry_count)) + '</td>' +
          '</tr>';
      }).join('')
    : '<tr><td colspan="5" class="oc-empty">No runs.</td></tr>';

  document.getElementById('runs-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadRuns');
};

// ── DLQ ───────────────────────────────────────────────────────────────────────

window.loadDlq = async function(page) {
  page = page || 1;
  var tbody = document.getElementById('dlq-list');
  if (tbody) tbody.innerHTML = _skeletonRows(5, 5);

  var r    = await authFetch('/api/v1/dlq?page=' + page + '&per_page=25');
  var data = await r.json();

  tbody.innerHTML = data.items.length
    ? data.items.map(function(item) {
        return '<tr>' +
          '<td style="font-family:var(--mono);font-size:.73rem;color:var(--accent)">' + _esc(item.kind) + '</td>' +
          '<td style="font-family:var(--mono);font-size:.7rem;color:var(--t-mid)">' + _esc(item.correlation_id.slice(0,22)) + '&#8230;</td>' +
          '<td style="font-size:.75rem;color:var(--err)">' + _esc(item.error_code || '—') + '</td>' +
          '<td style="font-size:.75rem;text-align:right;color:var(--t-mid)">' + _esc(String(item.retry_count)) + '</td>' +
          '<td style="white-space:nowrap">' +
            '<button class="oc-btn oc-btn-primary oc-btn-sm" style="margin-right:.3rem" onclick="retryDlq(\'' + _esc(item.id) + '\')">RETRY</button>' +
            '<button class="oc-btn oc-btn-danger  oc-btn-sm" onclick="dismissDlq(\'' + _esc(item.id) + '\')">DISMISS</button>' +
          '</td>' +
          '</tr>';
      }).join('')
    : '<tr><td colspan="5" class="oc-empty">DLQ is empty.</td></tr>';

  document.getElementById('dlq-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadDlq');
};

window.retryDlq = async function(id) {
  var r = await authFetch('/api/v1/dlq/' + id + '/retry', {method:'POST'});
  if (r.ok) { _toast('Queued for retry', 'ok'); loadDlq(1); }
  else _toast('Retry failed (HTTP ' + r.status + ')', 'error');
};

window.dismissDlq = async function(id) {
  var r = await authFetch('/api/v1/dlq/' + id + '/dismiss', {method:'POST'});
  if (r.ok) { _toast('Item dismissed', 'ok'); loadDlq(1); }
  else _toast('Dismiss failed (HTTP ' + r.status + ')', 'error');
};

// ── Config ────────────────────────────────────────────────────────────────────

var _origConfig = '';

async function loadConfig() {
  var editor = document.getElementById('config-editor');
  if (editor) editor.value = '';
  var r    = await authFetch('/api/v1/config');
  var data = await r.json();
  _origConfig = data.yaml_text;
  if (editor) editor.value = data.yaml_text;
  var diff = document.getElementById('config-diff');
  if (diff) diff.style.display = 'none';
  var msg = document.getElementById('config-msg');
  if (msg) msg.textContent = '';
}

function _diffHtml(oldT, newT) {
  var o = oldT.split('\n');
  var n = newT.split('\n');
  var out = [];
  for (var i = 0; i < Math.max(o.length, n.length); i++) {
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
      saveBtn.innerHTML = '<span class="oc-spin"></span> SAVING…';
      try {
        var r = await authFetch('/api/v1/config', {
          method: 'PUT',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({yaml_text: yaml_text}),
        });
        var data = await r.json();
        if (r.ok) {
          msg.style.color = 'var(--ok)';
          msg.textContent = 'Saved. Reload event published.';
          _origConfig = data.yaml_text;
          document.getElementById('config-diff').style.display = 'none';
          _toast('Config saved and reload event published', 'ok');
        } else {
          msg.style.color = 'var(--err)';
          msg.textContent = data.detail || 'Save failed';
          _toast(data.detail || 'Config save failed', 'error');
        }
      } catch (e) {
        msg.style.color = 'var(--err)';
        msg.textContent = String(e);
        _toast('Config save error: ' + e.message, 'error');
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = 'SAVE CONFIG';
      }
    });
  }
});

// ── Audit ─────────────────────────────────────────────────────────────────────

window.loadAudit = async function(page) {
  page = page || 1;
  var tbody = document.getElementById('audit-list');
  if (tbody) tbody.innerHTML = _skeletonRows(6, 4);

  var actor  = document.getElementById('audit-actor-filter')?.value  || '';
  var action = document.getElementById('audit-action-filter')?.value || '';
  var qs = new URLSearchParams({page: page, per_page: 50});
  if (actor)  qs.set('actor',  actor);
  if (action) qs.set('action', action);
  var r    = await authFetch('/api/v1/audit?' + qs);
  var data = await r.json();

  tbody.innerHTML = data.items.length
    ? data.items.map(function(e) {
        return '<tr>' +
          '<td style="font-size:.72rem;white-space:nowrap;color:var(--t-mid)">' + _esc(_ts(e.at)) + '</td>' +
          '<td style="font-family:var(--mono);font-size:.73rem;color:var(--accent)">' + _esc(e.actor) + '</td>' +
          '<td style="font-family:var(--mono);font-size:.73rem">' + _esc(e.action) + '</td>' +
          '<td style="font-size:.75rem;color:var(--t-mid)">' + _esc(e.target) + '</td>' +
          '</tr>';
      }).join('')
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
  var container = document.getElementById('selectors-list');
  container.innerHTML = '<div class="oc-spinner-wrap"><div class="oc-spinner"></div></div>';

  var r     = await authFetch('/api/v1/selectors');
  var items = await r.json();

  if (!items.length) {
    container.innerHTML = '<div class="oc-empty">No pending selector proposals.</div>';
    return;
  }

  container.innerHTML = items.map(function(s) {
    return '<div class="oc-card" id="sel-' + _esc(s.id) + '">' +
      '<div class="oc-card-header">' +
        '<span class="oc-card-title">' + _esc(s.source.toUpperCase()) + ' &mdash; ' + _esc(s.key_path) + '</span>' +
        _statusPill(s.status) +
      '</div>' +
      '<div style="font-family:var(--mono);font-size:.78rem;color:var(--ok);margin-bottom:.5rem">NEW: ' + _esc(s.selector) + '</div>' +
      '<div style="font-size:.73rem;color:var(--t-mid);margin-bottom:.875rem">' +
        'Proposed by <strong style="color:var(--t-hi)">' + _esc(s.proposed_by) + '</strong> at ' + _esc(_ts(s.proposed_at)) +
      '</div>' +
      '<div style="display:flex;gap:.5rem">' +
        '<button class="oc-btn oc-btn-primary oc-btn-sm" onclick="approveSelector(\'' + _esc(s.id) + '\')">APPROVE</button>' +
        '<button class="oc-btn oc-btn-danger  oc-btn-sm" onclick="rejectSelector(\'' + _esc(s.id) + '\')">REJECT</button>' +
      '</div>' +
      '</div>';
  }).join('');
}

window.approveSelector = async function(id) {
  var r = await authFetch('/api/v1/selectors/' + id + '/approve', {method:'POST'});
  if (r.ok) { _toast('Selector approved', 'ok'); loadSelectors(); }
  else _toast('Approve failed (HTTP ' + r.status + ')', 'error');
};

window.rejectSelector = async function(id) {
  var r = await authFetch('/api/v1/selectors/' + id + '/reject', {method:'POST'});
  if (r.ok) { _toast('Selector rejected', 'ok'); loadSelectors(); }
  else _toast('Reject failed (HTTP ' + r.status + ')', 'error');
};

// ── Jobs ──────────────────────────────────────────────────────────────────────

window.loadJobs = async function(page) {
  page = page || 1;
  var tbody = document.getElementById('jobs-list');
  if (tbody) tbody.innerHTML = _skeletonRows(8, 7);

  var status = document.getElementById('jobs-status-filter')?.value || '';
  var source = document.getElementById('jobs-source-filter')?.value || '';
  var qs = new URLSearchParams({page: page, per_page: 50});
  if (status) qs.set('status', status);
  if (source) qs.set('source', source);

  var r    = await authFetch('/api/v1/jobs?' + qs);
  var data = await r.json();

  var countEl = document.getElementById('jobs-count');
  if (countEl) countEl.textContent = data.total + ' TOTAL';

  tbody.innerHTML = data.items.length
    ? data.items.map(function(j) {
        var score = j.match_score != null
          ? '<span class="oc-score" style="--s:' + Math.round(j.match_score) + '">' + Math.round(j.match_score) + '</span>'
          : '<span style="color:var(--t-lo)">—</span>';
        var star = j.starred
          ? '<button class="oc-btn oc-btn-sm oc-btn-star active" title="Unstar" onclick="toggleStar(\'' + _esc(j.id) + '\')">&#9733;</button>'
          : '<button class="oc-btn oc-btn-sm oc-btn-star" title="Star"   onclick="toggleStar(\'' + _esc(j.id) + '\')">&#9734;</button>';
        var dimmed = j.dismissed ? ' style="opacity:.4"' : '';
        return '<tr' + dimmed + '>' +
          '<td style="font-size:.75rem;max-width:220px"><a href="' + _esc(j.url || '#') + '" target="_blank" rel="noopener" class="oc-job-link">' + _esc(j.title) + '</a></td>' +
          '<td style="font-size:.75rem;color:var(--t-mid)">' + _esc(j.company) + '</td>' +
          '<td style="font-size:.75rem;color:var(--t-mid)">' + _esc(j.location || '—') + '</td>' +
          '<td><span class="oc-source-badge ' + _esc(j.source) + '">' + _esc(j.source.toUpperCase()) + '</span></td>' +
          '<td style="text-align:center">' + score + '</td>' +
          '<td>' + _statusPill(j.status) + '</td>' +
          '<td style="white-space:nowrap">' +
            star +
            '<button class="oc-btn oc-btn-ghost oc-btn-sm" style="margin-left:.3rem" onclick="tailorJob(\'' + _esc(j.id) + '\')" title="Generate tailored resume + cover letter">TAILOR</button>' +
            (j.dismissed
              ? ''
              : '<button class="oc-btn oc-btn-danger oc-btn-sm" style="margin-left:.3rem" onclick="dismissJob(\'' + _esc(j.id) + '\')">✕</button>') +
          '</td>' +
          '</tr>';
      }).join('')
    : '<tr><td colspan="7" class="oc-empty">No jobs found.</td></tr>';

  document.getElementById('jobs-pagination').innerHTML =
    _paginationButtons(page, data.has_next, 'loadJobs');
};

window.toggleStar = async function(id) {
  var r = await authFetch('/api/v1/jobs/' + id + '/star', {method: 'POST'});
  if (r.ok) loadJobs(1);
  else _toast('Action failed', 'error');
};

window.dismissJob = async function(id) {
  var r = await authFetch('/api/v1/jobs/' + id + '/dismiss', {method: 'POST'});
  if (r.ok) { _toast('Job dismissed', 'ok'); loadJobs(1); }
  else _toast('Dismiss failed', 'error');
};

window.tailorJob = async function(id) {
  _toast('Tailoring queued…', 'info');
  var r = await authFetch('/api/v1/jobs/' + id + '/tailor', {method: 'POST'});
  if (r.ok) _toast('Tailor task queued', 'ok');
  else {
    var d = await r.json().catch(function() { return {}; });
    _toast(d.detail || 'Tailor failed (HTTP ' + r.status + ')', 'error');
  }
};

document.addEventListener('DOMContentLoaded', function() {
  var sf = document.getElementById('jobs-status-filter');
  var xf = document.getElementById('jobs-source-filter');
  if (sf) sf.addEventListener('change', function() { loadJobs(1); });
  if (xf) xf.addEventListener('change', function() { loadJobs(1); });
});

// ── Profile ───────────────────────────────────────────────────────────────────

var _profileData = {};
var _profileTitles = [];
var _profileSkills = [];

function _renderTags(containerId, items, inputId, arrRef) {
  var container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = items.map(function(tag, i) {
    return '<span class="oc-tag">' + _esc(tag) +
      '<button class="oc-tag-remove" aria-label="Remove ' + _esc(tag) + '" data-i="' + i + '">&#x2715;</button>' +
      '</span>';
  }).join('');
  container.querySelectorAll('.oc-tag-remove').forEach(function(btn) {
    btn.addEventListener('click', function() {
      arrRef.splice(parseInt(btn.dataset.i), 1);
      _renderTags(containerId, arrRef, inputId, arrRef);
    });
  });
}

function _setupTagInput(inputId, containerId, arrRef) {
  var input = document.getElementById(inputId);
  if (!input) return;
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      var val = input.value.trim().replace(/,$/, '');
      if (val && !arrRef.includes(val)) {
        arrRef.push(val);
        _renderTags(containerId, arrRef, inputId, arrRef);
      }
      input.value = '';
    }
  });
}

function _renderExperience() {
  var list = document.getElementById('prof-experience-list');
  if (!list) return;
  var exp = _profileData.experience || [];
  if (!exp.length) {
    list.innerHTML = '<div class="oc-empty">No experience entries.</div>';
    return;
  }
  list.innerHTML = exp.map(function(e, i) {
    return '<div class="oc-exp-item" data-i="' + i + '">' +
      '<div class="oc-exp-header">' +
        '<div style="flex:1">' +
          '<div style="font-size:.82rem;font-weight:600;color:var(--t-hi)">' + _esc(e.title) + '</div>' +
          '<div style="font-size:.73rem;color:var(--t-mid);font-family:var(--mono)">' + _esc(e.company) + ' &bull; ' + _esc(e.dates) + '</div>' +
        '</div>' +
        '<button class="oc-btn oc-btn-danger oc-btn-sm" onclick="removeExperience(' + i + ')">REMOVE</button>' +
      '</div>' +
      '<ul style="margin:.5rem 0 0 1.25rem;display:flex;flex-direction:column;gap:.25rem">' +
        (e.bullets || []).map(function(b) { return '<li style="font-size:.76rem;color:var(--t-mid)">' + _esc(b) + '</li>'; }).join('') +
      '</ul>' +
      '</div>';
  }).join('');
}

window.addExperience = function() {
  var title   = prompt('Job title:');   if (!title)   return;
  var company = prompt('Company:');     if (!company) return;
  var dates   = prompt('Date range (e.g. 01/2020 - 12/2022):') || '';
  var bullStr = prompt('Bullet points (one per line):') || '';
  var bullets = bullStr.split('\n').map(function(s) { return s.trim(); }).filter(Boolean);
  (_profileData.experience = _profileData.experience || []).push({title: title, company: company, dates: dates, bullets: bullets});
  _renderExperience();
};

window.removeExperience = function(i) {
  if (_profileData.experience) {
    _profileData.experience.splice(i, 1);
    _renderExperience();
  }
};

async function loadProfile() {
  var r    = await authFetch('/api/v1/profile');
  var body = await r.json();
  _profileData   = body.data || {};
  _profileTitles = (_profileData.preferred_titles || []).slice();
  _profileSkills = (_profileData.skills || []).slice();

  var set = function(id, val) {
    var el = document.getElementById(id);
    if (el) el.value = val || '';
  };
  set('prof-name',     _profileData.name);
  set('prof-email',    _profileData.email);
  set('prof-phone',    _profileData.phone);
  set('prof-location', _profileData.location);
  set('prof-headline', _profileData.headline);
  set('prof-summary',  _profileData.summary);

  _renderTags('prof-titles-tags', _profileTitles, 'prof-titles-input', _profileTitles);
  _setupTagInput('prof-titles-input', 'prof-titles-tags', _profileTitles);
  _renderTags('prof-skills-tags', _profileSkills, 'prof-skills-input', _profileSkills);
  _setupTagInput('prof-skills-input', 'prof-skills-tags', _profileSkills);
  _renderExperience();
}

document.addEventListener('DOMContentLoaded', function() {
  var saveBtn = document.getElementById('prof-save-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async function() {
      var msg = document.getElementById('prof-msg');
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="oc-spin"></span> SAVING…';
      try {
        _profileData.name              = document.getElementById('prof-name')?.value || '';
        _profileData.email             = document.getElementById('prof-email')?.value || '';
        _profileData.phone             = document.getElementById('prof-phone')?.value || '';
        _profileData.location          = document.getElementById('prof-location')?.value || '';
        _profileData.headline          = document.getElementById('prof-headline')?.value || '';
        _profileData.summary           = document.getElementById('prof-summary')?.value || '';
        _profileData.preferred_titles  = _profileTitles.slice();
        _profileData.skills            = _profileSkills.slice();

        var r = await authFetch('/api/v1/profile', {
          method:  'PUT',
          headers: {'Content-Type': 'application/json'},
          body:    JSON.stringify({data: _profileData}),
        });
        if (r.ok) {
          msg.style.color = 'var(--ok)';
          msg.textContent = 'Saved.';
          _toast('Profile saved', 'ok');
          setTimeout(function() { msg.textContent = ''; }, 3000);
        } else {
          var err = await r.json().catch(function() { return {}; });
          msg.style.color = 'var(--err)';
          msg.textContent = err.detail || 'Save failed';
          _toast('Profile save failed', 'error');
        }
      } catch (e) {
        msg.style.color = 'var(--err)';
        msg.textContent = String(e);
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = 'SAVE PROFILE';
      }
    });
  }
});

// ── Resume & Artifacts ────────────────────────────────────────────────────────

function _bytesLabel(n) {
  if (n < 1024) return n + ' B';
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
  return (n / 1048576).toFixed(1) + ' MB';
}

function _artifactRow(subdir, file) {
  return '<div class="oc-artifact-row">' +
    '<span class="oc-artifact-name" title="' + _esc(file.name) + '">' + _esc(file.name) + '</span>' +
    '<span class="oc-artifact-meta">' + _esc(_bytesLabel(file.size)) + ' &bull; ' + _esc(_ts(file.modified)) + '</span>' +
    '<a href="/api/v1/artifacts/download/' + _esc(subdir) + '/' + _esc(encodeURIComponent(file.name)) + '" class="oc-btn oc-btn-ghost oc-btn-sm" download>' +
      'DOWNLOAD' +
    '</a>' +
    '</div>';
}

function _artifactList(containerId, subdir, files) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = files.length
    ? files.map(function(f) { return _artifactRow(subdir, f); }).join('')
    : '<div class="oc-empty">No files yet.</div>';
}

async function loadResume() {
  var r    = await authFetch('/api/v1/artifacts');
  var data = await r.json();
  _artifactList('resume-uploads-list',  'uploads', data.uploads);
  _artifactList('resume-resumes-list',  'resumes', data.resumes);
  _artifactList('resume-covers-list',   'covers',  data.covers);
}

document.addEventListener('DOMContentLoaded', function() {
  var dz    = document.getElementById('resume-dropzone');
  var input = document.getElementById('resume-file-input');
  var status = document.getElementById('resume-upload-status');
  if (!dz || !input) return;

  function _startUpload(file) {
    if (!file) return;
    status.style.color = 'var(--t-mid)';
    status.textContent = 'Uploading ' + file.name + '…';
    dz.classList.add('oc-dropzone-busy');

    var fd = new FormData();
    fd.append('file', file);
    authFetch('/api/v1/artifacts/upload', {method: 'POST', body: fd})
      .then(function(r) { return r.json().then(function(d) { return {ok: r.ok, d: d}; }); })
      .then(function(res) {
        dz.classList.remove('oc-dropzone-busy');
        if (res.ok) {
          status.style.color = 'var(--ok)';
          status.textContent = res.d.name + ' uploaded (' + _bytesLabel(res.d.size) + ')';
          _toast('Resume uploaded', 'ok');
          if (document.getElementById('resume-uploads-list')) loadResume();
        } else {
          status.style.color = 'var(--err)';
          status.textContent = res.d.detail || 'Upload failed';
          _toast('Upload failed', 'error');
        }
      })
      .catch(function(e) {
        dz.classList.remove('oc-dropzone-busy');
        status.style.color = 'var(--err)';
        status.textContent = String(e);
        _toast('Upload error', 'error');
      });
  }

  dz.addEventListener('click', function() { input.click(); });
  dz.addEventListener('keydown', function(e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  input.addEventListener('change', function() { if (input.files[0]) _startUpload(input.files[0]); input.value = ''; });

  dz.addEventListener('dragover', function(e) { e.preventDefault(); dz.classList.add('oc-dropzone-over'); });
  dz.addEventListener('dragleave', function() { dz.classList.remove('oc-dropzone-over'); });
  dz.addEventListener('drop', function(e) {
    e.preventDefault();
    dz.classList.remove('oc-dropzone-over');
    var file = e.dataTransfer?.files[0];
    if (file) _startUpload(file);
  });
});

// ── Credentials ───────────────────────────────────────────────────────────────

async function loadCredentials() {
  var r    = await authFetch('/api/v1/credentials');
  var data = await r.json();

  ['linkedin', 'naukri'].forEach(function(platform) {
    var info    = data.platforms[platform] || {};
    var pillEl  = document.getElementById('cred-' + platform + '-pill');
    var sessEl  = document.getElementById('cred-' + platform + '-session');
    var emailEl = document.getElementById('cred-' + platform + '-email');

    if (pillEl) pillEl.outerHTML = _statusPill(info.status === 'connected' ? 'connected' : info.status === 'expired' ? 'failed' : 'pending');
    if (sessEl) {
      sessEl.textContent = info.session_at
        ? 'Last session: ' + _ts(info.session_at)
        : 'No active session stored.';
    }
    if (emailEl && info.email) emailEl.value = info.email;
  });
}

window.saveCredentials = async function(platform) {
  var email = document.getElementById('cred-' + platform + '-email')?.value?.trim();
  var pass  = document.getElementById('cred-' + platform + '-pass')?.value;
  var msg   = document.getElementById('cred-' + platform + '-msg');
  if (!email || !pass) {
    if (msg) { msg.style.color = 'var(--err)'; msg.textContent = 'Email and password required.'; }
    return;
  }
  try {
    var r = await authFetch('/api/v1/credentials', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({platform: platform, email: email, password: pass}),
    });
    if (r.ok) {
      if (msg) { msg.style.color = 'var(--ok)'; msg.textContent = 'Saved.'; }
      document.getElementById('cred-' + platform + '-pass').value = '';
      _toast(platform + ' credentials saved', 'ok');
      setTimeout(function() { if (msg) msg.textContent = ''; }, 3000);
    } else {
      var err = await r.json().catch(function() { return {}; });
      if (msg) { msg.style.color = 'var(--err)'; msg.textContent = err.detail || 'Save failed'; }
    }
  } catch (e) {
    if (msg) { msg.style.color = 'var(--err)'; msg.textContent = String(e); }
  }
};

window.triggerRelogin = async function(platform) {
  var btn = document.getElementById('cred-' + platform + '-relogin');
  var msg = document.getElementById('cred-' + platform + '-msg');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="oc-spin"></span> LOGGING IN…'; }
  try {
    var r = await authFetch('/api/v1/credentials/' + platform + '/relogin', {method: 'POST'});
    var d = await r.json().catch(function() { return {}; });
    if (r.ok) {
      if (msg) { msg.style.color = 'var(--ok)'; msg.textContent = 'Task queued (' + (d.task_id || '').slice(0,8) + '…)'; }
      _toast(platform + ' re-login queued', 'ok');
      setTimeout(function() { loadCredentials(); }, 5000);
    } else {
      if (msg) { msg.style.color = 'var(--err)'; msg.textContent = d.detail || 'Failed'; }
      _toast(d.detail || platform + ' re-login failed', 'error');
    }
  } catch (e) {
    if (msg) { msg.style.color = 'var(--err)'; msg.textContent = String(e); }
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = 'RE-LOGIN'; }
  }
};

// ── Pipeline trigger ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  var btn = document.getElementById('trigger-btn');
  if (!btn) return;
  btn.addEventListener('click', async function() {
    btn.disabled = true;
    btn.innerHTML = '<span class="oc-spin"></span> QUEUING…';
    try {
      var key = 'web-' + Date.now();
      var r   = await authFetch('/api/v1/pipeline/trigger', {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'Idempotency-Key': key},
        body: JSON.stringify({}),
      });
      var data = await r.json();
      btn.innerHTML = '&#10003; ' + _esc(data.correlation_id.slice(0,8)) + '…';
      _toast('Pipeline queued (' + data.correlation_id.slice(0,8) + '…)', 'ok');
      setTimeout(function() {
        btn.innerHTML = '<svg viewBox="0 0 20 20" fill="currentColor" style="width:12px;height:12px"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/></svg> TRIGGER PIPELINE';
        btn.disabled = false;
      }, 4000);
    } catch (e) {
      btn.innerHTML = '<svg viewBox="0 0 20 20" fill="currentColor" style="width:12px;height:12px"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/></svg> TRIGGER PIPELINE';
      btn.disabled = false;
      _toast('Trigger failed: ' + (e.message || e), 'error');
    }
  });
});

// ── Runs filter ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  var f = document.getElementById('runs-status-filter');
  if (f) f.addEventListener('change', function() { loadRuns(1); });
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
  _startClock();

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
      errEl.style.display = 'none';
      if (!secret) {
        errEl.style.display = 'block';
        errEl.textContent = 'Enter the bootstrap secret.';
        return;
      }
      loginBtn.disabled = true;
      loginBtn.innerHTML = '<span class="oc-spin"></span> PAIRING…';
      try {
        await pairDevice(secret);
        _showConsole();
        _loadRoute(currentRoute());
      } catch (e) {
        errEl.style.display = 'block';
        errEl.textContent = e.message || 'Pairing failed.';
        loginBtn.disabled = false;
        loginBtn.innerHTML = 'PAIR DEVICE';
      }
    });
  }

  /* Bootstrap input: pair on Enter */
  var inp = document.getElementById('bootstrap-input');
  if (inp) {
    inp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') document.getElementById('login-btn')?.click();
    });
  }

  initAuth().then(function(result) {
    if (result === 'console') {
      _showConsole();
      _loadRoute(currentRoute());
    } else {
      _showLogin();
    }
  });
});
