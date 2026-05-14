/**
 * JetWatch Africa — Implémentation Crypto Client
 * 
 * ECDH pour le chiffrement des sessions
 * EC Proof-of-Work (SHA-256 synchrone) pour le défi mathématique
 */

const API_URL = import.meta.env.VITE_API_URL || '';

let currentSessionId: string | null = null;
let sharedSecretAesKey: CryptoKey | null = null;

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) bytes[i/2] = parseInt(hex.substring(i, i+2), 16);
  return bytes;
}

export function getSessionId(): string | null {
  return currentSessionId;
}

export async function initEcdhSession(): Promise<void> {
  try {
    const keyPair = await window.crypto.subtle.generateKey(
      { name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveKey', 'deriveBits']
    );
    const exportedPublicKey = await window.crypto.subtle.exportKey('spki', keyPair.publicKey);
    const exportedAsBase64 = btoa(String.fromCharCode.apply(null, new Uint8Array(exportedPublicKey) as unknown as number[]));
    const clientPublicKeyPem = `-----BEGIN PUBLIC KEY-----\n${exportedAsBase64.match(/.{1,64}/g)?.join('\n')}\n-----END PUBLIC KEY-----`;

    const resp = await fetch(`${API_URL}/ecdh/handshake`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_public_key_pem: clientPublicKeyPem }),
    });

    if (!resp.ok) throw new Error('Échec ECDH');
    const data = await resp.json();
    currentSessionId = data.session_id;
  } catch (err) {
    console.error('Erreur initEcdhSession:', err);
  }
}

export async function getPoWToken(): Promise<{ challengeId: string, nonce: string }> {
  const resp = await fetch(`${API_URL}/pow/challenge`, { cache: 'no-store' });
  if (!resp.ok) throw new Error('Impossible de récupérer le challenge PoW');

  const challenge = await resp.json();
  const challengeId = challenge.challenge_id;
  const xBytes = hexToBytes(challenge.point_x);
  const yBytes = hexToBytes(challenge.point_y);
  const difficulty = challenge.difficulty;

  const fullBytes = Math.floor(difficulty / 8);
  const remainingBits = difficulty % 8;
  const mask = (0xFF << (8 - remainingBits)) & 0xFF;

  const buffer = new Uint8Array(xBytes.length + yBytes.length + 8);
  buffer.set(xBytes, 0);
  buffer.set(yBytes, xBytes.length);

  const maxNonce = 30000000;

  for (let nonce = 0; nonce < maxNonce; nonce++) {
    // Écriture du nonce (Big Endian 8 bytes)
    let n = nonce;
    for (let i = 7; i >= 0; i--) {
      buffer[xBytes.length + yBytes.length + i] = n & 0xff;
      n >>>= 8;
    }

    // Utilise le SHA-256 natif du navigateur (correct et rapide)
    const hashBuf = await crypto.subtle.digest('SHA-256', buffer);
    const hash = new Uint8Array(hashBuf);

    let valid = true;
    for (let i = 0; i < fullBytes; i++) {
      if (hash[i] !== 0) { valid = false; break; }
    }
    if (valid && remainingBits > 0) {
      if ((hash[fullBytes] & mask) !== 0) valid = false;
    }

    if (valid) {
      return { challengeId, nonce: nonce.toString() };
    }
  }

  throw new Error("PoW a échoué (difficulté extrême, >30M itérations)");
}

