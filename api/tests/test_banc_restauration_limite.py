"""La limite du banc de restauration reste VRAIE (#2476).

`restaurer-copie-hors-site.sh --banc` fait naître son PostgreSQL d'un `docker run`,
sans la configuration du service `postgres` du compose ; ce qu'il ne reprend pas
est nommé UNE fois (`BANC_PG_NON_REPRODUIT`), rappelé à chaque passage et dit dans
`docs/restauration-complete.md`. Ce contrôle confronte cette liste au compose :
un réglage ajouté au service, et que le banc ignorerait, l'oblige à être déclaré
— ou repris ; une entrée qui ne correspond plus à rien est refusée.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = (RACINE / "scripts" / "exploitation" / "restaurer-copie-hors-site.sh").read_text(
    encoding="utf-8"
)
PG = yaml.safe_load((RACINE / "docker-compose.yml").read_text(encoding="utf-8"))["services"][
    "postgres"
]

#: Ce qui ne change rien à ce que le banc éprouve — l'archive et l'import.
SANS_EFFET = {
    "container_name": "le banc nomme le sien (`banc_restau_pg`)",
    "restart": "un conteneur jetable, détruit en sortie",
    "stop_grace_period": "le banc le détruit, il ne l'arrête pas",
    "logging": "la rotation des journaux d'un serveur de quelques minutes",
    "ports": "le banc n'expose rien : l'API le joint par son réseau jetable",
    "healthcheck": "le banc attend `pg_isready` lui-même",
    "networks": "le banc a son réseau jetable (`banc_restau_net`)",
}
#: Repris par le banc (en partie : le détail manquant est déclaré).
REPRIS = {"image", "environment", "volumes"}


def _declares() -> set[str]:
    m = re.search(r'^\s*BANC_PG_NON_REPRODUIT="([^"]*)"', SCRIPT, re.M)
    assert m, "BANC_PG_NON_REPRODUIT introuvable dans restaurer-copie-hors-site.sh"
    return set(m.group(1).split())


def _env_du_banc() -> set[str]:
    m = re.search(r"docker run -d --name banc_restau_pg(.*?)\"\$IMAGE_PG\"", SCRIPT, re.S)
    assert m, "le banc ne lance plus son PostgreSQL par `docker run` : retirer la limite"
    return set(re.findall(r"-e (\w+)", m.group(1)))


def _non_repris() -> set[str]:
    cles = set(PG) - set(SANS_EFFET) - REPRIS
    montages = {Path(v.split(":")[0]).name for v in PG["volumes"] if v.startswith(("./", "/"))}
    env = {e.split("=", 1)[0] for e in PG["environment"]} - _env_du_banc()
    return cles | montages | env


def test_ce_que_le_banc_ne_reprend_pas_est_declare():
    oublies = _non_repris() - _declares()
    assert not oublies, (
        f"le service `postgres` porte {sorted(oublies)}, que le banc ne reprend pas : "
        "l'ajouter à BANC_PG_NON_REPRODUIT (et à la limite de docs/restauration-complete.md), "
        "ou le reprendre dans le banc"
    )


def test_aucune_entree_de_la_limite_ne_vit_plus():
    perimes = _declares() - _non_repris()
    assert not perimes, f"BANC_PG_NON_REPRODUIT nomme {sorted(perimes)}, qui n'est plus à déclarer"


def test_la_limite_est_dite_au_banc_et_dans_la_procedure():
    assert _declares(), "cas zéro : une limite vide ne dit rien"
    assert "$BANC_PG_NON_REPRODUIT" in SCRIPT.split("BANC_PG_NON_REPRODUIT=", 1)[1]
    doc = (RACINE / "docs" / "restauration-complete.md").read_text(encoding="utf-8")
    assert "Limite connue** (#2476)" in doc
    assert set(SANS_EFFET) <= set(PG), "SANS_EFFET nomme une clé que le service n'a plus"
