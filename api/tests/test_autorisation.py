"""Garde-fou préventif : aucun endpoint sans autorisation, aucun passe-droit.

L'exigence : **toutes** les règles de sécurité vivent dans `app/auth/deps.py`, et
tout endpoint y passe. Ce test échoue si un endpoint apparaît sans dépendance
d'autorisation, ou si un contrôle de rôle contourne le module central.

POURQUOI (audit du 26/07/2026) — l'exigence était respectée dans les grandes
lignes (276 endpoints, aucun contrôle sur `user.role`, tout via `has_role()`), mais
trois dérives s'étaient installées sans que rien ne les signale :

1. `GET /config` filtrait par liste NOIRE : toute clé de configuration non
   explicitement interdite était publiée **sans authentification**. 31 clés
   fuyaient, dont la configuration SMTP, l'URL interne du bridge WhatsApp et un
   lien d'invitation fonctionnel au groupe privé des résidents.
2. `bailleur.py` définissait `_require_bailleur`, doublon exact de
   `require_proprietaire`, hors du module central — 17 endpoints s'appuyaient
   dessus. Un durcissement de la règle centrale ne les aurait pas atteints.
3. Deux contrôles utilisaient des chaînes littérales (`has_role("admin")`) au lieu
   de l'enum `RoleUtilisateur`.

Aucune de ces dérives n'était détectable autrement qu'à la relecture. D'où ce test.
"""

import ast
import pathlib

from tests.aides_sources import modules_app

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_ROUTERS = _API_DIR / "app" / "routers"


def _fichiers_routers() -> list[pathlib.Path]:
    """Tous les modules de routers, **sous-paquets compris**.

    ⚠️ Cette fonction est la PORTÉE du contrôle, donc une partie du contrôle
    (`standards/05-tests-et-garde-fous.md` §9). Les quatre tests de ce fichier
    parcouraient `glob("*.py")`, sans récursion. Le jour où `admin.py` est devenu
    le paquet `admin/` (06/08/2026, 2057 lignes → 8 modules), ses **45 endpoints**
    sont sortis du champ d'un coup — et le test serait resté VERT en vérifiant
    simplement moins de choses. Un contrôle qui rétrécit sans le dire est pire
    qu'un contrôle absent : il continue de rassurer.

    C'est le test des endpoints orphelins qui a levé le lièvre, parce que sa liste
    d'exceptions est vérifiée dans les deux sens. Ce test-ci n'avait pas cette
    chance ; d'où le contrôle de couverture minimale ci-dessous.
    """
    #  Garde-fou du garde-fou : un glob cassé rendrait une liste vide, et tous les
    #  tests de ce fichier passeraient sans rien examiner — `minimum=25` lève alors.
    return [m.chemin for m in modules_app("routers", minimum=25)]


# Dépendances d'autorisation — TOUTES définies dans app/auth/deps.py.
#
# ⚠️ `ma_notification` en fait partie depuis le 18/09/2026, et elle a un statut
# à part : elle n'autorise pas un RÔLE, elle résout un OBJET dont elle vérifie
# l'appartenance (« une notification n'appartient qu'à son destinataire »).
# Elle porte donc `get_current_user` en interne — un endpoint qui la prend est
# authentifié ET filtré. C'est ce contrôle-ci qui a exigé qu'elle vive dans
# `deps.py` plutôt que dans son routeur : il ne reconnaît une autorisation qu'au
# module où elle est écrite, et c'est précisément le point (audit du 26/07/2026,
# `_require_bailleur` posé hors du module central avec 17 endpoints dessus).
#
# `get_acting_user` et `require_role` en sont sortis le 02/10/2026 (#1534) :
# aucune route ne les prenait, et le cas zéro plus bas le refuse désormais.
#
# `require_questions_reglement` (11/10/2026) prend `require_proprietaire` et y
# ajoute la case de l'administration qui ouvre l'usage aux copropriétaires : une
# règle de RÔLE et une de CONFIGURATION, écrites dans `deps.py` comme les autres.
_DEPS_AUTORISATION = {
    "get_current_user",
    "require_proprietaire",
    "require_questions_reglement",
    "require_cs_or_admin",
    "require_admin",
    #  L'opérateur de la plateforme (#1750) : supervision technique et base.
    "require_operateur",
    "ma_notification",
}

