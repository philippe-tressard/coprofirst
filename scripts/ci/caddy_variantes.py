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


def resume(routes: list[dict]) -> str:
    """Les routes dans l'ordre : chemins et gestionnaires — de quoi lire une faute."""
    lignes = []
    for r in routes:
        gestes = re.findall(r'"handler": "(\w+)"', json.dumps(r))
        lignes.append(
            f"  {_chemins(r) or '(sans chemin)'} → {', '.join(dict.fromkeys(gestes))}"
        )
    return "\n".join(lignes)


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
        #  Caddy FUSIONNE deux `handle` de même matcher en une route : le relais et
        #  le service de la racine y sont tous deux. Qui répond ne se lit pas ici,
        #  il se constate par une vraie requête (`eprouver`).
        if '"api:8000"' not in texte_uploads:
            fautes.append("commune : aucun relais vers l'API sur /uploads/*")
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


# ── Le comportement : une vraie requête, des amonts factices ─────────────────
#  Les faux `api` et `front` sont des Caddy de la MÊME image (aucune image de
#  plus à suivre) : l'API répond 204 à `verifier-acces` pour la session « ok »,
#  401 sinon, 204 à l'aiguillage, et « relais-api » à tout le reste ; son journal
#  dit quels chemins elle a reçus.
FAUX_API = """{
\tadmin off
}
:8000 {
\tlog {
\t\toutput stdout
\t\tformat json
\t}
\t@session header Cookie *ok*
\thandle /auth/verifier-acces {
\t\trespond @session 204
\t\trespond 401
\t}
\thandle /plateforme/aiguillage/hote {
\t\trespond 204
\t}
\thandle {
\t\trespond "relais-api" 200
\t}
}
"""
FAUX_FRONT = '{\n\tadmin off\n}\n:3000 {\n\trespond "front" 200\n}\n'
TEMOIN = "photos/temoin.txt"


def _docker(*args: str, verifier: bool = True) -> str:
    sortie = subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=False
    )
    if verifier and sortie.returncode != 0:
        raise SystemExit(
            f"INCONNU — docker {' '.join(args[:2])} : {sortie.stderr.strip()}"
        )
    return sortie.stdout


def _get(port: str, chemin: str, session: bool) -> tuple[int, str]:
    import urllib.error
    import urllib.request

    requete = urllib.request.Request(f"http://127.0.0.1:{port}{chemin}")
    if session:
        requete.add_header("Cookie", "access_token=ok")
    try:
        with urllib.request.urlopen(requete, timeout=10) as r:  # noqa: S310 (local)
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def attendus(variante: str) -> list[tuple[str, bool, int, str]]:
    """(chemin, session, statut, corps) attendus — la règle, en une table PURE."""
    fichier = f"/uploads/{TEMOIN}"
    if variante == "propre":
        return [(fichier, True, 200, "TEMOIN"), (fichier, False, 401, "")]
    return [(fichier, True, 200, "relais-api"), ("/", True, 200, "front")]


def eprouver(dossier: Path, image: str, variante: str) -> list[str]:
    """Lance Caddy sur `dossier` entre deux amonts factices, et le juge à ses réponses."""
    nom = f"caddy-variante-{variante}"
    amonts = Path(tempfile.mkdtemp())
    for fichier, texte in (("api", FAUX_API), ("front", FAUX_FRONT)):
        (amonts / fichier).mkdir()
        (amonts / fichier / "Caddyfile").write_text(texte, encoding="utf-8")
    (amonts / "srv" / "uploads" / "photos").mkdir(parents=True)
    (amonts / "srv" / "uploads" / TEMOIN).write_text("TEMOIN", encoding="utf-8")
    for chemin in amonts.rglob("*"):
        chemin.chmod(0o755 if chemin.is_dir() else 0o644)
    amonts.chmod(0o755)
    fautes: list[str] = []
    _docker("network", "create", nom)
    try:
        for alias in ("api", "front"):
            _docker(
                "run",
                "-d",
                "--name",
                f"{nom}-{alias}",
                "--network",
                nom,
                "--network-alias",
                alias,
                "-v",
                f"{amonts / alias}:/etc/caddy:ro",
                image,
            )
        _docker(
            "run",
            "-d",
            "--name",
            nom,
            "--network",
            nom,
            "-p",
            "127.0.0.1::80",
            "-v",
            f"{dossier}:/etc/caddy:ro",
            "-v",
            f"{amonts / 'srv'}:/srv:ro",
            "-e",
            "LEURRE_ADRESSE=",
            "-e",
            "LEURRE_CLE_MAINTENANCE=",
            image,
        )
        port = _docker("port", nom, "80/tcp").strip().rsplit(":", 1)[-1]
        import time

        for _ in range(30):
            try:
                _get(port, "/", True)
                break
            except OSError:
                time.sleep(1)
        for chemin, session, statut, corps in attendus(variante):
            recu = _get(port, chemin, session)
            if recu[0] != statut or (corps and recu[1].strip() != corps):
                fautes.append(
                    f"{variante} : {chemin} (session={session}) → {recu}, attendu {statut} {corps!r}"
                )
        journal = _docker("logs", f"{nom}-api", verifier=False)
        if variante == "commune" and "/auth/verifier-acces" in journal:
            fautes.append(
                "commune : Caddy a interrogé verifier-acces — il sert sa racine"
            )
        if variante == "propre" and "/auth/verifier-acces" not in journal:
            fautes.append("propre : le fichier a été servi sans forward_auth")
        if fautes:
            print(_docker("logs", nom, verifier=False)[-3000:])
    finally:
        for conteneur in (nom, f"{nom}-api", f"{nom}-front"):
            _docker("rm", "-f", conteneur, verifier=False)
        _docker("network", "rm", nom, verifier=False)
        shutil.rmtree(amonts, ignore_errors=True)
    return fautes


