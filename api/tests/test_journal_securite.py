"""Ce qu'on ne journalise pas n'a pas eu lieu.

## Le constat (#1040, audit du 19/09/2026)

**Aucun événement de sécurité n'était journalisé**, et aucune fonction d'audit
n'existait : zéro `logger` dans `routers/auth.py`, `auth_mot_de_passe.py`,
`admin/utilisateurs.py`, `auth/deps.py`, `auth/jwt.py`.

Un compte compromis, une élévation de rôle ou une attaque par force brute — que
le rate limit freine sans la **signaler** — ne laissaient donc aucune trace
exploitable après coup. On peut constater qu'un mot de passe a changé ; on ne
pouvait pas savoir **qui** l'a changé, **quand**, ni combien de tentatives
avaient précédé.

Seuls journaux de sécurité existants : les refus de téléversement et les
violations CSP (leur collecte a été retirée le 01/10/2026).

## Ce que ces tests verrouillent

1. La fonction d'audit existe, elle est **unique**, et elle porte les trois
   champs qui rendent une ligne exploitable : quoi, qui, sur qui.
2. Chaque geste sensible l'appelle — connexion refusée, mot de passe changé ou
   réinitialisé, rôle ajouté ou retiré, bannissement. La liste est **déclarée**
   (`aides_gestes_sensibles.GESTES_SENSIBLES`, avec sa raison) et **dérivée** de
   ce que le code émet (#2941) : toute fonction de `app/` qui appelle le journal y
   figure, toute entrée l'appelle. Un geste qui cesse d'exister fait échouer le
   test, plutôt que de laisser une exigence protéger une fonction disparue.
3. 🔴 **Aucune donnée personnelle dans le journal.** #777 a montré l'inverse :
   des adresses e-mail journalisées en clair sur échec d'envoi. Un journal de
   sécurité nomme un **identifiant**, jamais une adresse, jamais un mot de passe
   — sans quoi la trace devient elle-même la fuite (`standards/14`).

⚠️ Ces tests lisent l'arbre syntaxique, pas le texte : un appel réparti sur
plusieurs lignes ou renommé à l'import est vu pareil.
"""

import ast
from pathlib import Path

from tests.aides_gestes_sensibles import GESTES_SENSIBLES
from tests.aides_sources import Module, modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#: La fonction d'audit, et le module qui la porte.
MODULE = RACINE / "utils" / "journal_securite.py"
FONCTION = "journaliser_securite"

#: Le module qui porte la fonction, relatif à `app/` — hors du relevé des émettrices.
MODULE_REL = MODULE.relative_to(RACINE).as_posix()

#: Ce qui reconnaît un geste sur un compte, partout dans `app/` — le relevé
#: mécanique que demande #1548, étendu des routeurs à tout `app/` par #2941 :
#: `GESTES_SENSIBLES` dit ce qui émet, ce relevé dit ce qui ÉCRIT un compte sans
#: émettre. Chaque signature nomme une ÉCRITURE, jamais une lecture :
#:   • `marquer_decide(...)` — la décision sur un compte (valider, refuser,
#:     désactiver) : `utils/comptes.py` la rend obligatoire pour les trois ;
#:   • `.ajouter_role(...)` / `.retirer_role(...)` / `poser_roles_du_statut(...)`
#:     ou `roles_json` écrit (affecté, ou passé à un constructeur) — les droits ;
#:   • `purger(session, "utilisateur", ...)` ou `supprimer_compte(...)` —
#:     l'effacement d'un compte (la seconde porte la première depuis #1580) ;
#:   • `Delegation(...)` ou `.statut = StatutDelegation.…` — la lecture au nom
#:     d'autrui qui commence ou cesse.
APPELS_SIGNATURES = {
    "marquer_decide",
    "ajouter_role",
    "retirer_role",
    "poser_roles_du_statut",
    "Delegation",
    "supprimer_compte",
}

#: Les PORTES : les primitives qui écrivent un compte sans juger du geste — c'est
#: leur appelant qui sait qui agit, et qui journalise. Une porte n'est admise que
#: si son nom est une signature : chacun de ses appelants est alors relevé à son
#: tour, et doit être déclaré (`test_les_portes_et_les_exceptions_servent`).
PORTES_D_ECRITURE = {
    ("models/core.py", "ajouter_role"): "la méthode du modèle : le routeur qui l'appelle "
    "journalise `role_ajoute`",
    ("models/core.py", "retirer_role"): "la méthode du modèle : le routeur qui l'appelle "
    "journalise `role_retire`",
    ("utils/roles_du_statut.py", "poser_roles_du_statut"): "la règle des rôles du statut "
    "— `changer_statut` journalise chaque rôle qui change ; l'inscription est déclarée plus bas",
    ("utils/suppression_compte.py", "supprimer_compte"): "l'effacement par `purger` — "
    "ses appelants (administration, demande, purge) journalisent qui l'a voulu",
}

