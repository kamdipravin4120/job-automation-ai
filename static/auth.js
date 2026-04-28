/* auth.js — Web Crypto Ed25519 device-pairing + authenticated fetch */

const _JWT_KEY = 'jaa_jwt';

function getToken() {
  return localStorage.getItem(_JWT_KEY);
}

function clearToken() {
  localStorage.removeItem(_JWT_KEY);
}

function _hexToBytes(hex) {
  return new Uint8Array(hex.match(/.{2}/g).map(b => parseInt(b, 16)));
}

function _bytesToHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

function _rawToPem(raw, label) {
  const b64 = btoa(String.fromCharCode(...new Uint8Array(raw)));
  const lines = b64.match(/.{1,64}/g).join('\n');
  return `-----BEGIN ${label}-----\n${lines}\n-----END ${label}-----`;
}

async function pairDevice(bootstrapSecret) {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'Ed25519' }, true, ['sign', 'verify']
  );
  const pubRaw = await crypto.subtle.exportKey('spki', keyPair.publicKey);
  const pubPem = _rawToPem(pubRaw, 'PUBLIC KEY');

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

  const sig = await crypto.subtle.sign(
    'Ed25519', keyPair.privateKey, _hexToBytes(challenge)
  );
  const sigHex = _bytesToHex(new Uint8Array(sig));

  const pr = await fetch('/api/v1/auth/pair', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bootstrap_secret: bootstrapSecret,
      public_key: pubPem,
      signature: sigHex,
    }),
  });
  if (!pr.ok) {
    const err = await pr.json().catch(() => ({}));
    throw new Error(err.detail || `Pairing failed (${pr.status})`);
  }
  const { token } = await pr.json();
  localStorage.setItem(_JWT_KEY, token);
  return token;
}

async function authFetch(url, opts = {}) {
  const token = getToken();
  if (!token) throw Object.assign(new Error('Not authenticated'), { status: 401 });
  const headers = { ...opts.headers, Authorization: `Bearer ${token}` };
  const r = await fetch(url, { ...opts, headers });
  if (r.status === 401) {
    clearToken();
    window.location.reload();
    throw Object.assign(new Error('Session expired'), { status: 401 });
  }
  return r;
}
