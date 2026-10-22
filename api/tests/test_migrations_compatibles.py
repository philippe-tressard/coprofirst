"""Une migration est compatible avec la version précédente du code (#1757, 08/10/2026).

Chantier multi-copropriétés, distribution : `specs/architecture/multi-coproprietes.md`
§4.10, règle 7, décision D14.

## Pourquoi

Une mise à jour qui échoue doit pouvoir revenir en arrière **par un simple
changement d'image** : l'image N-1 redémarre sur la base que la version N vient
de migrer. Cela ne marche que si le schéma de N reste lisible ET inscriptible par
le code de N-1. Sinon, revenir en arrière demande de restaurer la sauvegarde — et
perd tout ce qui a été écrit depuis la mise à jour.

C'est vrai dès aujourd'hui pour 5Hostachy (le retour arrière de `mep-precheck`),
et ce sera vrai chaque nuit pour chaque installation CoproFirst (#1756).

## La règle : ajouter, puis retirer — jamais dans la même version

| Geste | Verdict |
|---|---|
| créer une table, ajouter une colonne **nullable ou avec `server_default`**, un index | libre : l'ancien code l'ignore |
| ajouter une colonne `nullable=False` **sans** `server_default` | refusé : l'ancien code y insère des lignes sans la remplir |
| retirer une table ou une colonne, renommer, passer une colonne à `nullable=False` | permis en **second temps** seulement |

Le second temps se déclare dans `CONTRACTIONS`, au moment où le code **cesse** de
dépendre de l'ancienne forme (premier temps, version V). La migration qui retire
vient dans une version **ultérieure** : le contrôle exige que V soit strictement
antérieure à la version de `front/package.json` — celle du lot, puisque le bump
en est le dernier commit. ⚠️ Avant ce bump, le second temps se lit donc en écart
quand V est la version en production : c'est attendu, le rejeu de la CI passe
après le bump.

Pour un retrait ou un renommage, le contrôle vérifie aussi le **fait** : aucun
modèle ne déclare plus la table ou la colonne retirée.

## Ce que le contrôle ne juge pas

- Le corps de `downgrade()`, qui défait par nature.
- Le SQL brut qui retire ou renomme : il est **refusé** dans une migration neuve,
  faute de pouvoir en lire la cible — passer par `op.drop_column`,
  `op.drop_table`, `op.alter_column`, que le contrôle sait lire.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

from tests.aides_migrations import VERSIONS

_RACINE = Path(__file__).resolve().parents[2]

#: Les contractions annoncées : la cible (`table` ou `table.colonne`), la version
#: du code qui a CESSÉ d'en dépendre, et pourquoi. Une entrée s'écrit au premier
#: temps, avec la version de ce lot ; la migration qui retire vient dans un lot
#: suivant. Une entrée reste après la migration : c'est la trace du retrait.
CONTRACTIONS: dict[str, tuple[str, str]] = {
    "ticket.non_relancable": (
        "2.130.5",
        "la relance syndic propose toute affaire suivie depuis v2.130.2 (#1796) ; "
        "le champ quitte le modèle, la 0272 lui donne un défaut (#1797)",
    ),
    "ticket.non_relancable_motif": ("2.130.5", "le motif du marquage retiré (#1797)"),
    "document.fichier_chemin": (
        "2.142.7",
        "le fichier se situe par sa clé depuis v2.142.3 (0283) ; le chemin absolu "
        "n'est plus ni lu ni écrit, la 0284 lui donne un défaut (#1816)",
    ),
    "diagnostic_rapport.fichier_chemin": ("2.142.7", "même règle que le document (#1816)"),
    "annonce_hall.pdf_chemin": ("2.142.7", "même règle que le document (#1816)"),
    #  Réglages écrits ou déclarés, jamais lus (#2059) : le code cesse d'en dépendre, la 0307
    #  donne un défaut aux colonnes NOT NULL ; le retrait vient dans une version ultérieure.
    "config_sauvegarde.frequence": (
        "3.11.0",
        "la sauvegarde est quotidienne depuis la 0139, rien ne lisait la fréquence (#2059)",
    ),
    "config_sauvegarde.jour_semaine": ("3.11.0", "même règle que la fréquence (#2059)"),
    "config_sauvegarde.jour_mois": ("3.11.0", "même règle que la fréquence (#2059)"),
    "modele_email.corps_texte": (
        "3.11.0",
        "le texte brut d'un modèle n'a jamais servi à l'envoi (#2059)",
    ),
    "copropriete.assurance_compagnie": (
        "3.11.0",
        "la fiche lit l'assurance sur le contrat depuis #490 ; la colonne ne sert plus (#2059)",
    ),
    "copropriete.assurance_numero_police": ("3.11.0", "même règle (#2059)"),
    "copropriete.assurance_echeance": ("3.11.0", "même règle (#2059)"),
}

#: Les gestes qui retirent quelque chose à l'ancien code.
RETRAITS = frozenset({"drop_table", "drop_column", "rename_table", "renommer_colonne"})

#: Le SQL brut qui retire ou renomme.
_SQL_DESTRUCTEUR = re.compile(r"\b(DROP\s+(TABLE|COLUMN)|RENAME\s+(TO|COLUMN))\b", re.IGNORECASE)


@dataclass(frozen=True)
class Geste:
    """Un geste de migration qui contracte le schéma, ou qui le serait par défaut."""

    geste: str  #: drop_table · drop_column · rename_table · renommer_colonne ·
    #: colonne_obligatoire (alter_column nullable=False) · ajout_sans_defaut · sql
    cible: str | None  #: `table` ou `table.colonne` ; None quand elle ne se lit pas
    ligne: int


def _constantes(arbre: ast.Module) -> dict[str, str]:
    """Les chaînes posées au niveau du module : `TABLE = "evenement"`."""
    return {
        cible.id: noeud.value.value
        for noeud in arbre.body
        if isinstance(noeud, ast.Assign)
        and isinstance(noeud.value, ast.Constant)
        and isinstance(noeud.value.value, str)
        for cible in noeud.targets
        if isinstance(cible, ast.Name)
    }


def _texte(noeud: ast.expr | None, constantes: dict[str, str]) -> str | None:
    """La valeur d'un argument littéral ou d'une constante du module, sinon None."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    if isinstance(noeud, ast.Name):
        return constantes.get(noeud.id)
    return None


