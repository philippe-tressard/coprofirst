"""Chaque image de `docker-compose.yml` reçoit ses correctifs ET ses montées (#1872).

POURQUOI (12/10/2026) — une image arrive à jour par DEUX chemins, et il les faut
tous les deux :

- le **re-tirage du dimanche** (`maintenance.sh` → `rafraichir_images_de_base`,
  #1379) amène les correctifs republiés sous la même étiquette (`17.11` reconstruite
  sur un Debian corrigé) ;
- **Dependabot** propose l'étiquette suivante (17.11 → 17.12).

`postgres:17.11`, déclaré par `image:` sans Dockerfile, n'avait ni l'un ni
l'autre : le re-tirage ne lisait que les `FROM`, Dependabot (`docker`) aussi. Le
même trou s'ouvrirait au prochain service tiré tel quel, ou au prochain
Dockerfile posé dans un dossier que ni l'un ni l'autre ne lit.

CE QUE CE TEST TIENT :

- le re-tirage, mesuré en exécutant la VRAIE `images_de_base` sur les fichiers
  que `maintenance.sh` lui passe : il lit le Dockerfile de chaque service
  construit, et nomme l'image de chaque service tiré ;
- Dependabot lit le dossier de chaque Dockerfile (`docker`) et le compose
  (`docker-compose`) — et jamais une majeure de PostgreSQL, qui change le format
  des données (`pg_upgrade`) ;
- la CI sur PostgreSQL (`postgresql.yml`) juge l'image de la production, pas une
  étiquette flottante.

L'étiquette explicite de PostgreSQL est tenue par `test_postgresql_compose.py`,
celle de Caddy par `test_image_caddy_epinglee.py` : pas ici.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.aides_compose import RACINE, images_tirees, lire_yaml, services_construits

MAINTENANCE = RACINE / "scripts" / "exploitation" / "maintenance.sh"
LIB = RACINE / "scripts" / "lib" / "lib-images-base.sh"
DEPENDABOT = RACINE / ".github" / "dependabot.yml"
WORKFLOWS = RACINE / ".github" / "workflows"

#: Les images dont une MAJEURE change le format des données sur disque : elles
#: ne montent jamais par une PR de Dependabot.
MAJEURE_EST_UNE_MIGRATION = {"postgres"}

_APPEL = re.compile(r"^\s*rafraichir_images_de_base\s+(?P<args>.+?)\s*$", re.M)


def _depot(image: str) -> str:
    """`postgres:17.11` → `postgres` (l'étiquette suit le dernier `/`)."""
    nom, _, _ = image.rpartition(":") if ":" in image.rsplit("/", 1)[-1] else (image, "", "")
    return nom


def _arguments_de_la_maintenance() -> str:
    appels = _APPEL.findall(MAINTENANCE.read_text(encoding="utf-8"))
    assert len(appels) == 1, (
        f"{len(appels)} appel(s) de `rafraichir_images_de_base` dans maintenance.sh : "
        "ce contrôle en attend un, celui de `hygiene_locale`"
    )
    return appels[0]


@pytest.fixture(scope="module")
def retirage() -> tuple[set[Path], set[str]]:
    """Les fichiers que la maintenance passe au re-tirage, et les images qu'il en lit."""
    if shutil.which("bash") is None:
        pytest.skip("bash absent : le re-tirage ne peut pas être mesuré")
    script = (
        f"REPO='{RACINE.as_posix()}'\n"
        f"source '{LIB.as_posix()}'\n"
        f"set -- {_arguments_de_la_maintenance()}\n"
        "printf 'FICHIER %s\\n' \"$@\"\n"
        "images_de_base \"$@\" | sed 's/^/IMAGE /'\n"
    )
    res = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert res.returncode == 0, f"`images_de_base` a échoué : {res.stderr}"
    lignes = res.stdout.splitlines()
    fichiers = {
        Path(ligne.removeprefix("FICHIER ")).resolve()
        for ligne in lignes
        if ligne.startswith("FICHIER ")
    }
    images = {ligne.removeprefix("IMAGE ") for ligne in lignes if ligne.startswith("IMAGE ")}
    return fichiers, images


def _blocs(ecosysteme: str) -> list[dict]:
    return [b for b in lire_yaml(DEPENDABOT)["updates"] if b["package-ecosystem"] == ecosysteme]


def _dossiers(bloc: dict) -> set[str]:
    return set(bloc.get("directories") or [bloc["directory"]])


def test_le_compose_a_ses_deux_natures_de_service():
    """Cas zéro : un relevé vide rendrait chaque contrôle ci-dessous vert sur rien."""
    assert len(services_construits()) >= 4, services_construits()
    assert "postgres" in images_tirees(), "plus de service `postgres` tiré : revoir ce contrôle"


def test_le_retirage_lit_chaque_dockerfile_construit(retirage):
    fichiers, _ = retirage
    absents = sorted(
        f"{nom} ({chemin})"
        for nom, (_, chemin) in services_construits().items()
        if (RACINE / chemin).resolve() not in fichiers
    )
    assert not absents, (
        f"Dockerfile que `maintenance.sh` ne passe pas au re-tirage : {absents} — "
        "ses images de base ne recevraient plus les correctifs de leur étiquette"
    )


def test_le_retirage_nomme_chaque_image_tiree(retirage):
    _, images = retirage
    absentes = sorted(f"{nom} ({img})" for nom, img in images_tirees().items() if img not in images)
    assert not absentes, (
        f"image(s) du compose que le re-tirage du dimanche ne tire pas : {absentes} — "
        "passer `docker-compose.yml` à `rafraichir_images_de_base` (une étiquette "
        "interpolée `${…}` ne se tire pas : l'écrire en clair)"
    )


def test_dependabot_lit_le_dossier_de_chaque_dockerfile():
    blocs = _blocs("docker")
    assert blocs, "aucun bloc `docker` dans dependabot.yml"
    lus = set().union(*(_dossiers(b) for b in blocs))
    dossiers = {
        nom: "/" + Path(chemin).parent.as_posix().removeprefix(".")
        for nom, (_, chemin) in services_construits().items()
    }
    absents = sorted(f"{nom} ({d})" for nom, d in dossiers.items() if d not in lus)
    assert not absents, f"Dockerfile hors de portée de Dependabot `docker` : {absents}"


def test_dependabot_lit_le_compose_sans_majeure_de_postgresql():
    blocs = [b for b in _blocs("docker-compose") if "/" in _dossiers(b)]
    assert len(blocs) == 1, (
        "aucun bloc `docker-compose` sur `/` dans dependabot.yml : les images tirées du "
        f"compose ({sorted(images_tirees().values())}) ne recevraient aucune montée"
    )
    ignorees = {
        r["dependency-name"]
        for r in blocs[0].get("ignore", [])
        if "version-update:semver-major" in r.get("update-types", [])
    }
    manquantes = sorted(
        img
        for img in images_tirees().values()
        if _depot(img) in MAJEURE_EST_UNE_MIGRATION and _depot(img) not in ignorees
    )
    assert not manquantes, (
        f"{manquantes} : une majeure change le format des données (pg_upgrade) — "
        "l'ignorer dans le bloc `docker-compose`, la montée est un lot à elle"
    )


def test_la_ci_juge_l_image_de_la_production():
    """Un `services:` de workflow qui tire la même image que le compose porte son étiquette."""
    production = {_depot(img): img for img in images_tirees().values()}
    vus, ecarts = 0, []
    for flux in sorted(WORKFLOWS.glob("*.yml")):
        for job in (lire_yaml(flux).get("jobs") or {}).values():
            for service in (job.get("services") or {}).values():
                image = service.get("image", "") if isinstance(service, dict) else ""
                attendue = production.get(_depot(image))
                if attendue:
                    vus += 1
                    if image != attendue:
                        ecarts.append(f"{flux.name} : {image} ≠ {attendue}")
    assert vus, "aucun workflow ne tire l'image de PostgreSQL : `postgresql.yml` a-t-il bougé ?"
    assert not ecarts, f"la CI ne juge pas l'image de la production : {ecarts}"


def test_le_depot_d_une_image_se_lit_sans_son_etiquette():
    assert _depot("postgres:17.11") == "postgres"
    assert _depot("ghcr.io:443/x/y:1.2") == "ghcr.io:443/x/y"
    assert _depot("postgres") == "postgres"
