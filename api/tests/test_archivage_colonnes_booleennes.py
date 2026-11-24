"""La liste figée des colonnes « booléen de disparition » (#1568, 02/10/2026).

« Pas de colonne `actif` par réflexe » (`CLAUDE.md`) n'avait aucune liste figée :
le 02/10/2026 les modèles en portaient QUINZE, dont `Evenement.archivee`, que plus
rien ne lisait ni n'écrivait — l'archivage des événements était parti avec leur
passage en affaires (#1092) et la colonne était restée (retirée par la 0250). Un
seizième `actif` serait passé de même.

Une colonne booléenne nommée `actif`, `active` ou `archivee` sur une table de
`app/models/` est donc l'une de DEUX choses :

- la décision d'archivage d'un objet de `REGLES` (`champ_actif` ou
  `champ_archive_manuel`) — une seule façon de disparaître ;
- un RÉFÉRENTIEL ou un DROIT, déclaré dans `REFERENTIELS` avec son sens : un
  booléen qui n'a rien à voir avec le fait de quitter les listes.

## Lu dans `SQLModel.metadata`, pas dans l'AST des classes (#2954, 24/11/2026)

Le relevé lisait l'AST des classes `table=True` : une colonne héritée d'une base
qui n'est pas une table (un mixin, comme `AssisteIAMixin`), ou une annotation
forgée (`bool | None`), lui échappaient. Il lit désormais les colonnes RÉELLES des
tables enregistrées, de type booléen, et retrouve la classe par le registre de
SQLModel. Les noms surveillés sont ceux d'une disparition : `actif`, `active`,
`archivee`, `archive_manuel`, `enabled`, `masque`, `masquee`, `visible` —
`masque` et `visible` ne nomment aucune colonne aujourd'hui, ils attendent la
suivante (un nom composé comme `contact_visible` n'est pas surveillé : il dit
ce qu'on montre d'un objet, pas que l'objet disparaît).

## Et les dates d'archivage

Une colonne non booléenne dont le nom dit l'archivage (`archive_le`,
`archive_par_id`…) est une seconde façon de disparaître si `REGLES` ne la
nomme pas : elle se déclare dans `ARCHIVAGES_HORS_REGLES`, avec sa raison.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import fields

import sqlalchemy as sa
from sqlmodel import SQLModel

import app.models  # noqa: F401 — enregistre toutes les tables dans `SQLModel.metadata`
from app.utils.archivage import REGLES, RegleArchivage
from tests.aides_archivage import MODELES

NOMS_BOOLEENS_DE_DISPARITION = frozenset(
    {"actif", "active", "archivee", "archive_manuel", "enabled", "masque", "masquee", "visible"}
)

#: Le sens de chaque colonne qui n'est PAS la décision d'archivage d'un objet de
#: `REGLES`, par (classe, champ). 🔴 Liste FIGÉE, qui ne fait que BAISSER : un
#: référentiel ajouté ici est un booléen de disparition de plus — il se justifie
#: dans le sens, et `PLAFOND_REFERENTIELS` se relève dans le même commit, à la
#: vue de la revue. Une entrée dont la colonne n'existe plus doit en sortir.
REFERENTIELS = {
    ("CompteurConfig", "actif"): (
        "référentiel : le compteur reste proposé au relevé, ou n'est plus relevé — "
        "l'historique des relevés ne disparaît pas"
    ),
    ("FaqItem", "actif"): "référentiel : une question de la FAQ masquée de l'écran, jamais effacée",
    ("Utilisateur", "actif"): (
        "droit de connexion : faux = compte pas encore validé, refusé ou désactivé ; "
        "le compte et ses écrits restent"
    ),
    ("UserLot", "actif"): (
        "lien actif d'un résident à un lot : fait foi pour « ce lot est le mien » "
        "(`est_rattache_au_lot`) ; le lien clos garde l'historique de l'occupation"
    ),
    ("Mandat", "actif"): "mandat de location ou juridique en cours : faux = mandat échu ou révoqué",
    ("DiagnosticType", "actif"): (
        "référentiel : un type de diagnostic réglementaire retiré de la liste proposée"
    ),
    ("ProfilAccesDocument", "actif"): (
        "référentiel : un profil d'accès aux documents (qui lit) mis hors service"
    ),
    ("CategorieDocument", "actif"): (
        "référentiel : une catégorie de la bibliothèque qui n'est plus proposée au dépôt ; "
        "ses documents restent lisibles"
    ),
    ("ModeleEmail", "actif"): (
        "référentiel : un modèle de courriel désactivé — l'envoi correspondant est coupé, "
        "ce n'est pas un objet qu'on archive ; sans effet sur un modèle non "
        "désactivable (#2054)"
    ),
    ("Perimetre", "actif"): (
        "référentiel : un nœud de l'arbre des périmètres retiré des choix ; "
        "le contenu qui le cite garde son code"
    ),
    ("Equipement", "actif"): (
        "référentiel : un équipement retiré des sélecteurs (#2442) ; les contrats, "
        "affaires et prestataires qui le citent gardent son code et son libellé"
    ),
    ("WhatsAppScheduled", "enabled"): (
        "interrupteur d'un message planifié : faux = le planificateur ne l'envoie plus "
        "(`whatsapp_scheduler`), la ligne et son journal d'envoi restent (#2954)"
    ),
}

#: Les colonnes NON booléennes qui disent l'archivage d'un objet hors de `REGLES`,
#: par (classe, champ) — un second mécanisme assumé, avec sa raison. 🔴 Liste
#: FIGÉE, qui ne fait que BAISSER ; une entrée dont la colonne n'existe plus en sort.
ARCHIVAGES_HORS_REGLES = {
    ("Avis", "archive_le"): (
        "l'avis se RETIRE par un geste daté, pas par une règle d'ancienneté : `REGLES` "
        "porte un délai, l'avis n'en a pas (`models/avis.py`, en-tête)"
    ),
    ("Avis", "archive_par_id"): (
        "qui a retiré l'avis : l'auteur peut ressortir ce qu'il a rangé, pas ce que le "
        "gestionnaire a retiré (`models/avis.py`, en-tête)"
    ),
}

#: Le plafond des référentiels. Il ne fait que BAISSER.
#: Déclarations permanentes : le compte ne baisse que si l'une cesse de servir
#: (relevé de clôture de la carte #1571, 30/10/2026 — aucune dette à solder).
PLAFOND_REFERENTIELS = 12


def classes_des_tables() -> dict[str, str]:
    """{nom de table: nom de classe} — lu dans le registre de SQLModel."""
    return {m.local_table.name: m.class_.__name__ for m in SQLModel._sa_registry.mappers}


def colonnes_booleennes_de_disparition(
    tables: Iterable[sa.Table], classes: dict[str, str]
) -> set[tuple[str, str]]:
    """Les (classe, champ) des tables qui portent un booléen de disparition. PURE.

    Les colonnes RÉELLES : héritées d'un mixin comprises, quelle que soit
    l'annotation écrite ; un schéma pydantic n'est pas une table, il n'y est pas.
    """
    return {
        (classes.get(t.name, t.name), c.name)
        for t in tables
        for c in t.columns
        if c.name in NOMS_BOOLEENS_DE_DISPARITION and isinstance(c.type, sa.Boolean)
    }


def colonnes_datees_d_archivage(
    tables: Iterable[sa.Table], classes: dict[str, str]
) -> set[tuple[str, str]]:
    """Les (classe, champ) NON booléens dont le nom dit l'archivage. PURE."""
    return {
        (classes.get(t.name, t.name), c.name)
        for t in tables
        for c in t.columns
        if "archiv" in c.name and not isinstance(c.type, sa.Boolean)
    }


