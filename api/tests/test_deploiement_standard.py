"""Le déploiement standard de CoproFirst : des images, jamais un build (#1755).

Lot DI-3 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.10, règle 8, D13). `deploiement/standard/compose.images.yml` se pose PAR-DESSUS
le `docker-compose.yml` de la racine, qui reste la seule description des services :
une copie complète de la composition aurait divergé au premier volume ajouté.

Ce que ce test tient :

- chaque service que la racine construit est remplacé, et seulement eux ;
- sa construction est retirée (`build: !reset`) — sans quoi une image introuvable
  serait construite en silence sur la machine ;
- son image est celle que la CI publie (`images.yml`), à la version
  `COPROFIRST_VERSION`, exigée ;
- l'archive jointe aux notes de version emporte tout ce que le mode d'emploi cite.

Le comportement de Compose sur ces fichiers (`!reset` compris) a été éprouvé sur
le standby le 08/10/2026 avec Compose 5.6 : `config` ne garde aucun `build`, et
refuse de lire sans version.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
SURCOUCHE = RACINE / "deploiement" / "standard" / "compose.images.yml"
LISEZMOI = RACINE / "deploiement" / "standard" / "LISEZMOI.md"
COMPOSE = RACINE / "docker-compose.yml"
IMAGES = RACINE / ".github" / "workflows" / "images.yml"
#: La liste des fichiers de l'archive, et sa fabrication.
NOTES = RACINE / "scripts" / "ci" / "lib-archive-deploiement.sh"


class _Lecteur(yaml.SafeLoader):
    """PyYAML ne connaît pas les étiquettes de Compose : `!reset` se lit en marqueur."""


_Lecteur.add_constructor("!reset", lambda _l, _n: "!reset")
#  `!override` remplace une liste héritée : on garde la liste, c'est elle qu'on juge.
_Lecteur.add_constructor("!override", lambda lecteur, noeud: lecteur.construct_sequence(noeud))

#: Les services que la surcouche règle SANS les construire : leur image est
#: l'officielle, et seule leur configuration change pour une réplique.
REGLES_SANS_IMAGE = {"postgres"}


def _yaml(chemin: Path) -> dict:
    return yaml.load(chemin.read_text(encoding="utf-8"), Loader=_Lecteur)  # noqa: S506 — SafeLoader


def _construits() -> set[str]:
    return {nom for nom, s in _yaml(COMPOSE)["services"].items() if s.get("build")}


def test_chaque_service_construit_prend_son_image():
    surcouche = _yaml(SURCOUCHE)["services"]
    construits = _construits()
    assert len(construits) >= 4, "le relevé de docker-compose.yml est cassé"
    assert set(surcouche) == construits | REGLES_SANS_IMAGE, (
        f"surcouche : {sorted(surcouche)} ; services construits par la racine : {sorted(construits)}"
        f" ; réglés sans image : {sorted(REGLES_SANS_IMAGE)}"
    )
    registre = yaml.safe_load(IMAGES.read_text(encoding="utf-8"))["env"]["REGISTRE"]
    for nom, service in surcouche.items():
        if nom in REGLES_SANS_IMAGE:
            continue
        assert service.get("build") == "!reset", f"{nom} : la construction n'est pas retirée"
        attendu = re.compile(
            rf"^{re.escape(registre)}/coprofirst-{re.escape(nom)}:\$\{{COPROFIRST_VERSION:\?.+\}}$"
        )
        assert attendu.match(service["image"]), f"{nom} : image inattendue « {service['image']} »"


def test_l_archive_emporte_ce_que_le_mode_d_emploi_cite():
    script = NOTES.read_text(encoding="utf-8")
    #  Le tableau des FICHIERS : une première colonne qui porte un chemin. Le
    #  tableau des réglages (`COPROFIRST_…`) n'en est pas un.
    cites = {
        c
        for c in re.findall(r"^\| `([^`]+)` \|", LISEZMOI.read_text(encoding="utf-8"), re.M)
        if re.search(r"[./]", c)
    }
    assert cites, "le tableau des fichiers du mode d'emploi est illisible"
    for fichier in cites:
        assert fichier in script, f"l'archive n'emporte pas {fichier}, que le mode d'emploi cite"
        assert (RACINE / fichier).exists(), f"{fichier} n'existe pas"


# ── La mise à jour nocturne (#1756) ──────────────────────────────────────────

MISE_A_JOUR = RACINE / "deploiement" / "standard" / "mise-a-jour.sh"


def _constante(nom: str) -> str:
    for ligne in MISE_A_JOUR.read_text(encoding="utf-8").splitlines():
        if ligne.startswith(f"{nom}="):
            return ligne.split("=", 1)[1].strip().strip('"')
    raise AssertionError(f"{nom} introuvable dans mise-a-jour.sh")


def test_la_mise_a_jour_vise_le_depot_le_registre_et_les_services_publies():
    from app.utils.plateforme import DEPOT_SOURCE

    assert DEPOT_SOURCE.endswith("/" + _constante("DEPOT")), (
        "le dépôt suivi n'est pas celui du source"
    )
    registre = yaml.safe_load(IMAGES.read_text(encoding="utf-8"))["env"]["REGISTRE"]
    assert _constante("REGISTRE") == registre
    assert set(_constante("SERVICES").split()) == _construits()


def test_la_mise_a_jour_sauvegarde_avant_de_toucher_au_service():
    """L'ordre est la promesse (D15) : rien ne s'arrête avant que tout soit prêt."""
    #  Le code seul : l'en-tête du script raconte le déroulé et en cite les gestes.
    texte = "\n".join(
        ligne
        for ligne in MISE_A_JOUR.read_text(encoding="utf-8").splitlines()
        if not ligne.lstrip().startswith("#")
    )
    ordre = [
        "pull --quiet",  # images tirées, service intact
        "stop api",  # premier geste qui coupe
        "export_copropriete verifier",  # la sauvegarde est réimportée à côté (PostgreSQL)…
        "integrity_check",  # … ou vérifiée en place (SQLite)…
        'sed -i "s/^COPROFIRST_VERSION=',  # … avant de poser la version
        "up -d --remove-orphans",
    ]
    positions = [texte.index(m) for m in ordre]
    assert positions == sorted(positions), dict(zip(ordre, positions))
    assert "COPROFIRST_SAUVEGARDES absent" in texte, "pas de mise à jour sans sauvegarde"


# ── PostgreSQL sur une réplique (DI-4 sous PostgreSQL) ───────────────────────


def test_le_postgresql_d_une_replique_n_est_pas_celui_de_la_reference():
    """Une réplique tient sur un serveur (D15) : ni réplication, ni port, ni IP de la référence."""
    pg = _yaml(SURCOUCHE)["services"]["postgres"]
    reference = _yaml(COMPOSE)["services"]["postgres"]
    assert "image" not in pg and "build" not in pg, (
        "l'image officielle, telle que la racine la nomme"
    )
    assert pg["ports"] == "!reset", "le port de la base ne s'ouvre pas sur le réseau local"
    montes = {v.split(":")[1] for v in pg["volumes"]}
    assert "/docker-entrypoint-initdb.d" not in montes, "pas de rôle de réplication"
    assert "/var/lib/postgresql/data" in montes, "le volume des données reste celui de la racine"
    hba = next(v.split(":")[0] for v in pg["volumes"] if v.endswith("/pg_hba.conf:ro"))
    fichier = RACINE / hba.removeprefix("./")
    assert fichier.exists() and hba.removeprefix("./") in NOTES.read_text(encoding="utf-8"), (
        "le pg_hba d'une réplique doit exister et partir dans l'archive"
    )
    lignes = [li for li in fichier.read_text(encoding="utf-8").splitlines() if li and li[0] != "#"]
    assert not [li for li in lignes if "replication" in li], lignes
    assert not re.search(r"192\.168\.", fichier.read_text(encoding="utf-8"))
    #  Et ce que la surcouche retire existe bien chez la référence : sinon elle ne
    #  retire plus rien, et ce test non plus ne mesure plus rien.
    assert any("initdb" in v for v in reference["volumes"]) and reference.get("ports")


def _corps(texte: str, fonction: str) -> str:
    #  La signature peut porter son commentaire (`{ # $1=… → …`) : il compte aussi.
    m = re.search(rf"^{fonction}\(\) \{{([^\n]*\n.*?)^\}}", texte, re.S | re.M)
    assert m, f"{fonction} introuvable"
    return m.group(1)


def test_le_moteur_se_lit_comme_chez_la_reference():
    """`moteur_de_url` est une COPIE déclarée : l'archive n'emporte pas `scripts/lib`."""
    reference = (RACINE / "scripts" / "lib" / "lib-replication.sh").read_text(encoding="utf-8")
    replique = MISE_A_JOUR.read_text(encoding="utf-8")
    assert _corps(replique, "moteur_de_url") == _corps(reference, "moteur_de_url"), (
        "les deux lectures du moteur ont divergé — recopier celle de lib-replication.sh"
    )


def test_le_listing_se_lit_comme_a_l_export_hors_site():
    """`listing_contient` est une COPIE déclarée, pour la même raison (#1820)."""
    reference = (RACINE / "scripts" / "lib" / "lib-export-hors-site.sh").read_text(encoding="utf-8")
    replique = MISE_A_JOUR.read_text(encoding="utf-8")
    assert _corps(replique, "listing_contient") == _corps(reference, "listing_contient"), (
        "les deux lectures d'un listing d'archive ont divergé — recopier celle de "
        "lib-export-hors-site.sh"
    )