def _mot_cle(appel: ast.Call, nom: str) -> ast.expr | None:
    return next((k.value for k in appel.keywords if k.arg == nom), None)


def _arg(appel: ast.Call, rang: int, nom: str) -> ast.expr | None:
    return appel.args[rang] if len(appel.args) > rang else _mot_cle(appel, nom)


def _colonne_sans_defaut(colonne: ast.expr | None) -> bool:
    """`sa.Column(..., nullable=False)` sans `server_default` ni clé primaire."""
    if not isinstance(colonne, ast.Call):
        return False
    nullable = _mot_cle(colonne, "nullable")
    obligatoire = isinstance(nullable, ast.Constant) and nullable.value is False
    return (
        obligatoire
        and _mot_cle(colonne, "server_default") is None
        and _mot_cle(colonne, "primary_key") is None
    )


def _joindre(table: str | None, colonne: str | None) -> str | None:
    return f"{table}.{colonne}" if table and colonne else None


def _geste_d_un_appel(appel: ast.Call, table_du_lot: str | None, constantes) -> Geste | None:
    """Le geste d'un appel `op.x(...)`, ou `lot.x(...)` dans un `batch_alter_table`."""
    if not isinstance(appel.func, ast.Attribute):
        return None
    nom, ligne = appel.func.attr, appel.lineno
    #  Dans un lot (`batch_alter_table`), la table est celle du `with` et la
    #  colonne vient en premier ; avec `op`, la table vient en premier.
    decalage = 0 if table_du_lot else 1

    def table() -> str | None:
        return table_du_lot or _texte(_arg(appel, 0, "table_name"), constantes)

    def colonne() -> str | None:
        return _texte(_arg(appel, decalage, "column_name"), constantes)

    if nom == "drop_table" and not table_du_lot:
        return Geste("drop_table", table(), ligne)
    if nom == "rename_table" and not table_du_lot:
        return Geste("rename_table", _texte(_arg(appel, 0, "old_table_name"), constantes), ligne)
    if nom == "drop_column":
        return Geste("drop_column", _joindre(table(), colonne()), ligne)
    if nom == "alter_column":
        if _mot_cle(appel, "new_column_name") is not None:
            return Geste("renommer_colonne", _joindre(table(), colonne()), ligne)
        nullable = _mot_cle(appel, "nullable")
        if isinstance(nullable, ast.Constant) and nullable.value is False:
            return Geste("colonne_obligatoire", _joindre(table(), colonne()), ligne)
    if nom == "add_column" and _colonne_sans_defaut(_arg(appel, decalage, "column")):
        nom_colonne = _texte(_arg(_arg(appel, decalage, "column"), 0, "name"), constantes)
        return Geste("ajout_sans_defaut", _joindre(table(), nom_colonne), ligne)
    return None


