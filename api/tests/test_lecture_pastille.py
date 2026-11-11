"""Qui LIT une affaire ou une actualité — la règle, face à son résumé à l'écran.

## Pourquoi ce test (lot 1 de la pastille de lecture, 25/09/2026)

La carte d'une affaire porte désormais une PASTILLE qui dit qui la lit :
« Copropriétaires », « Occupants », « CS »… Ce résumé est calculé à
l'écran (`front/src/lib/lecture.ts`), alors que la règle, elle, vit ici
(`ticket_visible`). Deux écritures d'une même notion — c'est le motif exact de
`test_destinataires_vocabulaire.py`, et un écart y serait SILENCIEUX : une
pastille qui dit « Tous » sur une affaire que les locataires ne lisent pas ment
à chaque lecteur, et rien ne casse.

Les deux côtés sont donc tenus par **une seule attente** :
`tests/donnees/lecture_pastille.json`. Ce test la vérifie contre la règle du
serveur, en l'EXÉCUTANT pour chaque statut, dans le périmètre et hors de lui ;
`test_lecture_pastille_servie.py` la vérifie contre la pastille servie (#2633). Ni l'un ni
l'autre ne peut changer sans que le fichier change — et alors l'autre tombe.

⚠️ Il a déjà servi : #1269, fusionné pendant ce lot, ouvre les affaires DATÉES
(nature calendrier) aux locataires de leur périmètre, hors « En AG ». La
pastille l'a appris dans le même lot, et les trois cas datés sont ici.

Depuis #1373 (27/09/2026), la pastille paraît aussi sur les cartes de petite
annonce, d'idée et de sondage : leurs cas portent `objet`, et c'est leur propre
règle qui les juge (`annonce_visible`, `idee_visible`, `sondage_accessible`).
"""

from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.communaute import Idee, PetiteAnnonce, Sondage
from app.models.core import StatutTicket, StatutUtilisateur, Ticket, Utilisateur
from app.utils import mes_batiments
from app.utils import perimetres as P
from app.utils.visibility import ticket_visible
from app.utils.visibility.objets import annonce_visible, idee_visible, sondage_accessible
from tests.aides_base import compte
from tests.aides_purge import purger_ligne

CAS = json.loads(
    (pathlib.Path(__file__).parent / "donnees" / "lecture_pastille.json").read_text(
        encoding="utf-8"
    )
)["cas"]

#  Les statuts que la pastille nomme — dans l'ordre de `PROFILS` côté écran.
#  Le conseil syndical et l'admin lisent toujours : ils ne sont pas un profil.
STATUTS = (
    StatutUtilisateur.copropriétaire_résident,
    StatutUtilisateur.copropriétaire_bailleur,
    StatutUtilisateur.mandataire,
    StatutUtilisateur.locataire,
)


@pytest.fixture()
def lecteurs(batiments):
    """Un compte par statut DANS le bâtiment visé, et un dans le bâtiment voisin."""
    SQLModel.metadata.create_all(engine)
    mes_batiments.invalider_cache()
    P.invalider_cache()
    with Session(engine) as session:
        dedans, dehors = batiments[0], batiments[1]
        comptes = {}
        for statut in STATUTS:
            for ou, bat in (("dedans", dedans), ("dehors", dehors)):
                comptes[(statut.value, ou)] = compte(
                    session,
                    prefixe="lecture",
                    nom="L",
                    prenom="P",
                    roles_json="résident",
                    statut=statut,
                    batiment_id=bat,
                )
        mes_batiments.invalider_cache()
        yield session, dedans, comptes
        for u in comptes.values():
            purger_ligne(session, Utilisateur, u.id)
        session.commit()
        mes_batiments.invalider_cache()


