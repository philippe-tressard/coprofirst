"""La pastille de lecture SERVIE dit ce que la règle de visibilité fait (#2633).

Le résumé « qui lit » se composait dans le front (`lectureDe`) et `npm run
lint:lecture` le confrontait à `tests/donnees/lecture_pastille.json`. Il est
désormais calculé ici (`utils/lecture_pastille.lecture_de`) et servi aux deux
clients : ce test reprend ce contrôle, cas par cas, contre la fonction du serveur.
`test_lecture_pastille.py` exécute les MÊMES cas contre `ticket_visible` — ni le
résumé ni la règle ne peuvent changer sans que le fichier change, et alors l'autre
tombe.

Sans régression : avant son retrait, l'ancien calcul du front a été relevé contre
cette fonction sur 39 236 entrées (toutes les natures, publics, périmètres,
réserves, genres) — aucun écart, libellés et phrases compris.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.utils.lecture_pastille.regle import lecture_ciblee, lecture_de
from app.utils.lecture_pastille.vocabulaire import PROFILS

CAS = json.loads(
    (pathlib.Path(__file__).parent / "donnees" / "lecture_pastille.json").read_text(
        encoding="utf-8"
    )
)["cas"]
STATUT = {p.code: p.statut for p in PROFILS}


def _lecture(c):
    restreint = c["perimetre"] != "global"
    if c.get("objet"):
        return lecture_ciblee(public_cible=c["public_cible"], perimetre_restreint=restreint)
    return lecture_de(
        actualite=c["actualite"],
        confidentiel=c["confidentiel"],
        public_cible=c["public_cible"],
        perimetre_restreint=restreint,
        reserve_perimetre=c["reserve_perimetre"],
        categorie=c.get("categorie"),
        statut=c.get("statut") or ("en_ag" if c.get("en_ag") else None),
    )


def test_cas_zero():
    assert len(CAS) >= 10 and any(c.get("objet") for c in CAS)


@pytest.mark.parametrize("c", CAS, ids=[c["nom"] for c in CAS])
def test_la_pastille_dit_ce_que_le_serveur_fait(c):
    lecture = _lecture(c)
    assert [STATUT[p] for p in lecture.profils] == c["lecteurs"]
    if c["hors_perimetre"] is not None and c["lecteurs"]:
        hp = c["hors_perimetre"]
        dehors = hp if isinstance(hp, list) else (c["lecteurs"] if hp else [])
        assert [STATUT[p] for p in lecture.hors_perimetre] == dehors
        assert lecture.perimetre_reserve is (dehors == [])
    else:
        assert not lecture.perimetre_reserve, "cadenas sans périmètre restreint ni lecteur"


@pytest.mark.parametrize(
    "entree, titre, phrase",
    [
        #  Une Panne au défaut, sur un bâtiment : les copropriétaires partout, les
        #  locataires du périmètre seulement.
        (
            dict(actualite=False, categorie="panne", perimetre_restreint=True),
            "Copropriétaires et locataires · locataires du périmètre seulement",
            "Lue par les copropriétaires (occupants et bailleurs) dans toute la copropriété, "
            "et par les locataires du périmètre seulement.",
        ),
        #  Confidentielle : la personne concernée et le conseil.
        (
            dict(actualite=False, confidentiel=True, categorie="panne", perimetre_restreint=False),
            "Résident concerné",
            "Lue par la personne concernée — son auteur, ou celle pour qui elle a été saisie "
            "— et par le conseil syndical, personne d’autre.",
        ),
        #  Un sondage (masculin) réservé à son périmètre.
        (
            dict(actualite=True, reserve_perimetre=True, perimetre_restreint=True, masculin=True),
            "Tous · du périmètre seulement",
            "Lu par tous, dans le périmètre seulement.",
        ),
    ],
)
def test_libelles_et_phrases(entree, titre, phrase):
    e = dict(confidentiel=False, public_cible=None, reserve_perimetre=False) | entree
    lecture = lecture_de(**e)
    assert (lecture.titre, lecture.phrase) == (titre, phrase)
