/* auth.js — Ed25519 device-pairing, IndexedDB key persistence, silent re-auth */

const _JWT_KEY = 'jaa_jwt';
const _IDB_NAME = 'jobai-auth';
const _IDB_STORE = 'keys';
const _IDB_RECORD = 'device';

// ── Token helpers ─────────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem(_JWT_KEY);
}

function clearToken() {
  localStorage.removeItem(_JWT_KEY);
}

function _decodeJwtPayload(token) {
  try {
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(b64));
  } catch { return null; }
}

// ── Byte helpers ──────────────────────────────────────────────────────────────

function _hexToBytes(hex) {
  return new Uint8Array(hex.match(/.{2}/g).map(b => parseInt(b, 16)));
}

function _bytesToHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

// ── IndexedDB — store / load Ed25519 private key ──────────────────────────────

function _openIdb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(_IDB_NAME, 1);
    req.onupgradeneeded = e => e.target.result.createObjectStore(_IDB_STORE);
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  });
}

async function _saveKeyRecord(privateKey, deviceId) {
  const db = await _openIdb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(_IDB_STORE, 'readwrite');
    tx.objectStore(_IDB_STORE).put({ privateKey, deviceId }, _IDB_RECORD);
    tx.oncomplete = resolve;
    tx.onerror = e => reject(e.target.error);
  });
}

async function _loadKeyRecord() {
  const db = await _openIdb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(_IDB_STORE, 'readonly');
    const req = tx.objectStore(_IDB_STORE).get(_IDB_RECORD);
    req.onsuccess = e => resolve(e.target.result || null);
    req.onerror = e => reject(e.target.error);
  });
}

async function _clearKeyRecord() {
  const db = await _openIdb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(_IDB_STORE, 'readwrite');
    tx.objectStore(_IDB_STORE).delete(_IDB_RECORD);
    tx.oncomplete = resolve;
    tx.onerror = e => reject(e.target.error);
  });
}

// ── Pairing — first-time bootstrap ───────────────────────────────────────────

async function pairDevice(bootstrapSecret) {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'Ed25519' }, true, ['sign', 'verify']
  );
  const pubRaw = await crypto.subtle.exportKey('spki', keyPair.publicKey);
  const pubHex = _bytesToHex(new Uint8Array(pubRaw));

  const cr = await fetch('/api/v1/auth/challenge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bootstrap_secret: bootstrapSecret }),
  });
  if (!cr.ok) {
    const err = await cr.json().catch(() => ({}));
    throw new Error(err.detail || `Challenge failed (${cr.status})`);
  }
  const { challenge } = await cr.json();

  const sig = await crypto.subtle.sign('Ed25519', keyPair.privateKey, _hexToBytes(challenge));
  const sigHex = _bytesToHex(new Uint8Array(sig));

  const pr = await fetch('/api/v1/auth/pair', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bootstrap_secret: bootstrapSecret, public_key: pubHex, signature: sigHex }),
  });
  if (!pr.ok) {
    const err = await pr.json().catch(() => ({}));
    throw new Error(err.detail || `Pairing failed (${pr.status})`);
  }
  const { token } = await pr.json();

  // Persist private key + device_id so we can renew silently later
  const payload = _decodeJwtPayload(token);
  if (payload?.sub) {
    await _saveKeyRecord(keyPair.privateKey, payload.sub);
  }

  localStorage.setItem(_JWT_KEY, token);
  return token;
}

// ── Silent re-auth — sign fresh challenge with stored private key ─────────────

async function renewToken() {
  const record = await _loadKeyRecord();
  if (!record) throw new Error('no_key_stored');

  const cr = await fetch('/api/v1/auth/reauth/challenge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_id: record.deviceId }),
  });
  if (!cr.ok) throw new Error('reauth_challenge_failed');
  const { challenge } = await cr.json();

  const sig = await crypto.subtle.sign('Ed25519', record.privateKey, _hexToBytes(challenge));
  const sigHex = _bytesToHex(new Uint8Array(sig));

  const tr = await fetch('/api/v1/auth/reauth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_id: record.deviceId, signature: sigHex }),
  });
  if (!tr.ok) throw new Error('reauth_failed');
  const { token } = await tr.json();

  localStorage.setItem(_JWT_KEY, token);
  return token;
}

// ── Authenticated fetch — auto-renew on 401 ───────────────────────────────────

async function authFetch(url, opts = {}) {
  const token = getToken();
  if (!token) throw Object.assign(new Error('Not authenticated'), { status: 401 });

  const headers = { ...opts.headers, Authorization: `Bearer ${token}` };
  const r = await fetch(url, { ...opts, headers });

  if (r.status === 401) {
    // Try silent renew before giving up
    try {
      await renewToken();
      const newToken = getToken();
      const retryHeaders = { ...opts.headers, Authorization: `Bearer ${newToken}` };
      const retry = await fetch(url, { ...opts, headers: retryHeaders });
      if (retry.status !== 401) return retry;
    } catch (_) { /* fall through to hard logout */ }

    // Renew failed — device revoked or key gone, force re-pair
    clearToken();
    await _clearKeyRecord().catch(() => {});
    window.location.reload();
    throw Object.assign(new Error('Session expired'), { status: 401 });
  }

  return r;
}

// ── Boot helper — call from app.js on DOMContentLoaded ───────────────────────

/**
 * Returns 'console' if ready to show the app, 'login' if bootstrap needed.
 * Attempts silent renewToken() if token missing but private key is stored.
 */
async function initAuth() {
  if (getToken()) return 'console';
  try {
    await renewToken();
    return 'console';
  } catch (_) {
    return 'login';
  }
}
