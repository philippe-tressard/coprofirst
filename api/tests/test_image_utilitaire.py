"""L'image des conteneurs jetables porte une étiquette, et quelque chose la fait monter (#2962).

POURQUOI (24/11/2026) — les scripts d'exploitation lancent des conteneurs jetables
(`docker run --rm … alpine …`) : la copie de l'état WhatsApp à chaque bascule
(`lib-volumes.sh`), la lecture des sauvegardes par l'export hors site, le banc des
volumes, le durcissement des sudoers. L'image était nommée `alpine`, sans étiquette :
ni le re-tirage du dimanche (il lit les `FROM` et les `image:`), ni Dependabot ne la
voyaient. Relevé sur les deux nœuds le 24/11 : `alpine:latest` en 3.23.4, tirée il y
a sept mois, jamais remontée.

CE QUE CE TEST TIENT :

- l'image se déclare UNE fois, dans `infra/Dockerfile.utilitaire`, avec une étiquette
  explicite — ni absente, ni `latest` ;
- le re-tirage de `maintenance.sh` la nomme (mesuré en exécutant la vraie
  `images_de_base` sur les fichiers qu'il lui passe), et Dependabot `docker` lit son
  dossier ;
- `image_utilitaire` (`lib-image-utilitaire.sh`) rend cette étiquette, lue dans le
  fichier, jamais recopiée ;
- aucun `docker run` des scripts ni des consignes ne nomme une image `alpine` nue ;
- `auto-deploy.sh` s'assure, à chaque passage, que l'image est sur le nœud : la
  bascule de 02:00 ne doit pas dépendre du réseau pour la tirer.
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from tests.aides_compose import RACINE, lire_yaml

DOCKERFILE = RACINE / "infra" / "Dockerfile.utilitaire"
LIB = RACINE / "scripts" / "lib" / "lib-image-utilitaire.sh"
LIB_BASES = RACINE / "scripts" / "lib" / "lib-images-base.sh"
MAINTENANCE = RACINE / "scripts" / "exploitation" / "maintenance.sh"
AUTO_DEPLOY = RACINE / "scripts" / "exploitation" / "auto-deploy.sh"
DEPENDABOT = RACINE / ".github" / "dependabot.yml"

#: Une image `alpine` NUE après `docker run` : sans `:` ni `@` collés à son nom.
ALPINE_NUE = re.compile(r"docker\s+(?:run|image\s+inspect)\b[^\n#]*?\salpine(?![:@\w-])")

#: Où l'on cherche : les scripts et les consignes qui donnent des commandes.
PORTEE = ("scripts", ".claude/skills", "deploiement", "docs", "infra")


def _bash(script: str) -> subprocess.CompletedProcess:
    if shutil.which("bash") is None:
        pytest.skip("bash absent : la bibliothèque ne peut pas être exécutée")
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def _etiquette_declaree() -> str:
    froms = [
        ligne.split()[1]
        for ligne in DOCKERFILE.read_text(encoding="utf-8").splitlines()
        if ligne.strip().upper().startswith("FROM ")
    ]
    assert len(froms) == 1, f"{DOCKERFILE.name} doit porter un seul FROM : {froms}"
    return froms[0]


def test_l_image_porte_une_etiquette_explicite():
    image = _etiquette_declaree()
    nom, _, etiquette = image.partition(":")
    assert nom == "alpine" and etiquette, image
    assert etiquette != "latest", "`latest` est une étiquette flottante : ni suivie, ni datée"


def test_la_bibliotheque_lit_l_etiquette_dans_le_fichier():
    res = _bash(f"source '{LIB.as_posix()}'; image_utilitaire")
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == _etiquette_declaree()


def test_le_retirage_du_dimanche_la_nomme():
    appel = re.search(r"^\s*rafraichir_images_de_base\s+(.+?)\s*$", MAINTENANCE.read_text("utf-8"), re.M)
    assert appel, "plus d'appel à rafraichir_images_de_base dans maintenance.sh"
    res = _bash(
        f"REPO='{RACINE.as_posix()}'; source '{LIB_BASES.as_posix()}'; "
        f"set -- {appel.group(1)}; images_de_base \"$@\""
    )
    assert res.returncode == 0, res.stderr
    assert _etiquette_declaree() in res.stdout.split(), (
        f"le re-tirage ne lit pas {DOCKERFILE.relative_to(RACINE)} : ses correctifs "
        "n'arriveraient jamais sur les nœuds"
    )


def test_dependabot_lit_son_dossier():
    dossiers = set()
    for bloc in lire_yaml(DEPENDABOT)["updates"]:
        if bloc["package-ecosystem"] == "docker":
            dossiers |= set(bloc.get("directories") or [bloc["directory"]])
    assert "/" + DOCKERFILE.parent.relative_to(RACINE).as_posix() in dossiers, dossiers


def _fichiers_suivis() -> list[str]:
    sortie = subprocess.run(
        ["git", "ls-files", "--", *PORTEE], cwd=RACINE, capture_output=True, text=True, check=True
    ).stdout.split()
    assert len(sortie) > 100, "la portée n'est pas lue en entier"  # cas zéro
    return sortie


def test_aucun_conteneur_jetable_ne_nomme_alpine_nue():
    fautes = []
    for rel in _fichiers_suivis():
        if not rel.endswith((".sh", ".md", ".yml", ".crontab")):
            continue
        texte = (RACINE / rel).read_text(encoding="utf-8", errors="replace")
        fautes += [f"{rel} : {m.group(0).strip()}" for m in ALPINE_NUE.finditer(texte)]
    assert fautes == [], (
        "image `alpine` sans étiquette — passer par `image_utilitaire` "
        f"(lib-image-utilitaire.sh) : {fautes}"
    )


def test_le_controle_voit_une_image_nue():
    """Témoin (`standards/04` §2) : les formes du 24/11 sont vues, les autres non."""
    for fautif in (
        "docker run --rm -v 5hostachy_uploads:/u:ro alpine",
        'docker run --rm -v x:/dst alpine sh -c "cp -a /src/. /dst/"',
        '"docker image inspect alpine"',
    ):
        assert ALPINE_NUE.search(fautif), fautif
    for juste in (
        'docker run --rm -v x:/d "$(image_utilitaire)" sh',
        "docker run --rm alpine:3.24 true",
        "FROM golang:1.27-alpine AS construction",
        "FROM node:26-alpine",
    ):
        assert not ALPINE_NUE.search(juste), juste


def test_auto_deploy_assure_l_image_a_chaque_passage():
    texte = AUTO_DEPLOY.read_text(encoding="utf-8")
    assert "lib-image-utilitaire.sh" in texte and "assurer_image_utilitaire" in texte
    #  Avant la décision : le passage « Aucun changement » sort tôt, et c'est le plus
    #  fréquent — l'image doit s'assurer aussi sur lui.
    assert texte.index("assurer_image_utilitaire") < texte.index('if [ "$LOCAL" = "$REMOTE" ]')