_VERBES = {"get", "post", "put", "patch", "delete"}

# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints VOLONTAIREMENT publics. Chaque entrée doit rester justifiable en une
#  phrase. Ajouter une ligne ici est une DÉCISION DE SÉCURITÉ : elle expose un
#  endpoint à Internet. Ne pas l'utiliser pour faire taire le test.
# ─────────────────────────────────────────────────────────────────────────────
_PUBLICS_ASSUMES = {
    # Pré-authentification : impossible d'exiger une session pour se connecter.
    ("auth.py", "login"),
    ("auth.py", "register"),
    ("auth.py", "refresh"),
    ("auth.py", "logout"),
    ("auth.py", "verify_email"),
    ("auth.py", "resend_verification"),
    #  Le bloc « mot de passe » a quitté `auth.py` le 14/08/2026 (modularité) : ces
    #  deux exemptions ont suivi le code, sans changer de nature. Qui a perdu son
    #  mot de passe ne peut pas prouver qui il est — c'est le jeton envoyé par
    #  courriel qui le fait, et sa vérification est dans l'endpoint lui-même.
    ("auth_mot_de_passe.py", "request_password_reset"),
    ("auth_mot_de_passe.py", "reset_password"),
    # Liste des bâtiments : alimente le formulaire d'inscription.
    ("auth.py", "list_batiments"),
    #  Le manuel utilisateur en PDF (#651). Public, comme
    #  `/manuel-utilisateur.html` que le front sert déjà sans session : un manuel
    #  qui explique comment se servir du site doit pouvoir être lu AVANT de
    #  savoir s'en servir.
    #
    #  ⚠️ Et il ne contient aucune donnée — ni nom, ni adresse, ni contenu de la
    #  copropriété : seulement la description des écrans. C'est cela qui rend
    #  l'exemption tenable, pas le fait qu'elle soit commode. Le jour où ce
    #  document citerait un résident, cette ligne devrait tomber.
    ("manuel.py", "manuel_pdf"),
    # Coquille d'interface et pages légales, filtrées par LISTE BLANCHE
    # (cf. `_PUBLIC_KEYS` dans routers/config.py) — vérifié plus bas.
    ("config.py", "get_config"),
    ("config.py", "get_legal_config"),
    #  Le logo de la résidence (#1728) : il s'affiche AVANT toute connexion —
    #  écran de connexion, onglet du navigateur, icône de l'application
    #  installée, courriels. Une image, aucune donnée de résident, des tailles
    #  bornées (`utils/logo.TAILLE_MAX`) — tenu par `test_config_logo.py`.
    ("config_logo.py", "servir_logo"),
    # Télémétrie par `sendBeacon`, visiteurs anonymes inclus. Elle rattache au
    # compte par `utilisateur_ou_anonyme` (auth/deps.py, #1595) sans jamais
    # refuser ; plafonnée par minute ET par jour, lot et champs bornés (#1597) —
    # tenu par `test_telemetrie_collecte_bornee.py`.
    ("telemetry_collecte.py", "collect"),
    #  Le lien de validation du compte rendu d'un point CS / Syndic (#2042) : un
    #  membre du syndic n'a souvent pas de compte, le JETON envoyé à son adresse
    #  l'identifie (stocké par empreinte, un par présent, refait à chaque envoi).
    #  Lire n'engage rien (`standards/03` §5 bis) ; seuls le clic et le
    #  commentaire agissent. Débit plafonné, et le « Conseil seul » n'est jamais
    #  servi — tenu par `test_points_conseil_validation.py`.
    ("points_conseil_validation.py", "lire_par_lien"),
    ("points_conseil_validation.py", "valider_par_lien"),
    ("points_conseil_validation.py", "commenter_par_lien"),
    #  🔴 Les quatre routes de `rapports_scripts.py` ONT QUITTÉ CETTE LISTE le
    #  19/09/2026 (#1028). Elles n'étaient pas publiques : elles sont
    #  authentifiées par une **clé partagée**, et les ranger ici en faisait un
    #  faux vert — une route déclarée « publique assumée » reste verte quand on
    #  retire son contrôle d'authentification.
    #
    #  Elles vivent maintenant dans `_AUTHENTIFIES_PAR_CLE`, et le test qui suit
    #  cette liste vérifie que chacune appelle bien `exiger_cle_maintenance`.
}


# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints authentifiés par **clé partagée**, et non par session (#1028).
#
#  🔴 Ce n'est pas la même chose qu'un endpoint public, et les confondre coûte un
#  contrôle : une route rangée parmi les publiques assumées reste verte si l'on
#  retire son authentification. Ces quatre-là y étaient.
#
#  Le canal n'autorise que les tâches planifiées des deux nœuds, qui lisent la
#  clé dans `/opt/5hostachy/.env`, et ne rend **aucune donnée de
#  copropriétaire** : dates d'exécution, comptes d'échecs par gabarit, noms de
#  tables. C'est cette portée qui rend le canal tenable — pas sa commodité.
# ─────────────────────────────────────────────────────────────────────────────
_AUTHENTIFIES_PAR_CLE = {
    ("rapports_scripts.py", "maintenance_rapport"),
    ("rapports_scripts.py", "maintenance_dernier_rapport"),
    ("rapports_scripts.py", "emails_echecs_recents"),
    #  Les purges hebdomadaires, rapatriées de `maintenance.sh` (#1232).
    ("rapports_scripts.py", "maintenance_purges"),
    #  Le battement des contrôles de fiabilité (#1396) : une date, rien d'autre.
    ("rapports_scripts.py", "maintenance_battement"),
    #  La version cible du bail, que suit la mise à jour nocturne d'une réplique
    #  (R5 #1881) : un état et une version, rien de la copropriété.
    ("rapports_scripts.py", "maintenance_bail"),
}

#: Le nom de la porte. Il est lu, pas supposé : le module d'authentification par
#: clé est `app/auth/cle_maintenance.py`, et la fonction s'y appelle ainsi.
_PORTE_PAR_CLE = "exiger_cle_maintenance"


