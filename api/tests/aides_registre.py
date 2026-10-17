"""Le registre des installations ALLUMÉ pour un test — une seule mise en place (§4.11).

Partagée par les tests du registre (inscription, bail, sauvegarde) : la base
`plateforme` est posée par SA chaîne de migrations (`registre.migrer`), le
registre se croit la référence sous son nom dédié, et toute lecture de sa base —
par la route (`get_session_plateforme`) comme par la sauvegarde (`base.moteur`) —
tombe sur la base du test.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from sqlmodel import Session

from app.config import get_settings
from app.main import app
from app.registre import base, migrer
from app.utils.limiter import limiter
from tests.aides_base import moteur_de_test
from tests.aides_caddy import bloc_handle, caddyfile

#: Le nom dédié du registre, dans les tests.
HOTE = "registre.example"


def prefixe_api_du_caddyfile() -> str:
    """Le préfixe du client (`inscription.client.PREFIXE_API`), confronté au `Caddyfile`
    versionné : c'est ce qu'un envoi au registre traverse réellement en production.
    Le jour où l'un change sans l'autre, les tests du registre échouent (#1878).
    """
    from app.inscription.client import PREFIXE_API

    bloc = bloc_handle(caddyfile(), f"{PREFIXE_API}/*")
    assert bloc is not None and f"uri strip_prefix {PREFIXE_API}" in bloc, (
        f"Caddyfile : aucun bloc `handle {PREFIXE_API}/*` qui retire `{PREFIXE_API}` — "
        "les envois au registre n'atteindraient pas l'API"
    )
    return PREFIXE_API


@contextmanager
def registre_allume(monkeypatch) -> Iterator:
    """Rend le moteur de la base `plateforme`, migrée ; tout est défait en sortie.

    🔴 Sous le rôle de la PRODUCTION : celui du registre n'est pas superutilisateur,
    et PostgreSQL lui refuse de différer les clés (`dialecte.differer_cles_etrangeres`).
    La suite tourne en superutilisateur et ne le montrerait pas : le refus est donc
    simulé pour TOUT test du registre. #1972 ne le simulait que pour la restauration,
    et l'épreuve de la sauvegarde nocturne a échoué en production pendant que ses
    tests restaient verts (17/10/2026).
    """
    import app.utils.import_copropriete as import_copropriete

    def refus(_connexion):
        raise RuntimeError("permission denied to set parameter session_replication_role")

    monkeypatch.setattr(import_copropriete, "differer_cles_etrangeres", refus)
    moteur = moteur_de_test(schema=False)
    migrer.migrer(moteur)
    reglages = get_settings()
    monkeypatch.setattr(reglages, "plateforme_database_url", "postgresql+psycopg://essai")
    monkeypatch.setattr(reglages, "hote_registre", HOTE)
    monkeypatch.setattr(base, "est_reference", lambda: True)
    monkeypatch.setattr(base, "moteur", lambda: moteur)

    def _session():
        with Session(moteur) as s:
            yield s

    app.dependency_overrides[base.get_session_plateforme] = _session
    limiter.reset()
    try:
        yield moteur
    finally:
        app.dependency_overrides.pop(base.get_session_plateforme, None)
        limiter.reset()


@contextmanager
def installation_branchee(monkeypatch, dossier) -> Iterator:
    """Le registre allumé, sa clé des baux posée, et une RÉPLIQUE qui l'appelle.

    Les appels HTTP de l'installation (`inscription.client`) sont routés vers
    l'application de test, sous le nom dédié du registre : les deux côtés parlent
    pour de vrai, le bail est réellement signé puis vérifié. Rend le moteur de la
    base `plateforme`.
    """
    from fastapi.testclient import TestClient

    from app.inscription import client, cles
    from app.registre import signature
    from app.utils import installation

    ref_privee, ref_publique = signature.generer_paire()
    reglages = get_settings()
    monkeypatch.setattr(reglages, "cle_signature_baux", signature.en_base64(ref_privee))
    monkeypatch.setattr(reglages, "installation_dir", str(dossier / "installation"))
    monkeypatch.setattr(reglages, "registre_url", f"https://{HOTE}")
    monkeypatch.setattr(reglages, "installation_essai", False)
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "replique")
    monkeypatch.setattr(cles, "CLES_REFERENCE", {1: ref_publique})

    prefixe = prefixe_api_du_caddyfile()

    def poster(url, content, headers, timeout):
        #  Comme Caddy : seul ce qui commence par le préfixe de l'API y arrive, et
        #  sans lui. Le reste partirait au FRONT — ici, un 404 (#1878 : le client
        #  postait sans `/api`, et l'aide, qui passait le chemin tel quel, le taisait).
        chemin = url.removeprefix(f"https://{HOTE}")
        if not chemin.startswith(prefixe + "/"):
            return httpx.Response(404, text="servi par le front, pas par l'API")
        return TestClient(app).post(
            chemin.removeprefix(prefixe), content=content, headers={**headers, "host": HOTE}
        )

    monkeypatch.setattr(client.httpx, "post", poster)
    with registre_allume(monkeypatch) as moteur:
        yield moteur