#: Les écritures sur un compte qui ne laissent pas de ligne, et pourquoi.
ECRITURES_SANS_LIGNE = {
    ("routers/auth.py", "register"): "l'inscription pose les rôles du statut sur un "
    "compte créé INACTIF : ils n'ouvrent rien avant la validation, que `traiter_compte` "
    "journalise (`compte_valide`)",
    ("demo/comptes.py", "_compte"): "les comptes FICTIFS de la démonstration, posés à sa "
    "création : aucune personne derrière eux, aucun geste à relire",
    ("seed/__init__.py", "_compte_technique"): "l'administrateur et l'opérateur initiaux "
    "d'une installation neuve, posés par le seed avant tout utilisateur",
}


def _arbre(chemin: Path) -> ast.Module:
    return ast.parse(chemin.read_text(encoding="utf-8"))


def _fonction(arbre: ast.Module, nom: str):
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    return None


def _noms_du_journal(arbre: ast.Module) -> set[str]:
    """`journaliser_securite` et les alias sous lesquels ce module l'importe."""
    noms = {FONCTION}
    for n in ast.walk(arbre):
        if isinstance(n, ast.ImportFrom):
            noms |= {a.asname for a in n.names if a.name == FONCTION and a.asname}
    return noms


def _appelle_le_journal(n: ast.AST, noms: set[str]) -> bool:
    """Un appel direct (`journaliser_securite(…)`, alias compris) ou par le module."""
    if not isinstance(n, ast.Call):
        return False
    f = n.func
    return (isinstance(f, ast.Name) and f.id in noms) or (
        isinstance(f, ast.Attribute) and f.attr == FONCTION
    )


def emettrices(modules) -> set[tuple[str, str]]:
    """Chaque `(module, fonction)` de ces modules qui écrit au journal de sécurité.

    L'appel revient à la fonction qui l'ENGLOBE au plus près : une fonction
    imbriquée est une émettrice à son nom. Un appel hors de toute fonction est
    rendu sous `<module>` — aucune entrée ne peut le déclarer, il échoue donc.
    Le module qui DÉFINIT la fonction n'est pas lu.
    """
    trouvees: set[tuple[str, str]] = set()
    for module in modules:
        if module.rel == MODULE_REL:
            continue
        noms = _noms_du_journal(module.arbre)

        def visiter(noeud: ast.AST, englobante: str) -> None:
            for enfant in ast.iter_child_nodes(noeud):
                if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    visiter(enfant, enfant.name)
                    continue
                if _appelle_le_journal(enfant, noms):
                    trouvees.add((module.rel, englobante))
                visiter(enfant, englobante)

        visiter(module.arbre, "<module>")
    return trouvees


def ecarts_aux_gestes_declares(emises: set, declares: set) -> tuple[list, list]:
    """`(émettrices non déclarées, gestes déclarés qui n'émettent pas)`, triés."""
    return sorted(emises - declares), sorted(declares - emises)


def test_la_fonction_d_audit_existe_et_porte_ce_qu_il_faut():
    """Quoi, qui, sur qui — une ligne sans ces trois champs ne sert à rien.

    Le cas ZÉRO de tous les autres tests : s'ils cherchaient un appel à une
    fonction disparue, ils échoueraient en nommant les appelants, et on
    corrigerait les appelants. C'est la fonction qu'il faut regarder d'abord.
    """
    assert MODULE.exists(), (
        f"{MODULE.relative_to(RACINE.parent)} a disparu : les gestes sensibles "
        f"n'ont plus où écrire."
    )
    fn = _fonction(_arbre(MODULE), FONCTION)
    assert fn is not None, f"`{FONCTION}` a disparu de {MODULE.name}"

    params = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
    for attendu in ("evenement", "acteur_id", "cible_id"):
        assert attendu in params, (
            f"`{FONCTION}` ne prend plus `{attendu}` : une ligne de journal qui ne dit "
            f"pas QUOI, QUI et SUR QUI ne permet de reconstituer aucun enchaînement."
        )


