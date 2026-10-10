"""Flux — contexte de collecte et notions partagées par toutes les rubriques.

Extrait de `flux.py` (1044 lignes) le 08/08/2026. Voir `__init__.py` pour la
règle de découpage.

Ce module porte ce qu'une rubrique ne peut **pas** redéfinir sans faire diverger
le fil : le libellé d'un périmètre, le résumé d'un texte riche, les marqueurs
« Épinglé » / « Urgent ». Une rubrique qui en réécrirait un afficherait la même
notion sous deux formes selon la ligne — c'est précisément ce que le découpage
doit empêcher, pas provoquer.
"""

import html as _html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlmodel import Session

from app.models.core import Utilisateur
from app.schemas import TicketRead

#  Les périmètres vivent dans `app/utils/perimetres.py` : la table et l'analyse
#  étaient écrites ici ET dans la relance syndic des tickets, avec deux résultats
#  différents pour AFUL. Importés sous leur vrai nom et non ré-exportés : un
#  alias qui délègue au helper partagé masque son origine (socle 02 §6).
from app.utils.perimetres import parse_json_perimetres, parse_perimetres
from app.utils.noms import nom_auteur
from app.utils.categories_ticket import libelle_categorie, ticket_urgent
from app.utils.fichiers import est_image
from app.utils.photos import parse_photos


@dataclass(frozen=True)
class ContexteFlux:
    """Ce que chaque rubrique reçoit pour collecter ses lignes.

    `now` et `since` sont calculés **une fois** par requête et transportés :
    douze rubriques qui appelleraient `utcnow()` chacune travailleraient sur
    douze instants différents, et la fenêtre glissante ne serait plus la même
    d'une ligne à l'autre.
    """

    session: Session
    user: Utilisateur
    now: datetime
    since: datetime


# ── Périmètres ───────────────────────────────────────────────────────────────


def perimetres_de(obj) -> list[str]:
    """Périmètre d'un élément qui porte `perimetre_cible` — ticket ou publication.

    Précision décroissante : la cible JSON explicite, sinon le bâtiment de
    rattachement, sinon le champ texte `perimetre`. Un `Ticket` n'a pas ce
    dernier champ, il retombe donc sur « résidence » — exactement le
    comportement d'avant le découpage, où les quatre blocs de ticket écrivaient
    cette cascade à la main, à l'identique.

    ⚠️ **Ne pas étendre aux événements.** Ceux-là n'ont pas de `perimetre_cible`
    et leur règle ignore volontairement `batiment_id` : les faire passer ici
    changerait le périmètre affiché dès qu'un bâtiment est renseigné. Deux règles
    qui se ressemblent ne sont pas la même règle
    (`standards/02-factorisation.md` §4) — d'où l'appel direct à
    `parse_perimetres` conservé dans `evenements.py`. Le devis relevait de la même
    exception jusqu'à son retrait ; `prestataires.py` ne lit plus aucun périmètre.
    """
    cible = getattr(obj, "perimetre_cible", None)
    if cible:
        return parse_json_perimetres(cible)
    batiment_id = getattr(obj, "batiment_id", None)
    if batiment_id:
        return [f"bat:{batiment_id}"]
    return parse_perimetres(getattr(obj, "perimetre", None))


# ── Résumés, auteurs, marqueurs ──────────────────────────────────────────────


def auteur_nom(session: Session, uid: Optional[int]) -> str:
    #  Sans compte (supprimé, #1688/#1821) : « Ancien résident », jamais rien.
    return nom_auteur(session.get(Utilisateur, uid) if uid else None)


def strip_html(text: Optional[str], max_len: int = 120) -> Optional[str]:
    """Retire les balises HTML et tronque pour un résumé texte."""
    if not text:
        return None
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = _html.unescape(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0] + "…"
    return clean


#: Ce que lit la ligne de pastilles d'une affaire (`PastillesAffaire`, côté
#: front) : catégorie, état, périmètre, lecteurs, urgence, marqueurs, numéro, IA.
CHAMPS_PASTILLES = (
    "numero",
    "categorie",
    "statut",
    "suivi_actualite",  # l'état d'une actualité suivie (10/10/2026)
    "priorite",
    "debut",
    "perimetre_cible",
    "public_cible",
    "reserve_perimetre",
    "confidentiel",
    "epingle",
    "assiste_ia",
)