def gestes_contractants(source: str) -> list[Geste]:
    """Les gestes d'une migration qui contractent le schéma, hors `downgrade()`."""
    arbre = ast.parse(source)
    constantes = _constantes(arbre)
    a_ignorer = {
        id(n)
        for f in arbre.body
        if isinstance(f, ast.FunctionDef) and f.name == "downgrade"
        for n in ast.walk(f)
    }
    #  Le nom lié par chaque `with op.batch_alter_table("t") as lot:` → sa table.
    lots: dict[int, str | None] = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.With):
            for item in noeud.items:
                appel = item.context_expr
                if (
                    isinstance(appel, ast.Call)
                    and isinstance(appel.func, ast.Attribute)
                    and appel.func.attr == "batch_alter_table"
                    and isinstance(item.optional_vars, ast.Name)
                ):
                    table = _texte(_arg(appel, 0, "table_name"), constantes)
                    for n in ast.walk(noeud):
                        if (
                            isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Attribute)
                            and isinstance(n.func.value, ast.Name)
                            and n.func.value.id == item.optional_vars.id
                        ):
                            lots[id(n)] = table or "?"
    gestes: list[Geste] = []
    for noeud in ast.walk(arbre):
        if id(noeud) in a_ignorer:
            continue
        if isinstance(noeud, ast.Call):
            geste = _geste_d_un_appel(noeud, lots.get(id(noeud)), constantes)
            if geste:
                gestes.append(geste)
        elif (
            isinstance(noeud, ast.Constant)
            and isinstance(noeud.value, str)
            and _SQL_DESTRUCTEUR.search(noeud.value)
        ):
            gestes.append(Geste("sql", None, noeud.lineno))
    return sorted(gestes, key=lambda g: g.ligne)


def _numero(chemin: Path) -> int | None:
    tete = chemin.name.split("_", 1)[0]
    return int(tete) if tete.isdigit() else None


def migrations() -> dict[str, tuple[int, str]]:
    """Chaque migration : son nom de fichier → (numéro, source)."""
    trouvees = {
        p.name: (_numero(p), p.read_text(encoding="utf-8"))
        for p in sorted(VERSIONS.glob("*.py"))
        if _numero(p) is not None
    }
    assert trouvees, "aucune migration lue : la portée est cassée"
    return trouvees


def _version(texte: str) -> tuple[int, ...]:
    return tuple(int(x) for x in texte.split("."))