def test_chaque_geste_sensible_laisse_une_trace():
    """La liste est déclarée, et elle est vérifiée dans les deux sens."""
    manquants = []
    for (fichier, fonction), pourquoi in GESTES_SENSIBLES.items():
        chemin = RACINE / fichier
        fn = _fonction(_arbre(chemin), fonction)
        if fn is None:
            continue  # vu par le test suivant
        appels = {
            n.func.id
            for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        if FONCTION not in appels:
            manquants.append(f"app/{fichier}::{fonction} — {pourquoi}")
    assert not manquants, (
        f"Ces gestes ne laissent aucune trace ({FONCTION} n'y est pas appelé) :\n"
        + "\n".join(f"  • {m}" for m in manquants)
        + "\n\nCe qu'on ne journalise pas n'a pas eu lieu (`standards/07` §1)."
    )


def test_les_gestes_declares_existent():
    """Une exigence qui protège une fonction disparue protège un souvenir."""
    perimes = []
    for fichier, fonction in GESTES_SENSIBLES:
        chemin = RACINE / fichier
        if not chemin.exists() or _fonction(_arbre(chemin), fonction) is None:
            perimes.append(f"app/{fichier}::{fonction}")
    assert not perimes, (
        f"GESTES_SENSIBLES cite {perimes}, qui n'existe(nt) plus : renommer l'entrée "
        f"ou la retirer, sinon la liste garde une porte qui n'est plus là."
    )


def test_les_emettrices_sont_exactement_les_gestes_declares():
    """La liste se DÉRIVE de ce que le code émet (#2941), dans les deux sens.

    Tenue à la main, elle comptait 24 entrées quand 41 fonctions émettaient :
    retirer l'appel de `routers/montres.py` ou de `routers/ecrans.py` laissait
    tous les tests verts. Toute émettrice est déclarée avec sa raison ; toute
    entrée émet encore.
    """
    emises = emettrices(modules_app())
    #  Cas ZÉRO : un relevé qui ne voit plus la connexion ne voit plus rien.
    assert ("routers/auth.py", "login") in emises, (
        f"le relevé ne voit plus `{FONCTION}` dans `routers/auth.py::login` : il est cassé"
    )
    hors_liste, muettes = ecarts_aux_gestes_declares(emises, set(GESTES_SENSIBLES))
    assert not hors_liste, (
        f"Ces fonctions appellent `{FONCTION}` sans figurer dans GESTES_SENSIBLES "
        "(`tests/aides_gestes_sensibles.py`) :\n"
        + "\n".join(f"  • app/{f}::{fn}" for f, fn in hors_liste)
        + "\n\nLes y déclarer, avec ce que la ligne permet de savoir après coup."
    )
    assert not muettes, (
        f"Ces gestes déclarés n'appellent plus `{FONCTION}` :\n"
        + "\n".join(f"  • app/{f}::{fn} — {GESTES_SENSIBLES[(f, fn)]}" for f, fn in muettes)
        + "\n\nCe qu'on ne journalise pas n'a pas eu lieu : rendre l'appel, ou retirer "
        "l'entrée en écrivant pourquoi le geste n'est plus sensible."
    )


def test_le_releve_des_emettrices_sait_refuser():
    """Le témoin : une émettrice FORGÉE, non déclarée, est vue et refusée.

    Alias d'import, appel par le module, fonction imbriquée, appel hors fonction :
    les formes qu'un relevé naïf (`ast.Name` seul, `ast.walk` de la fonction
    externe) laisserait passer ou attribuerait à la mauvaise fonction.
    """
    source = (
        "from app.utils.journal_securite import journaliser_securite as noter\n"
        "import app.utils.journal_securite as journal\n"
        "def geste():\n"
        "    noter('role_ajoute')\n"
        "def lecture():\n"
        "    return 1\n"
        "def externe():\n"
        "    def interne():\n"
        "        journal.journaliser_securite('role_retire')\n"
        "    return interne\n"
        "journal.journaliser_securite('ban_communaute')\n"
    )
    forge = Module(RACINE / "utils" / "forge.py", "utils/forge.py", source)
    emises = emettrices([forge])
    assert emises == {
        ("utils/forge.py", "geste"),
        ("utils/forge.py", "interne"),
        ("utils/forge.py", "<module>"),
    }
    declares = set(GESTES_SENSIBLES) | {("utils/forge.py", "lecture")}
    hors_liste, muettes = ecarts_aux_gestes_declares(emises, declares)
    assert hors_liste == sorted(emises), "une émettrice forgée non déclarée doit être refusée"
    assert ("utils/forge.py", "lecture") in muettes, "une entrée qui n'émet pas doit l'être aussi"


def test_le_journal_ne_porte_aucune_donnee_personnelle():
    """🔴 La trace ne doit pas devenir la fuite.

    #777 a montré le défaut inverse — des adresses e-mail journalisées en clair
    sur échec d'envoi. Un journal de sécurité nomme un identifiant ; l'adresse,
    le mot de passe et le jeton restent dehors, y compris tronqués : un condensé
    partiel d'adresse reste une donnée personnelle (`standards/14`).
    """
    source = MODULE.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    fn = _fonction(arbre, FONCTION)
    assert fn is not None

    corps = ast.unparse(fn)
    for interdit in ("email", "mot_de_passe", "password", "token", "jeton"):
        assert interdit not in corps, (
            f"`{FONCTION}` manipule `{interdit}` : un journal de sécurité nomme un "
            f"IDENTIFIANT, jamais une adresse, un mot de passe ou un jeton — sinon la "
            f"trace devient la fuite (#777)."
        )

    #: Et les appelants ne lui passent pas non plus une adresse.
    fautes = []
    for fichier, fonction in GESTES_SENSIBLES:
        arbre = _arbre(RACINE / fichier)
        fn_appelante = _fonction(arbre, fonction)
        if fn_appelante is None:
            continue
        noms = _noms_du_journal(arbre)
        for n in ast.walk(fn_appelante):
            if not _appelle_le_journal(n, noms):
                continue
            #  ⚠️ Les littéraux sont EXCLUS, et ce n'est pas une tolérance : le nom
            #  de l'événement est `"mot_de_passe_change"`, et ce contrôle le
            #  refusait — il confondait le NOM de la chose avec la chose. Ce qui
            #  fuite est une VALEUR : une variable, un attribut, une f-string.
            valeurs = [
                a
                for a in list(n.args) + [k.value for k in n.keywords]
                if not (isinstance(a, ast.Constant) and isinstance(a.value, str))
            ]
            for valeur in valeurs:
                texte = ast.unparse(valeur)
                if any(x in texte for x in ("email", "password", "mot_de_passe", "token")):
                    fautes.append(f"app/{fichier}::{fonction} — {texte[:90]}")
    assert not fautes, "Une adresse ou un mot de passe est passé au journal :\n" + "\n".join(fautes)


def _signatures(fn) -> set[str]:
    """Les gestes sur un compte que cette fonction écrit (voir `APPELS_SIGNATURES`)."""
    vues = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            nom = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            if nom in APPELS_SIGNATURES:
                vues.add(nom)
            if any(k.arg == "roles_json" for k in n.keywords):
                vues.add("roles_json=")
            if (
                nom == "purger"
                and len(n.args) >= 2
                and isinstance(n.args[1], ast.Constant)
                and n.args[1].value == "utilisateur"
            ):
                vues.add('purger("utilisateur")')
        if isinstance(n, ast.Assign) and any(
            isinstance(c, ast.Attribute) and c.attr == "roles_json" for c in n.targets
        ):
            vues.add(".roles_json =")
        if isinstance(n, ast.Assign) and "StatutDelegation." in ast.unparse(n.value):
            if any(isinstance(c, ast.Attribute) and c.attr == "statut" for c in n.targets):
                vues.add(".statut = StatutDelegation")
    return vues


def _ecritures_sur_un_compte() -> dict[tuple[str, str], set[str]]:
    """Chaque fonction de `app/` qui écrit un compte, avec ses signatures."""
    vues = {}
    for module in modules_app():
        for n in ast.walk(module.arbre):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if signatures := _signatures(n):
                    vues[(module.rel, n.name)] = signatures
    return vues


def test_tout_geste_sur_un_compte_est_declare():
    """Le relevé mécanique (#1548) : la liste tenue à la main ne suffit pas.

    `GESTES_SENSIBLES` comptait huit gestes quand l'audit du 02/10/2026 en a
    trouvé six autres sans trace — valider, désactiver, supprimer un compte,
    créer, accepter, révoquer une délégation. Une liste qu'on complète quand on y
    pense oublie précisément ce à quoi on ne pensait pas : ce test la confronte
    à ce que le code ÉCRIT — dans tout `app/` depuis #2941, et plus seulement
    dans les routeurs : la suppression demandée et la purge vivent dans `utils/`.
    """
    declares = set(GESTES_SENSIBLES) | set(PORTES_D_ECRITURE) | set(ECRITURES_SANS_LIGNE)
    vus = _ecritures_sur_un_compte()
    oublies = [
        f"app/{rel}::{nom} — {sorted(signatures)}"
        for (rel, nom), signatures in sorted(vus.items())
        if (rel, nom) not in declares
    ]
    #  Cas ZÉRO : un relevé qui ne trouve plus rien est un relevé cassé, pas un
    #  dépôt sain — les rôles s'écrivent dans un routeur, l'effacement demandé
    #  dans `utils/`.
    for attendu in (
        ("routers/admin/utilisateurs.py", "ajouter_role"),
        ("utils/demande_suppression.py", "traiter"),
    ):
        assert attendu in vus, (
            f"Le relevé ne reconnaît plus app/{attendu[0]}::{attendu[1]} : ses signatures "
            "ne disent plus comment le code écrit un compte, ou sa portée a rétréci."
        )
    assert not oublies, (
        "Ces fonctions écrivent un compte (droits, décision, effacement, délégation) "
        "sans figurer dans GESTES_SENSIBLES :\n"
        + "\n".join(f"  • {o}" for o in oublies)
        + "\n\nLes y déclarer — ce qui exigera l'appel à `journaliser_securite` —, "
        "ou, avec la raison : dans PORTES_D_ECRITURE si c'est une primitive dont "
        "l'appelant journalise, dans ECRITURES_SANS_LIGNE si le geste n'a rien à relire."
    )


def test_les_portes_et_les_exceptions_servent():
    """Les deux listes d'écarts se vérifient dans l'autre sens (#2941).

    Une porte ou une exception que le relevé ne voit plus protège un souvenir ;
    une porte dont le nom n'est pas une signature laisserait ses appelants hors
    du relevé ; une exception qui émet n'en est pas une.
    """
    vus = _ecritures_sur_un_compte()
    perimees = [
        f"app/{rel}::{nom}"
        for rel, nom in sorted({*PORTES_D_ECRITURE, *ECRITURES_SANS_LIGNE})
        if (rel, nom) not in vus
    ]
    assert not perimees, f"Portes ou exceptions qui n'écrivent plus de compte : {perimees}"
    hors_signatures = sorted(nom for _, nom in PORTES_D_ECRITURE if nom not in APPELS_SIGNATURES)
    assert not hors_signatures, (
        f"Portes dont le nom n'est pas dans APPELS_SIGNATURES : {hors_signatures} — "
        "leurs appelants échapperaient au relevé."
    )
    doubles = sorted(set(ECRITURES_SANS_LIGNE) & set(GESTES_SENSIBLES))
    assert not doubles, f"Déclarées sans ligne ET émettrices : {doubles}"


def test_chaque_evenement_journalise_est_declare():
    """Un code absent de `_NIVEAUX` part en WARNING par défaut, sans un mot.

    La fonction ne refuse pas une clé inconnue — le journal ne doit jamais casser
    la requête qu'il observe. C'est donc ici que la faute de frappe se voit : un
    `"compte_valider"` pour `"compte_valide"` serait un geste tracé sous un nom
    que personne ne cherchera.
    """
    from app.utils.journal_securite import _NIVEAUX

    appels, inconnus = 0, []
    for module in modules_app():
        noms = _noms_du_journal(module.arbre)
        for n in ast.walk(module.arbre):
            if not _appelle_le_journal(n, noms):
                continue
            appels += 1
            premier = n.args[0] if n.args else None
            #  Un choix entre deux codes (`"compte_valide" if … else "compte_refuse"`)
            #  reste lisible : chaque branche doit être un littéral déclaré.
            if isinstance(premier, ast.IfExp):
                feuilles = [premier.body, premier.orelse]
            else:
                feuilles = [premier]
            ou = f"app/{module.rel}:{n.lineno}"
            for f in feuilles:
                if not (isinstance(f, ast.Constant) and isinstance(f.value, str)):
                    inconnus.append(f"{ou} — code non littéral")
                elif f.value not in _NIVEAUX:
                    inconnus.append(f"{ou} — {f.value!r}")
    #  Cas ZÉRO : un relevé qui ne voit aucun appel ne vérifie aucun code.
    assert appels, f"aucun appel à `{FONCTION}` trouvé dans app/ : le relevé ne voit plus rien"
    assert not inconnus, "Codes d'événement absents de `_NIVEAUX` :\n" + "\n".join(inconnus)
