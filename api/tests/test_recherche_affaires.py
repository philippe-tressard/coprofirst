"""La recherche libre des affaires ne trouve que ce que le lecteur peut LIRE.

## Pourquoi ce test (27/09/2026)

La recherche remplace le filtre « Catégorie » et cherche partout : suites,
messages, documents. Un compte de résultats est une information — trouver
« impayé » dans une affaire dont on ne lit pas le fil suffit à apprendre que
le mot y est. Chaque règle de lecture est donc éprouvée ICI, contre la route qui
montre le même texte :

| Ce qu'on cherche | La règle, partagée avec |
|---|---|
| l'affaire | `ticket_visible` — la liste |
| une suite | `ticket_visible` — `GET /{id}/evolutions` (29/09/2026) |
| une note interne | `lit_les_notes_internes` — `GET /{id}/messages` |

La règle de correspondance elle-même (accents, casse, tous les mots, extrait)
a son `--selftest` : `app/utils/recherche_affaires.py`.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import (
    MessageTicket,
    StatutTicket,
    StatutUtilisateur,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.routers.tickets.evolutions import get_evolutions
from app.routers.tickets.messages import get_messages
from app.routers.tickets.recherche import rechercher
from app.utils import mes_batiments
from app.utils import perimetres as P
from app.utils.noms import nom_affiche
from app.utils.visibility import ticket_visible
from tests.aides_base import compte, moteur_de_test
from tests.aides_purge import purger_ligne


def _mot() -> str:
    """Un mot que personne d'autre n'a écrit dans la base de test."""
    return "zq" + uuid.uuid4().hex[:10]


def _utilisateur(session, roles, batiment_id) -> Utilisateur:
    return compte(
        session,
        prefixe="rech",
        nom="Sorel",
        prenom="Camille",
        roles_json=roles,
        statut=StatutUtilisateur.copropriétaire_résident,
        batiment_id=batiment_id,
    )


def _ids(session, user, q) -> list[int]:
    return [r.ticket_id for r in rechercher(q=q, session=session, user=user)]


@pytest.fixture()
def scene(batiments):
    """Une affaire de toute la résidence, avec un fil, deux messages et un voisin.

    Le voisin LIT l'affaire (portée résidence) sans pouvoir y écrire. Depuis le
    29/09/2026, il en lit aussi le fil : les droits sont ceux de l'affaire.
    """
    SQLModel.metadata.create_all(engine)
    mes_batiments.invalider_cache()
    P.invalider_cache()
    mots = {k: _mot() for k in ("titre", "suite", "public", "interne", "secret")}
    with Session(engine) as session:
        auteur = _utilisateur(session, "résident", batiments[0])
        voisin = _utilisateur(session, "résident", batiments[0])
        cs = _utilisateur(session, "conseil_syndical", batiments[1])
        affaire = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre=f"Dégât des eaux {mots['titre']}",
            description="Une flaque au pied de l'escalier.",
            #  Lue par les copropriétaires parce que le conseil les a CHOISIS :
            #  sans choix, une Nuisance est au « Résident concerné » (#1436) et
            #  Étude & travaux au conseil seul (29/09/2026).
            categorie="etude_travaux",
            public_cible=json.dumps(["copropriétaires_occupants", "bailleurs"], ensure_ascii=False),
            auteur_id=auteur.id,
            statut=StatutTicket.ouvert,
            perimetre_cible=json.dumps(["résidence"]),
        )
        confidentielle = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre=f"Litige {mots['secret']}",
            description="…",
            categorie="nuisance",
            auteur_id=auteur.id,
            statut=StatutTicket.ouvert,
            perimetre_cible=json.dumps(["résidence"]),
            confidentiel=True,
        )
        session.add(affaire)
        session.add(confidentielle)
        session.commit()
        lignes = [
            TicketEvolution(
                ticket_id=affaire.id,
                auteur_id=cs.id,
                type="commentaire",
                contenu=f"<p>Le plombier confirme une fuite, {mots['suite']}.</p>",
            ),
            MessageTicket(ticket_id=affaire.id, auteur_id=auteur.id, contenu=mots["public"]),
            MessageTicket(
                ticket_id=affaire.id, auteur_id=cs.id, contenu=mots["interne"], interne=True
            ),
        ]
        for ligne in lignes:
            session.add(ligne)
        session.commit()
        mes_batiments.invalider_cache()
        yield session, affaire, confidentielle, auteur, voisin, cs, mots
        for ligne in lignes:
            purger_ligne(session, type(ligne), ligne.id)
        for t in (affaire, confidentielle):
            purger_ligne(session, Ticket, t.id)
        for u in (auteur, voisin, cs):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()
        mes_batiments.invalider_cache()


def test_le_voisin_lit_l_affaire_ET_son_fil(scene):
    """🔴 TK-124285 (29/09/2026) : des copropriétaires lisaient l'affaire et en
    voyaient les suites VIDES — la règle du fil était celle de l'écriture."""
    session, affaire, _c, _a, voisin, _cs, mots = scene
    assert ticket_visible(affaire, voisin) is True
    lus = get_evolutions(affaire.id, session=session, user=voisin)
    assert any(mots["suite"] in (e.contenu or "") for e in lus)


