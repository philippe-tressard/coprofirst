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
   ici : un geste qui cesse d'exister fait échouer le test, plutôt que de laisser
   une exigence protéger une fonction disparue.
3. 🔴 **Aucune donnée personnelle dans le journal.** #777 a montré l'inverse :
   des adresses e-mail journalisées en clair sur échec d'envoi. Un journal de
   sécurité nomme un **identifiant**, jamais une adresse, jamais un mot de passe
   — sans quoi la trace devient elle-même la fuite (`standards/14`).

⚠️ Ces tests lisent l'arbre syntaxique, pas le texte : un appel réparti sur
plusieurs lignes ou renommé à l'import est vu pareil.
"""

import ast
from pathlib import Path

from tests.aides_sources import modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#: La fonction d'audit, et le module qui la porte.
MODULE = RACINE / "utils" / "journal_securite.py"
FONCTION = "journaliser_securite"

#: Les gestes qui DOIVENT laisser une trace : (fichier, fonction du routeur).
#: Une entrée dont la fonction a disparu fait échouer `test_les_gestes_declares_existent`.
GESTES_SENSIBLES = {
    ("routers/auth.py", "login"): "une connexion refusée — sans elle, une attaque "
    "par force brute est freinée par le rate limit mais jamais signalée",
    ("routers/auth_mot_de_passe.py", "change_password"): "un mot de passe changé par son porteur",
    ("routers/auth_mot_de_passe.py", "reset_password"): "un mot de passe réinitialisé "
    "par jeton — le chemin qu'emprunterait quelqu'un qui a pris la boîte mail",
    ("routers/admin/utilisateurs.py", "ajouter_role"): "une élévation de rôle : c'est "
    "le geste qui donne des droits, et rien ne nommait l'admin qui l'a fait",
    ("routers/admin/utilisateurs.py", "retirer_role"): "un retrait de rôle",
    ("routers/admin/utilisateurs.py", "ban_communaute"): "un bannissement",
    ("routers/auth.py", "refresh"): "un jeton de rafraîchissement rejoué — le seul "
    "signal d'un vol de session, et toutes les sessions du compte viennent de fermer",
    ("auth/appartenance.py", "exiger_lot_du_bailleur"): "un bail demandé sur le lot "
    "d'un autre — l'écran ne le propose pas, la requête a été forgée (#1535)",
    #  Le cycle de vie d'un compte (#1548, audit du 02/10/2026) : #1040 avait posé
    #  la porte, la liste s'arrêtait aux mots de passe et aux rôles.
    ("auth/appartenance.py", "exiger_lots_proposes_au_locataire"): "un locataire qui "
    "se dit locataire d'un lot qu'on ne lui proposait pas — requête forgée",
    ("utils/rattachement_locataire.py", "rattacher_lots_declares"): "un locataire "
    "rattaché sur sa seule déclaration : il reçoit les badges du lot",
    ("routers/admin/comptes.py", "traiter_compte"): "un compte validé ou refusé — "
    "le geste qui OUVRE l'accès, fait par le conseil syndical",
    ("routers/admin/utilisateurs.py", "modifier_utilisateur"): "un compte désactivé ou "
    "réactivé par l'administration",
    ("routers/admin/utilisateurs.py", "supprimer_utilisateur"): "un compte effacé "
    "définitivement — après lui, il ne reste QUE cette ligne pour dire qui l'a fait",
    ("routers/delegations.py", "create_delegation"): "une délégation créée : un "
    "tiers va lire au nom d'un résident",
    ("routers/delegations.py", "accepter_delegation"): "une délégation acceptée — "
    "c'est à cet instant que la lecture au nom d'autrui commence",
    ("routers/delegations.py", "revoquer_delegation"): "une délégation révoquée",
    ("utils/verification_adresse.py", "demander_changement_adresse"): "un changement "
    "d'adresse demandé, par le titulaire ou l'administrateur — le premier geste d'un "
    "détournement de compte, que rien ne traçait (#1549)",
    ("utils/verification_adresse.py", "_confirmer_changement"): "une nouvelle adresse "
    "confirmée : c'est désormais elle qui reçoit le mot de passe oublié (#1549)",
    #  La purge des comptes inactifs (#1580) : personne n'agit, le planificateur
    #  efface. Après lui, il ne reste QUE cette ligne pour dire qu'un compte a
    #  existé et pourquoi il n'est plus là.
    ("utils/purge_comptes/tache.py", "_supprimer"): "un compte effacé par la purge "
    "des comptes inactifs, sans acteur humain",
    ("utils/purge_comptes/tache.py", "_avertir"): "l'avertissement qui ouvre le délai "
    "de trente jours avant l'effacement",
}

#: Ce qui reconnaît un geste sur un compte dans un routeur — le relevé mécanique
#: que demande #1548 : la liste ci-dessus est tenue à la main, ce relevé dit ce
#: qu'elle oublie. Chaque signature nomme une ÉCRITURE, jamais une lecture :
#:   • `marquer_decide(...)` — la décision sur un compte (valider, refuser,
#:     désactiver) : `utils/comptes.py` la rend obligatoire pour les trois ;
#:   • `.ajouter_role(...)` / `.retirer_role(...)` — les droits ;
#:   • `purger(session, "utilisateur", ...)` ou `supprimer_compte(...)` —
#:     l'effacement d'un compte (la seconde porte la première depuis #1580) ;
#:   • `Delegation(...)` ou `.statut = StatutDelegation.…` — la lecture au nom
#:     d'autrui qui commence ou cesse.
APPELS_SIGNATURES = {
    "marquer_decide",
    "ajouter_role",
    "retirer_role",
    "Delegation",
    "supprimer_compte",
}


def _arbre(chemin: Path) -> ast.Module:
    return ast.parse(chemin.read_text(encoding="utf-8"))


def _fonction(arbre: ast.Module, nom: str):
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    return None


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
        fn_appelante = _fonction(_arbre(RACINE / fichier), fonction)
        if fn_appelante is None:
            continue
        for n in ast.walk(fn_appelante):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)):
                continue
            if n.func.id != FONCTION:
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
            if (
                nom == "purger"
                and len(n.args) >= 2
                and isinstance(n.args[1], ast.Constant)
                and n.args[1].value == "utilisateur"
            ):
                vues.add('purger("utilisateur")')
        if isinstance(n, ast.Assign) and "StatutDelegation." in ast.unparse(n.value):
            if any(isinstance(c, ast.Attribute) and c.attr == "statut" for c in n.targets):
                vues.add(".statut = StatutDelegation")
    return vues


def test_tout_geste_sur_un_compte_est_declare():
    """Le relevé mécanique (#1548) : la liste tenue à la main ne suffit pas.

    `GESTES_SENSIBLES` comptait huit gestes quand l'audit du 02/10/2026 en a
    trouvé six autres sans trace — valider, désactiver, supprimer un compte,
    créer, accepter, révoquer une délégation. Une liste qu'on complète quand on y
    pense oublie précisément ce à quoi on ne pensait pas : ce test la confronte
    à ce que les routeurs ÉCRIVENT.
    """
    declares = set(GESTES_SENSIBLES)
    vus, oublies = set(), []
    for module in modules_app("routers", minimum=20):
        for n in ast.walk(module.arbre):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            signatures = _signatures(n)
            if not signatures:
                continue
            vus.add((module.rel, n.name))
            if (module.rel, n.name) not in declares:
                oublies.append(f"app/{module.rel}::{n.name} — {sorted(signatures)}")
    #  Cas ZÉRO : un relevé qui ne trouve plus rien est un relevé cassé, pas un
    #  dépôt sain — les rôles, au moins, s'écrivent dans un routeur.
    assert ("routers/admin/utilisateurs.py", "ajouter_role") in vus, (
        "Le relevé ne reconnaît plus `ajouter_role` : ses signatures ne disent plus "
        "comment le code écrit un compte, et il ne garde plus rien."
    )
    assert not oublies, (
        "Ces fonctions écrivent un compte (droits, décision, effacement, délégation) "
        "sans figurer dans GESTES_SENSIBLES :\n"
        + "\n".join(f"  • {o}" for o in oublies)
        + "\n\nLes y déclarer — ce qui exigera l'appel à `journaliser_securite` —, "
        "ou retirer la signature ici en écrivant pourquoi ce n'est pas un geste sensible."
    )


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
        for n in ast.walk(module.arbre):
            if not (isinstance(n, ast.Call) and getattr(n.func, "id", None) == FONCTION):
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
