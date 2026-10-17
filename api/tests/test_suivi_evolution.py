"""Le Suivi des affaires signale ce qui a évolué depuis le dernier résumé (#2044).

Ce qui est tenu :
- **jamais résumée** → nouvelle ; **une entrée au fil après le résumé** → elle a
  évolué, et le motif est le type de cette entrée ; une entrée ANTÉRIEURE, ou une
  simple correction de champ, ne compte pas ;
- **« Résumer »** n'envoie au modèle que les affaires nouvelles ou qui ont évolué,
  et rien du tout quand il n'y en a pas.
"""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur
from app.models.tickets import Ticket, TicketEvolution
from app.utils import horloge
from app.utils.suivi_affaires import resumes as module_resumes
from app.utils.suivi_affaires.releve import evolution
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte


def test_evolution_regle_pure():
    maintenant = horloge.maintenant()
    avant, apres = maintenant - timedelta(hours=1), maintenant + timedelta(hours=1)
    assert evolution(None, None) == (True, "nouvelle")
    assert evolution(maintenant, None) == (False, None)
    assert evolution(maintenant, (avant, "commentaire")) == (False, None)
    assert evolution(maintenant, (apres, "etat")) == (True, "etat")


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _resume_il_y_a(moteur, tid: int, *, heures: int) -> None:
    with Session(moteur) as s:
        t = s.get(Ticket, tid)
        t.resume_ia = "Le syndic attend un devis."
        t.resume_ia_le = horloge.maintenant() - timedelta(hours=heures)
        s.add(t)
        s.commit()


def _entree(moteur, tid: int, *, il_y_a_heures: int, nature: str = "commentaire") -> None:
    with Session(moteur) as s:
        s.add(
            TicketEvolution(
                ticket_id=tid,
                type=nature,
                contenu="<p>Point d'étape.</p>",
                cree_le=horloge.maintenant() - timedelta(hours=il_y_a_heures),
            )
        )
        s.commit()


def _par_id(http) -> dict[int, dict]:
    return {a["id"]: a for a in http.get("/suivi-affaires").json()["affaires"]}


def test_nouvelle_puis_resumee_puis_une_entree_au_fil(moteur):
    tid = affaire_ouverte(moteur, "Interphone muet", jours=12)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    a = _par_id(http)[tid]
    assert (a["a_evolue"], a["motif_evolution"]) == (True, "nouvelle")

    _entree(moteur, tid, il_y_a_heures=5)
    _resume_il_y_a(moteur, tid, heures=2)
    a = _par_id(http)[tid]
    assert (a["a_evolue"], a["motif_evolution"]) == (False, None), "entrée antérieure"

    #  Une correction de champ n'est pas une entrée au fil.
    with Session(moteur) as s:
        t = s.get(Ticket, tid)
        t.titre, t.mis_a_jour_le = "Interphone muet, bât. C", horloge.maintenant()
        s.add(t)
        s.commit()
    assert _par_id(http)[tid]["a_evolue"] is False

    _entree(moteur, tid, il_y_a_heures=1, nature="etat")
    a = _par_id(http)[tid]
    assert (a["a_evolue"], a["motif_evolution"]) == (True, "etat")


def test_resumer_n_envoie_que_ce_qui_a_evolue(moteur, monkeypatch):
    stable = affaire_ouverte(moteur, "Stable", jours=20)
    evoluee = affaire_ouverte(moteur, "Évoluée", jours=10)
    _resume_il_y_a(moteur, stable, heures=2)
    _resume_il_y_a(moteur, evoluee, heures=3)
    _entree(moteur, evoluee, il_y_a_heures=1)
    with Session(moteur) as s:
        numero_stable = s.get(Ticket, stable).numero
        numero_evoluee = s.get(Ticket, evoluee).numero

    envoyes: list[str] = []

    async def faux_demander(session, *, usage, consigne, message, demandeur):
        envoyes.append(message)
        return SimpleNamespace(texte=json.dumps({"affaires": {numero_evoluee: "Devis reçu."}}))

    monkeypatch.setattr(module_resumes, "demander", faux_demander)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    assert http.post("/suivi-affaires/resumes").json() == {"rediges": 1}
    (message,) = envoyes
    assert numero_evoluee in message and numero_stable not in message

    #  Plus rien n'a évolué : rien ne part, et la route le dit.
    reponse = http.post("/suivi-affaires/resumes")
    assert reponse.status_code == 400 and len(envoyes) == 1