def test_qui_ne_lit_pas_l_affaire_ne_lit_pas_son_fil(scene):
    """Le fil se ferme avec l'affaire : une confidentielle reste close au voisin."""
    session, _a, confidentielle, auteur, voisin, _cs, _m = scene
    assert ticket_visible(confidentielle, voisin) is False
    with pytest.raises(HTTPException) as refus:
        get_evolutions(confidentielle.id, session=session, user=voisin)
    assert refus.value.status_code == 403
    assert get_evolutions(confidentielle.id, session=session, user=auteur) == []


def test_accents_et_majuscules_ne_comptent_pas(scene):
    session, affaire, _c, auteur, _v, _cs, mots = scene
    assert affaire.id in _ids(session, auteur, f"DEGAT {mots['titre'].upper()}")


def test_une_suite_se_trouve_avec_son_extrait(scene):
    session, affaire, _c, auteur, _v, _cs, mots = scene
    (r,) = [r for r in rechercher(q=mots["suite"], session=session, user=auteur)]
    assert (r.ticket_id, r.ou) == (affaire.id, "suite")
    assert [s.texte for s in r.extrait if s.surligne] == [mots["suite"]]
    assert "<p>" not in "".join(s.texte for s in r.extrait), "l'extrait est du texte, pas du HTML"
    assert r.auteur == nom_affiche("Camille", "Sorel")


def test_le_fil_se_trouve_par_qui_lit_l_affaire(scene):
    """La recherche dit ce que `GET /evolutions` montre : le voisin lit le fil."""
    session, affaire, _c, _au, voisin, cs, mots = scene
    assert _ids(session, voisin, mots["suite"]) == [affaire.id]
    assert _ids(session, cs, mots["suite"]) == [affaire.id]


def test_une_note_interne_ne_se_trouve_que_par_le_conseil(scene):
    session, affaire, _c, auteur, voisin, cs, mots = scene
    assert _ids(session, auteur, mots["interne"]) == []
    assert _ids(session, voisin, mots["interne"]) == []
    assert _ids(session, cs, mots["interne"]) == [affaire.id]
    #  … et la messagerie dit la même chose que la recherche.
    lus = [m.contenu for m in get_messages(affaire.id, session=session, user=voisin)]
    assert mots["public"] in lus and mots["interne"] not in lus
    assert _ids(session, voisin, mots["public"]) == [affaire.id]


def test_une_affaire_confidentielle_reste_introuvable_du_voisin(scene):
    session, _a, confidentielle, auteur, voisin, _cs, mots = scene
    assert _ids(session, voisin, mots["secret"]) == []
    assert _ids(session, auteur, mots["secret"]) == [confidentielle.id]


def test_tous_les_mots_sont_exiges(scene):
    session, _a, _c, auteur, _v, _cs, mots = scene
    assert _ids(session, auteur, f"{mots['titre']} {_mot()}") == []


def test_la_route_n_est_pas_avalee_par_la_fiche():
    """`/tickets/recherche` monté APRÈS `/tickets/{ticket_id}` répondrait 422.

    Éprouvé par une vraie requête : l'ordre des routes ne se lit plus dans
    `router.routes`, que FastAPI peuple à la demande. Base en mémoire partagée
    entre les fils (`StaticPool`), comme `test_audit_baux_sans_locataire.py`.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.deps import get_current_user
    from app.database import get_session
    from app.routers.tickets import router

    moteur = moteur_de_test()
    mot = _mot()
    with Session(moteur) as session:
        auteur = _utilisateur(session, "résident", None)
        affaire = Ticket(numero="T-1", titre=mot, description="…", auteur_id=auteur.id)
        session.add(affaire)
        session.commit()
        appli = FastAPI()
        appli.include_router(router)
        appli.dependency_overrides[get_current_user] = lambda: auteur
        appli.dependency_overrides[get_session] = lambda: session
        reponse = TestClient(appli).get("/tickets/recherche", params={"q": mot})
        assert reponse.status_code == 200, reponse.text
        assert [r["ticket_id"] for r in reponse.json()] == [affaire.id]
