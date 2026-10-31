"""L'image de base de Caddy porte une version MINEURE explicite (#1602, 04/10/2026).

POURQUOI — `FROM caddy:2` n'a qu'une majeure : Dependabot (`docker`) ne propose
jamais de 2.x → 2.y, et `maintenance.sh` (#1379) re-tire l'image chaque dimanche,
donc le Caddy de production change sans qu'aucun commit ne le dise. Avec
`caddy:2.11`, la mineure servie est écrite dans le dépôt : un correctif de la
même mineure se tire toujours, et un changement de mineure arrive par une PR.

CE QUE CE TEST REFUSE : un `FROM caddy` sans `<majeure>.<mineure>`. Les autres
images de base (python, node) restent à étiquette flottante par choix
(`dependabot.yml` : leurs mineures changent assez pour que Dependabot les suive),
et ne sont pas jugées ici.
"""

import re

from tests.conftest import racine_depot

DOCKERFILE = racine_depot() / "Dockerfile.caddy"
_FROM = re.compile(r"^\s*FROM\s+(?P<image>caddy)(?::(?P<tag>\S+))?(\s+AS\s+\S+)?\s*$", re.I | re.M)
_MINEURE = re.compile(r"^\d+\.\d+(\.\d+)?(-[A-Za-z0-9.]+)?$")


def _bases() -> list[tuple[str, str | None]]:
    return [(m["image"], m["tag"]) for m in _FROM.finditer(DOCKERFILE.read_text(encoding="utf-8"))]


def test_le_dockerfile_de_caddy_est_lu():
    """Cas zéro : un contrôle qui ne trouve aucun `FROM caddy` n'a rien jugé."""
    assert _bases(), "aucun `FROM caddy` lu dans Dockerfile.caddy"


def test_caddy_porte_une_mineure_explicite():
    flottantes = [
        f"caddy:{tag or '(latest)'}" for _, tag in _bases() if not (tag and _MINEURE.match(tag))
    ]
    assert not flottantes, (
        f"image(s) de base sans version mineure : {flottantes} — écrire `caddy:<majeure>.<mineure>` "
        "(la mineure servie se lit : `docker exec hostachy_caddy caddy version`)"
    )


# ── Le binaire recompilé (#2377, 31/10/2026) ─────────────────────────────────
#  L'image officielle `caddy:2.11` porte un binaire compilé en Go 1.26.8 (six
#  HIGH) : `Dockerfile.caddy` compile la même version depuis sa source et la
#  pose sur l'image d'exécution. Trois choses rendent ce montage vrai.
_VERSION_COMPILEE = re.compile(r"^\s*ARG\s+CADDY_VERSION=v(?P<v>\d+\.\d+)\.\d+\s*$", re.M)
_COPIE_DU_BINAIRE = re.compile(
    r"^\s*COPY\s+--from=construction\s+/caddy\s+/usr/bin/caddy\s*$", re.M
)


def test_la_version_compilee_est_celle_de_l_image_d_execution():
    """Un Caddy 2.12 posé sur l'image 2.11 mélangerait deux versions sans que rien ne le dise."""
    source = DOCKERFILE.read_text(encoding="utf-8")
    compilee = _VERSION_COMPILEE.search(source)
    if not compilee:
        #  Retour au binaire officiel : la compilation doit être retirée EN ENTIER.
        assert not _COPIE_DU_BINAIRE.search(source), "binaire copié sans `ARG CADDY_VERSION`"
        return
    tags = [tag for _, tag in _bases()]
    assert tags and all(tag and tag.startswith(compilee["v"]) for tag in tags), (
        f"Caddy compilé en {compilee['v']}, image d'exécution {tags} : aligner les deux mineures"
    )
    assert _COPIE_DU_BINAIRE.search(source), (
        "la version est compilée mais le binaire n'est pas copié : l'image sert encore le "
        "binaire officiel, et ses vulnérabilités"
    )


def test_le_binaire_et_curl_sont_verifies_dans_l_image():
    """La construction échoue si la version servie n'est pas celle compilée, ou si curl revient."""
    source = DOCKERFILE.read_text(encoding="utf-8")
    if _VERSION_COMPILEE.search(source):
        assert 'caddy version | grep -q "^${CADDY_VERSION} "' in source
    assert "! command -v curl" in source, "curl retiré de l'image (#2377) : sa preuve a disparu"
