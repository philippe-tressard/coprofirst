"""Une colonne d'état a une liste de valeurs admises, déclarée (#2954, 24/11/2026).

Socle `06` §7 : « énumérations fermées côté modèle, jamais de chaîne libre pour un
état ». Dix-sept colonnes `statut`/`etat` sont pourtant du TEXTE en base, et leur
vocabulaire vivait en commentaire — l'un d'eux faux : `WhatsAppLog.statut` disait
« envoyé | échec » quand `utils/whatsapp` en écrit quatre.

Passer une colonne en énumération change la base (migration en deux temps,
`CONTRACTIONS`) : ce n'est pas l'objet de ce contrôle. Il exige que chaque colonne
d'état en texte soit l'une de deux choses :

- dans `VALEURS_ADMISES`, avec ses valeurs LUES DANS LE CODE (les constantes que
  le code écrit, jamais une copie) — et sa valeur par défaut doit en être ;
- dans `ETATS_LIBRES`, liste FIGÉE qui ne fait que BAISSER : le vocabulaire n'y
  existe qu'en commentaire, et l'entrée dit où. En sortir, c'est donner à la
  colonne une liste fermée dans le code, puis l'inscrire dans `VALEURS_ADMISES`.

Une colonne d'état neuve en texte, sans l'une ni l'autre, échoue.

⚠️ Non vérifié : les valeurs réellement présentes en base de production. Ce
contrôle lit le code, pas les lignes ; une valeur héritée hors liste n'est pas vue.
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from sqlmodel import AutoString, SQLModel

import app.models  # noqa: F401 — enregistre toutes les tables dans `SQLModel.metadata`
from app.models.roles import StatutUtilisateur
from app.models.synthese import STATUTS_SYNTHESE
from app.models.tickets import StatutTicket
from app.models.validations import StatutDemandeSuppression
from app.models import points_conseil
from app.utils import courriel_a_classer, llm_journal, whatsapp
from app.utils.points_conseil_etats import ETATS_A_LA_VALIDATION
from app.utils.question_reglement import transcription

#: (table, colonne) → les valeurs que le code écrit, lues à leur source.
VALEURS_ADMISES: dict[tuple[str, str], tuple[str, ...]] = {
    ("whatsapp_log", "statut"): (
        whatsapp.STATUT_ENVOYE,
        whatsapp.STATUT_ECHEC,
        whatsapp.STATUT_INCERTAIN,
        whatsapp.STATUT_EN_COURS,
    ),
    ("courriel_a_classer", "statut"): tuple(courriel_a_classer.STATUTS),
    ("appel_ia", "statut"): (
        llm_journal.STATUT_SUCCES,
        llm_journal.STATUT_ERREUR,
        *llm_journal.STATUTS_REFUS,
    ),
    ("synthese_affaire", "statut"): tuple(STATUTS_SYNTHESE),
    ("transcription_pv", "statut"): tuple(transcription.STATUTS),
    ("point_conseil", "etat"): (
        points_conseil.EN_COURS,
        points_conseil.A_VALIDER,
        points_conseil.VALIDE,
    ),
    ("point_conseil_cr", "etat_cible"): tuple(ETATS_A_LA_VALIDATION),
    ("demande_suppression_compte", "statut"): tuple(e.value for e in StatutDemandeSuppression),
    ("demande_modification_profil", "statut_souhaite"): tuple(e.value for e in StatutUtilisateur),
    ("versement_courriel", "statut_avant"): tuple(e.value for e in StatutTicket),
}

#: (table, colonne) → où vit son vocabulaire, faute de liste dans le code.
#: 🔴 FIGÉE : elle ne fait que BAISSER, et une entrée qui ne sert plus échoue.
ETATS_LIBRES: dict[tuple[str, str], str] = {
    ("evenement", "statut_kanban"): "commentaire de `models/evenement.py` (ag|cs|syndic|…)",
    ("tentative_synthese", "statut"): "commentaire de `models/synthese.py` (succes|erreur|…)",
    ("idee", "statut"): "commentaire de `models/communaute.py` (ouverte|retenue|…)",
    ("signalement", "statut"): "commentaire de `models/communaute.py` (en_attente|traite|…)",
    ("historique_email", "statut"): "commentaire de `models/exploitation.py` (succes|erreur|…)",
    ("historique_maintenance", "statut"): "commentaire de `models/exploitation.py` (succes|…)",
    ("historique_telemetrie", "statut"): "commentaire de `models/telemetrie.py` (en_cours|…)",
}

#: Le plafond des états libres. Il ne fait que BAISSER.
PLAFOND_ETATS_LIBRES = 7


def _est_un_etat(nom: str) -> bool:
    return nom in ("statut", "etat") or nom.startswith(("statut_", "etat_"))


def colonnes_d_etat_en_texte(tables: Iterable[sa.Table]) -> set[tuple[str, str]]:
    """Les (table, colonne) d'état typées en texte libre — une énumération exclue. PURE."""
    return {
        (t.name, c.name)
        for t in tables
        for c in t.columns
        if _est_un_etat(c.name)
        #  `AutoString` (le `str` de SQLModel) est un TypeDecorator, pas un `String`.
        and isinstance(c.type, (sa.String, AutoString))
        and not isinstance(c.type, sa.Enum)
    }


