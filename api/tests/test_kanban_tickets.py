"""Un ticket « Étude & travaux » au kanban — la correspondance ne dérive pas (#833).

## Ce que ce fichier verrouille

1. la **correspondance** statut → colonne, dans les deux langages ;
2. les **colonnes visées existent** dans le kanban — une carte rangée dans une
   colonne inconnue disparaît sans rien dire ;
3. `fournisseur` reste **inatteignable** depuis un ticket, et c'est un constat
   déclaré, pas un oubli.

⚠️ La table est écrite **deux fois** — `app/utils/kanban_tickets.py` et
`front/src/lib/kanban.ts` — parce que les contextes de build sont `./api` et
`./front` : le partage d'un fichier est impossible, seule la copie l'est. C'est
le même dispositif que `KANBAN_LABELS` de `calendrier_historique.py`, et c'est ce
test qui rend la copie tenable.
"""

from __future__ import annotations

import pathlib
import re

from app.models.tickets import StatutTicket
from app.utils.kanban_tickets import (
    CATEGORIES_SUIVIES,
    COLONNE_PAR_STATUT,
    colonne_du_ticket,
    suivi_par_defaut,
)

_KANBAN_TS = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "kanban.ts"


def _table_ts(nom: str) -> dict[str, str]:
    source = _KANBAN_TS.read_text(encoding="utf-8")
    debut = source.index(f"export const {nom}")
    corps = source[source.index("{", debut) + 1 : source.index("};", debut)]
    return {
        m.group(1): m.group(2) for m in re.finditer(r"^\t(\S+?):\s*'([^']*)',", corps, re.MULTILINE)
    }


def _colonnes_du_front() -> set[str]:
    """Les identifiants de `KANBAN_COLS` — la source unique des colonnes."""
    source = _KANBAN_TS.read_text(encoding="utf-8")
    debut = source.index("export const KANBAN_COLS")
    corps = source[debut : source.index("];", debut)]
    return set(re.findall(r"id:\s*'([^']+)'", corps))


def test_TOUS_les_statuts_de_ticket_ont_une_colonne():
    """🔴 Un statut sans colonne fait disparaître la carte, en silence.

    L'énumération fait foi : si un cinquième état apparaît, ce test l'exige ici
    avant que le tableau ne se mette à perdre des tickets.
    """
    #  ⚠️ SAUF l'état sans cycle (#1091) : une actualité ne paraît PAS au kanban,
    #  et c'est l'absence de colonne qui l'en sort. Déclaré par le modèle, lu ici
    #  — et le test suivant exige qu'il n'en ait vraiment aucune.
    from app.models.tickets import STATUTS_TICKET_SANS_CYCLE

    for statut in StatutTicket:
        if statut.value in STATUTS_TICKET_SANS_CYCLE:
            assert statut.value not in COLONNE_PAR_STATUT, (
                f"{statut.value} a une colonne : l'actualité paraîtrait au kanban."
            )
            continue
        assert statut.value in COLONNE_PAR_STATUT, (
            f"statut sans colonne kanban : {statut.value}. Le ticket "
            "disparaîtrait du tableau sans que rien ne le signale."
        )


def test_TOUTES_les_colonnes_du_kanban_sont_atteignables():
    """Les six colonnes ont chacune un état d'affaire (#1092, lot 5, 23/09/2026).

    Ce test disait l'inverse — « la colonne fournisseur reste inatteignable » —
    et posait la question le jour où un état apparaîtrait. Elle a été posée et
    tranchée : `en_ag` et `chez_prestataire` sont nés quand les événements du
    calendrier sont devenus des affaires. Une colonne sans état redeviendrait un
    endroit où une carte atterrit dans un état que le serveur ne connaît pas.

    L'égalité tient les deux sens : une colonne visée qui n'existe pas au front
    range la carte nulle part ; une colonne du front qu'aucun état ne vise reste
    vide pour toujours.
    """
    colonnes = set(_colonnes_du_front())
    #  Cas zéro : une extraction cassée rendrait deux ensembles vides, et égaux.
    assert len(colonnes) >= 6, "extraction de `KANBAN_COLS` cassée — rien ne serait mesuré"
    visees = set(COLONNE_PAR_STATUT.values())
    assert visees == colonnes, (
        f"colonnes visées inconnues du kanban : {sorted(visees - colonnes)} ; "
        f"colonnes du kanban qu'aucun état ne vise : {sorted(colonnes - visees)}"
    )


