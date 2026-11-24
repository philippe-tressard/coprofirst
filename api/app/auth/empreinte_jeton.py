"""Un jeton se STOCKE par son empreinte, jamais en clair (#1389, 27/09/2026).

## Pourquoi

Les trois familles de jetons — rafraîchissement de session, mot de passe oublié,
vérification d'adresse — étaient stockées telles quelles et recherchées par
égalité. Une copie de la base (sauvegarde quotidienne, export hors site, poste
de l'administrateur) donnait donc des jetons UTILISABLES tant qu'ils n'avaient
pas expiré : une session ouverte, un mot de passe à réinitialiser, une adresse à
valider.

Désormais la base ne garde que l'empreinte ; le jeton brut ne vit que chez son
porteur (le cookie, le lien du courriel). À la réception, on calcule l'empreinte
de ce qui arrive et on la cherche.

## Pourquoi un HMAC, et pas un simple SHA-256

Un jeton est long et aléatoire : un condensé sans clé suffirait contre la
lecture. Le HMAC avec la clé du serveur ajoute que, sans elle, une empreinte
n'est comparable à RIEN — même famille que `jwt.empreinte_secret`.

⚠️ Conséquence assumée : changer `SECRET_KEY` rend toutes les empreintes
introuvables — sessions fermées, liens en attente invalides. C'était déjà le cas
des jetons d'accès, signés avec la même clé : une rotation de clé est une
révocation générale, et c'est ce qu'on attend d'elle.

🔒 `test_jetons_empreinte.py` refuse un jeton construit, affecté ou cherché sans passer
par `empreinte` ; ses colonnes se lisent dans le schéma (#2940) — une seule porte.
"""

from __future__ import annotations

import hashlib
import hmac
import re

from app import contexte

#: Ce qu'une empreinte a l'air d'être : 64 caractères hexadécimaux. Aucun jeton
#: brut n'a cette forme — un jeton de rafraîchissement est un JWT (il contient
#: des points), les deux autres sortent de `secrets.token_urlsafe(32)` (43
#: caractères base64url). C'est ce qui rend la migration rejouable sans
#: re-hacher une empreinte.
FORME_EMPREINTE = re.compile(r"^[0-9a-f]{64}$")


def empreinte(brut: str, cle: str | None = None) -> str:
    """L'empreinte stockée d'un jeton brut.

    :param cle: la clé du serveur ; `None` = celle de la configuration. La
        migration la passe explicitement, pour ne dépendre que de ce qu'elle lit.
    """
    secret = (cle if cle is not None else contexte.courante().secret).encode("utf-8")
    return hmac.new(secret, brut.encode("utf-8"), hashlib.sha256).hexdigest()


def est_empreinte(valeur: str) -> bool:
    return bool(FORME_EMPREINTE.match(valeur or ""))
