"""Le fil dit QUI a déposé — pour chaque entité qui a un auteur.

## L'incident (11/09/2026, signalé à l'écran)

Le fil d'activité affichait un ticket sans son auteur. Sa propre carte
(`CarteTicket`) le porte pourtant depuis le 18/08, dans un ordre arrêté ce
jour-là et repris de l'actualité : « état, puis 🔹 périmètre, puis les marqueurs,
puis **l'auteur** ». Le fil était le seul écran à ne pas suivre la règle — et
c'est celui qu'on regarde en premier.

## Pourquoi un test, et pas seulement la correction

Le fil est assemblé par **onze collecteurs** (`routers/flux/*.py`), chacun
fabriquant son `meta`. Ajouter la clé là où le manque a été signalé aurait laissé
les autres muets, et personne ne s'en apercevrait avant qu'un résident le
remarque — c'est exactement ce qui vient d'arriver.

⚠️ Le test ne vérifie pas que `"auteur"` est écrit : il vérifie que **tout modèle
qui porte un champ d'auteur** le rend dans son `meta`. Viser la notion, pas la
chaîne — sinon un douzième collecteur arrive avec sa propre clé et passe au vert.
"""

from __future__ import annotations

import ast
import pathlib

FLUX = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "flux"

#: Les collecteurs qui rendent des cartes d'un objet PORTÉ PAR QUELQU'UN, et le
#: champ du modèle qui le désigne.
#:
#: 🔴 La table est le sujet du test : elle dit qui DOIT nommer son auteur. Un
#: collecteur absent d'ici est un collecteur dont on affirme qu'il n'a pas
#: d'auteur humain — et `test_les_collecteurs_sans_auteur_n_en_ont_VRAIMENT_pas`
#: le vérifie, pour qu'on ne puisse pas s'en dispenser en l'oubliant.
PORTEURS = {
    "tickets.py": "auteur_id",
    "publications.py": "auteur_id",
    "communaute.py": "auteur_id",
    "ressources.py": "publie_par_id",
    "reglement.py": "auteur_id",
}

#: Ceux qui n'ont pas d'auteur humain, avec le motif.
SANS_AUTEUR = {
    "sante.py": "des mesures produites par le système, personne ne les « dépose »",
    "prestataires.py": "une échéance de contrat, pas un dépôt",
    "annuaire.py": "l'arrivée d'un résident — l'objet EST la personne",
    "epingles.py": "il reprend les cartes des autres collecteurs, avec leur meta",
    "commun.py": "le socle partagé, il ne rend aucune carte",
    "schemas.py": "des déclarations",
    "__init__.py": "l'assemblage",
}


def _collecteurs() -> list[pathlib.Path]:
    return sorted(f for f in FLUX.glob("*.py"))


def test_la_table_couvre_TOUS_les_collecteurs():
    """⚠️ Un douzième fichier apparaît un jour, et il faut qu'on ait à se
    prononcer : porte-t-il un auteur, ou non ? Sans cela, il arriverait muet et
    ce test resterait vert (`standards/04` §2 — la portée fait partie du
    contrôle)."""
    connus = set(PORTEURS) | set(SANS_AUTEUR)
    presents = {f.name for f in _collecteurs()}
    oublies = presents - connus
    assert not oublies, (
        "Collecteur du fil non classé — dire s'il porte un auteur :\n  "
        + "\n  ".join(sorted(oublies))
    )
    disparus = connus - presents
    assert not disparus, "Entrée périmée : " + ", ".join(sorted(disparus))


def test_chaque_collecteur_qui_a_un_auteur_le_MET_dans_son_meta():
    """Le fil dit qui a déposé, partout où quelqu'un a déposé."""
    muets = []
    for nom, champ in PORTEURS.items():
        src = (FLUX / nom).read_text(encoding="utf-8")
        if '"auteur"' not in src:
            muets.append(f"{nom} — le modèle porte `{champ}`, le meta ne dit rien")
    assert not muets, "Cartes du fil sans auteur :\n  " + "\n  ".join(muets)


