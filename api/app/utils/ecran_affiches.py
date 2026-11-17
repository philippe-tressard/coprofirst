"""Ce qu'un écran de hall montre — LA porte de sortie vers le hall (#2770).

## 🔴 Un lieu lu par tous (`standards/03` §2 bis)

L'écran du hall est lu par des visiteurs, des livreurs, des voisins d'un autre
bâtiment. Ce qui peut y paraître se décide ICI, à partir de l'objet — l'affiche, son
périmètre, son archivage — et jamais d'un paramètre que l'appelant devrait penser à
passer : la route (`routers/ecrans.py`) n'a rien à transmettre que l'écran lui-même.

- **Quelles affiches** (`sur_l_ecran`) : les affiches non archivées — l'archivage
  EFFECTIF, la règle du site comprise (`archivage.est_archivable`) — dont le périmètre
  cible COUVRE celui de l'écran (`perimetres.couvre`) : le même nœud, un ancêtre, ou un
  périmètre à portée globale (« Copropriété entière », qui n'est l'ancêtre de rien),
  sans franchir la frontière d'un tiers (AFUL). Une affiche du bâtiment 3 ne paraît pas
  dans le hall du bâtiment 2, ni une affiche de l'ascenseur du bâtiment 2 sur l'écran
  de tout le bâtiment. `couvre` répond « oui » quand il ne peut pas décider (un filtre) :
  ici l'arbre vide, le code de l'écran inconnu ou un périmètre illisible ne laissent
  RIEN paraître — cette question décide d'une sortie.
- **Quels champs** (`AfficheEcran`) : une LISTE BLANCHE — titre, message, format,
  images, dates. Ni auteur (arbitré : une affiche papier ne le porte pas), ni
  destinataires, ni gestes, ni l'affaire d'origine. Le message passe par l'assainisseur
  du serveur (`utils/html_sur`) : l'écran n'a pas à faire confiance à ce qu'il reçoit.
- **Quelles images** (`image_de_l_ecran`) : celles d'une affiche que l'écran montre, par
  leur rang, et seulement des images — jamais une adresse `/uploads/…` que l'écran irait
  lire avec une session qu'il n'a pas.

🔒 `tests/test_ecrans.py` lit ce qui est reçu (`standards/04` §14), pas le seul 200.
"""

from __future__ import annotations

import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.models.annonce_hall import AnnonceHall
from app.models.ecrans import Ecran
from app.utils import horloge
from app.utils.archivage import est_archivable, seuil_archivage_jours
from app.utils.html_sur import assainir_html
from app.utils.perimetres import arbre, couvre, perimetre_defaut_liste
from app.utils.photos import parse_photos
from app.utils.stockage import stockage


class AfficheEcran(BaseModel):
    """Une affiche telle que la montre un écran de hall — rien d'autre ne sort."""

    model_config = ConfigDict(extra="forbid")

    id: int
    titre: str
    #: Le HTML de l'affiche, assaini par le serveur.
    message: str
    #: `a4` | `a5` | `a6` | `a7` — le format de l'affiche imprimée.
    format: str
    #: Les chemins de ses images dans l'API, à lire avec le jeton de l'écran.
    images: list[str]
    envoyee_le: Optional[datetime]
    creee_le: datetime


def _codes_cibles(affiche: AnnonceHall) -> list[str]:
    """Le périmètre cible, lu sans repli : illisible → aucun code, donc aucune sortie.
    Une liste vide vaut la racine, comme partout ailleurs (`perimetre_cible_json`)."""
    try:
        codes = json.loads(affiche.perimetre_cible or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes):
        return []
    return [c for c in codes if c.strip()] or perimetre_defaut_liste()


def sur_l_ecran(affiche: AnnonceHall, ecran: Ecran, seuil_jours: int, maintenant: datetime) -> bool:
    """Cette affiche paraît-elle sur cet écran ? Défaut fermé."""
    if est_archivable("annonce_hall", affiche, seuil_jours=seuil_jours, maintenant=maintenant):
        return False
    codes = _codes_cibles(affiche)
    #  Les trois cas où `couvre` répond « oui » faute de pouvoir décider : fermés ici.
    if not codes or ecran.perimetre.strip().lower() not in arbre():
        return False
    return couvre(codes, ecran.perimetre)


def affiches_de_l_ecran(session: Session, ecran: Ecran) -> list[AnnonceHall]:
    """Les affiches que montre l'écran, les plus récentes d'abord."""
    seuil = seuil_archivage_jours(session)
    maintenant = horloge.maintenant()
    toutes = session.exec(
        select(AnnonceHall).order_by(AnnonceHall.cree_le.desc(), AnnonceHall.id.desc())  # type: ignore[arg-type]
    ).all()
    return [a for a in toutes if sur_l_ecran(a, ecran, seuil, maintenant)]


def chemin_image(affiche_id: int, rang: int) -> str:
    """Le chemin d'une image d'affiche dans l'API — la seule adresse que l'écran reçoit."""
    return f"/ecrans/moi/affiches/{affiche_id}/images/{rang}"


def ce_que_montre_l_ecran(affiche: AnnonceHall) -> AfficheEcran:
    return AfficheEcran(
        id=affiche.id,
        titre=affiche.titre,
        message=assainir_html(affiche.message),
        format=affiche.format_effectif,
        images=[chemin_image(affiche.id, r) for r in range(len(parse_photos(affiche.images_json)))],
        envoyee_le=affiche.envoye_le,
        creee_le=affiche.cree_le,
    )


def image_de_l_ecran(
    session: Session, ecran: Ecran, affiche_id: int, rang: int
) -> Optional[tuple[Path, str]]:
    """Le fichier et le type de l'image `rang` d'une affiche que l'écran montre, ou `None`."""
    affiche = session.get(AnnonceHall, affiche_id)
    if affiche is None or rang < 0:
        return None
    if not sur_l_ecran(affiche, ecran, seuil_archivage_jours(session), horloge.maintenant()):
        return None
    urls = parse_photos(affiche.images_json)
    if rang >= len(urls):
        return None
    fichier = stockage().fichier_de_url(urls[rang])
    type_mime = mimetypes.guess_type(fichier.name)[0] if fichier else None
    if fichier is None or not (type_mime or "").startswith("image/"):
        return None
    return fichier, type_mime