def champs_nommes_par_les_regles() -> set[tuple[str, str]]:
    """Chaque (classe, champ) qu'une déclaration de `REGLES` nomme, quel que soit son rôle."""
    nommes = set()
    for type_objet, regle in REGLES.items():
        for f in fields(RegleArchivage):
            if not f.name.startswith("champ"):
                continue
            valeur = getattr(regle, f.name)
            for champ in valeur if isinstance(valeur, tuple) else (valeur,):
                if isinstance(champ, str):
                    nommes.add((MODELES[type_objet].__name__, champ))
    return nommes


def ecarts_d_archivage_date(trouvees, nommes, declarees) -> list[str]:
    """Ce qui rend `ARCHIVAGES_HORS_REGLES` faux — vide si chaque colonne est dite. PURE."""
    hors_regles = trouvees - nommes
    ecarts = [
        f"{classe}.{champ} : une date d'archivage ni dans REGLES ni dans "
        "ARCHIVAGES_HORS_REGLES — une seconde façon de disparaître ; la déclarer dans "
        "`utils/archivage.REGLES`, ou la justifier ici"
        for classe, champ in sorted(hors_regles - set(declarees))
    ]
    ecarts += [
        f"{classe}.{champ} : déclarée dans ARCHIVAGES_HORS_REGLES, mais la colonne n'existe "
        "plus ou REGLES la nomme — retirer l'entrée"
        for classe, champ in sorted(set(declarees) - hors_regles)
    ]
    return ecarts


