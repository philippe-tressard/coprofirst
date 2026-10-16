"""L'effacement de la mesure d'audience d'un compte est écrit une fois (#1629).

Les deux gestes qui l'effacent — le compte depuis son profil, l'administrateur
qui supprime le compte — passent par `utils/telemetrie_compte.effacer_telemetrie`.
Le second n'effaçait que les évènements : la présence mensuelle restait en base,
sans clé étrangère pour la retenir.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.telemetrie import DerniereVisite, PresenceMensuelle, TelemetryEvent
from app.routers.admin.utilisateurs import supprimer_utilisateur
from app.utils.telemetrie_compte import effacer_telemetrie
from tests.aides_base import compte, moteur_de_test


def _trois_tables(s: Session, user_id: int) -> None:
    s.add(TelemetryEvent(user_id=user_id, page="/"))
    s.add(PresenceMensuelle(mois="2026-09", user_id=user_id))
    s.add(DerniereVisite(user_id=user_id, jour="2026-09-30"))


def _restants(s: Session) -> set[tuple[str, int]]:
    return (
        {("evenement", e.user_id) for e in s.exec(select(TelemetryEvent)).all()}
        | {("presence", p.user_id) for p in s.exec(select(PresenceMensuelle)).all()}
        | {("visite", d.user_id) for d in s.exec(select(DerniereVisite)).all()}
    )


def test_l_effacement_porte_sur_les_trois_tables_et_sur_ce_compte_seul():
    with Session(moteur_de_test()) as s:
        moi, autre = compte(s).id, compte(s).id
        _trois_tables(s, moi)
        _trois_tables(s, autre)
        s.commit()
        effacer_telemetrie(s, moi)
        s.commit()
        assert _restants(s) == {("evenement", autre), ("presence", autre), ("visite", autre)}


def test_supprimer_un_compte_efface_aussi_sa_presence_et_sa_derniere_visite():
    with Session(moteur_de_test()) as s:
        admin = compte(s, roles_json="admin")
        partant = compte(s).id
        _trois_tables(s, partant)
        s.commit()
        supprimer_utilisateur(partant, session=s, admin=admin)
        assert _restants(s) == set()