def test_chaque_route_a_cle_partagee_exige_VRAIMENT_la_cle():
    """🔴 Le faux vert que la catégorie précédente laissait passer.

    Tant que ces routes étaient déclarées « publiques assumées », retirer leur
    appel à la fonction d'authentification ne faisait rougir aucun contrôle :
    elles devenaient réellement publiques, en silence, et le canal qu'elles
    ouvrent est celui des scripts d'exploitation.

    Le contrôle vérifie **trois** choses, parce que les deux premières seules se
    contournent : que la route appelle la porte, qu'elle reçoit bien l'en-tête
    qui porte la clé, et que la porte existe toujours là où elle est censée
    vivre.
    """
    import ast

    module_porte = _API_DIR / "app" / "auth" / "cle_maintenance.py"
    assert module_porte.exists(), (
        "app/auth/cle_maintenance.py a disparu : l'authentification par clé est "
        "revenue dans un routeur, là où aucun contrôle ne la raisonne comme une "
        "porte"
    )
    assert f"def {_PORTE_PAR_CLE}(" in module_porte.read_text(encoding="utf-8"), (
        f"`{_PORTE_PAR_CLE}` a disparu de son module"
    )

    manquantes = []
    for fichier, fonction in sorted(_AUTHENTIFIES_PAR_CLE):
        chemins = list((_API_DIR / "app" / "routers").rglob(fichier))
        assert chemins, f"{fichier} introuvable — le contrôle a perdu sa portée"
        corps = {
            n.name: ast.unparse(n)
            for n in ast.walk(ast.parse(chemins[0].read_text(encoding="utf-8")))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert fonction in corps, f"`{fonction}` a disparu de {fichier}"
        if f"{_PORTE_PAR_CLE}(" not in corps[fonction]:
            manquantes.append(f"  {fichier}::{fonction} — n'appelle pas la porte")
        elif "x_maintenance_key" not in corps[fonction]:
            manquantes.append(f"  {fichier}::{fonction} — ne reçoit pas l'en-tête")

    assert not manquantes, "Ces routes sont ouvertes sans vérifier la clé partagée :\n" + "\n".join(
        manquantes
    )


def _noms(node) -> set[str]:
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _endpoints():
    """Itère sur (fichier, ligne, verbe, chemin, nom_fonction, dependances_prises).

    `dependances_prises` est l'ensemble des dépendances d'autorisation que
    l'endpoint prend — vide (donc faux) s'il n'en prend aucune."""
    for f in _fichiers_routers():
        if f.name == "__init__.py":
            continue
        arbre = ast.parse(f.read_text(encoding="utf-8-sig"))
        for node in ast.walk(arbre):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            deco = next(
                (
                    d
                    for d in node.decorator_list
                    if isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Attribute)
                    and d.func.attr in _VERBES
                ),
                None,
            )
            if deco is None:
                continue
            chemin = (
                deco.args[0].value if deco.args and isinstance(deco.args[0], ast.Constant) else ""
            )
            prises = _deps_prises(deco, node)
            yield f.name, node.lineno, deco.func.attr.upper(), chemin, node.name, prises


def _deps_prises(deco, node) -> set[str]:
    """Les dépendances d'autorisation que prend un endpoint — par `dependencies=`
    du décorateur ou par les valeurs par défaut de ses paramètres."""
    defauts = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
    noms = set()
    for kw in deco.keywords:
        if kw.arg == "dependencies":
            noms |= _noms(kw.value)
    for d in defauts:
        noms |= _noms(d)
    return noms & _DEPS_AUTORISATION


def test_tout_endpoint_porte_une_autorisation():
    """Aucun endpoint sans autorisation, hors des DEUX catégories dispensées.

    Elles ne disent pas la même chose : `_PUBLICS_ASSUMES` expose à Internet,
    `_AUTHENTIFIES_PAR_CLE` authentifie autrement. Les avoir confondues jusqu'au
    19/09/2026 coûtait un contrôle — une route déclarée publique reste verte
    quand on retire son authentification (#1028).
    """
    manquants = [
        f"{fichier}:{ligne} {verbe} {chemin or '/'} -> {fn}()"
        for fichier, ligne, verbe, chemin, fn, ok in _endpoints()
        if not ok and (fichier, fn) not in _PUBLICS_ASSUMES | _AUTHENTIFIES_PAR_CLE
    ]
    assert not manquants, (
        "Endpoint(s) sans autorisation. Ajouter une dépendance de `app/auth/deps.py` "
        "(get_current_user, require_cs_or_admin, require_admin…). Si l'endpoint doit "
        "vraiment être public, l'inscrire dans `_PUBLICS_ASSUMES` AVEC sa "
        "justification — c'est une décision de sécurité :\n" + "\n".join(manquants)
    )


