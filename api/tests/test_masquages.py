"""Masquer ce que publie un autre résident — pour soi seul (#2861).

La règle vit dans `utils/masquage` ; ces tests l'éprouvent par les vraies routes :
le geste (`/masquages`), chaque liste où il s'applique — annonces, réponses, fil,
suites et messages d'une affaire — et celle où il ne s'applique pas : une idée,
dont l'auteur ne se dit pas. Le conseil syndical et l'administration voient
tout, ne masquent pas et ne se masquent pas.

On ne masque que l'auteur d'une publication SIGNÉE qu'on lit
(`masquage.auteur_lu_par`) : sinon la route répond comme pour un compte absent, et
ne nomme personne. Une idée et un sondage ne servent leur auteur qu'à lui-même et
à qui modère.
"""

from __future__ import annotations

import ast

import pytest
from sqlmodel import Session

from app.models.communaute import (
    CommentaireSondage,
    Idee,
    PetiteAnnonce,
    ReponseCommunaute,
    Sondage,
)
from app.models.core import RoleUtilisateur
from app.models.tickets import MessageTicket, TicketEvolution
from app.utils import masquage
from app.utils.limiter import LIMITE_PREFERENCE
from tests.aides_base import compte
from tests.aides_sources import modules_app
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _voisin(moteur, **champs) -> int:
    with Session(moteur) as s:
        return compte(s, prefixe="voisin", nom="Durand", prenom="Reine", **champs).id


def _voisin_lu(moteur, **champs) -> int:
    """Un voisin dont une annonce se lit de toute la résidence : son nom s'y affiche."""
    voisin = _voisin(moteur, **champs)
    _poser(moteur, PetiteAnnonce(titre="Annonce lue", description="…", auteur_id=voisin))
    return voisin


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
    voisin = _voisin_lu(moteur)
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
    #  Le motif « on ne masque pas le conseil » se dit depuis une publication VUE.
    cs = _voisin_lu(moteur, roles_json="conseil_syndical")
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
    voisin = _voisin_lu(moteur)
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


# ── On ne masque que l'auteur d'une publication signée qu'on lit ─────────────


def _absent(http) -> dict:
    r = http.post("/masquages", json={"auteur_id": 999_999})
    assert r.status_code == 404, r.text
    return r.json()


def test_un_compte_dont_je_ne_lis_rien_repond_comme_un_compte_absent(moteur):
    """Ni publication, ni seulement une idée (qui ne dit pas son auteur), ni une suite
    d'une affaire que je ne lis pas : la réponse est celle d'un compte absent, et le
    nom n'y est pas. Rien n'est posé."""
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    attendu = _absent(http)
    muet = _voisin(moteur)
    anonyme = _voisin(moteur)
    _poser(moteur, Idee(titre="Idée", description="…", auteur_id=anonyme))
    hors_de_vue = _voisin(moteur)
    secrete = affaire_ouverte(moteur, "Litige privé", confidentiel=True)
    _poser(
        moteur,
        TicketEvolution(
            ticket_id=secrete, type="commentaire", contenu="Secret", auteur_id=hors_de_vue
        ),
    )
    cs_jamais_lu = _voisin(moteur, roles_json="conseil_syndical")
    for ident in (muet, anonyme, hors_de_vue, cs_jamais_lu):
        r = http.post("/masquages", json={"auteur_id": ident})
        assert (r.status_code, r.json()) == (404, attendu), ident
        assert "DURAND" not in r.text
    assert http.get("/masquages").json() == []


def _publication_signee(moteur, quoi: str, auteur: int) -> None:
    if quoi == "annonce":
        _poser(moteur, PetiteAnnonce(titre="Vélo", description="…", auteur_id=auteur))
    elif quoi == "reponse":
        (idee,) = _poser(moteur, Idee(titre="Bancs", description="…"))
        _poser(
            moteur,
            ReponseCommunaute(rubrique="idee", cible_id=idee, contenu="Oui", auteur_id=auteur),
        )
    elif quoi == "commentaire":
        (sondage,) = _poser(moteur, Sondage(question="Peinture ?"))
        _poser(moteur, CommentaireSondage(sondage_id=sondage, contenu="Non", auteur_id=auteur))
    elif quoi == "suite":
        affaire = affaire_ouverte(moteur)
        _poser(
            moteur,
            TicketEvolution(ticket_id=affaire, type="commentaire", contenu="Vu", auteur_id=auteur),
        )
    else:
        affaire = affaire_ouverte(moteur)
        _poser(moteur, MessageTicket(ticket_id=affaire, contenu="Bonjour", auteur_id=auteur))


