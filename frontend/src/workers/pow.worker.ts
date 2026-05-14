/**
 * JetWatch Africa — Web Worker : Solveur EC Proof-of-Work
 *
 * Ce worker tourne dans un thread dédié pour ne pas bloquer l'interface.
 * Il reçoit un défi EC-PoW du serveur et cherche un nonce valide via SHA-256.
 *
 * Algorithme :
 *   Trouver nonce ∈ ℕ tel que :
 *   SHA256( point_x_bytes(32) ‖ point_y_bytes(32) ‖ nonce_bytes(8) )
 *   commence par `difficulty` bits à zéro.
 *
 * Complexité moyenne : 2^difficulty essais → ~65ms pour difficulty=16
 */

interface PowChallenge {
  challenge_id: string;
  point_x: string;   // Hex 64 chars (256-bit)
  point_y: string;   // Hex 64 chars (256-bit)
  difficulty: number;
  expires_at: number;
}

interface PowResult {
  challenge_id: string;
  nonce: number;
  attempts: number;
  duration_ms: number;
}

// ── Utilitaires de conversion ─────────────────────────────────────────

function hexToBytes(hex: string): Uint8Array {
  // S'assurer d'une longueur paire
  const padded = hex.length % 2 === 0 ? hex : '0' + hex;
  const bytes = new Uint8Array(padded.length / 2);
  for (let i = 0; i < padded.length; i += 2) {
    bytes[i / 2] = parseInt(padded.slice(i, i + 2), 16);
  }
  return bytes;
}

function numberToBytes8(n: number): Uint8Array {
  // nonce sur 8 octets big-endian (correspond au serveur Python)
  const buf = new ArrayBuffer(8);
  const view = new DataView(buf);
  // JavaScript ne gère pas les BigInt 64-bit natif en DataView,
  // on utilise deux int32 (nonces < 2^32 suffisent pour difficulty ≤ 22)
  view.setUint32(0, 0, false);           // Partie haute toujours 0
  view.setUint32(4, n >>> 0, false);     // Partie basse (unsigned)
  return new Uint8Array(buf);
}

// ── Vérification du PoW ───────────────────────────────────────────────

function checkLeadingZeroBits(hashBytes: Uint8Array, difficulty: number): boolean {
  const fullBytes = Math.floor(difficulty / 8);
  const remainingBits = difficulty % 8;

  for (let i = 0; i < fullBytes; i++) {
    if (hashBytes[i] !== 0) return false;
  }

  if (remainingBits > 0) {
    const mask = (0xFF << (8 - remainingBits)) & 0xFF;
    if ((hashBytes[fullBytes] & mask) !== 0) return false;
  }

  return true;
}

// ── Solveur principal ─────────────────────────────────────────────────

async function solvePow(challenge: PowChallenge): Promise<PowResult> {
  const xBytes = hexToBytes(challenge.point_x);
  const yBytes = hexToBytes(challenge.point_y);

  // Pré-allouer le buffer d'entrée : 32 + 32 + 8 = 72 octets
  const inputBuffer = new Uint8Array(72);
  inputBuffer.set(xBytes.slice(-32), 0);   // point_x (32B, tronqué/paddé)
  inputBuffer.set(yBytes.slice(-32), 32);  // point_y (32B)
  // inputBuffer[64..71] = nonce (mis à jour à chaque itération)

  const startTime = performance.now();
  let attempts = 0;

  // Boucle de recherche — bloque le thread worker (intentionnel)
  for (let nonce = 0; nonce <= 0xFFFFFFFF; nonce++) {
    // Écrire le nonce dans les 8 derniers octets (big-endian)
    inputBuffer[64] = 0;
    inputBuffer[65] = 0;
    inputBuffer[66] = 0;
    inputBuffer[67] = 0;
    inputBuffer[68] = (nonce >>> 24) & 0xFF;
    inputBuffer[69] = (nonce >>> 16) & 0xFF;
    inputBuffer[70] = (nonce >>> 8)  & 0xFF;
    inputBuffer[71] = nonce & 0xFF;

    // SHA-256 via Web Crypto API (hardware-accelerated)
    const hashBuffer = await crypto.subtle.digest('SHA-256', inputBuffer);
    const hashBytes = new Uint8Array(hashBuffer);
    attempts++;

    if (checkLeadingZeroBits(hashBytes, challenge.difficulty)) {
      const duration_ms = Math.round(performance.now() - startTime);
      return {
        challenge_id: challenge.challenge_id,
        nonce,
        attempts,
        duration_ms
      };
    }

    // Signaler la progression toutes les 10 000 itérations
    if (nonce % 10_000 === 0) {
      self.postMessage({
        type: 'progress',
        attempts: nonce,
        elapsed_ms: Math.round(performance.now() - startTime)
      });
    }
  }

  throw new Error('Nonce introuvable dans la plage 0..2^32');
}

// ── Écouter les messages du thread principal ─────────────────────────

self.addEventListener('message', async (event) => {
  const { type, challenge } = event.data;

  if (type === 'solve') {
    try {
      const result = await solvePow(challenge);
      self.postMessage({ type: 'solved', result });
    } catch (error) {
      self.postMessage({
        type: 'error',
        message: error instanceof Error ? error.message : String(error)
      });
    }
  }
});