def ecarts(trouvees, admises, libres) -> list[str]:
    """Ce qui rend les deux listes fausses — vide si chaque colonne est dite une fois. PURE."""
    dites = set(admises) | set(libres)
    sortie = [
        f"{t}.{c} : un état en texte libre sans liste de valeurs — une énumération, ou "
        "ses constantes dans le code, déclarées dans VALEURS_ADMISES"
        for t, c in sorted(trouvees - dites)
    ]
    sortie += [
        f"{t}.{c} : déclarée, mais la colonne n'existe plus (ou est devenue une énumération) "
        "— retirer l'entrée"
        for t, c in sorted(dites - trouvees)
    ]
    sortie += [f"{t}.{c} : dans les DEUX listes" for t, c in sorted(set(admises) & set(libres))]
    return sortie


def _tables():
    return SQLModel.metadata.tables.values()


def test_chaque_etat_en_texte_a_sa_liste():
    trouvees = colonnes_d_etat_en_texte(_tables())
    assert len(trouvees) >= 10, f"le relevé ne voit que {len(trouvees)} colonne(s) : contrôle vide"
    fautes = ecarts(trouvees, VALEURS_ADMISES, ETATS_LIBRES)
    assert not fautes, "\n".join(fautes)


def test_la_valeur_par_defaut_est_admise():
    """Le défaut du modèle est une valeur de sa liste : la liste n'est pas décorative."""
    tables = SQLModel.metadata.tables
    fautes = []
    for (table, colonne), valeurs in VALEURS_ADMISES.items():
        assert valeurs and all(isinstance(v, str) for v in valeurs), (
            f"{table}.{colonne} : liste vide"
        )
        defaut = tables[table].columns[colonne].default
        if defaut is not None and defaut.is_scalar and defaut.arg not in valeurs:
            fautes.append(f"{table}.{colonne} : défaut {defaut.arg!r} hors de {valeurs}")
    assert not fautes, "\n".join(fautes)


def test_le_controle_sait_refuser():
    table = sa.Table(
        "tableau",
        sa.MetaData(),
        sa.Column("statut", sa.String),
        sa.Column("etat_cible", sa.String),
        sa.Column("statut_change_le", sa.DateTime),
        sa.Column("etat", sa.Enum("a", "b", name="etat_tableau")),
        sa.Column("statuts_vus", sa.String),
    )
    trouvees = colonnes_d_etat_en_texte([table])
    assert trouvees == {("tableau", "statut"), ("tableau", "etat_cible")}
    assert ecarts(trouvees, {}, {}) != [], "une colonne d'état neuve sans liste passe"
    assert ecarts(set(), {("tableau", "statut"): ("a",)}, {}) != [], "une entrée périmée passe"
    double = {("tableau", "statut"): "x"}
    assert ecarts({("tableau", "statut")}, double, double) != [], "un double compte passe"


def test_les_etats_libres_ne_font_que_baisser():
    assert len(ETATS_LIBRES) <= PLAFOND_ETATS_LIBRES, (
        "un état libre de plus : lui donner une liste dans le code, pas une entrée ici"
    )
    assert len(ETATS_LIBRES) == PLAFOND_ETATS_LIBRES, (
        "une entrée a disparu : abaisser PLAFOND_ETATS_LIBRES au même nombre"
    )