@pytest.mark.parametrize("quoi", ["annonce", "reponse", "commentaire", "suite", "message"])
def test_depuis_une_publication_signee_que_je_lis_le_masque_se_pose(moteur, quoi):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin = _voisin(moteur)
    _publication_signee(moteur, quoi, voisin)
    r = http.post("/masquages", json={"auteur_id": voisin})
    assert (r.status_code, r.json().get("auteur")) == (201, "Reine DURAND"), r.text


def test_les_publications_signees_sont_celles_que_le_masque_retire():
    """Le registre de la question et les listes filtrées par `garder` se confrontent
    dans les deux sens : une liste neuve qui masque, ou un type retiré du registre,
    fait échouer ici."""
    filtrent = {
        m.rel.removeprefix("routers/")
        for m in modules_app("routers", minimum=25)
        if any(
            isinstance(n, ast.Call) and ast.unparse(n.func) == "garder" for n in ast.walk(m.arbre)
        )
    }
    #  Fichier qui filtre → ce qu'il filtre ; le fil ne fait que réunir les autres.
    attendus = {
        "annonces.py": PetiteAnnonce,
        "reponses_communaute.py": ReponseCommunaute,
        "sondages/crud.py": CommentaireSondage,
        "tickets/evolutions.py": TicketEvolution,
        "tickets/messages.py": MessageTicket,
        "flux/__init__.py": None,
    }
    assert filtrent == set(attendus)
    modeles = {m for m, _ in masquage.publications_signees()}
    assert modeles == {m for m in attendus.values() if m is not None}


def test_l_auteur_d_une_idee_ne_se_sert_qu_a_lui_et_a_qui_modere(moteur):
    """Une idée ne dit pas son auteur : son identifiant ne se sert qu'à lui (le
    drapeau « signaler » ne lui est pas tendu) et à qui modère."""
    auteur, auteur_id = client_http(moteur, RoleUtilisateur.propriétaire)
    autre, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    _poser(moteur, Idee(titre="Bancs", description="…", auteur_id=auteur_id))
    assert [i["auteur_id"] for i in autre.get("/idees").json()] == [None]
    assert [i["auteur_id"] for i in auteur.get("/idees").json()] == [auteur_id]
    assert [i["auteur_id"] for i in cs.get("/idees").json()] == [auteur_id]


def test_l_auteur_d_un_sondage_ne_se_sert_qu_a_lui_et_a_qui_modere(moteur):
    """Un sondage ne dit pas son auteur : son identifiant ne se sert, en liste comme
    sur la fiche, qu'à lui (les boutons « modifier », « stopper », « supprimer ») et
    à qui modère. Ailleurs la clé reste, à `None` : la forme ne change pas.

    L'auteur est ici un ancien conseiller redevenu propriétaire : il reste l'auteur
    sans modérer, ce qui sépare les deux raisons de recevoir l'identifiant."""
    auteur, auteur_id = client_http(moteur, RoleUtilisateur.propriétaire)
    autre, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    (sondage,) = _poser(moteur, Sondage(question="Peinture ?", auteur_id=auteur_id))
    for http, attendu in ((autre, None), (auteur, auteur_id), (cs, auteur_id)):
        assert [s["auteur_id"] for s in http.get("/sondages").json()] == [attendu]
        fiche = http.get(f"/sondages/{sondage}").json()
        assert "auteur_id" in fiche and fiche["auteur_id"] == attendu


def test_le_geste_a_sa_limite_de_debit(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    plafond = int(LIMITE_PREFERENCE.split("/")[0])
    codes = [
        http.post("/masquages", json={"auteur_id": 999_999}).status_code for _ in range(plafond + 1)
    ]
    assert codes[:plafond] == [404] * plafond and codes[-1] == 429, codes