IMPORT_RELAIS = "\timport commune/fichiers*.caddy\n"


def relais_deplace(caddyfile: str) -> str:
    """Le témoin fautif (PURE) : l'import du relais placé APRÈS le service de la racine."""
    sans = caddyfile.replace(IMPORT_RELAIS, "", 1)
    debut = sans.index("\thandle /uploads/* {")
    fin = sans.index("\n\t}\n", debut) + len("\n\t}\n")
    return sans[:fin] + IMPORT_RELAIS + sans[fin:]


def principal() -> int:
    image = image_caddy()
    fautes = []
    #  Le troisième passage est le contrôle qui s'éprouve : relais placé après la
    #  racine, la variante commune DOIT échouer — sinon les requêtes ne jugent rien.
    for variante in ("propre", "commune", "temoin-fautif"):
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            texte = (RACINE / "Caddyfile").read_text(encoding="utf-8")
            if variante == "temoin-fautif":
                texte = relais_deplace(texte)
            (dossier / "Caddyfile").write_text(texte, encoding="utf-8")
            if variante != "propre":
                (dossier / "commune").mkdir()
                for nom in FRAGMENTS:
                    shutil.copy(COMMUNE / nom, dossier / "commune" / nom)
            dossier.chmod(0o755)
            config = adapter(dossier, image)
            if variante == "temoin-fautif":
                if eprouver(dossier, image, "commune"):
                    print("témoin fautif : refusé, le contrôle discrimine")
                else:
                    fautes.append(
                        "le relais placé après la racine passe : le contrôle ne juge rien"
                    )
                continue
            fautes_variante = verdicts(config, variante) + eprouver(
                dossier, image, variante
            )
            fautes += fautes_variante
        print(f"{variante} : chargée par {image}")
        if fautes_variante:
            print(resume(routes_du_site(config)))
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
            "commune : aucun relais vers l'API",
            verdicts(site(racine, garde), "commune"),
            1,
        ),
        (
            "attendus : propre sert le témoin à la session, 401 sans elle",
            []
            if attendus("propre")
            == [
                ("/uploads/photos/temoin.txt", True, 200, "TEMOIN"),
                ("/uploads/photos/temoin.txt", False, 401, ""),
            ]
            else ["x"],
            0,
        ),
        (
            "attendus : commune relaie, jamais le témoin",
            [] if all(c != "TEMOIN" for *_, c in attendus("commune")) else ["x"],
            0,
        ),
        (
            "commune : front sans garde",
            verdicts(site(relais, racine, front), "commune"),
            1,
        ),
        ("propre : garde chargée", verdicts(site(racine, garde), "propre"), 1),
        ("route absente → INCONNU, pas OK", verdicts(site(front), "propre"), 1),
        (
            "témoin fautif : le relais suit la racine",
            []
            if relais_deplace(
                "a\n\timport commune/fichiers*.caddy\n\thandle /uploads/* {\n\t\tx\n\t}\nz"
            )
            == "a\n\thandle /uploads/* {\n\t\tx\n\t}\n\timport commune/fichiers*.caddy\nz"
            else ["x"],
            0,
        ),
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
