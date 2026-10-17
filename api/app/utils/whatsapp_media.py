"""Ce qui accompagne un message WhatsApp : la photo, et son repli.

Extrait de `utils/whatsapp.py` le 19/09/2026 (#1057), au fil de l'eau : ce
fichier-là était à 499 lignes et le garde-fou de modularité refusait qu'il
grossisse. La coupe suit une notion — `whatsapp.py` compose et poste le message,
ce module prépare ce qui l'accompagne.

## Le budget, et pourquoi il existe

Le bridge reçoit la photo **en base64 dans le corps JSON**. Express borne ce
corps. Tant que ce plafond n'était écrit nulle part, il valait celui par défaut
d'express — **100 kio** — pendant qu'une photo du site en pesait deux fois plus :
le bridge rendait `413` avant d'avoir lu la requête, et **tout partage portant
une photo était perdu**, sur tous les objets du site. Constaté le 19/09/2026 sur
un ticket, deux tentatives, aucune arrivée dans le groupe.

Le budget est donc **déclaré une fois**, dans `docker-compose.yml`, et lu des
deux côtés : `WA_PHOTO_BUDGET_KO` — ici via `get_settings()`, et dans le bridge, qui en
dérive la borne de son corps JSON. Deux nombres écrits séparément auraient
divergé au premier ajustement — c'est exactement ce qui vient de coûter un
message (`standards/02-factorisation.md` §4 bis).
"""

import base64
import logging

from app.config import get_settings
from app.utils.fichiers import chemins_locaux
from app.utils.images import reduire_sous_budget
from app.utils.liens import adresse_du_site

logger = logging.getLogger(__name__)


def budget_photo_octets() -> int:
    """Poids maximal, en octets, d'une photo jointe à un message WhatsApp."""
    return max(1, get_settings().wa_photo_budget_ko) * 1024


def image_pour_bridge(image_url: str | None) -> str | None:
    """Photo interne → octets en base64, prêts pour le bridge. None si indisponible.

    ⚠️ On ne donne PLUS d'URL au bridge. Baileys allait alors chercher le fichier
    par l'internet public, ce qui exigeait que le dossier soit servi en anonyme :
    `/uploads/publications/` était le seul dans ce cas, et le seul pour cette
    raison. Le 10/08/2026, l'unification des galeries a fait atterrir les photos
    de publication dans le dossier authentifié — le bridge a reçu un 401 et
    l'annonce entière a disparu du groupe.

    L'API a le fichier sous la main : le lui faire retélécharger par le réseau
    public était un détour, et ce détour imposait de publier des photos que rien
    n'obligeait à rendre publiques. La résolution passe par `chemins_locaux`, qui
    refuse ce qui n'est pas à nous et ce qui sort du bac à sable.

    La photo est ramenée sous le budget **avant** d'être encodée. Le cas courant
    ne recompresse rien : une photo du site tient déjà, et la dégrader à chaque
    diffusion serait une perte gratuite.
    """
    if not image_url:
        return None
    chemins = chemins_locaux([image_url])
    if not chemins:
        logger.warning("Photo WhatsApp introuvable ou hors périmètre : %s", image_url)
        return None
    try:
        with open(chemins[0], "rb") as f:
            octets = f.read()
    except OSError as exc:
        logger.warning("Photo WhatsApp illisible (%s) : %s", image_url, exc)
        return None

    budget = budget_photo_octets()
    reduite = reduire_sous_budget(octets, budget)
    if len(reduite) != len(octets):
        logger.info(
            "Photo WhatsApp réduite pour tenir le budget : %d → %d octets (budget %d).",
            len(octets),
            len(reduite),
            budget,
        )
    if len(reduite) > budget:
        #  Aucun palier n'a suffi. On tente quand même : le bridge acceptera
        #  peut-être, et s'il refuse, l'appelant se replie sur le texte seul.
        logger.warning(
            "Photo WhatsApp encore au-dessus du budget après réduction : %d > %d octets.",
            len(reduite),
            budget,
        )
    return base64.b64encode(reduite).decode("ascii")


def renvoi_photos(config: dict, cible: str | None = None) -> str:
    """Phrase ajoutée au message quand la photo n'a pas pu l'accompagner.

    Elle renvoie à l'adresse du MESSAGE (`cible`) quand il en porte une — la
    fiche de l'affaire, de l'actualité, de l'événement —, et à l'accueil du site
    sinon. Elle renvoyait à `/actualites` pour TOUT message, ticket compris : une
    page où la photo d'un ticket ne s'est jamais trouvée, et qui n'existe plus
    depuis le 23/09/2026 (#1091).

    Un envoi perdu est bien pire qu'un envoi sans image : le message part, et il
    dit où voir la photo plutôt que de laisser croire qu'il n'y en a pas.

    Rend une chaîne vide si le site n'a pas d'adresse configurée — une phrase qui
    renverrait vers nulle part vaut moins que pas de phrase.
    """
    lien = adresse_du_site().rstrip("/")
    if not lien:
        return ""
    return f"\n\n📷 Photos à voir sur le site : {cible or lien + '/'}"
