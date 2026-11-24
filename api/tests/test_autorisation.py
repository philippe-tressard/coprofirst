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

LA PORTÉE (#2911, audit du 23/11/2026) — le contrôle lisait le TEXTE de `app/routers/`,
`__init__.py` exclus : douze routes montées lui échappaient (le registre, l'installation
commune, la sonde de `main.py`, deux paquets de routeurs). Une route sans aucune
dépendance ajoutée là restait verte. Il lit désormais les routes MONTÉES
(`aides_sources.operations_montees`) et les dépendances que FastAPI leur résout
(`route.dependant`), reconnues par l'IDENTITÉ de l'objet de `deps.py`, pas par un nom.
Une exemption se nomme `(module relatif à app/, fonction)` : trois noms de fichier
sont portés par deux modules de routes.

Les règles LOCALES (dépendance ou refus écrit hors d'`auth/`) : `test_autorisation_regles_locales.py`.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

from fastapi.routing import APIRoute

from app.auth import deps
from app.main import app
from tests.aides_sources import module_app, operations_montees

_APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Cas zéro de la portée : l'application montait 456 opérations le 23/11/2026. Une
#: portée qui rétrécit (un montage perdu, un parcours qui ne descend plus dans les
#: routeurs inclus) fait échouer ce plancher avant de rendre un vert vide.
PLANCHER_OPERATIONS = 450


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
    #  La cloche seule : la session, ou le jeton d'une montre (#2771) —
    #  `test_jetons_montre.py` refuse qu'une autre route la prenne.
    "lecteur_de_la_cloche",
    #  L'écran de hall appairé (#2770) : son jeton, sa portée — `test_jetons_appareil.py`
    #  balaie toutes les routes et refuse qu'une route hors de la table le prenne.
    "ecran_appaire",
}

_VERBES = {"get", "post", "put", "patch", "delete"}

# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints VOLONTAIREMENT publics. Chaque entrée doit rester justifiable en une
#  phrase. Ajouter une ligne ici est une DÉCISION DE SÉCURITÉ : elle expose un
#  endpoint à Internet. Ne pas l'utiliser pour faire taire le test.
# ─────────────────────────────────────────────────────────────────────────────
_PUBLICS_ASSUMES = {
    # Pré-authentification : impossible d'exiger une session pour se connecter.
    ("routers/auth.py", "login"),
    ("routers/auth.py", "register"),
    ("routers/auth.py", "refresh"),
    ("routers/auth.py", "logout"),
    ("routers/auth.py", "verify_email"),
    ("routers/auth.py", "resend_verification"),
    #  Le bloc « mot de passe » a quitté `auth.py` le 14/08/2026 (modularité) : ces
    #  deux exemptions ont suivi le code, sans changer de nature. Qui a perdu son
    #  mot de passe ne peut pas prouver qui il est — c'est le jeton envoyé par
    #  courriel qui le fait, et sa vérification est dans l'endpoint lui-même.
    ("routers/auth_mot_de_passe.py", "request_password_reset"),
    ("routers/auth_mot_de_passe.py", "reset_password"),
    # Liste des bâtiments : alimente le formulaire d'inscription.
    ("routers/auth.py", "list_batiments"),
    #  Le manuel utilisateur en PDF (#651). Public, comme
    #  `/manuel-utilisateur.html` que le front sert déjà sans session : un manuel
    #  qui explique comment se servir du site doit pouvoir être lu AVANT de
    #  savoir s'en servir.
    #
    #  ⚠️ Et il ne contient aucune donnée — ni nom, ni adresse, ni contenu de la
    #  copropriété : seulement la description des écrans. C'est cela qui rend
    #  l'exemption tenable, pas le fait qu'elle soit commode. Le jour où ce
    #  document citerait un résident, cette ligne devrait tomber.
    ("routers/manuel.py", "manuel_pdf"),
    # Coquille d'interface et pages légales, filtrées par LISTE BLANCHE
    # (cf. `_PUBLIC_KEYS` dans routers/config.py) — vérifié plus bas.
    ("routers/config.py", "get_config"),
    #  Les pages légales, lisibles sans compte (LCEN) : le texte rendu de la
    #  copropriété servie ; leur source et leur relecture restent à l'admin (#2065).
    ("routers/textes_legaux.py", "textes_publics"),
    #  Le logo de la résidence (#1728) : il s'affiche AVANT toute connexion —
    #  écran de connexion, onglet du navigateur, icône de l'application
    #  installée, courriels. Une image, aucune donnée de résident, des tailles
    #  bornées (`utils/logo.TAILLE_MAX`) — tenu par `test_config_logo.py`.
    ("routers/config_logo.py", "servir_logo"),
    # Télémétrie par `sendBeacon`, visiteurs anonymes inclus. Elle rattache au
    # compte par `utilisateur_ou_anonyme` (auth/deps.py, #1595) sans jamais
    # refuser ; plafonnée par minute ET par jour, lot et champs bornés (#1597) —
    # tenu par `test_telemetrie_collecte_bornee.py`.
    ("routers/telemetry_collecte.py", "collect"),
    #  Le lien de validation du compte rendu d'un point CS / Syndic (#2042) : un
    #  membre du syndic n'a souvent pas de compte, le JETON envoyé à son adresse
    #  l'identifie (stocké par empreinte, un par présent, refait à chaque envoi).
    #  Lire n'engage rien (`standards/03` §5 bis) ; seuls le clic et le
    #  commentaire agissent. Débit plafonné, et le « Conseil seul » n'est jamais
    #  servi — tenu par `test_points_conseil_validation.py`.
    ("routers/points_conseil_validation.py", "lire_par_lien"),
    ("routers/points_conseil_validation.py", "valider_par_lien"),
    ("routers/points_conseil_validation.py", "commenter_par_lien"),
    #  L'appairage d'un écran de hall (#2770, RFC 8628) : l'écran n'a encore AUCUN
    #  jeton, c'est ce qu'il vient chercher. La demande ne rend que deux codes, rien de
    #  l'installation ; le jeton n'est rendu qu'après la confirmation par un membre du
    #  conseil CONNECTÉ (`POST /ecrans`, `require_cs_or_admin`), à qui détient le code
    #  d'appareil (256 bits). Débit plafonné, demandes en attente bornées — tenu par
    #  `test_ecrans.py`.
    ("routers/ecrans.py", "demander_appairage"),
    ("routers/ecrans.py", "interroger_appairage"),
    #  ── Hors de `app/routers/` (#2911) : la portée lisait ce seul dossier, et ces
    #  routes n'avaient d'exemption que dans la docstring de leur module. ──
    #  La sonde d'exploitation : quatre scripts des nœuds décident sur elle, sans
    #  compte. Un état et la version du contrat, rien de la copropriété.
    ("main.py", "health"),
    #  L'hôte commun d'une installation partagée (#2053) : AVANT toute connexion, le
    #  visiteur choisit sa copropriété. Un booléen sur l'hôte qu'il a lui-même demandé,
    #  une destination à partir d'un alias qu'il saisit (débit plafonné), et la garde
    #  des pages que Caddy consulte (204, 308 ou 421) — aucune donnée d'une copropriété.
    ("installation_commune/routeur.py", "hote_commun"),
    ("installation_commune/routeur.py", "aiguiller"),
    ("installation_commune/routeur.py", "garde_des_pages"),
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
    ("routers/admin/rapports_scripts.py", "maintenance_rapport"),
    ("routers/admin/rapports_scripts.py", "maintenance_dernier_rapport"),
    ("routers/admin/rapports_scripts.py", "emails_echecs_recents"),
    #  Les purges hebdomadaires, rapatriées de `maintenance.sh` (#1232).
    ("routers/admin/rapports_scripts.py", "maintenance_purges"),
    #  Le battement des contrôles de fiabilité (#1396) : une date, rien d'autre.
    ("routers/admin/rapports_scripts.py", "maintenance_battement"),
    #  La version cible du bail, que suit la mise à jour nocturne d'une réplique
    #  (R5 #1881) : un état et une version, rien de la copropriété.
    ("routers/admin/rapports_scripts.py", "maintenance_bail"),
    #  L'accusé de copie des archives d'affaires (#2014) : des noms et des empreintes.
    ("routers/admin/rapports_scripts.py", "maintenance_archives_affaires_copiees"),
}


# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints authentifiés par la **signature d'une installation** (#2911, #2953).
#
#  Une installation n'a pas de compte chez la référence : elle signe ses envois de
#  SA clé privée. Ce n'est ni une session ni un jeton d'appareil ; la porte est
#  `registre/gardes.exiger_signature`, et `test_signature_registre_source_unique.py`
#  vérifie que chaque route de `app/registre/` l'atteint. Ici, on vérifie que ces
#  routes-là sont TOUTES sous `app/registre/` — une route signée ailleurs échapperait
#  à ce contrôle.
# ─────────────────────────────────────────────────────────────────────────────
_AUTHENTIFIES_PAR_SIGNATURE = {
    ("registre/routeur.py", "inscrire"),
    ("registre/routeur.py", "renouveler_bail"),
    ("registre/routeur.py", "recevoir_rapport"),
    ("registre/relais.py", "relayer"),
}

_DISPENSES = _PUBLICS_ASSUMES | _AUTHENTIFIES_PAR_CLE | _AUTHENTIFIES_PAR_SIGNATURE

#: Le nom de la porte. Il est lu, pas supposé : le module d'authentification par
#: clé est `app/auth/cle_maintenance.py`, et la fonction s'y appelle ainsi.
_PORTE_PAR_CLE = "exiger_cle_maintenance"

#: Les dépendances reconnues, par OBJET : une fonction homonyme définie ailleurs
#: n'est pas une autorisation.
_RECONNUES = {getattr(deps, nom): nom for nom in _DEPS_AUTORISATION}


def _cle(route: APIRoute) -> tuple[str, str]:
    """`(module relatif à app/, fonction)` — slowapi enveloppe l'endpoint : on le déballe."""
    point = inspect.unwrap(route.endpoint)
    chemin = pathlib.Path(inspect.getsourcefile(point)).resolve()
    return chemin.relative_to(_APP_DIR).as_posix(), point.__name__


def _operations() -> list[tuple[str, str, tuple[str, str], set[str]]]:
    """(méthode, chemin, clé, dépendances d'autorisation prises) de chaque opération montée.

    Les dépendances sont celles que FastAPI résout pour la route — paramètres,
    `dependencies=` du décorateur ET du routeur inclus —, au premier niveau : une
    dépendance locale qui prendrait `get_current_user` en interne n'est pas reconnue.
    """
    operations = []
    for methode, chemin, route in operations_montees(app):
        if methode == "HEAD":
            continue
        assert isinstance(route, APIRoute), (
            f"{methode} {chemin} n'est pas une route d'API ({type(route).__name__}) : "
            "ce contrôle ne sait pas dire ce qui la garde — la déclarer ici, avec sa raison."
        )
        prises = {_RECONNUES[d.call] for d in route.dependant.dependencies if d.call in _RECONNUES}
        operations.append((methode, chemin, _cle(route), prises))
    assert len(operations) >= PLANCHER_OPERATIONS, (
        f"{len(operations)} opération(s) montée(s), plancher {PLANCHER_OPERATIONS} : "
        "la portée du contrôle a rétréci."
    )
    return operations


def test_tout_endpoint_porte_une_autorisation():
    """Aucune route MONTÉE sans autorisation, hors des TROIS catégories dispensées.

    Elles ne disent pas la même chose : `_PUBLICS_ASSUMES` expose à Internet,
    `_AUTHENTIFIES_PAR_CLE` et `_AUTHENTIFIES_PAR_SIGNATURE` authentifient autrement.
    Les avoir confondues jusqu'au 19/09/2026 coûtait un contrôle — une route déclarée
    publique reste verte quand on retire son authentification (#1028).
    """
    manquants = sorted(
        f"{module}::{fn} — {methode} {chemin}"
        for methode, chemin, (module, fn), prises in _operations()
        if not prises and (module, fn) not in _DISPENSES
    )
    assert not manquants, (
        "Endpoint(s) sans autorisation. Ajouter une dépendance de `app/auth/deps.py` "
        "(get_current_user, require_cs_or_admin, require_admin…). Si l'endpoint doit "
        "vraiment être public, l'inscrire dans `_PUBLICS_ASSUMES` AVEC sa "
        "justification — c'est une décision de sécurité :\n" + "\n".join(manquants)
    )


def test_chaque_route_a_cle_partagee_exige_VRAIMENT_la_cle():
    """🔴 Le faux vert que la catégorie des publiques laissait passer (#1028).

    Trois vérifications, parce que les deux premières seules se contournent : la
    route appelle la porte, elle reçoit l'en-tête qui porte la clé, et la porte
    existe toujours là où elle est censée vivre.
    """
    porte = module_app("auth/cle_maintenance.py")
    assert f"def {_PORTE_PAR_CLE}(" in porte.source, f"`{_PORTE_PAR_CLE}` a disparu de son module"

    manquantes = []
    for module, fonction in sorted(_AUTHENTIFIES_PAR_CLE):
        corps = {
            n.name: ast.unparse(n)
            for n in ast.walk(module_app(module).arbre)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert fonction in corps, f"`{fonction}` a disparu de {module}"
        if f"{_PORTE_PAR_CLE}(" not in corps[fonction]:
            manquantes.append(f"  {module}::{fonction} — n'appelle pas la porte")
        elif "x_maintenance_key" not in corps[fonction]:
            manquantes.append(f"  {module}::{fonction} — ne reçoit pas l'en-tête")
    assert not manquantes, "Ces routes sont ouvertes sans vérifier la clé partagée :\n" + "\n".join(
        manquantes
    )


def test_les_routes_signees_sont_celles_du_registre():
    """Une route « signée » hors de `app/registre/` échapperait au contrôle de la porte."""
    du_registre = {cle for _m, _c, cle, _p in _operations() if cle[0].startswith("registre/")}
    assert du_registre == _AUTHENTIFIES_PAR_SIGNATURE, (
        f"routes du registre non déclarées : {sorted(du_registre - _AUTHENTIFIES_PAR_SIGNATURE)} ; "
        f"déclarées mais absentes : {sorted(_AUTHENTIFIES_PAR_SIGNATURE - du_registre)}"
    )


def test_chaque_dependance_d_autorisation_est_prise_par_une_route():
    """Cas zéro de la liste ci-dessus (`standards/04` §2) : une dépendance
    reconnue qu'AUCUNE route ne prend est une promesse sans effet.

    🔴 Le défaut qu'il attrape (#1534, audit du 02/10/2026). `get_acting_user`
    figurait dans `_DEPS_AUTORISATION` et dans la table des dépendances de
    `CLAUDE.md` ; aucune route ne l'a jamais prise : l'aidant écrivait sous sa
    propre identité. Une dépendance qu'on retire de toutes les routes se retire
    donc aussi d'ici et de `deps.py`, et la documentation qui la promet avec elle.
    """
    prises = set().union(*(p for *_, p in _operations()))
    orphelines = sorted(_DEPS_AUTORISATION - prises)
    assert not orphelines, (
        "Dépendance(s) d'autorisation qu'aucune route ne prend — la règle qu'elles "
        "portent ne s'applique nulle part, et ce qui la promet (écran, manuel, "
        "`CLAUDE.md`) ment :\n" + "\n".join(f"  {d}" for d in orphelines)
    )


def test_aucune_dispense_obsolete():
    """Une dispense qui survit à la disparition ou à la protection de son endpoint
    devient un trou prêt à se rouvrir sous le même nom — vérifié dans les trois listes."""
    sans_autorisation = {cle for _m, _c, cle, prises in _operations() if not prises}
    obsoletes = sorted(_DISPENSES - sans_autorisation)
    assert not obsoletes, "Dispense(s) devenue(s) inutile(s) — à retirer :\n" + "\n".join(
        f"  {m} -> {fn}()" for m, fn in obsoletes
    )
