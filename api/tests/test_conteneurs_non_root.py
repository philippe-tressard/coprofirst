"""Aucun conteneur ne sert en root — et le contrôle regarde le FAIT, pas le mot.

## Le défaut (#769, audit du 05/09/2026)

`api/Dockerfile` et `front/Dockerfile` ne posaient aucun `USER` : les deux
conteneurs s'exécutaient en **root**. Un défaut d'exécution — rendu PDF,
dépendance compromise, désérialisation — donnait alors root sur le volume de
données. Le confinement Docker ne sépare rien quand le processus est root.

🔴 Le front CRÉAIT DÉJÀ l'utilisateur (`adduser -S app`) et ne s'en servait
jamais. C'est le pire des trois états : un `grep adduser` rassurait, et rien ne
protégeait. Un compte créé mais jamais endossé ne donne que l'air.

## Ce que ce test vérifie, et pourquoi pas simplement « USER est présent »

L'API ne PEUT PAS poser `USER` dans son Dockerfile : ses trois volumes sont
écrits par root sur les deux nœuds, et un conteneur qui démarrerait directement
en `app` ne pourrait plus y écrire. Elle bascule donc dans `start.sh`,
après avoir repris les propriétés.

Exiger le mot `USER` aurait donc refusé la seule solution qui marche, et poussé
à la contourner. Le test demande le FAIT — « ce conteneur finit-il par quitter
root ? » — et accepte les deux formes, en vérifiant pour chacune ce qui la rend
vraie.
"""

from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]


def _lire(chemin: str) -> str:
    fichier = _RACINE / chemin
    assert fichier.exists(), f"{chemin} introuvable — le contrôle a perdu sa portée"
    return fichier.read_text(encoding="utf-8")


def test_le_front_endosse_l_utilisateur_qu_il_cree():
    """`adduser` sans `USER` : le compte existe, le serveur reste root."""
    source = _lire("front/Dockerfile")
    assert re.search(r"\badduser\b", source), (
        "l'utilisateur applicatif du front a disparu du Dockerfile"
    )
    assert re.search(r"^\s*USER\s+app\s*$", source, re.M), (
        "front/Dockerfile crée un utilisateur `app` mais ne l'endosse pas : "
        "le serveur SSR tourne en root. Ajouter `USER app` avant `CMD`."
    )


def test_l_api_bascule_hors_de_root_avant_d_ecrire():
    """L'API ne peut pas poser `USER` — elle doit donc basculer dans `start.sh`.

    Trois choses sont exigées, et chacune répare une moitié du geste :

    1. l'utilisateur existe (`useradd`) ;
    2. `start.sh` reprend les propriétés des volumes — sans quoi le processus
       non-root ne pourrait pas écrire dans des volumes écrits par root ;
    3. il se relance en `app` **avant** Alembic : ce qui s'exécute ensuite ne
       tourne jamais en root.
    """
    dockerfile = _lire("api/Dockerfile")
    assert re.search(r"\buseradd\b.*\bapp\b", dockerfile), (
        "api/Dockerfile ne crée plus d'utilisateur applicatif"
    )

    start = _lire("api/start.sh")
    assert "chown -R app:app" in start, (
        "start.sh ne reprend plus les propriétés des volumes : un conteneur "
        "non-root ne pourra pas écrire dans ses volumes, écrits par root."
    )
    bascule = re.search(r"^\s*exec setpriv .*--reuid=app\b.*$", start, re.M)
    assert bascule, (
        "start.sh ne bascule plus hors de root : l'API sert en root, ce que #769 corrigeait."
    )
    #  Les migrations de CHAQUE base passent par `utils/preparer_bases` (#2053).
    alembic = re.search(r"^BASES=\$\(python -m app\.utils\.preparer_bases\)$", start, re.M)
    assert alembic, "start.sh ne lance plus les migrations"
    assert bascule.start() < alembic.start(), (
        "les migrations tournent AVANT la bascule : elles s'exécuteraient en root."
    )


def test_le_bridge_descend_vers_node_avant_de_servir():
    """Le bridge démarre en root le temps de rendre son état à `node` (#2368).

    Son conteneur est durci (`docker-compose.yml`) : root n'y garde que de quoi
    réaligner `auth_state` et changer d'identité. La descente doit donc avoir
    lieu, et AVANT que Baileys ou le serveur HTTP ne démarrent ; le compte vers
    lequel elle descend se vérifie à la construction de l'image.
    """
    index = _lire("whatsapp-bridge/index.js")
    descente = re.search(r"^\s*const descente = descendreDeRoot\(AUTH_DIR\);", index, re.M)
    assert descente, "index.js n'appelle plus descendreDeRoot : Baileys tourne en root"
    for premier_usage in ("useMultiFileAuthState(AUTH_DIR)", "app.listen("):
        assert premier_usage in index, f"repère introuvable dans index.js : {premier_usage}"
        assert descente.start() < index.index(premier_usage), (
            f"{premier_usage} précède la descente : il s'exécuterait en root"
        )
    dockerfile = _lire("whatsapp-bridge/Dockerfile")
    assert re.search(r"^COPY .*\bprivileges\.js\b", dockerfile, re.M), (
        "privileges.js n'est plus copié dans l'image : le bridge ne démarre pas"
    )
    assert '"$(id -u node):$(id -g node)" = "1000:1000"' in dockerfile, (
        "l'uid du compte node n'est plus vérifié à la construction (privileges.js le suppose)"
    )


