"""
JetWatch Africa — ECDH Session Encryption

Échange de clé Diffie-Hellman sur courbe elliptique (ECDH) pour établir
une clé de session partagée entre le client et le serveur.

Protocole :
  1. Client génère sa paire ECDH éphémère (navigateur Web Crypto API)
  2. Client envoie sa clé publique → POST /ecdh/handshake
  3. Serveur génère sa propre paire éphémère
  4. Serveur calcule : shared_secret = ECDH(server_private, client_public)
  5. Serveur dérive une clé AES-256 via HKDF-SHA256
  6. Serveur retourne sa clé publique + session_id
  7. Client calcule la même clé partagée côté navigateur
  → Les deux parties ont désormais la même clé AES-256 sans jamais la transmettre

Propriété fondamentale (Forward Secrecy) :
  Chaque session utilise des clés éphémères. Même si la clé du serveur est
  compromise un jour, les sessions passées restent indéchiffrables.
"""

import os
import time
import secrets
import threading
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend


# ── Store des sessions ────────────────────────────────────────────────

_lock = threading.Lock()
_sessions: dict = {}       # {session_id: {aes_key, expires, request_count}}
SESSION_TTL = 3600         # 1 heure
MAX_SESSION_REQUESTS = 500 # Rotation forcée après N requêtes


def _cleanup_sessions() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if s["expires"] < now]
    for sid in expired:
        del _sessions[sid]


# ── Handshake ECDH ────────────────────────────────────────────────────

def ecdh_handshake(client_public_key_pem: str) -> dict:
    """
    Effectue le handshake ECDH avec la clé publique du client.

    Args:
        client_public_key_pem: Clé publique ECDH du client au format PEM

    Returns:
        {
            "session_id": str,
            "server_public_key_pem": str,  # Clé publique serveur (le client calcule son côté)
            "expires_at": float
        }
    """
    # Charger la clé publique du client
    try:
        client_public_key = serialization.load_pem_public_key(
            client_public_key_pem.encode(),
            backend=default_backend()
        )
    except Exception as e:
        raise ValueError(f"Clé publique client invalide: {e}")

    # Générer une paire de clés éphémère côté serveur (même courbe que le client)
    server_private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    server_public_key = server_private_key.public_key()

    # Calculer le secret partagé ECDH
    shared_secret = server_private_key.exchange(ec.ECDH(), client_public_key)

    # Dériver une clé AES-256 à partir du secret partagé via HKDF-SHA256
    # HKDF garantit une clé uniformément distribuée même si ECDH produit un
    # point avec une faible entropie dans certains bits
    session_id = secrets.token_hex(16)
    salt = session_id.encode()  # Salt unique par session

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,            # 256 bits = clé AES-256
        salt=salt,
        info=b"jetwatch-session-v1",
        backend=default_backend()
    )
    aes_key = hkdf.derive(shared_secret)

    # Exporter la clé publique serveur pour le client
    server_public_pem = server_public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    expires_at = time.time() + SESSION_TTL

    with _lock:
        _cleanup_sessions()
        _sessions[session_id] = {
            "aes_key": aes_key,
            "expires": expires_at,
            "request_count": 0
        }

    return {
        "session_id": session_id,
        "server_public_key_pem": server_public_pem,
        "expires_at": expires_at
    }


def get_session_key(session_id: str) -> bytes | None:
    """
    Retourne la clé AES-256 d'une session active, ou None si invalide.
    Incrémente le compteur de requêtes et invalide la session si trop utilisée.
    """
    with _lock:
        session = _sessions.get(session_id)
        if not session:
            return None
        if time.time() > session["expires"]:
            del _sessions[session_id]
            return None
        session["request_count"] += 1
        # Rotation forcée si trop de requêtes (Forward Secrecy partielle)
        if session["request_count"] >= MAX_SESSION_REQUESTS:
            del _sessions[session_id]
            return None
        return session["aes_key"]


def session_exists(session_id: str) -> bool:
    """Vérifie qu'une session est active sans en extraire la clé."""
    with _lock:
        session = _sessions.get(session_id)
        if not session:
            return False
        return time.time() < session["expires"]


def get_session_stats() -> dict:
    with _lock:
        _cleanup_sessions()
        return {
            "active_sessions": len(_sessions),
            "total_requests": sum(s["request_count"] for s in _sessions.values())
        }
# Force IDE refresh
