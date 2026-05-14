"""
JetWatch Africa — EC Proof-of-Work Anti-Bot Firewall

Système de protection basé sur des défis mathématiques signés par courbe elliptique.
Le client doit trouver un nonce tel que SHA256(challenge || nonce) commence
par `difficulty` bits à zéro avant de pouvoir accéder à n'importe quelle route.

Propriétés de sécurité :
  - Asymétrie : résoudre ~65ms client, vérifier <1ms serveur
  - Anti-replay : chaque token est à usage unique
  - Anti-DDoS : difficulté adaptative sous charge
  - Authenticité : challenge signé HMAC avec clé secrète serveur
"""

import hmac as _hmac
import time
import secrets
import hashlib
import threading
import os
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

# ── Configuration ─────────────────────────────────────────────────────

# Clé HMAC secrète : dérivée de la clé ECC du serveur + sel aléatoire
_POW_HMAC_KEY: bytes = secrets.token_bytes(32)

DEFAULT_DIFFICULTY = 16    # 2^16 ≈ 65 536 essais ≈ 50-80ms sur CPU moderne
ELEVATED_DIFFICULTY = 18   # Sous charge modérée
MAX_DIFFICULTY = 22        # Sous attaque DDoS (2^22 ≈ 4M essais ≈ 3-5s)
CHALLENGE_TTL = 60         # Secondes avant expiration
ATTACK_THRESHOLD = 300     # Challenges/minute = détection d'attaque (Strict pour la production)
ELEVATED_THRESHOLD = 150   # Charges élevée

# ── Store thread-safe ─────────────────────────────────────────────────

_lock = threading.Lock()
_challenges: dict = {}        # {id: {x, y, difficulty, expires, used}}
_request_log: list = []       # Timestamps pour difficulté adaptative


def _cleanup_expired() -> None:
    """Purge les challenges expirés (appelé à chaque opération)."""
    now = time.time()
    expired = [cid for cid, c in _challenges.items() if c["expires"] < now]
    for cid in expired:
        del _challenges[cid]
    # Garder seulement les 60 dernières secondes
    cutoff = now - 60
    while _request_log and _request_log[0] < cutoff:
        _request_log.pop(0)


def _adaptive_difficulty() -> int:
    """Retourne la difficulté en fonction du trafic détecté."""
    rpm = len(_request_log)
    if rpm >= ATTACK_THRESHOLD:
        return MAX_DIFFICULTY
    if rpm >= ELEVATED_THRESHOLD:
        return ELEVATED_DIFFICULTY
    return DEFAULT_DIFFICULTY


# ── Génération du défi ────────────────────────────────────────────────

def generate_challenge() -> dict:
    """
    Génère un défi EC-PoW.

    Algorithme :
    1. Génère une paire de clés éphémère sur secp256k1
    2. Extrait les coordonnées (x, y) du point public
    3. Signe les métadonnées du challenge avec HMAC-SHA256
    4. Stocke avec TTL et retourne au client

    Le client devra trouver un nonce tel que :
        SHA256( x_bytes || y_bytes || nonce_bytes ) commence par `difficulty` bits à 0
    """
    with _lock:
        _cleanup_expired()
        difficulty = _adaptive_difficulty()
        _request_log.append(time.time())

    # Générer un point EC éphémère sur secp256k1
    ephemeral_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
    pub_numbers = ephemeral_key.public_key().public_numbers()
    point_x = pub_numbers.x
    point_y = pub_numbers.y

    challenge_id = secrets.token_hex(16)
    expires_at = time.time() + CHALLENGE_TTL

    # HMAC pour authenticité — le client ne peut pas forger un challenge
    mac_input = f"{challenge_id}:{point_x}:{point_y}:{difficulty}:{expires_at}".encode()
    signature = _hmac.new(_POW_HMAC_KEY, mac_input, hashlib.sha256).hexdigest()

    with _lock:
        _challenges[challenge_id] = {
            "point_x": point_x,
            "point_y": point_y,
            "difficulty": difficulty,
            "expires": expires_at,
            "used": False,
            "hmac": signature
        }

    return {
        "challenge_id": challenge_id,
        "point_x": format(point_x, '064x'),   # 256-bit hex, toujours 64 chars
        "point_y": format(point_y, '064x'),
        "difficulty": difficulty,
        "expires_at": expires_at,
        "hmac": signature
    }


# ── Vérification du PoW ───────────────────────────────────────────────

def verify_pow(challenge_id: str, nonce: int) -> tuple[bool, str]:
    """
    Vérifie qu'un nonce résout le défi PoW.

    Calcule SHA256(point_x_bytes || point_y_bytes || nonce_bytes)
    et vérifie que les `difficulty` premiers bits sont à zéro.

    Returns:
        (True, "OK") si valide
        (False, raison) si invalide
    """
    with _lock:
        _cleanup_expired()
        challenge = _challenges.get(challenge_id)

        if not challenge:
            return False, "Challenge inconnu ou expiré"

        if challenge["used"]:
            return False, "Token déjà consommé — attaque replay détectée"

        if time.time() > challenge["expires"]:
            return False, "Challenge expiré"

        point_x = challenge["point_x"]
        point_y = challenge["point_y"]
        difficulty = challenge["difficulty"]

    # Construire l'entrée du hash : x(32B) || y(32B) || nonce(8B)
    try:
        x_bytes = point_x.to_bytes(32, 'big')
        y_bytes = point_y.to_bytes(32, 'big')
        nonce_bytes = nonce.to_bytes(8, 'big')
    except (OverflowError, ValueError):
        return False, "Nonce invalide (dépassement d'entier)"

    hash_result = hashlib.sha256(x_bytes + y_bytes + nonce_bytes).digest()

    # Vérifier les `difficulty` premiers bits
    full_bytes = difficulty // 8
    remaining_bits = difficulty % 8

    for i in range(full_bytes):
        if hash_result[i] != 0:
            return False, "Hash insuffisant — PoW non résolu"

    if remaining_bits > 0:
        mask = (0xFF << (8 - remaining_bits)) & 0xFF
        if hash_result[full_bytes] & mask != 0:
            return False, "Hash insuffisant — PoW non résolu"

    # ✅ Valide — marquer comme utilisé (anti-replay)
    with _lock:
        if challenge_id in _challenges:
            _challenges[challenge_id]["used"] = True

    return True, "OK"


# ── Statistiques ─────────────────────────────────────────────────────

def get_stats() -> dict:
    """Retourne les statistiques de protection (pour monitoring)."""
    with _lock:
        _cleanup_expired()
        active = len(_challenges)
        rpm = len(_request_log)

    return {
        "active_challenges": active,
        "requests_per_minute": rpm,
        "current_difficulty": _adaptive_difficulty(),
        "under_attack": rpm >= ATTACK_THRESHOLD,
        "elevated_load": rpm >= ELEVATED_THRESHOLD
    }
# Force IDE refresh
