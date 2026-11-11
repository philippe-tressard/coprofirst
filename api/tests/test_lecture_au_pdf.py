"""« Qui la lit » au PDF du point CS / Syndic : le mot de la pastille SERVIE (#2669).

Le PDF du point (`suivi_affaires/releve`) et la rubrique des CR d'une affaire
(`pdf_disponible`) disent qui lit une affaire. Depuis #2633, la pastille de la page
Affaires est servie par `utils/lecture_pastille` : le PDF la LIT, il ne la
recompose pas. `utils/lecture_affaire` la recomposait — sa propre table de libellés,
sa propre règle — et disait « Concerné » d'une actualité confidentielle, là où
l'écran dit « CS ».

Ce qui est tenu :
- le mot du PDF est le libellé court de la pastille, pour chaque nature, état,
  Destinataires et confidentialité — l'actualité confidentielle comprise ;
- le lien du PDF d'un CR s'offre sur une affaire que la pastille dit « CS » ;
- aucun module de l'API, hors `utils/lecture_pastille`, n'écrit les libellés de la
  pastille : une table recopiée diverge au premier cas limite.
"""

from __future__ import annotations

import ast
import itertools
import json
import pathlib

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur
from app.models.tickets import CategorieTicket, StatutTicket, Ticket
from app.utils import horloge
from app.utils.lecture_pastille import vocabulaire as V
from app.utils.lecture_pastille.objets import lecture_du_ticket
from app.utils.suivi_affaires.releve import lire_affaire
from tests.aides_http import base_http, client_http
from tests.aides_points_conseil import intercepter_envois, point_termine

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
PASTILLE = APP / "utils" / "lecture_pastille"

#: Destinataires : aucun choix (la nature décide), le conseil seul, des profils, tous.
PUBLICS = (
    [],
    ["conseil_syndical"],
    ["copropriétaires"],
    ["locataires"],
    ["résidents"],
)


def _ticket(categorie: str, statut: str, confidentiel: bool, public: list[str]) -> Ticket:
    return Ticket(
        numero="L",
        titre="Lecture",
        categorie=categorie,
        statut=statut,
        confidentiel=confidentiel,
        public_cible=json.dumps(public, ensure_ascii=False) if public else None,
        cree_le=horloge.maintenant(),
    )


def _mot_du_pdf(ticket: Ticket) -> str:
    return lire_affaire(ticket, horloge.aujourd_hui(), {}).lecture


CAS = list(
    itertools.product(
        [c.value for c in CategorieTicket],
        [s.value for s in StatutTicket],
        [False, True],
        PUBLICS,
    )
)


@pytest.mark.parametrize("categorie,statut,confidentiel,public", CAS)
def test_le_pdf_dit_le_mot_de_la_pastille(categorie, statut, confidentiel, public):
    t = _ticket(categorie, statut, confidentiel, public)
    assert _mot_du_pdf(t) == lecture_du_ticket(t).court


def test_une_actualite_confidentielle_se_dit_cs():
    """Le cas de #2669 : « Résident concerné » ne vaut que pour une affaire."""
    actualite = _ticket("actualite", "ouvert", True, [])
    assert _mot_du_pdf(actualite) == V.CS.court
    affaire = _ticket("panne", "ouvert", True, [])
    assert _mot_du_pdf(affaire) == V.CONCERNE.court


# ── Le lien du PDF d'un CR, dans la rubrique de l'affaire ──────────────────


@pytest.mark.parametrize(
    "categorie,disponible", [("actualite", True), ("panne", False)], ids=["actualite", "affaire"]
)
def test_le_pdf_du_cr_s_offre_sur_une_affaire_que_la_pastille_dit_cs(
    monkeypatch, categorie, disponible
):
    intercepter_envois(monkeypatch)
    with base_http() as moteur:
        cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        point, t, _ = point_termine(moteur, cs)
        assert cs.post(f"/points-conseil/{point}/valider").status_code == 204
        with Session(moteur) as s:
            ticket = s.get(Ticket, t)
            ticket.categorie = categorie
            ticket.confidentiel = True
            s.add(ticket)
            s.commit()
            court = lecture_du_ticket(s.get(Ticket, t)).court
        (cr,) = cs.get(f"/points-conseil/affaires/{t}").json()
        assert (court == V.CS.court) is disponible
        assert cr["pdf_disponible"] is disponible


# ── Une seule écriture des libellés ────────────────────────────────────────

#: Les libellés propres à la pastille — « CS », « Tous », « Locataires » sont des
#: mots que d'autres écrans emploient pour autre chose, ils ne prouveraient rien.
PROPRES = {"Copro-bailleurs", "Copropriétaires + locataires", "Concerné", "Occupants"}


def _libelles_ecrits(chemin: pathlib.Path) -> set[str]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    return {
        n.value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in PROPRES
    }


def test_les_libelles_temoins_sont_ceux_de_la_pastille():
    """Cas zéro : les témoins sont bien écrits par la pastille, sinon le balayage ne
    mesurerait rien."""
    courts = {p.court for p in V.PROFILS} | {v.court for _, v in V.NOMMEES}
    courts |= {V.CS.court, V.CONCERNE.court}
    assert PROPRES <= courts, sorted(PROPRES - courts)
    vus = set().union(*(_libelles_ecrits(f) for f in PASTILLE.glob("*.py")))
    assert vus == PROPRES, sorted(PROPRES - vus)


def test_aucun_module_ne_recopie_les_libelles_de_la_pastille():
    fautifs = {
        str(f.relative_to(APP)): sorted(ecrits)
        for f in APP.rglob("*.py")
        if PASTILLE not in f.parents and (ecrits := _libelles_ecrits(f))
    }
    assert fautifs == {}, (
        "« qui la lit » se demande à `utils/lecture_pastille` (`lecture_du_ticket(t).court`), "
        f"jamais à une table recopiée : {fautifs}"
    )
