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
antérieure à la version de `front/package.json`. Depuis #2631, un lot ne porte plus
de bump — la version se pose à la MEP : ce fichier dit donc la dernière version
posée par un train, et le second temps n'est admis que si l'annonce est déjà
partie dans un train précédent.

Un RETRAIT de données (`drop_column`, `drop_table`) exige en plus sa **preuve sans
perte, lue sur la production** (`standards/06` §3, #2124 annulé par #2149, #2937) :
une ligne de `PREUVES_SANS_PERTE` — date, requête jouée sur la base servie, résultat.
Que le code n'en dépende plus ne dit pas que la colonne est vide. Une session qui ne
lit pas la production (session cloud) ne peut pas l'écrire : elle donne la requête à
jouer au poste, et le lot attend.

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
import re
from dataclasses import dataclass
from pathlib import Path

from tests.aides_contractions import (
    CONTRACTIONS,
    PREUVE_EXIGEE_APRES,
    PREUVES_SANS_PERTE,
    tables_et_colonnes_des_modeles,
    version_du_lot,
)
from tests.aides_migrations import CHAINES

#: Les gestes qui PERDENT des données, et donc exigent leur preuve.
PERTES = frozenset({"drop_table", "drop_column"})

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
    """Chaque migration des DEUX chaînes : `<chaîne>/<fichier>` → (numéro, source)."""
    trouvees = {}
    for chaine, dossier in CHAINES.items():
        lues = {
            f"{chaine}/{p.name}": (_numero(p), p.read_text(encoding="utf-8"))
            for p in sorted(dossier.glob("*.py"))
            if _numero(p) is not None
        }
        assert lues, f"aucune migration lue dans la chaîne `{chaine}` : la portée est cassée"
        trouvees |= lues
    return trouvees


def _preuve_exigee(fichier: str) -> bool:
    """Une migration écrite après la règle de SA chaîne (ou un cas forgé, sans numéro).

    `fichier` : `<chaîne>/<nom>` ; un nom nu est de la chaîne d'une copropriété."""
    chaine, _, nom = fichier.rpartition("/")
    numero = _numero(Path(nom))
    return numero is None or numero > PREUVE_EXIGEE_APRES[chaine or "copropriete"]


def _version(texte: str) -> tuple[int, ...]:
    return tuple(int(x) for x in texte.split("."))


def ecarts(
    fichier: str, gestes: list[Geste], contractions, version: str, modeles, preuves=None
) -> list[str]:
    """Ce qui rend une migration neuve incompatible avec la version précédente du code."""
    preuves = PREUVES_SANS_PERTE if preuves is None else preuves
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
        elif g.geste in PERTES and g.cible not in preuves and _preuve_exigee(fichier):
            sortie.append(
                f"{lieu} : `{g.cible}` est retirée sans preuve sans perte lue sur la "
                "PRODUCTION (`standards/06` §3) — jouer sur l'actif la requête qui montre "
                "qu'elle ne porte rien qui ne soit repris ailleurs, et noter date, requête "
                "et résultat dans `PREUVES_SANS_PERTE`. Une session sans accès à la "
                "production donne la requête et ne fusionne pas."
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
    preuve = {"facture.ancien": "23/11/2026 — select count(*) … → 0"}
    assert ecarts("m.py", retrait, annonce, "2.120.0", {"facture.ancien"}, preuve)
    assert not ecarts("m.py", retrait, annonce, "2.120.0", {"facture"}, preuve)
    assert not ecarts("m.py", retrait, annonce, "2.119.10", set(), preuve), "comparaison numérique"
    #  #2937 : annoncé, plus déclaré, mais sans preuve lue sur la production → refusé.
    assert ecarts("m.py", retrait, annonce, "2.120.0", {"facture"}, {})
    #  Les retraits d'avant la règle ne la produisent pas après coup ; un neuf, si.
    assert not ecarts("0308_x.py", retrait, annonce, "2.120.0", {"facture"}, {})
    assert ecarts(
        f"{PREUVE_EXIGEE_APRES['copropriete'] + 1:04d}_x.py",
        retrait,
        annonce,
        "2.120.0",
        {"facture"},
        {},
    )
    #  #3098 : le seuil est celui de la chaîne. Une 0007 du registre retire sans preuve :
    #  refusée, bien que 7 < 346 ; ses migrations d'avant la règle ne la produisent pas.
    assert ecarts("plateforme/0007_x.py", retrait, annonce, "2.120.0", {"facture"}, {})
    assert not ecarts("plateforme/0006_x.py", retrait, annonce, "2.120.0", {"facture"}, {})
    assert not ecarts("copropriete/0308_x.py", retrait, annonce, "2.120.0", {"facture"}, {})
    #  Un renommage ne perd rien : il n'exige pas de preuve.
    renommage = [Geste("rename_table", "avant", 4)]
    assert not ecarts("m.py", renommage, {"avant": ("2.119.0", "x")}, "2.120.0", set(), {})
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


def test_le_controle_lit_les_deux_chaines_et_le_registre():
    """Témoin de portée (#3098) : la chaîne `plateforme` et ses modèles sont lus."""
    noms = set(migrations())
    assert any(n.startswith("copropriete/") for n in noms)
    assert "plateforme/0005_canaux_et_vagues.py" in noms
    assert {"installation", "version_disponible"} <= tables_et_colonnes_des_modeles()


def test_une_table_annoncee_au_dernier_train_ne_se_retire_qu_au_suivant():
    """La version d'une annonce est la dernière posée par un train (#2631) : un retrait
    dans le même train est refusé, dans le suivant admis — avec sa preuve."""
    retrait = [Geste("drop_table", "canal_distribution", 3)]
    annonce = {"canal_distribution": CONTRACTIONS["canal_distribution"]}
    preuve = {"canal_distribution": "jj/mm/aaaa — select … → …"}
    meme_train = CONTRACTIONS["canal_distribution"][0]
    assert ecarts("plateforme/0007_x.py", retrait, annonce, meme_train, set(), preuve)
    suivant = ".".join(meme_train.split(".")[:-1] + [str(int(meme_train.split(".")[-1]) + 1)])
    assert not ecarts("plateforme/0007_x.py", retrait, annonce, suivant, set(), preuve)


def test_une_table_annoncee_reste_lisible_dans_les_sauvegardes_d_avant():
    """Chaque table annoncée est déclarée retirée à l'import, et réciproquement (#3098) :
    sans quoi chaque sauvegarde d'avant son retrait serait refusée à la restauration."""
    from app.utils.import_copropriete import TABLES_RETIREES

    annoncees = {c for c in CONTRACTIONS if "." not in c}
    assert annoncees == set(TABLES_RETIREES), (
        f"CONTRACTIONS annonce {sorted(annoncees)}, l'import écarte {sorted(TABLES_RETIREES)}"
    )
