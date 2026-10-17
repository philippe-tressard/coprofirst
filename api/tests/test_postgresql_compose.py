"""Le service PostgreSQL du compose : la base de la pile, fermée, sans secret connu (#1759, DI-7).

PostgreSQL est le seul moteur : le service démarre avec la pile, et l'API attend
elle-même qu'il réponde (`start.sh`). Ces contrôles tiennent ce qui ferait du mal — un port ouvert, un
mot de passe par défaut, des réglages qui useraient la carte SD ou céderaient la
durabilité.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((RACINE / "docker-compose.yml").read_text(encoding="utf-8"))
PG = COMPOSE["services"]["postgres"]


def _reglages() -> dict[str, str]:
    commande = PG["command"]
    return dict(commande[i + 1].split("=", 1) for i, m in enumerate(commande) if m == "-c")


def test_le_service_fait_partie_de_la_pile_sans_que_l_api_le_demarre():
    assert "profiles" not in PG, (
        "PostgreSQL est la base de l'application : derrière un profil, `docker compose "
        "up -d` démarrerait une API sans base"
    )
    #  🔴 Un `depends_on` ferait démarrer la base par `up -d api` — une base VIDE
    #  sur un nœud sans réplique (CLAUDE.md, règle d'or). L'API attend la base
    #  au démarrage (`utils/attendre_base`, appelé par `utils/preparer_bases`, que
    #  `start.sh` lance depuis #2053), sans jamais la démarrer.
    assert "postgres" not in COMPOSE["services"]["api"].get("depends_on", {}), (
        "`up -d api` démarrerait la base si elle est arrêtée"
    )
    assert "app.utils.preparer_bases" in (RACINE / "api" / "start.sh").read_text(encoding="utf-8")
    preparer = (RACINE / "api" / "app" / "utils" / "preparer_bases.py").read_text(encoding="utf-8")
    assert "from app.utils.attendre_base import" in preparer


def test_le_port_n_est_lie_qu_a_l_ip_du_lan_ou_a_la_boucle_locale():
    """La réplication passe par le LAN (DI-7b) ; jamais toutes les interfaces."""
    assert PG["ports"] == ["${PG_ECOUTE:-127.0.0.1}:5432:5432"], (
        "le port se lie à `PG_ECOUTE` (l'IP du nœud), 127.0.0.1 par défaut — "
        "jamais `5432:5432` nu, qui écouterait sur toutes les interfaces"
    )
    assert PG["networks"] == ["hostachy"]


def test_l_acces_reseau_exige_scram_et_la_replication_vient_de_l_autre_noeud():
    hba = (RACINE / "infra" / "postgresql" / "pg_hba.conf").read_text(encoding="utf-8")
    lignes = [
        li.split() for li in hba.splitlines() if li.strip() and not li.lstrip().startswith("#")
    ]
    assert lignes, "pg_hba.conf vide : tout serait refusé, ou le contrôle ne mesure plus rien"
    for champs in lignes:
        if champs[0] == "local":
            continue
        assert champs[-1] == "scram-sha-256", f"accès réseau sans scram : {champs}"
    replication = [c for c in lignes if c[1] == "replication"]
    #  Les IP des nœuds se lisent dans `lib-role.sh`, seule table « nœud ⇄ IP » :
    #  ce test ne les recopie pas (le dépôt est public, `test_hygiene_depot`).
    role = (RACINE / "scripts" / "lib" / "lib-role.sh").read_text(encoding="utf-8")
    ips = set(re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", role))
    assert len(ips) == 2, f"lib-role.sh devrait nommer les deux nœuds : {ips}"
    assert {c[3] for c in replication} == {f"{ip}/32" for ip in ips}
    assert {c[2] for c in replication} == {"replication"}
    assert any(v.startswith("hba_file=") for v in PG["command"])
    assert "./infra/postgresql/pg_hba.conf:/etc/postgresql/pg_hba.conf:ro" in PG["volumes"]


def test_le_role_de_replication_exige_son_mot_de_passe():
    script = (RACINE / "infra" / "postgresql" / "initdb" / "10-replication.sh").read_text(
        encoding="utf-8"
    )
    assert "mdp=${PG_REPLICATION_PASSWORD:-}" in script
    assert 'if [ -z "$mdp" ]; then' in script and "exit 1" in script
    environnement = dict(e.split("=", 1) for e in PG["environment"])
    assert environnement["PG_REPLICATION_PASSWORD"] == "${PG_REPLICATION_PASSWORD:-}"


def test_aucun_mot_de_passe_par_defaut():
    environnement = dict(e.split("=", 1) for e in PG["environment"])
    assert environnement["POSTGRES_PASSWORD"] == "${POSTGRES_PASSWORD:-}", (
        "vide sans `.env` : l'image refuse alors d'initialiser la base — jamais un secret écrit ici"
    )


def test_l_image_porte_une_mineure_explicite():
    nom, _, etiquette = PG["image"].partition(":")
    assert nom == "postgres" and etiquette.count(".") == 1, (
        "majeure.mineure, comme Caddy (#1602) : Dependabot propose les montées"
    )


def test_les_donnees_vivent_dans_un_volume_nomme():
    assert "pg_data:/var/lib/postgresql/data" in PG["volumes"]
    assert "pg_data" in COMPOSE["volumes"]


def test_les_reglages_menagent_la_carte_sans_ceder_la_durabilite():
    reglages = _reglages()
    #  Moins d'écritures : points de contrôle espacés, journal compressé.
    assert reglages["checkpoint_timeout"] == "15min"
    assert reglages["wal_compression"] == "on"
    #  La réplication en continu vers le standby (DI-7b) en a besoin.
    assert reglages["wal_level"] == "replica"
    #  Le journal gardé pour une réplique en retard : borné, sur une carte SD.
    assert reglages["wal_keep_size"] == "512MB"
    #  🔴 Jamais au prix d'un commit perdu : ces deux-là restent à leur défaut, actifs.
    for interdit in ("fsync", "synchronous_commit", "full_page_writes"):
        assert interdit not in reglages, f"`{interdit}` ne se règle pas ici : la durabilité prime"


def test_les_pages_portent_une_somme_de_controle():
    """Sans elles, `dialecte.verifier_integrite` ne saurait rien dire de la base."""
    environnement = dict(e.split("=", 1) for e in PG["environment"])
    assert environnement.get("POSTGRES_INITDB_ARGS") == "--data-checksums"


def test_la_base_dit_quand_elle_est_prete():
    assert "pg_isready" in " ".join(PG["healthcheck"]["test"])
