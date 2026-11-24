"""La branche `replica` et sa promotion sont retirées (#3009, 24/11/2026).

Depuis #2210, une installation suit son BAIL (`registre/canaux.py`) : la version que
la référence lui signe. `replica` n'avançait plus que par le workflow « Promotion »,
et aucune installation ne la lisait (relevé du registre au ticket). Ce test refuse
qu'elle revienne :

- les fichiers de la promotion n'existent plus, et rien ne les appelle ;
- aucun code, script ni workflow ne lit la branche (`origin/replica`,
  `refs/heads/replica`, une comparaison GitHub vers `...replica`) ;
- le rôle « Réplique » ne suit plus une branche (`installation.cible_suivie`).

Le MOT `replica` reste ailleurs, sous d'autres sens : `wal_level=replica` et
`session_replication_role = replica` (PostgreSQL), l'ancien canal-branche que
`registre/canaux.suivi_de` relit encore pour un retour arrière (#2210), la
migration 0006 et l'histoire datée des spécifications. Ce test ne le chasse donc
pas : il cherche les LECTURES de la branche.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

from app.utils import installation

RACINE = pathlib.Path(__file__).resolve().parents[2]

#: Ce que la promotion était — aucun ne doit revenir.
RETIRES = (
    ".github/workflows/promotion.yml",
    "scripts/ci/promotion.sh",
    "scripts/ci/lib-replica.sh",
    "api/tests/test_promotion_replica.py",
)

#: Une LECTURE de la branche, sous toutes les formes que le dépôt a connues.
LECTURE_DE_LA_BRANCHE = re.compile(
    r"origin/replica\b|refs/heads/replica\b|\.\.\.replica\b"
    r"|(?<![\w-])promotion\.(?:sh|yml)\b|lib-replica\.sh\b"
)


def _suivis() -> list[str]:
    sortie = subprocess.run(
        ["git", "ls-files"], cwd=RACINE, capture_output=True, text=True, check=True
    ).stdout.split()
    assert len(sortie) > 500, "le dépôt n'est pas lu en entier"  # cas zéro
    return sortie


@pytest.mark.parametrize("chemin", RETIRES)
def test_la_promotion_ne_revient_pas(chemin):
    assert not (RACINE / chemin).exists(), chemin


def test_rien_ne_lit_plus_la_branche():
    lecteurs = []
    for rel in _suivis():
        if rel == "api/tests/test_replica_retiree.py" or not rel.endswith(
            (".py", ".sh", ".yml", ".yaml", ".ts", ".svelte", ".md", ".mjs")
        ):
            continue
        texte = (RACINE / rel).read_text(encoding="utf-8", errors="replace")
        lecteurs += [f"{rel} : {m.group(0)}" for m in LECTURE_DE_LA_BRANCHE.finditer(texte)]
    assert lecteurs == [], lecteurs


def test_le_controle_voit_une_lecture():
    """Témoin : chaque forme connue est bien vue (`standards/04` §2)."""
    for fautif in (
        "git rev-parse origin/replica",
        'git push origin "$c:refs/heads/replica"',
        "compare/7bec36e...replica",
        "bash scripts/ci/promotion.sh --selftest",
        "source lib-replica.sh",
    ):
        assert LECTURE_DE_LA_BRANCHE.search(fautif), fautif
    #  …et les homonymes ne le sont pas : la bascule PostgreSQL garde ses scripts.
    for homonyme in ("- wal_level=replica", "lib-promotion.sh", "lib-replication.sh"):
        assert not LECTURE_DE_LA_BRANCHE.search(homonyme), homonyme


def test_aucun_role_ne_suit_la_branche():
    for role in (*installation.ROLES, installation.INCONNU):
        assert installation.cible_suivie(role, "3.124.1") != "replica", role