def test_chaque_dependance_d_autorisation_est_prise_par_une_route():
    """Cas zéro de la liste ci-dessus (`standards/04` §2) : une dépendance
    reconnue qu'AUCUNE route ne prend est une promesse sans effet.

    🔴 Le défaut qu'il attrape (#1534, audit du 02/10/2026). `get_acting_user`
    figurait dans `_DEPS_AUTORISATION` et dans la table des dépendances de
    `CLAUDE.md` — « délégation, en-tête `X-Acting-As` ». Le front posait bien
    l'en-tête, l'écran affichait « Vous agissez pour… », et aucune route n'a
    jamais pris la dépendance : l'aidant écrivait sous sa propre identité. Ce
    fichier vérifiait qu'une route prenait une dépendance de la liste, jamais
    que chaque dépendance de la liste servait — il aurait accepté la route qui
    la prenait, et n'a rien dit de son absence.

    Une dépendance qu'on retire de toutes les routes se retire donc aussi d'ici
    et de `deps.py`, et la documentation qui la promet avec elle.
    """
    prises = set().union(*(p for *_, p in _endpoints()))
    orphelines = sorted(_DEPS_AUTORISATION - prises)
    assert not orphelines, (
        "Dépendance(s) d'autorisation qu'aucune route ne prend — la règle qu'elles "
        "portent ne s'applique nulle part, et ce qui la promet (écran, manuel, "
        "`CLAUDE.md`) ment :\n" + "\n".join(f"  {d}" for d in orphelines)
    )


def test_pas_de_public_assume_obsolete():
    """`_PUBLICS_ASSUMES` ne doit pas conserver d'entrées périmées.

    Une exemption qui survit à la disparition ou à la protection de son endpoint
    devient un trou prêt à se rouvrir sous le même nom de fonction.
    """
    reels = {(fichier, fn) for fichier, _, _, _, fn, ok in _endpoints() if not ok}
    obsoletes = sorted(_PUBLICS_ASSUMES - reels)
    assert not obsoletes, (
        "Exemption(s) devenue(s) inutile(s) dans `_PUBLICS_ASSUMES` — à retirer :\n"
        + "\n".join(f"  {f} -> {fn}()" for f, fn in obsoletes)
    )


def test_aucune_dependance_d_autorisation_locale():
    """Les règles de sécurité vivent dans `app/auth/deps.py`, nulle part ailleurs.

    Attrape la dérive de `_require_bailleur` : un doublon local de
    `require_proprietaire`, invisible depuis le module central.
    """
    locales = []
    for f in _fichiers_routers():
        arbre = ast.parse(f.read_text(encoding="utf-8-sig"))
        for node in ast.walk(arbre):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.lstrip("_").startswith("require"):
                continue
            locales.append(f"{f.name}:{node.lineno} {node.name}()")
    assert not locales, (
        "Dépendance d'autorisation définie hors de `app/auth/deps.py` : la règle "
        "doit être centralisée, sinon un durcissement du module central ne "
        "l'atteindra pas.\n" + "\n".join(locales)
    )


def test_controles_de_role_via_l_enum():
    """`has_role()` doit recevoir l'enum `RoleUtilisateur`, pas des chaînes.

    Une chaîne échoue en silence sur une faute de frappe. Le comportement est
    heureusement fail-closed (accès refusé), mais la protection devient illisible
    et le renommage d'un rôle casse le contrôle sans erreur.
    """
    fautifs = []
    for f in _fichiers_routers() + sorted((_API_DIR / "app" / "utils").glob("*.py")):
        for num, ligne in enumerate(f.read_text(encoding="utf-8-sig").splitlines(), 1):
            if "has_role(" in ligne and '"' in ligne.split("has_role(", 1)[1][:60]:
                fautifs.append(f"{f.name}:{num}: {ligne.strip()}")
    assert not fautifs, (
        "Contrôle de rôle par chaîne littérale — utiliser `RoleUtilisateur.<role>` :\n"
        + "\n".join(fautifs)
    )


