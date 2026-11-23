#!/usr/bin/env python3
"""Le `Caddyfile` se charge dans ses deux variantes, sur un vrai Caddy (claude-config#604).

Le `Caddyfile` importe les fragments d'une installation commune par un MOTIF
(`import commune/<nom>*.caddy`) que la surcouche `compose.commune.yml` monte :

- **propre** (5Hostachy, toute installation à une copropriété) : rien n'est monté,
  le motif n'importe rien, la configuration se charge — et `/uploads/*` est servi
  par Caddy après `forward_auth` ;
- **commune** : les deux fragments sont montés ; la première route de
  `/uploads/*` RELAIE à l'API (aucun `file_server`), et le service du front passe
  par la garde des pages.

`caddy adapt` traduit le `Caddyfile` en JSON, dans l'ordre où Caddy évaluera les
routes : c'est cet ordre qu'on lit, pas le texte. L'image est celle d'exécution de
`Dockerfile.caddy` (sa ligne `FROM caddy:…`), jamais recopiée ici.

    python scripts/ci/caddy_variantes.py            # docker requis
    python scripts/ci/caddy_variantes.py --selftest # la lecture du JSON, sans docker
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
COMMUNE = RACINE / "deploiement" / "standard" / "commune"
FRAGMENTS = ("fichiers.caddy", "garde-des-pages.caddy")


def image_caddy() -> str:
    """L'image d'exécution de `Dockerfile.caddy` : la dernière ligne `FROM caddy:…`."""
    texte = (RACINE / "Dockerfile.caddy").read_text(encoding="utf-8")
    images = re.findall(r"^FROM\s+(caddy:\S+)", texte, re.M)
    if not images:
        raise SystemExit("INCONNU — aucune ligne `FROM caddy:` dans Dockerfile.caddy")
    return images[-1]


def routes_du_site(config: dict) -> list[dict]:
    """Les routes du bloc `:80`, dans l'ordre d'évaluation (sous-route du site comprise)."""
    serveurs = config["apps"]["http"]["servers"]
    routes = next(iter(serveurs.values()))["routes"]
    #  Un site sans hôte : ses `handle` sont directement les routes du serveur.
    #  Avec hôte, Caddy les enveloppe dans une sous-route : on la déplie.
    if (
        len(routes) == 1
        and routes[0].get("handle", [{}])[0].get("handler") == "subroute"
    ):
        return routes[0]["handle"][0]["routes"]
    return routes


def _chemins(route: dict) -> list[str]:
    return [p for m in route.get("match", []) for p in m.get("path", [])]


def premiere_route(routes: list[dict], chemin: str) -> dict | None:
    return next((r for r in routes if chemin in _chemins(r)), None)


def route_attrape_tout(routes: list[dict]) -> dict | None:
    """Le dernier `handle { … }` : une route sans `match`."""
    return next((r for r in reversed(routes) if not r.get("match")), None)


def verdicts(config: dict, variante: str) -> list[str]:
    """Les fautes de la configuration traduite (liste vide : conforme)."""
    routes = routes_du_site(config)
    fautes = []
    uploads = premiere_route(routes, "/uploads/*")
    front = route_attrape_tout(routes)
    if uploads is None or front is None:
        return [
            f"{variante} : route /uploads/* ou route du front introuvable — INCONNU"
        ]
    texte_uploads, texte_front = json.dumps(uploads), json.dumps(front)
    if variante == "propre":
        if (
            "file_server" not in texte_uploads
            or "/auth/verifier-acces" not in texte_uploads
        ):
            fautes.append(
                "propre : /uploads/* n'est plus servi par Caddy après forward_auth"
            )
        if "/plateforme/aiguillage/hote" in texte_front:
            fautes.append(
                "propre : la garde des pages d'une installation commune est chargée"
            )
    else:
        if "file_server" in texte_uploads or '"reverse_proxy"' not in texte_uploads:
            fautes.append(
                "commune : la première route /uploads/* sert la racine au lieu de relayer"
            )
        if "/plateforme/aiguillage/hote" not in texte_front:
            fautes.append("commune : le front n'est pas gardé par l'aiguillage")
    return fautes


def adapter(dossier: Path, image: str) -> dict:
    sortie = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{dossier}:/etc/caddy:ro",
            "-e",
            "LEURRE_ADRESSE=",
            "-e",
            "LEURRE_CLE_MAINTENANCE=",
            image,
            "caddy",
            "adapt",
            "--config",
            "/etc/caddy/Caddyfile",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if sortie.returncode != 0:
        raise SystemExit(
            f"ÉCHEC — caddy adapt refuse la configuration :\n{sortie.stderr}"
        )
    return json.loads(sortie.stdout)


def principal() -> int:
    image = image_caddy()
    fautes = []
    for variante in ("propre", "commune"):
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            shutil.copy(RACINE / "Caddyfile", dossier / "Caddyfile")
            if variante == "commune":
                (dossier / "commune").mkdir()
                for nom in FRAGMENTS:
                    shutil.copy(COMMUNE / nom, dossier / "commune" / nom)
            dossier.chmod(0o755)
            fautes += verdicts(adapter(dossier, image), variante)
        print(f"{variante} : chargée par {image}")
    for faute in fautes:
        print(f"FAUTE  {faute}")
    print("OK — deux variantes conformes" if not fautes else "ÉCHEC")
    return 1 if fautes else 0


def _autotest() -> int:
    def site(*routes):
        return {
            "apps": {
                "http": {
                    "servers": {
                        "srv0": {
                            "routes": [
                                {
                                    "handle": [
                                        {"handler": "subroute", "routes": list(routes)}
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }

    racine = {
        "match": [{"path": ["/uploads/*"]}],
        "handle": [
            {"handler": "reverse_proxy", "rewrite": {"uri": "/auth/verifier-acces"}},
            {"handler": "file_server"},
        ],
    }
    relais = {
        "match": [{"path": ["/uploads/*"]}],
        "handle": [{"handler": "reverse_proxy", "upstreams": [{"dial": "api:8000"}]}],
    }
    front = {
        "handle": [{"handler": "reverse_proxy", "upstreams": [{"dial": "front:3000"}]}]
    }
    garde = {
        "handle": [
            {
                "handler": "subroute",
                "routes": [
                    {
                        "handle": [
                            {
                                "handler": "reverse_proxy",
                                "rewrite": {"uri": "/plateforme/aiguillage/hote"},
                            }
                        ]
                    },
                    {
                        "handle": [
                            {
                                "handler": "reverse_proxy",
                                "upstreams": [{"dial": "front:3000"}],
                            }
                        ]
                    },
                ],
            }
        ]
    }
    cas = [
        ("propre conforme", verdicts(site(racine, front), "propre"), 0),
        (
            "commune conforme : le relais d'abord",
            verdicts(site(relais, racine, garde), "commune"),
            0,
        ),
        (
            "commune : relais APRÈS la racine",
            verdicts(site(racine, relais, garde), "commune"),
            1,
        ),
        (
            "commune : front sans garde",
            verdicts(site(relais, racine, front), "commune"),
            1,
        ),
        ("propre : garde chargée", verdicts(site(racine, garde), "propre"), 1),
        ("route absente → INCONNU, pas OK", verdicts(site(front), "propre"), 1),
        (
            "image lue dans Dockerfile.caddy",
            [] if image_caddy().startswith("caddy:") else ["x"],
            0,
        ),
    ]
    echec = 0
    for nom, fautes, attendu in cas:
        ok = len(fautes) == attendu
        echec |= not ok
        print(f"{'PASS' if ok else 'FAIL'}  {nom}")
    return echec


if __name__ == "__main__":
    sys.exit(_autotest() if "--selftest" in sys.argv else principal())
