"""Les images se construisent par UNE porte, et elle porte le commit (#1684).

Le front grave `GIT_HASH` dans son bundle (`front/Dockerfile`, défaut `dev`).
Quatre scripts lançaient chacun leur `docker compose build` : le déploiement
et l'alignement d'`auto-deploy.sh` exportaient le commit, son rattrapage
(#1131) et la synchronisation du pair par `bascule.sh` (phase 0) non — un
front reconstruit par eux se disait « dev ». Chaque écriture était juste ou
fausse selon que son auteur y avait pensé.

La porte est `construire_images` (`scripts/lib/lib-parite.sh`) : elle lit le
commit du dépôt au moment du build, l'exporte, puis construit. Ce test refuse
tout `docker compose … build` (ou `up --build`) écrit ailleurs, et toute
seconde écriture de `GIT_HASH=$(git rev-parse …)`.

Même règle pour le DÉMARRAGE (#1697) : l'étiquette `git.hash` du front se lit au
`up`, pas au build. Cinq `docker compose up -d` tournaient sans `GIT_HASH` et
étiquetaient le front « dev » ; ils passent par `demarrer_conteneurs`.
"""

from __future__ import annotations

import re

from tests.conftest import racine_depot, scripts_shell_versionnes

PORTE = "scripts/lib/lib-parite.sh"

#: Un build lancé en position de COMMANDE — début de ligne, après `&&`, `;`,
#: `||`, `if`, `!`, ou en tête d'une chaîne passée à ssh. Une mention entre
#: accents graves dans un message (« son `docker compose build` a échoué ») n'en
#: est pas une : elle ne construit rien.
BUILD = re.compile(
    r"""(?:^|&&|\|\||;|\bif\b|!|\bthen\b|["'(])\s*docker\s+compose"""
    r"""(?:\s+-f\s+\S+)?\s+(?:build\b|up\b[^#\n]*--build\b)"""
)
HASH = re.compile(r"\bGIT_HASH=\$\(\s*git\s+rev-parse")
#: Un démarrage en position de commande (même forme que BUILD, sans `--build`).
UP = re.compile(
    r"""(?:^|&&|\|\||;|\bif\b|!|\bthen\b|["'(])\s*docker\s+compose"""
    r"""(?:\s+-f\s+\S+)?\s+up\b"""
)

#: Scripts qui écrivent un `up` eux-mêmes, parce qu'ils exportent le commit DANS
#: LEUR PROPRE SHELL avant : (marque à trouver dans le code, raison). Une entrée
#: dont le script n'écrit plus de `up`, ou ne porte plus la marque, échoue.
#: Vide depuis #1997/#1999 : `auto-deploy.sh` et `MaJ-Hostachy.sh` servent par
#: `servir_images` (`lib-servir.sh`), qui passe par la porte.
EXPORTEURS: dict[str, tuple[str, str]] = {}

#: Lignes qui NOMMENT un `up` à un humain (message, consigne d'alerte) sans le
#: lancer : `{script: nombre de lignes}`. Elles ne lancent rien ; le compte exact
#: fait échouer l'entrée qui cesse de servir.
MESSAGES = {
    #  Le rollback : relance échouée, et base locale NON relancée (#2318).
    "scripts/exploitation/bascule.sh": 2,  # « vérifier manuellement : … docker compose up -d »
    "scripts/lib/lib-mises-a-jour.sh": 1,  # consigne du contrôle C30
    "scripts/lib/lib-precheck-infra.sh": 1,  # consigne du point 18
}


def _code(texte: str) -> list[tuple[int, str]]:
    """Les lignes qui ne sont pas des commentaires, numérotées."""
    return [
        (n, ligne)
        for n, ligne in enumerate(texte.splitlines(), 1)
        if not ligne.lstrip().startswith("#")
    ]


def _ecarts(motif: re.Pattern, fichiers) -> list[str]:
    racine = racine_depot()
    trouves = []
    for chemin in fichiers:
        rel = chemin.relative_to(racine).as_posix()
        for n, ligne in _code(chemin.read_text(encoding="utf-8", errors="replace")):
            if motif.search(ligne):
                trouves.append(f"{rel}:{n}")
    return trouves


def test_un_seul_build_dans_les_scripts():
    scripts = scripts_shell_versionnes()
    assert len(scripts) > 40, "cas zéro : la portée des scripts a bougé"
    trouves = _ecarts(BUILD, scripts)
    hors_porte = [t for t in trouves if not t.startswith(PORTE + ":")]
    assert hors_porte == [], (
        "un build d'images écrit hors de `construire_images` (lib-parite.sh) : "
        f"il bâtirait le front sans GIT_HASH — {hors_porte}"
    )
    assert len(trouves) == 1, f"la porte elle-même doit construire, une fois : {trouves}"