def test_config_publique_filtree_par_liste_blanche():
    """`GET /config` est public : son filtre doit être une liste BLANCHE.

    Une liste noire échoue en s'ouvrant — toute nouvelle clé de configuration
    devient publique par défaut. C'est ainsi que 31 clés ont fuité, dont la
    configuration SMTP et un lien d'invitation au groupe WhatsApp privé.
    """
    import re

    src = (_ROUTERS / "config.py").read_text(encoding="utf-8-sig")
    assert "_PUBLIC_KEYS" in src, "config.py doit définir une liste blanche `_PUBLIC_KEYS`"
    # On cherche une AFFECTATION en début de ligne, pas une mention : le commentaire
    # du module cite `_PRIVATE_KEYS` pour expliquer d'où venait la fuite.
    assert not re.search(r"^_PRIVATE_KEYS\s*=", src, re.MULTILINE), (
        "config.py contient encore une liste noire `_PRIVATE_KEYS` : "
        "le filtre doit être une liste blanche (fail-closed)"
    )
    # La liste blanche ne doit contenir aucune clé manifestement sensible.
    bloc = re.search(r"^_PUBLIC_KEYS\s*=\s*\{(.*?)\}", src, re.DOTALL | re.MULTILINE)
    assert bloc, "impossible de lire `_PUBLIC_KEYS`"
    contenu = bloc.group(1)
    for interdit in (
        "smtp",
        "api_key",
        "password",
        "secret",
        "token",
        "group_jid",
        "community_url",
        "manager_user_id",
    ):
        assert interdit not in contenu, (
            f"`_PUBLIC_KEYS` contient une clé sensible ('{interdit}') : "
            "cet endpoint est lisible sans authentification"
        )


def test_aucune_regle_de_visibilite_ne_vit_dans_un_router():
    """Les règles de visibilité vivent dans `app/utils/visibility.py`, et nulle part ailleurs.

    L'en-tête de ce module l'énonce depuis toujours : « Toute logique de filtrage par
    rôle/périmètre/profil doit passer par ce module. Ne jamais dupliquer ces règles
    dans les routers. » La règle documents, elle, était restée dans
    `routers/documents.py` sous le nom `_user_can_read`, et `flux.py` l'importait
    depuis ce router.

    Ce n'est pas un détail d'organisation : une règle hors du module central est une
    règle qu'un durcissement ultérieur peut manquer. C'est exactement ce qui est
    arrivé aux pièces jointes d'actualité — autorisées sans consulter l'actualité
    porteuse, donc téléchargeables par n'importe quel compte authentifié
    (cf. `test_documents_acces.py`), pendant que les trois chemins d'accès concernés
    partageaient la même fonction fautive et se confirmaient mutuellement.

    Deux interdits, donc : définir une règle de visibilité dans un router, et
    importer une règle depuis un router plutôt que depuis le module central.
    """
    import re

    central = _API_DIR / "app" / "utils" / "visibility.py"
    # Une règle de visibilité se reconnaît à son nom : `*_visible`, `*_accessible`,
    # `can_see_*`, ou l'ancien `_user_can_read`.
    motif_def = re.compile(
        r"^def\s+(\w*_visible|\w*_accessible|can_see_\w*|_user_can_read)\s*\(",
        re.MULTILINE,
    )
    # `from app.routers.x import ... visible/accessible/can_read ...`
    motif_import = re.compile(
        r"^from\s+app\.routers\.[\w.]+\s+import\s+[^\n]*"
        r"(?:_visible|_accessible|can_see|can_read)",
        re.MULTILINE,
    )

    egarees, imports_croises = [], []
    for f in _fichiers_routers():
        src = f.read_text(encoding="utf-8-sig")
        for m in motif_def.finditer(src):
            egarees.append(f"  {f.name} définit {m.group(1)}()")
        for m in motif_import.finditer(src):
            imports_croises.append(f"  {f.name} : {m.group(0).strip()}")

    assert not egarees, (
        "Règle(s) de visibilité définie(s) dans un router — à déplacer dans "
        f"{central.relative_to(_API_DIR.parent)} :\n" + "\n".join(egarees)
    )
    assert not imports_croises, (
        "Règle(s) de visibilité importée(s) depuis un router au lieu du module "
        "central — le jour où le router change, l'appelant ne le saura pas :\n"
        + "\n".join(imports_croises)
    )
