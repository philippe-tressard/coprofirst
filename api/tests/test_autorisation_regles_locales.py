"""Aucune règle d'autorisation LOCALE : ni dépendance, ni refus écrit hors d'`app/auth/`.

Venu de `test_autorisation.py` (#2911, modularité) : celui-là dit que chaque route MONTÉE
est gardée ; celui-ci, que ce qui la garde vit au module central.

## Les refus hors d'`auth/` (#2942, audit du 23/11/2026)

Le contrôle ne lisait que les noms en `require*`, dans `app/routers/` : trois
`_exiger_conseil` (une synthèse, des affaires liées, une fusion) et un quatrième refus
recopié dans `utils/fusion_affaires` levaient 403 sur `not est_moderateur(…)` sans que
rien ne les voie. Les quatre appellent désormais `deps.exiger_moderateur`. Toute
fonction de `app/` qui lève 401 ou 403 hors d'`auth/` et d'`utils/visibility/` est
DÉCLARÉE ci-dessous avec la règle centrale qu'elle appelle, et la liste se vérifie dans
les deux sens.
"""

import ast
import pathlib

from tests.aides_sources import PLANCHER_APP, modules_app

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_ROUTERS = _API_DIR / "app" / "routers"
_VERBES = {"get", "post", "put", "patch", "delete"}


def _fichiers_routers() -> list[pathlib.Path]:
    """Tous les modules de routers, sous-paquets compris — `minimum=25` lève sur une
    portée vide (le paquet `admin/` en était sorti d'un coup le 06/08/2026)."""
    return [m.chemin for m in modules_app("routers", minimum=25)]


#: Les fonctions de `app/` qui REFUSENT (401, 403) hors d'`auth/` et d'`utils/visibility/`,
#: et la raison pour laquelle le refus y est tenable. Chacune appelle la règle centrale
#: qui dit « qui » — elle n'ajoute que le message ; une règle de qui redérivée ici serait
#: une copie. Vérifiée dans les deux sens : une entrée qui ne refuse plus échoue.
REFUS_DECLARES = {
    ("registre/gardes.py", "exiger_signature"): "la signature d'une INSTALLATION — pas un "
    "compte ; la porte du registre (#2953)",
    ("registre/relais.py", "_bail_admis"): "le bail d'une installation, cru par "
    "`inscription/constat` — pas un compte",
    ("routers/avis.py", "_exiger_gestionnaire"): "appelle `est_gestionnaire_du_site`, le "
    "prédicat de la télémétrie ; n'ajoute que le message",
    ("routers/tickets/messages.py", "_message_de_l_auteur"): "appelle `est_auteur` (auth/deps.py)",
    ("utils/communaute.py", "exiger_acces"): "appelle `motif_de_refus` du même module — "
    "l'ouverture de la communauté (dates, profil), une règle de CONFIGURATION",
    ("utils/demo.py", "refuser_fichier_recu"): "l'instance de DÉMONSTRATION ferme un "
    "geste à tous ; aucun compte n'est jugé",
    ("utils/evolutions.py", "evolution_modifiable"): "appelle `peut_editer` (auth/deps.py)",
    ("utils/suivi_actualite.py", "refuser_etat"): "reçoit `est_cs` de la route, qui "
    "l'a lu sur `est_moderateur`",
}


def _code_refuse(appel: ast.Call):
    valeurs = [*appel.args[:1], *[k.value for k in appel.keywords if k.arg == "status_code"]]
    for v in valeurs:
        if isinstance(v, ast.Constant) and v.value in (401, 403):
            return v.value
        if isinstance(v, ast.Attribute) and v.attr in (
            "HTTP_401_UNAUTHORIZED",
            "HTTP_403_FORBIDDEN",
        ):
            return v.attr
    return None


def _propres(fonction):
    """Les nœuds d'une fonction, sans descendre dans les fonctions qu'elle définit."""
    a_voir = list(ast.iter_child_nodes(fonction))
    while a_voir:
        noeud = a_voir.pop()
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield noeud
        a_voir.extend(ast.iter_child_nodes(noeud))


def _est_route(fonction) -> bool:
    return any(
        isinstance(d, ast.Call) and getattr(d.func, "attr", None) in _VERBES
        for d in fonction.decorator_list
    )


