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

Le relevé se fait sur l'AST : un formateur peut couper `actif: bool = Field(…)`
sur plusieurs lignes, une recherche de texte le raterait.
"""

from __future__ import annotations

import ast

from app.utils.archivage import REGLES
from tests.aides_archivage import MODELES
from tests.aides_sources import modules_app

NOMS_BOOLEENS_DE_DISPARITION = frozenset({"actif", "active", "archivee"})

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
}

#: Le plafond des référentiels. Il ne fait que BAISSER.
#: Déclarations permanentes : le compte ne baisse que si l'une cesse de servir
#: (relevé de clôture de la carte #1571, 30/10/2026 — aucune dette à solder).
PLAFOND_REFERENTIELS = 11


def colonnes_booleennes_de_disparition(sources: dict[str, str]) -> set[tuple[str, str]]:
    """Les (classe, champ) des tables qui portent un booléen de disparition.

    Lu sur l'AST : seule une classe `table=True` est une table (un schéma
    pydantic a le droit de rendre `archivee`), et l'annotation est lue
    quelle que soit la façon dont le formateur coupe la ligne.
    """
    trouvees: set[tuple[str, str]] = set()
    for source in sources.values():
        for classe in ast.walk(ast.parse(source)):
            if not isinstance(classe, ast.ClassDef):
                continue
            if not any(k.arg == "table" for k in classe.keywords):
                continue
            for ligne in classe.body:
                if (
                    isinstance(ligne, ast.AnnAssign)
                    and isinstance(ligne.target, ast.Name)
                    and ligne.target.id in NOMS_BOOLEENS_DE_DISPARITION
                    and ast.unparse(ligne.annotation).replace(" ", "") in ("bool", "Optional[bool]")
                ):
                    trouvees.add((classe.name, ligne.target.id))
    return trouvees


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


def _sources_des_modeles() -> dict[str, str]:
    return {m.rel: m.source for m in modules_app("models", minimum=20)}


def test_chaque_colonne_booleenne_de_disparition_est_dite():
    """Le contrôle : les colonnes réelles des modèles, confrontées aux deux listes."""
    ecarts = ecarts_de_declaration(
        colonnes_booleennes_de_disparition(_sources_des_modeles()),
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
    trouvees = colonnes_booleennes_de_disparition(_sources_des_modeles())
    couvertes = colonnes_couvertes_par_les_regles()
    assert len(trouvees) >= 10, f"le relevé ne trouve que {len(trouvees)} colonne(s)"
    assert couvertes, "REGLES ne couvre aucune colonne booléenne : le témoin ne sert pas"
    assert couvertes <= trouvees, f"vues de REGLES, pas du relevé : {sorted(couvertes - trouvees)}"


def test_le_controle_refuse_une_colonne_de_plus():
    """Le cas fautif : un booléen de plus non déclaré, une entrée périmée, un double compte."""
    reel = colonnes_booleennes_de_disparition(_sources_des_modeles())
    couvertes = colonnes_couvertes_par_les_regles()
    de_plus = reel | {("Neuf", "actif")}
    assert ecarts_de_declaration(de_plus, couvertes, REFERENTIELS) != []
    sans_la_colonne = reel - {("Perimetre", "actif")}
    assert ecarts_de_declaration(sans_la_colonne, couvertes, REFERENTIELS) != []
    double = dict(REFERENTIELS) | {next(iter(couvertes)): "dit deux fois"}
    assert ecarts_de_declaration(reel, couvertes, double) != []


def test_le_releve_lit_l_ast_pas_une_ligne_de_texte():
    """Une colonne coupée par le formateur est vue ; un schéma non-table ne l'est pas."""
    source = (
        "class Tableau(SQLModel, table=True):\n"
        "    actif: bool = Field(\n"
        "        default=True,\n"
        "    )\n"
        "    archivee: Optional[bool] = None\n"
        "    ordre: bool = True\n"
        "class Schema(BaseModel):\n"
        "    archivee: bool = False\n"
    )
    assert colonnes_booleennes_de_disparition({"x.py": source}) == {
        ("Tableau", "actif"),
        ("Tableau", "archivee"),
    }


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