def test_le_FRONT_ecrit_EXACTEMENT_la_meme_table():
    """🔴 Le garde-fou de la copie assumée.

    Deux écritures d'une même correspondance divergent au premier ajustement, et
    le tableau rangerait alors les cartes autrement que le serveur ne le croit.
    """
    du_front = _table_ts("COLONNE_PAR_STATUT_TICKET")
    assert du_front == COLONNE_PAR_STATUT, (
        "la table du front et celle du serveur ont divergé :\n"
        f"  serveur : {COLONNE_PAR_STATUT}\n"
        f"  front   : {du_front}"
    )


def test_un_statut_INCONNU_ne_range_nulle_part():
    """⚠️ `None`, jamais un repli sur `cs`.

    Une carte posée dans la mauvaise colonne se lit comme une information, et
    personne ne la remet en cause. Mieux vaut qu'elle n'apparaisse pas.
    """
    assert colonne_du_ticket("chez_le_notaire") is None
    assert colonne_du_ticket(None) is None
    assert colonne_du_ticket("") is None


def test_seule_ETUDE_TRAVAUX_entre_au_tableau_d_office():
    """Le défaut par catégorie — et le fait que les autres n'y entrent pas.

    Sans le second cas, « coché d'office » pourrait vouloir dire « coché pour
    tout le monde », et le tableau du conseil se remplirait d'ampoules grillées.
    """
    assert suivi_par_defaut("etude_travaux") is True
    for autre in ("panne", "nuisance", "sinistre", "bug", None):
        assert suivi_par_defaut(autre) is False, f"{autre} entre au tableau d'office"


def test_la_categorie_visee_EXISTE_vraiment():
    """Un identifiant de catégorie mal orthographié ne lève pas : il n'apparie rien.

    `suivi_par_defaut` rendrait alors `False` pour tout le monde, et la
    fonctionnalité serait silencieusement morte.
    """
    from app.utils.categories_ticket import LIBELLES_CATEGORIE

    for categorie in CATEGORIES_SUIVIES:
        assert categorie in LIBELLES_CATEGORIE, (
            f"catégorie inconnue : {categorie}. `suivi_par_defaut` rendrait "
            "toujours False, et aucun ticket n'entrerait au tableau."
        )


# ── Avec l'ÉNUMÉRATION, pas seulement la chaîne (#1092, 23/09/2026) ───────────
#
#  🔴 `str(CategorieTicket.etude_travaux)` vaut « CategorieTicket.etude_travaux »,
#  pas « etude_travaux ». La création passe l'énumération (`body.categorie`) :
#  le défaut « Étude & travaux entre au kanban » ne s'est donc jamais posé. Les
#  tests ci-dessus n'éprouvaient que des chaînes.


def test_le_defaut_de_suivi_accepte_l_enumeration():
    from app.models.tickets import CategorieTicket

    assert suivi_par_defaut(CategorieTicket.etude_travaux) is True
    assert suivi_par_defaut(CategorieTicket.panne) is False


def test_la_colonne_accepte_l_enumeration():
    from app.models.tickets import StatutTicket
    from app.utils.kanban_tickets import colonne_du_ticket

    assert colonne_du_ticket(StatutTicket.ouvert) == colonne_du_ticket("ouvert") is not None


def test_les_colonnes_servies_sont_celles_du_front():
    """`GET /tickets/referentiels` sert `COLONNES_KANBAN` (#2508) : l'ordre, le
    libellé et le mot court de `KANBAN_COLS`, que l'app ne recopie plus."""
    from app.utils.kanban_tickets import COLONNES_KANBAN

    source = _KANBAN_TS.read_text(encoding="utf-8")
    debut = source.index("export const KANBAN_COLS")
    corps = source[debut : source.index("];", debut)]
    front = re.findall(
        r"id:\s*'([^']+)',\s*label:\s*'([^']+)',\s*labelCourt:\s*'([^']+)'", corps, re.S
    )
    assert len(front) == 6, f"{len(front)} colonne(s) lue(s) : le motif ne correspond plus."
    assert list(COLONNES_KANBAN) == front