def refus_hors_d_auth(modules) -> set[tuple[str, str]]:
    """(module, fonction) de chaque fonction NON-route qui lève 401/403 hors d'`auth/`."""
    trouves = set()
    for module in modules:
        if module.rel.startswith(("auth/", "utils/visibility/")):
            continue
        for fonction in ast.walk(module.arbre):
            if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if _est_route(fonction):
                continue
            for noeud in _propres(fonction):
                if (
                    isinstance(noeud, ast.Raise)
                    and isinstance(noeud.exc, ast.Call)
                    and (
                        getattr(noeud.exc.func, "id", None) or getattr(noeud.exc.func, "attr", None)
                    )
                    == "HTTPException"
                    and _code_refuse(noeud.exc)
                ):
                    trouves.add((module.rel, fonction.name))
                    break
    return trouves


def dependances_locales(modules) -> list[str]:
    """Les `require*` définis hors de `auth/deps.py` — une dépendance d'autorisation locale."""
    return [
        f"{m.rel}:{n.lineno} {n.name}()"
        for m in modules
        if m.rel != "auth/deps.py"
        for n in ast.walk(m.arbre)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name.lstrip("_").startswith("require")
    ]


def test_aucune_dependance_d_autorisation_locale():
    """Les dépendances d'autorisation vivent dans `app/auth/deps.py`, nulle part ailleurs.

    Attrape la dérive de `_require_bailleur` : un doublon local de `require_proprietaire`,
    invisible depuis le module central. Portée : tout `app/` (#2942 — elle ne lisait que
    `app/routers/`).
    """
    locales = dependances_locales(modules_app(minimum=PLANCHER_APP))
    assert not locales, (
        "Dépendance d'autorisation définie hors de `app/auth/deps.py` : la règle "
        "doit être centralisée, sinon un durcissement du module central ne "
        "l'atteindra pas.\n" + "\n".join(locales)
    )


def test_aucun_refus_hors_d_auth_non_declare():
    """Un refus 401/403 écrit dans une fonction hors d'`auth/` est déclaré, ou appelle la porte.

    « Réservé au conseil » se refuse par `deps.exiger_moderateur(user, motif)` (ou la
    dépendance `require_cs_or_admin`) — jamais par une copie, même fidèle au prédicat.
    """
    trouves = refus_hors_d_auth(modules_app(minimum=PLANCHER_APP))
    declares = set(REFUS_DECLARES)
    assert trouves == declares, (
        "Refus hors d'`auth/` à centraliser (ou à déclarer avec sa raison) : "
        f"{sorted(trouves - declares)}\nDéclaration(s) qui ne refuse(nt) plus — à retirer : "
        f"{sorted(declares - trouves)}"
    )


def test_temoin_le_detecteur_voit_un_refus_recopie():
    """Cas zéro du détecteur : la forme d'avant #2942 est vue, une route ne l'est pas."""
    from tests.aides_sources import Module

    forge = Module(
        chemin=pathlib.Path("forge.py"),
        rel="utils/forge.py",
        source=(
            "def _exiger_conseil(user):\n"
            "    if not est_moderateur(user):\n"
            "        raise HTTPException(403, 'Seul le conseil')\n"
            "def _autre(user):\n"
            "    if not x:\n"
            "        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)\n"
            "@router.get('/x')\n"
            "def route(user):\n"
            "    raise HTTPException(403)\n"
            "def _require_local(user):\n"
            "    return user\n"
        ),
    )
    assert refus_hors_d_auth([forge]) == {
        ("utils/forge.py", "_exiger_conseil"),
        ("utils/forge.py", "_autre"),
    }
    assert dependances_locales([forge]) == ["utils/forge.py:10 _require_local()"]


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
    """Les règles de visibilité vivent dans le paquet `app/utils/visibility/`, et nulle part ailleurs.

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

    central = _API_DIR / "app" / "utils" / "visibility"
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
        "Règle(s) de visibilité définie(s) dans un router — à déplacer dans le paquet "
        f"{central.relative_to(_API_DIR.parent)}/ :\n" + "\n".join(egarees)
    )
    assert not imports_croises, (
        "Règle(s) de visibilité importée(s) depuis un router au lieu du module "
        "central — le jour où le router change, l'appelant ne le saura pas :\n"
        + "\n".join(imports_croises)
    )
