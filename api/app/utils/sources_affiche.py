"""Ce qu'on peut reprendre au hall — et d'où.

## Ce qui a été demandé (10/09/2026)

*« Permet la génération d'une affiche à partir de n'importe quelle publication
incluse dans le fil d'actualité, quel que soit le type de publication, et
restreint à celles qui ne sont pas archivées »*, puis, après livraison : *« je ne
vois pas la présélection de toutes les publications, tickets etc. publiés dans le
fil d'actualité »*.

Le premier lot n'avait retiré qu'un **plafond** : le sélecteur proposait toujours
des `Publication`, et rien d'autre. Le fil, lui, agrège trois familles — les
actualités, les tickets et les événements. C'est le fil qui est la référence,
pas la table.

## Ce que ce module porte, et ce qu'il ne porte pas

Il répond à deux questions, et à elles seules :

* **que peut-on reprendre ?** — `sources_disponibles()` ;
* **avec quoi pré-remplir ?** — `prefill_source()`.

Le rendu de l'affiche vit dans `utils/annonce_hall.py` ; la décision d'envoyer,
dans le routeur. Ici, on ne fait que désigner et lire.

## 🔴 Ce qui est EXCLU, et pourquoi

| Exclu | Raison |
|---|---|
| brouillons | un texte que personne n'a validé n'a pas à paraître au hall |
| archivés | c'est la demande : ce qui a quitté le fil a cessé d'être d'actualité |
| **confidentiels** | une affiche de hall est lue par **tout le monde**, y compris des gens qui n'ont pas accès à l'objet. Reprendre un ticket refermé sur son auteur et le CS le publierait au mur — c'est le pire sens de l'erreur, et rien à l'écran ne le rattraperait |
| **réservés au conseil syndical** (🛡️) | même raison, autre mécanisme : la restriction passe par `public_cible`, pas par `confidentiel`. Confirmé à l'écran le 10/09/2026 — *« les publications confidentielles ne sont bien sûr pas affichées, ou celles qui sont réservées au Conseil Syndical »*. Les deux notions coexistent depuis #347 et se combinent en ET : n'en filtrer qu'une laissait l'autre passer |
| tickets **annulés** | ils partent aux Archives sur-le-champ (`utils/archivage`) : une affaire abandonnée n'a rien à annoncer au hall |
| **réservés au périmètre** (🔒) | un hall se lit sans badge d'accès : ce que l'Accès referme sur un bâtiment n'y va pas |

## Une famille depuis le 23/09/2026 (#1091 lot 4, #1092 lot 5)

Une actualité EST une affaire de catégorie « Actualité ». Elle n'est plus une
famille à part : elle se reprend comme affaire, sous son libellé « Actualité ».
Les trois refus — confidentiel, réservé au conseil, réservé au périmètre — sont
une seule règle, `visibility.hors_du_hall`, que la génération de l'affiche
appelle aussi. Deux écritures divergeraient sur le cas limite, et l'une des deux
publierait au mur ce que l'autre refuse.

⚠️ La confidentialité est vérifiée **ici**, à la source, et non à l'affichage du
sélecteur : une liste qui montre ce qu'on ne doit pas reprendre invite à le
reprendre, et le premier qui contournera l'écran passera par l'API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from app.utils import horloge
from typing import Optional

from sqlmodel import Session, select

from app.models.core import Ticket
from app.utils.archivage import est_archivable, seuil_archivage_jours
from app.utils.categories_ticket import libelle_categorie
from app.utils.nature_affaire import est_actualite
from app.utils.perimetres import parse_json_perimetres
from app.utils.visibility import hors_du_hall

#: Les familles reprenables, et leur libellé à l'écran. Une affaire de catégorie
#: « Actualité » garde le sien (`SourceAffiche.famille`).
FAMILLES: dict[str, str] = {
    "ticket": "Affaire",
}
#  « evenement » est parti le 23/09/2026 (#1092, lot 5) : les événements du
#  calendrier sont devenus des affaires, reprises par la famille « ticket ».

#: Fenêtre du fil, en jours. Recopiée depuis `routers/flux/__init__.py` —
#: l'importer créerait un cycle (le routeur importe les utilitaires). Le test
#: `test_sources_affiche.py` refuse que les deux divergent.
FENETRE_JOURS = 377


@dataclass
class SourceAffiche:
    """Un élément du fil, réduit à ce qu'un sélecteur doit montrer."""

    type: str
    id: int
    titre: str
    date: datetime
    epingle: bool
    #: Le libellé propre à l'élément, quand sa famille n'en dit pas assez : une
    #: affaire de catégorie « Actualité » se présente comme une actualité.
    libelle: str = ""

    @property
    def famille(self) -> str:
        return self.libelle or FAMILLES[self.type]

    def cle(self) -> str:
        """Identifiant stable côté écran — le type SEUL ne suffit pas, et l'id
        non plus : trois familles peuvent porter le même numéro."""
        return f"{self.type}:{self.id}"


def sources_disponibles(
    session: Session, *, maintenant: Optional[datetime] = None
) -> list[SourceAffiche]:
    """Tout ce que le fil montre aujourd'hui et qu'on peut reprendre au hall.

    Trié comme le fil : les épinglés d'abord, puis du plus récent au plus ancien.
    """
    maintenant = maintenant or horloge.maintenant()
    depuis = maintenant - timedelta(days=FENETRE_JOURS)
    sources: list[SourceAffiche] = []

    #  ── Affaires, actualités comprises ─────────────────────────────────────
    #  « Archivé » est la règle des listes (`est_archivable`), qui sait qu'une
    #  actualité se périme autrement qu'une affaire suivie : on l'appelle plutôt
    #  que de la refaire — deux copies divergeraient sur le cas limite.
    seuil = seuil_archivage_jours(session)
    for tk in session.exec(select(Ticket).where(Ticket.cree_le >= depuis)).all():
        if hors_du_hall(tk) or est_archivable(
            "ticket", tk, seuil_jours=seuil, maintenant=maintenant
        ):
            continue
        sources.append(
            SourceAffiche(
                "ticket",
                tk.id,
                tk.titre,
                tk.cree_le,
                bool(tk.epingle),
                libelle=libelle_categorie(tk.categorie) if est_actualite(tk) else "",
            )
        )

    sources.sort(key=lambda s: (not s.epingle, -s.date.timestamp()))
    return sources


def prefill_source(session: Session, type_source: str, id_source: int) -> Optional[dict]:
    """Les champs d'un élément du fil, prêts à alimenter le formulaire d'affiche.

    Rend `None` quand l'élément n'existe pas **ou qu'il n'est pas reprenable** :
    l'appelant répond alors 404, sans distinguer les deux cas. Dire « il existe
    mais vous ne pouvez pas le reprendre » renseignerait sur un contenu
    confidentiel.
    """
    reprenable = {s.cle() for s in sources_disponibles(session)}
    if f"{type_source}:{id_source}" not in reprenable:
        return None

    if type_source == "ticket":
        tk = session.get(Ticket, id_source)
        #  ⚠️ Les photos d'une affaire suivie sont des CONSTATS — une fuite, une
        #  porte cassée. On ne les reprend pas : une affiche de hall montre ce
        #  qu'on annonce, pas l'état des lieux. Celles d'une actualité, elles,
        #  illustrent l'annonce : elles suivent, comme à la génération directe.
        images = []
        if est_actualite(tk):
            from app.routers.annonces_hall import images_de

            images = images_de(tk, session)
        return {
            "titre": tk.titre,
            "message": tk.description,
            "perimetre_cible": parse_json_perimetres(tk.perimetre_cible),
            "images": images,
        }

    return None