def colonnes_couvertes_par_les_regles() -> set[tuple[str, str]]:
    """Les colonnes que `REGLES` déclare comme décision d'archivage, par (classe, champ)."""
    couvertes = set()
    for type_objet, regle in REGLES.items():
        for champ in (regle.champ_actif, regle.champ_archive_manuel):
            if champ in NOMS_BOOLEENS_DE_DISPARITION:
                couvertes.add((MODELES[type_objet].__name__, champ))
    return couvertes


def ecarts_de_declaration(trouvees, couvertes, referentiels) -> list[str]:
    """Ce qui rend la liste fausse — vide si chaque colonne est dite, et rien de plus."""
    ecarts = [
        f"{classe}.{champ} : ni dans REGLES, ni dans REFERENTIELS — une seconde façon de "
        "disparaître ; la déclarer dans `utils/archivage.REGLES`, ou la justifier ici"
        for classe, champ in sorted(trouvees - couvertes - set(referentiels))
    ]
    ecarts += [
        f"{classe}.{champ} : déclarée dans REFERENTIELS, mais la colonne n'existe plus — "
        "retirer l'entrée (la liste ne fait que baisser)"
        for classe, champ in sorted(set(referentiels) - trouvees)
    ]
    ecarts += [
        f"{classe}.{champ} : couverte par REGLES ET listée dans REFERENTIELS — une seule des deux"
        for classe, champ in sorted(couvertes & set(referentiels))
    ]
    return ecarts


def _reel() -> set[tuple[str, str]]:
    return colonnes_booleennes_de_disparition(
        SQLModel.metadata.tables.values(), classes_des_tables()
    )


def _table_factice(*colonnes: sa.Column) -> sa.Table:
    """Une table hors de `SQLModel.metadata` : le cas fautif ne pollue pas le registre."""
    return sa.Table("tableau", sa.MetaData(), sa.Column("id", sa.Integer), *colonnes)


def test_chaque_colonne_booleenne_de_disparition_est_dite():
    """Le contrôle : les colonnes réelles des modèles, confrontées aux deux listes."""
    ecarts = ecarts_de_declaration(
        _reel(),
        colonnes_couvertes_par_les_regles(),
        REFERENTIELS,
    )
    assert not ecarts, "\n".join(ecarts)


def test_le_releve_voit_ce_que_regles_declare():
    """Cas zéro : le relevé trouve des colonnes, et chaque colonne que `REGLES` nomme.

    Un relevé qui ne verrait rien rendrait le test précédent vert pour toujours.
    Le témoin doit SERVIR : si `REGLES` déclare `Prestataire.actif` et que le
    relevé ne le voit pas, c'est le relevé qui est faux.
    """
    trouvees = _reel()
    couvertes = colonnes_couvertes_par_les_regles()
    assert len(trouvees) >= 10, f"le relevé ne trouve que {len(trouvees)} colonne(s)"
    assert couvertes, "REGLES ne couvre aucune colonne booléenne : le témoin ne sert pas"
    assert couvertes <= trouvees, f"vues de REGLES, pas du relevé : {sorted(couvertes - trouvees)}"


