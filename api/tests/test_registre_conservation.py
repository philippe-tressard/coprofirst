"""Les échéances de conservation d'une installation résiliée (conditions v1 §4).

`registre/conservation.purger` efface les coordonnées 12 mois après la résiliation
et l'archive du contrat 5 ans après — et l'écrit au journal. La date se lit au
journal (la ligne « resilier »), jamais ailleurs.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.registre import conservation
from app.registre.modeles import (
    AcceptationConditions,
    ContactInstallation,
    DecisionRegistre,
    EtatInscription,
    Installation,
)
from app.utils import taches
from tests.aides_registre import registre_allume

RESILIEE_LE = datetime(2026, 10, 13, 22, 35)


def _resiliee(s: Session, etat=EtatInscription.resiliee) -> Installation:
    inst = Installation(identifiant="CF-000002", cle_publique="cle", etat=etat)
    s.add(inst)
    s.flush()
    s.add(
        ContactInstallation(installation_id=inst.id, prenom="Alix", nom="Durand", courriel="a@b.c")
    )
    s.add(
        AcceptationConditions(
            installation_id=inst.id, version=1, empreinte="e", texte="t", accepte_par="Alix Durand"
        )
    )
    s.add(
        DecisionRegistre(installation_id=inst.id, geste="resilier", auteur="x", cree_le=RESILIEE_LE)
    )
    s.commit()
    return inst


def _compte(s: Session, modele) -> int:
    return len(s.exec(select(modele)).all())


def test_les_echeances_s_appliquent_a_leur_date_et_s_ecrivent_au_journal(monkeypatch):
    with registre_allume(monkeypatch) as moteur, Session(moteur) as s:
        _resiliee(s)
        assert conservation.purger(s, datetime(2027, 10, 13, 22, 34)) == {
            "coordonnees_effacees": 0,
            "contrat_efface": 0,
        }
        conservation.purger(s, datetime(2027, 10, 13, 22, 35))
        assert _compte(s, ContactInstallation) == 0 and _compte(s, AcceptationConditions) == 1
        conservation.purger(s, datetime(2031, 10, 13, 22, 34))
        assert _compte(s, AcceptationConditions) == 1
        bilan = conservation.purger(s, datetime(2031, 10, 13, 22, 35))
        assert bilan == {"coordonnees_effacees": 0, "contrat_efface": 1}
        assert _compte(s, AcceptationConditions) == 0
        gestes = [d.geste for d in s.exec(select(DecisionRegistre).order_by(DecisionRegistre.id))]
        assert gestes == ["resilier", "coordonnees_effacees", "contrat_efface"]
        assert _compte(s, Installation) == 1  # la ligne reste : son numéro ne se réattribue pas


def test_une_installation_non_resiliee_ne_perd_rien(monkeypatch):
    with registre_allume(monkeypatch) as moteur, Session(moteur) as s:
        _resiliee(s, etat=EtatInscription.active)
        conservation.purger(s, datetime(2040, 1, 1))
        assert _compte(s, ContactInstallation) == 1 and _compte(s, AcceptationConditions) == 1


def test_un_29_fevrier_tombe_au_1er_mars():
    assert conservation.plus_annees(datetime(2028, 2, 29, 8), 1) == datetime(2029, 3, 1, 8)


def test_la_purge_est_une_tache_de_la_plateforme():
    assert "conservation_registre" in taches.TACHES_PERMANENTES
    assert "conservation_registre" in taches.TACHES_DE_LA_PLATEFORME
