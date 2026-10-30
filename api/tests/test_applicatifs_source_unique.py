"""L'application se nomme une fois, la base mise à part (DI-7b, #1781).

Sous PostgreSQL, une RÉPLIQUE de la base tourne en permanence sur le standby.
Les scripts qui comptaient « tout hostachy » pour dire « ce nœud est actif »
y auraient vu un split-brain sans fin, et un `docker compose stop` sans liste
aurait arrêté la réplique. `scripts/lib/lib-applicatifs.sh` nomme l'application ;
ce contrôle tient :

- ses listes suivent `docker-compose.yml` (tout service, sauf la base) ;
- aucun script ne recompte `docker ps … name=hostachy` ;
- aucun script n'arrête ni ne démarre le compose SANS LISTE de services (#1999) :
  un `up` ou un `stop` qui ne nomme rien touche aussi la base. Le 15/10/2026, un
  `up -d --no-recreate` sans liste a relancé un primaire PostgreSQL sur un nœud
  rétrogradé (#1997), et `MaJ-Hostachy.sh` recréait le primaire par un `up` nu.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from tests.conftest import scripts_shell_versionnes

RACINE = Path(__file__).resolve().parents[2]
MODULE = RACINE / "scripts" / "lib" / "lib-applicatifs.sh"
COMPOSE = yaml.safe_load((RACINE / "docker-compose.yml").read_text(encoding="utf-8"))

#: La base : le seul service qui n'est pas de l'application.
BASE = "postgres"

#: Un `docker compose up|stop|down` en position de commande, SANS service nommé :
#: le verbe, ses options (`-d`, `--no-recreate`, `-t 30`…), puis la fin de la
#: commande. Un service, une variable de liste ou `"$@"` (la porte) le satisfont.
SANS_LISTE = re.compile(
    r"docker\s+compose(?:\s+-f\s+\S+)?\s+(?:up|stop|down)((?:\s+-[-\w]+(?:\s+\d+)?)*)"
    #  Fin de commande — un guillemet qui FERME (pas celui qui ouvre `"$@"`).
    r"\s*(?:$|[;&|>)`]|2>|[\"'](?![$\w]))"
)
#: `demarrer_conteneurs` appelée sans argument : un `up` sans liste, derrière la porte.
DEMARRER_NU = re.compile(r"\bdemarrer_conteneurs\s*(?:$|[;&|>)]|2>|[\"'](?![$\w]))")

#: Les démarrages SANS LISTE qui restent, et pourquoi : `{script: (nombre, raison)}`.
#: Ils démarrent « selon le profil », juste après avoir décidé de la base. La liste
#: ne fait que baisser : une entrée dont le compte change échoue. Suivi des deux de
#: `bascule.sh` : #2318.
DEMARRAGES_SANS_LISTE = {
    "scripts/exploitation/bascule.sh": (
        2,
        "rollback (le primaire local reprend après l'isolement du pair promu) et "
        "phase 5 chez le pair, dont la réplique vient d'être promue — chemin de "
        "nuit éprouvé, à expliciter dans un lot qui le rejoue en conditions réelles",
    ),
    "scripts/exploitation/restaurer-copie-hors-site.sh": (
        1,
        "la base neuve est déjà démarrée et importée (étape 3) : l'application suit",
    ),
    "scripts/lib/lib-parite.sh": (
        1,
        "autotest de la porte elle-même : un commit illisible n'empêche pas le démarrage",
    ),
}


def _liste(nom: str) -> list[str]:
    m = re.search(rf'^{nom}="([^"]+)"', MODULE.read_text(encoding="utf-8"), re.M)
    assert m, f"`{nom}` n'est plus déclaré dans lib-applicatifs.sh"
    return m.group(1).split()


def _scripts() -> list[Path]:
    trouves = scripts_shell_versionnes()
    assert len(trouves) >= 50, "la portée des scripts a changé : le contrôle ne mesure plus rien"
    return trouves


def test_les_services_applicatifs_sont_ceux_du_compose_sauf_la_base():
    services = set(COMPOSE["services"]) - {BASE}
    assert set(_liste("SERVICES_APPLICATIFS")) == services
    assert BASE in COMPOSE["services"], "la base n'est plus dans le compose : revoir ce contrôle"
    assert _liste("SERVICE_BASE") == [BASE]


def test_les_conteneurs_suivent_les_services_au_meme_rang():
    attendus = [COMPOSE["services"][s]["container_name"] for s in _liste("SERVICES_APPLICATIFS")]
    assert _liste("CONTENEURS_APPLICATIFS") == attendus


def test_aucun_script_ne_recompte_tout_hostachy():
    fautes = [
        f"{p.relative_to(RACINE).as_posix()}:{n}"
        for p in _scripts()
        if p != MODULE
        for n, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "filter name=hostachy" in ligne and not ligne.lstrip().startswith("#")
    ]
    assert not fautes, (
        "compter « tout hostachy » compte aussi la réplique de la base — employer "
        f"`compter_applicatifs` ou `$COMPTER_APPLICATIFS` : {fautes}"
    )


#: Un commentaire en fin de ligne (`source … # demarrer_conteneurs`) n'est pas du code.
COMMENTAIRE_FINAL = re.compile(r"\s+#\s.*$")


def _lignes_de_code(p: Path) -> list[tuple[int, str]]:
    return [
        (n, COMMENTAIRE_FINAL.sub("", ligne))
        for n, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if not ligne.lstrip().startswith("#")
    ]


def test_aucun_up_ni_stop_du_compose_sans_liste():
    """Zéro exception : même un message qui NOMME le geste à un humain le nomme
    avec sa liste — c'est la commande qu'il recopiera."""
    fautes = [
        f"{p.relative_to(RACINE).as_posix()}:{n}"
        for p in _scripts()
        for n, ligne in _lignes_de_code(p)
        if SANS_LISTE.search(ligne)
    ]
    assert not fautes, (
        "un `docker compose up|stop|down` sans liste démarre ou arrête aussi la base — "
        f"nommer les services (`$SERVICES_APPLICATIFS`, `$SERVICE_BASE`, "
        f"`$SERVICES_DU_NOEUD`) : {fautes}"
    )


def test_demarrer_conteneurs_sans_liste_seulement_declare():
    vus: dict[str, int] = {}
    for p in _scripts():
        n = sum(1 for _, ligne in _lignes_de_code(p) if DEMARRER_NU.search(ligne))
        if n:
            vus[p.relative_to(RACINE).as_posix()] = n
    attendus = {rel: nombre for rel, (nombre, _) in DEMARRAGES_SANS_LISTE.items()}
    assert vus == attendus, (
        "`demarrer_conteneurs` sans liste démarre aussi la base : passer la liste "
        "(`$SERVICES_DU_NOEUD`), ou déclarer l'appel dans DEMARRAGES_SANS_LISTE avec "
        f"sa raison — vus {vus}, déclarés {attendus}"
    )


def test_le_motif_voit_les_gestes_du_15_10():
    """Cas zéro : les écritures fautives de #1997 et #1999 sont refusées, et ce qui
    nomme ses services ne l'est pas."""
    fautives = [
        "    docker compose up -d --no-recreate",  # auto-deploy, servir_images (#1997)
        '    docker compose -f "$REPO/docker-compose.yml" up --force-recreate -d',  # MaJ (#1999)
        '    docker compose -f "$REPO/docker-compose.yml" up -d',  # MaJ (#1999)
        '"cd /opt/5hostachy && docker compose stop 2>/dev/null"',  # health-watch, isolement
        "docker compose down -t 30;",
    ]
    assert all(SANS_LISTE.search(f) for f in fautives), [
        f for f in fautives if not SANS_LISTE.search(f)
    ]
    innocentes = [
        '    docker compose up -d "$@"',
        "docker compose stop $SERVICES_APPLICATIFS 2>/dev/null",
        'docker compose up -d --no-recreate "$SERVICE_BASE"',
        "docker compose stop postgres >/dev/null",
        "docker compose ps",
    ]
    assert not any(SANS_LISTE.search(i) for i in innocentes)
    assert DEMARRER_NU.search("  if demarrer_conteneurs; then")
    assert DEMARRER_NU.search("demarrer_conteneurs >/dev/null 2>&1 || echec")
    assert not DEMARRER_NU.search("demarrer_conteneurs $A_DEMARRER >> /dev/null")
    assert not DEMARRER_NU.search("demarrer_conteneurs() {")