def pastilles_affaire(ticket) -> dict:
    """La ligne de pastilles d'une affaire, pour le fil (27/09/2026).

    Arbitré à l'écran : la carte d'une affaire fait la norme, et le fil rend la
    même ligne. Il ne recevait que le numéro, le périmètre et l'auteur.

    ⚠️ Par `TicketRead`, pas par une recopie colonne à colonne : ses validateurs
    décodent `perimetre_cible` et `public_cible`, et une copie en oublierait un
    (CLAUDE.md, « lire un objet pour le RENDRE »). 🔒 `test_flux_pastilles.py`.
    """
    return TicketRead.model_validate(ticket).model_dump(mode="json", include=set(CHAMPS_PASTILLES))


def badges_ticket(ticket) -> list[str]:
    """Les badges d'un ticket dans le fil : son numéro, sa catégorie, son urgence.

    🔴 Cette liste était écrite TROIS fois dans `flux/tickets.py` — ouverts,
    résolus, épinglés — sous la forme `[f"#{tk.numero}", tk.categorie]`. Trois
    copies d'une même règle, qui n'ont pas divergé par chance.

    ⚠️ Le badge « urgent » ne pouvait PAS y être ajouté à la main sans la
    factoriser d'abord : il aurait fallu le poser aux trois endroits, et le
    quatrième appel — celui qu'on écrit dans six mois — l'aurait oublié. Le front
    lit ce badge (`estUrgent`, `flux.ts`) pour teinter la carte ; il lisait
    jusqu'ici la catégorie « urgence », qui n'existe plus (migration 0177).
    """
    #  Le LIBELLÉ, jamais la valeur de l'énumération : le fil affichait
    #  `acces_accueil` (#1310). `badgeClass` compare en minuscules, « Panne » y
    #  garde sa teinte. 🔒 `test_flux_badges_categorie.py`.
    badges = [f"#{ticket.numero}", libelle_categorie(ticket.categorie)]
    if ticket_urgent(ticket):
        badges.append("urgent")
    return badges


def pieces_de_evolution(evol, porteur) -> dict:
    """Les pièces à montrer sur une carte de MISE À JOUR : celles de l'entrée,
    sinon celles de l'objet porteur.

    🔴 Écrite DEUX fois avant le 16/09/2026 — dans `tickets.py` et dans
    `evenements.py` —, et la seconde le DISAIT : « même règle et même raison
    que `flux/tickets.py` ». Une copie qui s'annonce comme telle reste une
    copie : elle ne se corrige pas avec l'autre, elle se contente de la citer.

    La règle, elle, n'a qu'une raison : la carte annonce une mise à jour et
    affiche le commentaire du jour ; lui faire porter les photos d'origine
    montrerait une image vieille de trois semaines à côté d'un texte de ce
    matin. Le repli sur l'objet porteur ne retire rien aux cartes qui
    fonctionnaient avant qu'une entrée puisse porter des pièces.

    ⚠️ La répartition `photos_urls` / `fichiers_urls` n'est pas cosmétique :
    `FluxCard` n'en fait pas le même usage — les premières alimentent la
    vignette, les secondes la liste dépliée. Le tri passe par `est_image`, la
    même règle qu'`estImage` côté front.
    """
    urls = parse_photos(evol.fichiers_urls)
    if not urls:
        return {
            "photos_urls": parse_photos(porteur.photos_urls),
            "fichiers_urls": parse_photos(porteur.fichiers_urls),
        }
    return {
        "photos_urls": [u for u in urls if est_image(u)],
        "fichiers_urls": [u for u in urls if not est_image(u)],
    }


def badges_marqueurs(obj) -> list[str]:
    """Marqueurs « Épinglé » / « Urgent », identiques quelle que soit la rubrique.

    Ils étaient construits à la main pour les publications ; les événements ont
    désormais le même épinglage, et rien ne justifie deux écritures du même badge.
    `getattr` avec défaut : toutes les rubriques ne portent pas les deux notions.
    """
    marqueurs = []
    if getattr(obj, "epingle", False):
        marqueurs.append("📌 Épinglé")
    #  Une affaire « Actualité » (#1091) dit l'urgence par sa priorité.
    if getattr(obj, "urgente", False) or getattr(obj, "priorite", None) == "haute":
        marqueurs.append("🔴 Urgent")
    #  Confidentiel (#347) : celui qui voit la carte fait partie du périmètre —
    #  le badge lui dit que les autres bâtiments, eux, ne la voient pas. Sans
    #  lui, rien ne distingue à l'écran une actualité restreinte d'une autre, et
    #  le périmètre seul ne le dit pas (il ne décrit que le sujet depuis #339).
    #  L'Accès « réservé au périmètre » s'appelle `reserve_perimetre` sur une
    #  affaire (#1091) — `confidentiel` y désigne autre chose (#710).
    if getattr(obj, "reserve_perimetre", False):
        marqueurs.append("🔒 Confidentiel")
    return marqueurs
