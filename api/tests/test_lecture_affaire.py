"""« Qui la lit » au PDF du point : le mot de la pastille de la page Affaires (#2089).

`utils/lecture_affaire` n'écrit pas la règle : il EXÉCUTE `public_cible_visible`
pour un compte de chaque statut. Il écrit les LIBELLÉS — et ce test les tient
d'accord avec l'écran :

- les profils qui lisent, comparés aux `lecteurs` des cas d'affaire de
  `tests/donnees/lecture_pastille.json` — l'attente commune de l'écran
  (`npm run lint:lecture`) et du serveur (`test_lecture_pastille.py`) ;
- les libellés courts, comparés à ceux de `front/src/lib/lecture.ts`.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

from app.models.tickets import StatutTicket, Ticket
from app.utils.lecture_affaire import NOMMEES, PROFILS, lecture_courte, statuts_lecteurs

RACINE = pathlib.Path(__file__).resolve().parents[2]
LECTURE_TS = RACINE / "front" / "src" / "lib" / "lecture.ts"
CAS = json.loads(
    (pathlib.Path(__file__).parent / "donnees" / "lecture_pastille.json").read_text(
        encoding="utf-8"
    )
)["cas"]

#: Les cas d'AFFAIRE suivie dans le périmètre — ni actualité, ni objet ciblé.
AFFAIRES = [c for c in CAS if not c.get("actualite") and "objet" not in c]


def _ticket(cas: dict) -> Ticket:
    return Ticket(
        numero="L",
        titre="Lecture",
        categorie=cas.get("categorie") or "question",
        public_cible=json.dumps(cas["public_cible"], ensure_ascii=False),
        confidentiel=cas["confidentiel"],
        statut=StatutTicket(cas["statut"])
        if cas.get("statut")
        else StatutTicket.en_ag
        if cas.get("en_ag")
        else StatutTicket.ouvert,
    )


def test_il_y_a_des_cas_d_affaire():
    assert len(AFFAIRES) >= 5, "le contrôle ne mesurerait rien"


@pytest.mark.parametrize("cas", AFFAIRES, ids=[c["nom"] for c in AFFAIRES])
def test_les_profils_sont_ceux_de_l_attente_commune(cas):
    attendus = [s for s, _ in PROFILS if s in cas["lecteurs"]]
    assert statuts_lecteurs(_ticket(cas)) == attendus


def test_les_libelles_sont_ceux_de_l_ecran():
    source = LECTURE_TS.read_text(encoding="utf-8")
    courts = set(re.findall(r"court:\s*'([^']+)'", source))
    ecrits = {c for _, c in PROFILS} | set(NOMMEES.values()) | {"CS", "Concerné"}
    assert ecrits <= courts, f"libellés absents de lecture.ts : {sorted(ecrits - courts)}"


def test_le_mot_de_la_pastille():
    assert lecture_courte(Ticket(numero="a", titre="a", categorie="panne")) == (
        "Copropriétaires + locataires"
    )
    assert lecture_courte(Ticket(numero="b", titre="b", categorie="question")) == "Concerné"
    assert lecture_courte(Ticket(numero="c", titre="c", categorie="etude_travaux")) == "CS"
    assert lecture_courte(Ticket(numero="d", titre="d", categorie="entretien")) == (
        "Copropriétaires"
    )
    tous = Ticket(numero="e", titre="e", categorie="question", public_cible='["résidents"]')
    assert lecture_courte(tous) == "Tous"
