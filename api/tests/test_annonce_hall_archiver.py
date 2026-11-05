"""« Archiver » et « Restaurer » une affiche de hall acceptent le corps que le site envoie (#2524).

## Le défaut

`PATCH /annonces-hall/{annonce_id}` prenait `AnnonceHallArchive`, dont DEUX champs
étaient requis : `archivee` et `archivee_manuellement`. Le site n'envoie que
`{ archivee }` (`annoncesHall.archiver`, `front/src/lib/api/index.ts`) : la route
répondait 422, et les deux gestes d'Espace CS › Annonces Hall restaient sans effet
depuis v2.93.0. `archivee_manuellement` est un champ de LECTURE (`_to_read`) qu'on
avait recopié dans le schéma d'ENTRÉE ; le gestionnaire ne lisait que `archivee`.

## Ce que ce test vérifie

Le corps exact du site passe la validation et archive, puis restaure, l'affiche ;
un client qui envoie encore les deux champs (l'app iOS, coprofirst-ios#15) reste
accepté : le champ en trop est ignoré, il ne décide rien.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.models.core import RoleUtilisateur
from app.routers import annonces_hall
from app.routers.annonces_hall_schemas import AnnonceHallArchive
from tests.aides_annonce_hall import contexte_fixture, creer  # noqa: F401 — la fixture `contexte`
from tests.aides_base import compte

CLIENT_FRONT = Path(__file__).resolve().parents[2] / "front/src/lib/api/index.ts"


def _corps_du_site() -> dict:
    """Le corps que `annoncesHall.archiver` envoie, lu dans le client du site."""
    source = CLIENT_FRONT.read_text(encoding="utf-8")
    m = re.search(
        r"archiver:\s*\(id: number, archivee: boolean\)\s*=>\s*\n?\s*api\.patch<[^>]*>\([^,]+,\s*(\{[^}]*\})",
        source,
    )
    assert m, "le client du site n'envoie plus `archiver` sous la forme attendue : relire ce test"
    cles = [c.strip() for c in m.group(1).strip("{} ").split(",") if c.strip()]
    return {cle: True for cle in cles}


def _archiver(session, annonce_id: int, corps: dict):
    admin = compte(session, prefixe="admin", roles_json=RoleUtilisateur.admin.value)
    body = AnnonceHallArchive.model_validate(corps)
    return annonces_hall.archiver_annonce(
        annonce_id=annonce_id, body=body, session=session, user=admin
    )


def test_le_corps_du_site_ne_porte_que_archivee():
    assert _corps_du_site() == {"archivee": True}


def test_archiver_puis_restaurer_avec_le_corps_du_site(contexte):
    session, cs = contexte
    annonce = creer(session, cs)
    rendu = _archiver(session, annonce.id, _corps_du_site())
    assert rendu.archivee is True and rendu.archivee_manuellement is True
    rendu = _archiver(session, annonce.id, {"archivee": False})
    assert rendu.archivee_manuellement is False


def test_un_client_qui_envoie_encore_les_deux_champs_reste_accepte(contexte):
    session, cs = contexte
    annonce = creer(session, cs)
    rendu = _archiver(session, annonce.id, {"archivee": True, "archivee_manuellement": False})
    assert rendu.archivee_manuellement is True, "seul `archivee` décide"
