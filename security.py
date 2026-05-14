import time
import os
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

# Clé privée sur Courbe Elliptique (ECC P-256) pour la sécurité réseau anti-falsification
ECC_KEY_FILE = os.path.join(os.path.dirname(__file__), "ecc_private_key.pem")

if os.path.exists(ECC_KEY_FILE):
    with open(ECC_KEY_FILE, "rb") as f:
        PRIVATE_KEY_BYTES = f.read()
else:
    # Génération d'une nouvelle clé sur la courbe SECP256R1 (NIST P-256)
    private_key = ec.generate_private_key(ec.SECP256R1())
    PRIVATE_KEY_BYTES = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(ECC_KEY_FILE, "wb") as f:
        f.write(PRIVATE_KEY_BYTES)

# Extraire la clé publique depuis la clé privée (nécessaire pour la vérification ES256)
_private_key_obj = serialization.load_pem_private_key(PRIVATE_KEY_BYTES, password=None)
PUBLIC_KEY_BYTES = _private_key_obj.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

ALGORITHM = "ES256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

def create_access_token(data: dict):
    """
    Crée un token JWT ultra-sécurisé signé avec ECC (ES256).
    Signe avec la clé PRIVÉE.
    """
    to_encode = data.copy()
    expire = time.time() + ACCESS_TOKEN_EXPIRE_MINUTES * 60
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, PRIVATE_KEY_BYTES.decode('utf-8'), algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """
    Vérifie la signature elliptique du token et retourne le payload.
    Vérifie avec la clé PUBLIQUE (asymétrique: privée pour signer, publique pour vérifier).
    """
    try:
        payload = jwt.decode(token, PUBLIC_KEY_BYTES.decode('utf-8'), algorithms=[ALGORITHM])
        return payload
    except Exception as e:
        print(f"[JWT] Erreur de vérification: {e}")
        return None