def version_du_lot() -> str:
    return json.loads((_RACINE / "front" / "package.json").read_text(encoding="utf-8"))["version"]


def tables_et_colonnes_des_modeles() -> set[str]:
    """`table` et `table.colonne` de chaque modèle SQLModel enregistré."""
    from sqlmodel import SQLModel

    #  `app.models.core` et non `app.models` : c'est lui qui charge tous les modules
    #  de modèles, comme `alembic/env.py` (CLAUDE.md, #1157).
    import app.models.core  # noqa: F401 — enregistre les tables

    cibles: set[str] = set()
    for nom, table in SQLModel.metadata.tables.items():
        cibles.add(nom)
        cibles |= {f"{nom}.{c.name}" for c in table.columns}
    return cibles


def ecarts(fichier: str, gestes: list[Geste], contractions, version: str, modeles) -> list[str]:
    """Ce qui rend une migration neuve incompatible avec la version précédente du code."""
    sortie = []
    for g in gestes:
        lieu = f"{fichier}:{g.ligne}"
        if g.geste == "sql":
            sortie.append(
                f"{lieu} : SQL brut qui retire ou renomme — sa cible ne se lit pas. "
                "Passer par op.drop_table, op.drop_column ou op.alter_column."
            )
        elif g.geste == "ajout_sans_defaut":
            sortie.append(
                f"{lieu} : colonne {g.cible or '?'} ajoutée `nullable=False` sans "
                "`server_default` — l'ancien code y insère des lignes sans la remplir. "
                "La rendre nullable, ou lui donner un `server_default`."
            )
        elif g.cible is None:
            sortie.append(
                f"{lieu} : {g.geste} dont la cible ne se lit pas (ni littéral, ni constante)"
            )
        elif g.cible not in contractions:
            sortie.append(
                f"{lieu} : {g.geste} sur `{g.cible}` en un seul temps. Premier temps : le "
                "code cesse d'en dépendre, et `CONTRACTIONS` l'annonce avec la version de "
                "ce lot-là ; second temps, dans une version ULTÉRIEURE : cette migration."
            )
        elif _version(contractions[g.cible][0]) >= _version(version):
            sortie.append(
                f"{lieu} : `{g.cible}` annoncée en v{contractions[g.cible][0]}, retirée en "
                f"v{version} — le second temps doit venir dans une version ultérieure. "
                "(Lot pas encore bumpé ? Ce contrôle se lit après le bump.)"
            )
        elif g.geste in RETRAITS and g.cible in modeles:
            sortie.append(
                f"{lieu} : `{g.cible}` est retirée, mais un modèle la déclare encore — "
                "le code en dépend toujours."
            )
    return sortie


def _neuves() -> dict[str, str]:
    return {nom: src for nom, (_num, src) in migrations().items()}


def test_aucune_migration_neuve_ne_contracte_en_un_seul_temps():
    """Le contrôle : chaque migration écrite après lui, confrontée à la règle."""
    neuves = _neuves()
    if not neuves:
        return
    version, modeles = version_du_lot(), tables_et_colonnes_des_modeles()
    trouves = [
        e
        for nom, src in neuves.items()
        for e in ecarts(nom, gestes_contractants(src), CONTRACTIONS, version, modeles)
    ]
    assert not trouves, "\n".join(trouves)


def test_une_contraction_annoncee_n_est_plus_declaree_par_un_modele():
    """Le premier temps lui-même : annoncer une contraction, c'est que le code a CESSÉ
    d'en dépendre. Un modèle qui déclare encore la cible ferait insérer la colonne par
    l'ancien code après son retrait — et le contrôle ne le verrait qu'au second temps."""
    modeles = tables_et_colonnes_des_modeles()
    encore = sorted(c for c in CONTRACTIONS if c in modeles)
    assert not encore, f"annoncées dans CONTRACTIONS mais encore déclarées : {encore}"