def test_le_controle_refuse_une_colonne_de_plus():
    """Le cas fautif : un booléen de plus non déclaré, une entrée périmée, un double compte."""
    reel = _reel()
    couvertes = colonnes_couvertes_par_les_regles()
    de_plus = reel | {("Neuf", "actif")}
    assert ecarts_de_declaration(de_plus, couvertes, REFERENTIELS) != []
    sans_la_colonne = reel - {("Perimetre", "actif")}
    assert ecarts_de_declaration(sans_la_colonne, couvertes, REFERENTIELS) != []
    double = dict(REFERENTIELS) | {next(iter(couvertes)): "dit deux fois"}
    assert ecarts_de_declaration(reel, couvertes, double) != []


def test_le_releve_lit_les_colonnes_reelles():
    """Une colonne booléenne au nom surveillé est vue, quelle que soit son écriture ;
    un booléen ordinaire ou un nom composé ne l'est pas — et l'héritage compte."""
    table = _table_factice(
        sa.Column("actif", sa.Boolean),
        sa.Column("enabled", sa.Boolean, nullable=True),
        sa.Column("ordre", sa.Boolean),
        sa.Column("contact_visible", sa.Boolean),
        sa.Column("actif_le", sa.DateTime),
    )
    assert colonnes_booleennes_de_disparition([table], {"tableau": "Tableau"}) == {
        ("Tableau", "actif"),
        ("Tableau", "enabled"),
    }
    #  Héritage : `PetiteAnnonce` tient `assiste_ia` de `AssisteIAMixin`, qui n'est
    #  pas une table — l'AST de la classe ne le voyait pas, la table, si.
    annonce = SQLModel.metadata.tables["petite_annonce"]
    assert "assiste_ia" in annonce.columns, "le témoin d'héritage a disparu"


def test_chaque_date_d_archivage_est_dite():
    """Le contrôle : une date d'archivage hors de `REGLES` est déclarée, et rien de plus."""
    trouvees = colonnes_datees_d_archivage(SQLModel.metadata.tables.values(), classes_des_tables())
    assert ("Avis", "archive_le") in trouvees, "le relevé ne voit pas le témoin : contrôle vide"
    nommes = champs_nommes_par_les_regles()
    ecarts = ecarts_d_archivage_date(trouvees, nommes, ARCHIVAGES_HORS_REGLES)
    assert not ecarts, "\n".join(ecarts)
    for cle, raison in ARCHIVAGES_HORS_REGLES.items():
        assert len(raison.strip()) >= 20, f"{cle} : la raison n'est pas écrite"


def test_le_controle_des_dates_refuse():
    """Le cas fautif : une date d'archivage neuve non déclarée, une entrée périmée."""
    table = _table_factice(sa.Column("archivee_le", sa.DateTime))
    neuve = colonnes_datees_d_archivage([table], {"tableau": "Tableau"})
    assert neuve == {("Tableau", "archivee_le")}
    assert ecarts_d_archivage_date(neuve, set(), {}) != []
    assert ecarts_d_archivage_date(set(), set(), ARCHIVAGES_HORS_REGLES) != []
    assert ecarts_d_archivage_date(neuve, neuve, {}) == [], "nommée par REGLES : dite"


def test_la_liste_des_referentiels_ne_fait_que_baisser():
    """Plafond décroissant, et chaque entrée dit son sens."""
    assert len(REFERENTIELS) <= PLAFOND_REFERENTIELS, (
        f"{len(REFERENTIELS)} référentiels pour un plafond de {PLAFOND_REFERENTIELS} : "
        "un booléen de disparition de plus — le justifier ne suffit pas, il faut d'abord "
        "se demander si `utils/archivage.REGLES` ne le porte pas"
    )
    assert len(REFERENTIELS) == PLAFOND_REFERENTIELS, (
        "une entrée a disparu : abaisser PLAFOND_REFERENTIELS au même nombre"
    )
    for cle, sens in REFERENTIELS.items():
        assert len(sens.strip()) >= 20, f"{cle} : le sens de la colonne n'est pas écrit"
