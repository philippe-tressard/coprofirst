import hashlib
import secrets
from datetime import timedelta
from app.utils import horloge
from typing import Optional

import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext

from app import contexte
from app.config import get_settings

settings = get_settings()

# rounds=10 : conforme OWASP (minimum recommandé), ~4× plus rapide que 12
# sur Raspberry Pi (auto-hébergé, <100 utilisateurs)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=10)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def verify_and_rehash(plain: str, hashed: str) -> tuple[bool, str | None]:
    """Vérifie le mot de passe et retourne (valide, nouveau_hash_si_upgrade_nécessaire).
    Permet de migrer silencieusement les hashes 12-rounds vers 10-rounds au login.
    """
    return pwd_context.verify_and_update(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def empreinte_secret(secret: str) -> str:
    """Une empreinte courte et non réversible d'un condensé de mot de passe.

    🔴 Elle voyage dans CHAQUE requête, à l'intérieur d'un jeton que son porteur
    peut lire : elle ne doit donc rien livrer du condensé. D'où un HMAC avec la
    clé du serveur plutôt qu'un simple `sha256` du condensé — sans la clé,
    l'empreinte n'est comparable à rien.

    Seize caractères hexadécimaux, soit 64 bits : de quoi rendre une collision
    hors de portée pour ce à quoi elle sert — distinguer deux mots de passe du
    même compte —, sans allonger inutilement le jeton.
    """
    return hashlib.blake2s(
        secret.encode("utf-8"), key=contexte.courante().secret.encode("utf-8")[:32], digest_size=8
    ).hexdigest()


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None, empreinte: str | None = None
) -> str:
    to_encode = data.copy()
    expire = horloge.maintenant() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    if empreinte is not None:
        to_encode["pwd"] = empreinte
    return jwt.encode(to_encode, contexte.courante().secret, algorithm=settings.algorithm)


def creer_jeton_acces(user_id: int, hashed_password: str) -> str:
    """LA porte d'émission d'un jeton d'accès (#1063, 22/09/2026).

    ## Pourquoi une porte, et pas deux appels qui composent leur charge

    Le jeton était fabriqué à la connexion ET au rafraîchissement, chacun
    écrivant son propre dictionnaire. Un jeton émis sans empreinte est
    aujourd'hui REFUSÉ : une porte oubliée ne se verrait pas à la relecture,
    elle déconnecterait des gens. `test_jeton_revocable.py` refuse un second
    appelant de `create_access_token`.

    ## Ce que l'empreinte apporte

    Le jeton d'accès est autoporteur : rien, côté serveur, ne pouvait
    l'invalider avant ses 120 minutes — ni un changement de mot de passe, ni une
    déconnexion. Il porte désormais l'empreinte du condensé du mot de passe, que
    `_get_current_user` compare à celle du compte qu'il charge **déjà**. Coût :
    nul. Effet : un mot de passe changé invalide d'un coup tous les jetons.
    """
    return create_access_token({"sub": str(user_id)}, empreinte=empreinte_secret(hashed_password))


def create_refresh_token(data: dict) -> str:
    """Un jeton de rafraîchissement — **unique par construction**.

    ## Pourquoi le `jti` (19/08/2026, trouvé par le point 6 du pré-check)

    Le contenu était entièrement déterministe : `{"sub": …, "exp": …, "type": …}`.
    `exp` a une résolution d'UNE SECONDE. Deux rafraîchissements du même
    utilisateur dans la même seconde produisaient donc deux jetons **identiques
    octet pour octet**, et la colonne `refresh_token.token` étant UNIQUE :

        IntegrityError: UNIQUE constraint failed: refresh_token.token
        POST /auth/refresh → 500

    Ce n'était pas un cas de bord. Quand une page charge, plusieurs appels
    reçoivent 401 **en même temps** et déclenchent chacun un rafraîchissement :
    sur les dernières 24 h de production, **4 collisions pour 4 appels** — c'est
    la totalité d'entre eux.

    `jti` est le champ prévu pour cela par la RFC 7519 (« JWT ID ») : un
    identifiant unique par jeton. `token_urlsafe(16)` donne 128 bits d'entropie,
    tirés de `secrets` — le générateur cryptographique, jamais `random`.

    ⚠️ Le jeton d'accès n'en a pas besoin : il n'est stocké nulle part, donc
    aucune contrainte d'unicité ne le concerne. En ajouter un rallongerait chaque
    en-tête de requête sans rien protéger.
    """
    to_encode = data.copy()
    expire = horloge.maintenant() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(16)})
    return jwt.encode(to_encode, contexte.courante().secret, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, contexte.courante().secret, algorithms=[settings.algorithm])
        return payload
    except PyJWTError:
        return None