#: Une commande lancée DANS le conteneur de l'API par un opérateur ou un script —
#: `docker exec hostachy_api python …`, `docker compose exec -T api python …`,
#: `"${COMPOSE[@]}" exec api sh …`. Les options avant le service sont capturées.
_EXEC_API = re.compile(
    r"\bexec\b((?:\s+-{1,2}[\w-]+(?:[ =](?!api\b|hostachy_api\b)[\w./=-]+)?)*)"
    r"\s+(?:api|hostachy_api)\s+(?:python\d*|sh|bash)\b"
)
_COMPTE_APP = re.compile(r"(?:^|\s)(?:-u|--user)[ =]app\b")


def _commandes_dans_l_api():
    """(fichier, numéro, ligne, options) de chaque `exec` dans l'API : scripts
    (hors commentaires), documents d'exploitation et docstrings du code."""
    from tests.conftest import scripts_shell_versionnes

    sources = [(s, True) for s in scripts_shell_versionnes()]
    for motif in ("deploiement/**/*.md", "docs/**/*.md", "api/app/**/*.py", "README.md"):
        sources += [(p, False) for p in _RACINE.glob(motif)]
    for chemin, est_script in sources:
        for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
            if est_script and ligne.strip().startswith("#"):
                continue
            for trouve in _EXEC_API.finditer(ligne):
                yield chemin.relative_to(_RACINE).as_posix(), numero, ligne.strip(), trouve.group(1)


def test_une_commande_dans_l_api_tourne_sous_le_compte_app():
    """`docker exec` entre en root — et le root du conteneur durci n'a plus
    DAC_OVERRIDE (#2368) : il ne peut plus écrire dans `/app/data` ni
    `/app/uploads`, qui appartiennent à `app`. Déclarer une copropriété
    (`creer-copropriete.sh`) échouait ainsi sur le banc du standby. Sous `-u app`,
    la commande écrit, et ses fichiers ont le propriétaire que l'API relit.
    """
    trouves = list(_commandes_dans_l_api())
    #  Cas zéro : `creer-copropriete.sh` en porte trois ; une portée cassée ne
    #  verrait rien et rendrait le test vert.
    assert (
        sum(f == "deploiement/standard/commune/creer-copropriete.sh" for f, *_ in trouves) >= 3
    ), "les commandes de creer-copropriete.sh ne sont plus vues — portée ou motif cassé"
    fautes = [
        f"{f}:{n} : {ligne}" for f, n, ligne, options in trouves if not _COMPTE_APP.search(options)
    ]
    assert not fautes, (
        "Commande lancée dans le conteneur de l'API sans `-u app` — root n'y peut plus "
        "écrire (conteneur durci, #2368) :\n" + "\n".join(fautes)
    )


def test_le_motif_exec_api_voit_et_ne_voit_que_lui():
    """Témoins du motif : chaque forme employée dans le dépôt, et ce qu'il laisse."""
    vus = (
        "docker compose exec api python -m app.seed --copropriete tilleuls",
        'NOMS=$("${COMPOSE[@]}" exec -T api python -m app.installation_commune.creer noms "$@")',
        "docker exec -i hostachy_api python3 script.py",
        "docker exec -e X=1 hostachy_api sh -c 'ls'",
    )
    ignores = (
        "docker exec hostachy_api curl -s http://localhost:8000/health",
        'docker exec hostachy_postgres psql -U coprofirst -Atc "select 1"',
        "docker compose logs api",
    )
    for ligne in vus:
        assert _EXEC_API.search(ligne), f"le motif devrait voir : {ligne}"
        assert not _COMPTE_APP.search(_EXEC_API.search(ligne).group(1)), ligne
    for ligne in ignores:
        assert not _EXEC_API.search(ligne), f"le motif voit à tort : {ligne}"
    assert _COMPTE_APP.search(
        _EXEC_API.search("docker compose exec -T -u app api python -m x").group(1)
    )
    assert _COMPTE_APP.search(
        _EXEC_API.search("docker exec --user=app hostachy_api python x").group(1)
    )
