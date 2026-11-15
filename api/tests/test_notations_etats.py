"""La notation d'un prestataire se lit en TROIS états (14/11/2026).

Mauvais · Neutre · Excellent. Un état nouveau s'écrit 1, 3 ou 5 ; une ancienne note
(1 à 5) se lit à la volée, sans réécriture : 1-2 → Mauvais, 3 → Neutre, 4-5 → Excellent.
Un avis Mauvais se justifie par un commentaire.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.prestataires import NotationPrestataire, Prestataire
from app.routers.prestataires import NotationCreate, create_notation, list_notations
from app.utils.notes_prestataires import ETATS, NOTE_DE_ETAT, etat_de_note
from tests.aides_badges import _compte


def test_chaque_etat_s_ecrit_sur_une_note_que_l_ancienne_lecture_comprend():
    assert ETATS == ("mauvais", "neutre", "excellent")
    assert NOTE_DE_ETAT == {"mauvais": 1, "neutre": 3, "excellent": 5}
    for etat, note in NOTE_DE_ETAT.items():
        assert etat_de_note(note) == etat


@pytest.mark.parametrize(
    ("ancienne", "attendu"),
    [(1, "mauvais"), (2, "mauvais"), (3, "neutre"), (4, "excellent"), (5, "excellent")],
)
def test_une_ancienne_note_se_lit_sans_etre_reecrite(ancienne, attendu):
    assert etat_de_note(ancienne) == attendu


def test_un_avis_mauvais_sans_commentaire_est_refuse():
    with pytest.raises(ValidationError):
        NotationCreate(prestataire_id=1, etat="mauvais", commentaire="   ")


def test_un_avis_neutre_ou_excellent_n_exige_pas_de_commentaire():
    assert NotationCreate(prestataire_id=1, etat="neutre").etat == "neutre"
    assert NotationCreate(prestataire_id=1, etat="excellent").etat == "excellent"


def test_l_ancien_format_une_note_entre_1_et_5_reste_accepte():
    saisie = NotationCreate(prestataire_id=1, note=4)
    assert saisie.etat == "excellent"


def test_une_saisie_sans_etat_ni_note_est_refusee():
    with pytest.raises(ValidationError):
        NotationCreate(prestataire_id=1)


def test_la_creation_ecrit_la_note_de_l_etat_et_la_relit(session):
    suffixe = uuid.uuid4().hex[:6]
    p = Prestataire(nom=f"Gerber {suffixe}", specialite="serrurerie")
    session.add(p)
    session.commit()
    compte = _compte(session, "Cs")

    cree = create_notation(
        body=NotationCreate(prestataire_id=p.id, etat="mauvais", commentaire="Retard de 3 jours"),
        session=session,
        user=compte,
    )
    assert cree.etat == "mauvais"
    assert session.get(NotationPrestataire, cree.id).note == 1

    lues = [
        n
        for n in list_notations(prestataire_id=p.id, session=session, _=compte)
        if n.prestataire_id == p.id
    ]
    assert [n.etat for n in lues] == ["mauvais"]
    assert lues[0].commentaire == "Retard de 3 jours"


def test_chaque_avis_porte_son_exercice_comptable(session):
    """L'écran regroupe les avis par exercice (R3d) : le serveur le calcule, l'écran ne le recopie pas."""
    suffixe = uuid.uuid4().hex[:6]
    p = Prestataire(nom=f"Gerber {suffixe}", specialite="serrurerie")
    session.add(p)
    session.commit()
    compte = _compte(session, "Cs")
    create_notation(
        body=NotationCreate(prestataire_id=p.id, etat="excellent"), session=session, user=compte
    )
    lues = [n for n in list_notations(prestataire_id=p.id, session=session, _=compte)]
    assert len(lues) == 1
    assert lues[0].exercice_annee is not None
    assert lues[0].exercice_libelle