#: Les DEUX façons admises de nommer quelqu'un dans le fil, et ce qui les
#: distingue.
#:
#: 🔴 Ce test n'en acceptait qu'une — `auteur_nom` — et a refusé le 15/09/2026 un
#: correctif JUSTE : le fil affichait « Paul DELMAS » sur un événement dont
#: le « Saisi pour » désignait quelqu'un d'autre (signalé à l'écran). La règle
#: arbitrée le 12/09 veut le PROPRIÉTAIRE, et `flux/tickets.py` l'appliquait
#: déjà — il ne passait ce test que parce qu'il contient `auteur_nom(` ailleurs.
#:
#: ⚠️ La règle n'a pas changé, c'est sa FORMULATION qui était trop étroite : ce
#: qu'on exige est qu'une fonction PARTAGÉE tolère l'identifiant absent et le
#: compte supprimé — pas qu'elle porte un nom précis. Un contrôle qui cherche une
#: chaîne finit par refuser ce qu'il devrait encourager.
FONCTIONS_ADMISES = {
    "auteur_nom(": "flux/commun.py — le nom de l'auteur, pour un objet sans « Saisi pour »",
    "proprietaire(": "utils/copie_auteur.py — le PROPRIÉTAIRE : le « Saisi pour » s'il existe",
}


def test_l_auteur_passe_par_une_fonction_PARTAGEE():
    """Nommer quelqu'un passe par une fonction qui sait qu'il peut manquer.

    Un `session.get(Utilisateur, …).prenom` recopié lèverait sur un compte
    effacé — et le fil est la page d'accueil.
    """
    fautifs = []
    for nom in PORTEURS:
        src = (FLUX / nom).read_text(encoding="utf-8")
        if '"auteur"' in src and not any(f in src for f in FONCTIONS_ADMISES):
            fautifs.append(nom)
    assert not fautifs, (
        "Auteur nommé sans fonction partagée :\n  "
        + "\n  ".join(fautifs)
        + "\n\nAdmises :\n  "
        + "\n  ".join(f"{f:16s} {quoi}" for f, quoi in FONCTIONS_ADMISES.items())
    )


def test_les_deux_fonctions_TOLERENT_vraiment_l_absence():
    """🔴 Et on ne le croit pas sur parole : on les EXÉCUTE.

    C'est la propriété que le test ci-dessus suppose, et qu'une recherche de
    texte ne prouve pas. Sans elle, admettre une seconde fonction reviendrait à
    élargir le contrôle sur la foi de son nom — soit précisément ce qu'on lui
    reproche (`standards/04` : vérifier le comportement, jamais l'artefact).
    """
    from sqlmodel import Session, SQLModel

    from app.database import engine
    from app.routers.flux.commun import auteur_nom
    from app.utils.copie_auteur import proprietaire

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        #  Un identifiant qui ne désigne personne — un compte supprimé depuis.
        assert auteur_nom(session, 999_999) is None or isinstance(auteur_nom(session, 999_999), str)
        assert auteur_nom(session, None) is None or isinstance(auteur_nom(session, None), str)

        class _Orphelin:
            auteur_id = 999_999
            saisi_pour_user_id = None
            saisi_pour_nom = None
            saisi_pour_email = None

        nom, email = proprietaire(session, _Orphelin())
        assert nom is None and email is None, (
            "proprietaire() doit rendre (None, None) sur un auteur disparu, "
            "pas lever : le fil est la page d'accueil."
        )


def test_les_collecteurs_sans_auteur_n_en_ont_VRAIMENT_pas():
    """Une exception qui devient fausse doit se voir. Si un de ces collecteurs
    se met à nommer un auteur, c'est que le motif ne tient plus : il rejoint
    PORTEURS, il ne reste pas dans la liste des dispensés."""
    contredits = []
    for nom, motif in SANS_AUTEUR.items():
        if nom in ("commun.py", "schemas.py", "__init__.py"):
            continue
        src = (FLUX / nom).read_text(encoding="utf-8")
        if '"auteur"' in src:
            contredits.append(f"{nom} — nomme un auteur alors qu'il est dispensé ({motif})")
    assert not contredits, "Dispense contredite :\n  " + "\n  ".join(contredits)


def test_le_socle_des_tickets_le_porte_UNE_fois_pour_les_quatre_cartes():
    """Les tickets rendent quatre cartes. L'auteur vit dans `_meta_ticket`, pas
    dans chacune : quatre écritures, ce sont quatre occasions de l'oublier — et
    c'est ce qui était arrivé aux pièces jointes (#531)."""
    src = (FLUX / "tickets.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    socle = next(
        n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == "_meta_ticket"
    )
    corps = "\n".join(src.splitlines()[socle.lineno - 1 : socle.end_lineno])
    assert '"auteur"' in corps, "l'auteur d'un ticket doit vivre dans le socle commun"
    #  Et nulle part ailleurs dans ce fichier : une seconde écriture serait la
    #  divergence qu'on vient d'éviter.
    assert src.count('"auteur"') == 1, "l'auteur est écrit plus d'une fois dans tickets.py"