def test_le_releve_reconnait_chaque_forme():
    """Chaque forme est vue ; ce qui ne contracte pas ne l'est pas ; `downgrade` est ignoré."""
    source = (
        "import sqlalchemy as sa\n"
        "from alembic import op\n"
        "TABLE = 'facture'\n"
        "def upgrade():\n"
        "    op.create_table('neuve', sa.Column('id', sa.Integer, primary_key=True))\n"
        "    op.add_column(TABLE, sa.Column('note', sa.String, nullable=True))\n"
        "    op.add_column(TABLE, sa.Column('etat', sa.String, nullable=False, server_default='x'))\n"
        "    op.add_column(TABLE, sa.Column('code', sa.String, nullable=False))\n"
        "    op.drop_column(TABLE, 'ancien')\n"
        "    op.drop_table('vieille')\n"
        "    op.rename_table('avant', 'apres')\n"
        "    op.alter_column(TABLE, 'nom', new_column_name='libelle')\n"
        "    op.alter_column(TABLE, 'montant', nullable=False)\n"
        "    op.alter_column(TABLE, 'montant', nullable=True)\n"
        "    with op.batch_alter_table('lot') as lot:\n"
        "        lot.drop_column('etage')\n"
        "        lot.add_column(sa.Column('surface', sa.Integer, nullable=False))\n"
        "    op.execute('ALTER TABLE x DROP COLUMN y')\n"
        "    op.execute('UPDATE facture SET note = NULL')\n"
        "def downgrade():\n"
        "    op.drop_table('neuve')\n"
        "    op.drop_column(TABLE, 'note')\n"
    )
    assert [(g.geste, g.cible) for g in gestes_contractants(source)] == [
        ("ajout_sans_defaut", "facture.code"),
        ("drop_column", "facture.ancien"),
        ("drop_table", "vieille"),
        ("rename_table", "avant"),
        ("renommer_colonne", "facture.nom"),
        ("colonne_obligatoire", "facture.montant"),
        ("drop_column", "lot.etage"),
        ("ajout_sans_defaut", "lot.surface"),
        ("sql", None),
    ]


def test_la_regle_refuse_et_admet_ce_qu_il_faut():
    """Un seul temps, une annonce trop récente, un modèle qui la lit encore : refusés."""
    retrait = [Geste("drop_column", "facture.ancien", 3)]
    annonce = {"facture.ancien": ("2.119.0", "le code a cessé de la lire")}
    assert ecarts("m.py", retrait, {}, "2.120.0", set())
    assert ecarts("m.py", retrait, annonce, "2.119.0", set())
    assert ecarts("m.py", retrait, annonce, "2.120.0", {"facture.ancien"})
    assert not ecarts("m.py", retrait, annonce, "2.120.0", {"facture"})
    assert not ecarts("m.py", retrait, annonce, "2.119.10", set()), "comparaison numérique"
    obligatoire = [Geste("colonne_obligatoire", "facture.montant", 4)]
    #  Une colonne rendue obligatoire existe toujours : le modèle la déclare, c'est normal.
    assert not ecarts(
        "m.py",
        obligatoire,
        {"facture.montant": ("2.119.0", "toujours écrite")},
        "2.120.0",
        {"facture.montant"},
    )
    assert ecarts("m.py", [Geste("sql", None, 5)], annonce, "2.120.0", set())
    assert ecarts("m.py", [Geste("ajout_sans_defaut", "facture.code", 6)], {}, "2.120.0", set())


def test_le_releve_des_modeles_dit_ce_que_le_code_declare():
    """Le témoin du fait vérifié : une colonne déclarée y est, une colonne retirée n'y est plus."""
    modeles = tables_et_colonnes_des_modeles()
    assert {"evenement", "utilisateur.communaute_interdit"} <= modeles
    assert "evenement.archivee" not in modeles, "retirée par la 0250 : le relevé est faux"
    assert "utilisateur.sondage_interdit" not in modeles, "renommée par la 0070"