def test_le_commit_ne_se_lit_qu_a_la_porte():
    trouves = _ecarts(HASH, scripts_shell_versionnes())
    assert trouves and all(t.startswith(PORTE + ":") for t in trouves), (
        f"GIT_HASH se lit dans `exporter_git_hash` (lib-parite.sh), et nulle part ailleurs : {trouves}"
    )
    assert len(trouves) == 1


def test_la_bascule_attend_l_api_en_secondes():
    """Même lot (#1684, point 3) : la phase 5 attend par `attendre_200`.

    Sa boucle comptait des TOURS (`seq 1 $HEALTH_TIMEOUT`), chacun coûtant un
    SSH jusqu'à dix secondes : « 150 s » pouvaient durer 25 min, site coupé.
    """
    bascule = (racine_depot() / "scripts/exploitation/bascule.sh").read_text(encoding="utf-8")
    code = "\n".join(ligne for _, ligne in _code(bascule))
    assert 'attendre_200 "$HEALTH_TIMEOUT"' in code
    assert "seq 1 $HEALTH_TIMEOUT" not in code


def test_le_motif_voit_les_quatre_builds_d_avant():
    """Cas zéro : les écritures fautives d'avant #1684 sont refusées."""
    fautives = [
        "        if docker compose build --quiet; then",  # rattrapage d'auto-deploy
        '  if $SSH_CMD p@"$PEER_IP" "cd /opt/5hostachy && git reset --hard $H && docker compose build --quiet" ; then',
        '    docker compose -f "$REPO/docker-compose.yml" build $SERVICES_TO_BUILD',  # MaJ-Hostachy
        "À faire sur $SELF : cd $REPO && docker compose build",  # consigne d'alerte
        "docker compose up --build -d",
    ]
    assert all(BUILD.search(ligne) for ligne in fautives)
    #  …et ce qui n'est pas un build ne l'est pas.
    innocentes = [
        "son \\`docker compose build\\` a échoué.",
        "docker compose up -d api",
        "docker builder prune -f",
    ]
    assert not any(BUILD.search(ligne) for ligne in innocentes)


def test_un_seul_demarrage_dans_les_scripts():
    """#1697 : un `up` hors de la porte est un front étiqueté « dev »."""
    racine = racine_depot()
    par_script: dict[str, list[str]] = {}
    for chemin in scripts_shell_versionnes():
        rel = chemin.relative_to(racine).as_posix()
        for n, ligne in _code(chemin.read_text(encoding="utf-8", errors="replace")):
            if UP.search(ligne):
                par_script.setdefault(rel, []).append(f"{rel}:{n}")
    assert PORTE in par_script and len(par_script[PORTE]) == 1, (
        f"cas zéro : la porte doit démarrer, une fois — {par_script.get(PORTE)}"
    )
    hors_porte = {
        rel: lignes
        for rel, lignes in par_script.items()
        if rel != PORTE and rel not in EXPORTEURS and len(lignes) != MESSAGES.get(rel, 0)
    }
    assert hors_porte == {}, (
        "un `docker compose up` écrit hors de `demarrer_conteneurs` (lib-parite.sh) : "
        f"le front serait étiqueté « dev » — {hors_porte}"
    )
    for rel, (marque, raison) in EXPORTEURS.items():
        assert rel in par_script, f"exception qui ne sert plus (aucun `up`) : {rel} — {raison}"
        code = "\n".join(ligne for _, ligne in _code((racine / rel).read_text(encoding="utf-8")))
        assert marque in code, f"{rel} ne porte plus `{marque}` : {raison}"
    for rel, n in MESSAGES.items():
        assert len(par_script.get(rel, [])) == n, f"message déclaré qui ne sert plus : {rel}"


def test_les_cinq_demarrages_d_avant_passent_par_la_porte():
    """Cas zéro : les `up -d` fautifs de #1697 sont vus par le motif."""
    fautives = [
        "  if docker compose up -d; then",  # rollback de bascule.sh
        "docker compose up -d >> /dev/null 2>&1 && log ok",  # health-watch.sh
        '  ( cd "$REPO" && docker compose up -d >/dev/null 2>&1 ) && log ok',  # boot-role-guard
        '        || (cd "$REPO" && docker compose up -d api >/dev/null 2>&1) || true',  # maintenance
        "run \"$SSH_CMD p@$PEER_IP 'cd /opt/5hostachy && env_role_appliquer .env actif && docker compose up -d'\"",
    ]
    assert all(UP.search(ligne) for ligne in fautives)
    assert not UP.search("  demarrer_conteneurs api")
