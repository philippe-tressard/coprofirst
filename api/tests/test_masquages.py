"""Masquer ce que publie un autre résident — pour soi seul (#2861).

La règle vit dans `utils/masquage` ; ces tests l'éprouvent par les vraies routes :
le geste (`/masquages`), chaque liste où il s'applique — annonces, réponses, fil,
suites et messages d'une affaire — et celle où il ne s'applique pas : une idée,
dont l'auteur ne se dit pas. Le conseil syndical et l'administration voient
tout, ne masquent pas et ne se masquent pas.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.communaute import Idee, PetiteAnnonce, ReponseCommunaute
from app.models.core import RoleUtilisateur
from app.models.tickets import MessageTicket, TicketEvolution
from app.utils import masquage
from tests.aides_base import compte
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _voisin(moteur, **champs) -> int:
    with Session(moteur) as s:
        return compte(s, prefixe="voisin", nom="Durand", prenom="Reine", **champs).id


def _poser(moteur, *objets) -> list[int]:
    with Session(moteur) as s:
        for o in objets:
            s.add(o)
        s.commit()
        return [o.id for o in objets]


def _titres(http, chemin: str, cle: str = "titre") -> set[str]:
    r = http.get(chemin)
    assert r.status_code == 200, r.text
    return {e[cle] for e in r.json()}


# ── Le geste ──────────────────────────────────────────────────────────────────


def test_masquer_lister_demasquer(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin = _voisin(moteur)
    r = http.post("/masquages", json={"auteur_id": voisin})
    assert r.status_code == 201, r.text
    assert r.json()["auteur"] == "Reine DURAND"
    #  Un second appui rend le même masque, sans doublon.
    assert http.post("/masquages", json={"auteur_id": voisin}).status_code == 201
    assert [m["auteur_id"] for m in http.get("/masquages").json()] == [voisin]
    assert http.delete(f"/masquages/{voisin}").status_code == 204
    assert http.get("/masquages").json() == []


def test_les_refus(moteur):
    http, moi = client_http(moteur, RoleUtilisateur.propriétaire)
    cs = _voisin(moteur, roles_json="conseil_syndical")
    assert http.post("/masquages", json={"auteur_id": moi}).json()["detail"] == masquage.REFUS_SOI
    r = http.post("/masquages", json={"auteur_id": cs})
    assert (r.status_code, r.json()["detail"]) == (422, masquage.REFUS_MODERATEUR_CIBLE)
    assert http.post("/masquages", json={"auteur_id": 999_999}).status_code == 404
    moderateur, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    r = moderateur.post("/masquages", json={"auteur_id": _voisin(moteur)})
    assert (r.status_code, r.json()["detail"]) == (422, masquage.REFUS_MODERATEUR)


# ── Où il s'applique ──────────────────────────────────────────────────────────


def test_ce_que_signe_le_masque_disparait_pour_moi_seul(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    autre, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    voisin = _voisin(moteur)
    (idee,) = _poser(moteur, Idee(titre="Idée neutre", description="…"))
    _poser(
        moteur,
        PetiteAnnonce(titre="Annonce du voisin", description="…", auteur_id=voisin),
        PetiteAnnonce(titre="Annonce neutre", description="…", auteur_id=_voisin(moteur)),
        ReponseCommunaute(rubrique="idee", cible_id=idee, contenu="Du voisin", auteur_id=voisin),
    )
    http.post("/masquages", json={"auteur_id": voisin})

    assert _titres(http, "/annonces") == {"Annonce neutre"}
    assert http.get(f"/idees/{idee}/reponses").json() == []
    #  Les autres, et le conseil, voient tout.
    tout = {"Annonce du voisin", "Annonce neutre"}
    assert _titres(autre, "/annonces") == tout
    assert _titres(cs, "/annonces") == tout
    #  Le fil aussi : la carte d'annonce dit son auteur, et le fil la retire.
    fil = {i["titre"] for i in http.get("/flux").json()["items"]}
    assert "Annonce du voisin" not in fil and "Annonce neutre" in fil


def test_une_idee_dont_l_auteur_ne_se_dit_pas_reste(moteur):
    """🔴 Une idée ne dit jamais son auteur : la retirer avec le reste révélerait
    qui l'a écrite. Elle reste, au fil comme dans sa liste."""
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin = _voisin(moteur)
    _poser(moteur, Idee(titre="Idée du voisin", description="…", auteur_id=voisin))
    http.post("/masquages", json={"auteur_id": voisin})
    assert _titres(http, "/idees") == {"Idée du voisin"}
    assert "Idée du voisin" in {i["titre"] for i in http.get("/flux").json()["items"]}


def test_les_suites_et_messages_du_masque_quittent_l_affaire_qui_reste(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin = _voisin(moteur)
    affaire = affaire_ouverte(moteur, "Fuite au 3e")
    _poser(
        moteur,
        TicketEvolution(
            ticket_id=affaire, type="commentaire", contenu="Du voisin", auteur_id=voisin
        ),
        TicketEvolution(ticket_id=affaire, type="commentaire", contenu="D'un autre"),
        MessageTicket(ticket_id=affaire, contenu="Message du voisin", auteur_id=voisin),
    )
    http.post("/masquages", json={"auteur_id": voisin})

    suites = {e["contenu"] for e in http.get(f"/tickets/{affaire}/evolutions").json()}
    assert "Du voisin" not in suites and "D'un autre" in suites
    assert http.get(f"/tickets/{affaire}/messages").json() == []
    assert http.get(f"/tickets/{affaire}").status_code == 200


def test_un_masque_devenu_conseiller_redevient_visible(moteur):
    """Le masque se relit à chaque lecture : entré au conseil, son auteur publie
    l'information de la copropriété, qui ne se masque pas."""
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin = _voisin(moteur)
    _poser(moteur, PetiteAnnonce(titre="Annonce du voisin", description="…", auteur_id=voisin))
    http.post("/masquages", json={"auteur_id": voisin})
    assert _titres(http, "/annonces") == set()
    with Session(moteur) as s:
        from app.models.core import Utilisateur

        u = s.get(Utilisateur, voisin)
        u.roles_json = "conseil_syndical"
        s.add(u)
        s.commit()
    assert _titres(http, "/annonces") == {"Annonce du voisin"}