def _ticket(cas: dict, batiment: int, auteur_id: int) -> Ticket:
    """L'objet tel que la règle le lit — jamais enregistré : seul le verdict compte."""
    perimetre = ["résidence"] if cas["perimetre"] == "global" else [f"bat:{batiment}"]
    return Ticket(
        numero=f"L-{uuid.uuid4().hex[:6]}",
        titre="Lecture",
        description="…",
        categorie="actualite" if cas["actualite"] else cas["categorie"],
        auteur_id=auteur_id,
        perimetre_cible=json.dumps(perimetre, ensure_ascii=False),
        public_cible=json.dumps(cas["public_cible"], ensure_ascii=False),
        reserve_perimetre=cas["reserve_perimetre"],
        confidentiel=cas["confidentiel"],
        debut=datetime(2026, 10, 1, 9, 0) if cas.get("datee") else None,
        statut=StatutTicket(cas["statut"])
        if cas.get("statut")
        else StatutTicket.en_ag
        if cas.get("en_ag")
        else StatutTicket.ouvert,
    )


#  Un objet CIBLÉ (#1373) : sa fabrique et SA règle — jamais `ticket_visible`,
#  qui ne dit rien de lui.
CIBLES = {
    "annonce": (
        lambda per, pub, a: PetiteAnnonce(
            titre="L", description="…", auteur_id=a, perimetre_cible=per, public_cible=pub
        ),
        annonce_visible,
    ),
    "idee": (
        lambda per, pub, a: Idee(
            titre="L", description="…", auteur_id=a, perimetre_cible=per, public_cible=pub
        ),
        idee_visible,
    ),
    "sondage": (
        lambda per, pub, a: Sondage(
            question="L", auteur_id=a, perimetre_cible=per, public_cible=pub
        ),
        sondage_accessible,
    ),
}


def _objet_et_regle(cas: dict, batiment: int):
    """L'objet du cas et la règle du serveur qui en décide."""
    if "objet" not in cas:
        return _ticket(cas, batiment, auteur_id=-1), ticket_visible
    fabrique, regle = CIBLES[cas["objet"]]
    perimetre = ["résidence"] if cas["perimetre"] == "global" else [f"bat:{batiment}"]
    objet = fabrique(
        json.dumps(perimetre, ensure_ascii=False),
        json.dumps(cas["public_cible"], ensure_ascii=False),
        -1,
    )
    return objet, regle


def test_le_fichier_d_attentes_n_est_pas_vide():
    """Cas zéro : un fichier vide ferait passer le test paramétré sans rien mesurer."""
    assert len(CAS) >= 10
    assert {c["actualite"] for c in CAS if "objet" not in c} == {True, False}
    assert {c["objet"] for c in CAS if "objet" in c} == set(CIBLES)


@pytest.mark.parametrize("cas", CAS, ids=[c["nom"] for c in CAS])
def test_la_regle_du_serveur_dit_ce_que_la_pastille_resume(lecteurs, cas):
    _session, batiment, comptes = lecteurs
    #  Un auteur hors du jeu : l'auteur lit toujours, et fausserait le relevé.
    objet, regle = _objet_et_regle(cas, batiment)

    lisent = [s.value for s in STATUTS if regle(objet, comptes[(s.value, "dedans")])]
    assert lisent == cas["lecteurs"], (
        f"« {cas['nom']} » : le serveur fait lire {lisent}, la pastille annonce "
        f"{cas['lecteurs']}. Corriger l'une ET l'autre, puis ce fichier d'attentes."
    )

    if cas["hors_perimetre"] is None:
        return
    dehors = [s.value for s in STATUTS if regle(objet, comptes[(s.value, "dehors")])]
    #  Une LISTE : seuls ces statuts lisent hors du périmètre — les copropriétaires
    #  d'une Panne au défaut, pas ses locataires (standard du 30/09/2026).
    if isinstance(cas["hors_perimetre"], list):
        attendu_dehors = cas["hors_perimetre"]
    else:
        attendu_dehors = cas["lecteurs"] if cas["hors_perimetre"] else []
    assert dehors == attendu_dehors, (
        f"« {cas['nom']} » : hors du périmètre, le serveur fait lire {dehors}, "
        f"la pastille annonce {attendu_dehors}."
    )
