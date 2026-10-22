"""Le journal des envois WhatsApp nomme le canal (#2059).

« Nom du canal » (`whatsapp_group_name`, Admin › WhatsApp) était écrit par l'onglet et lu
par personne. Le journal (`GET /config/whatsapp-logs`) le lit : chaque envoi dit vers
quel canal il est parti.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.core import ConfigSite, WhatsAppLog
from app.routers.config import list_whatsapp_logs


class _Admin:
    id = 1


def _journal_avec_un_envoi(session: Session) -> None:
    session.add(WhatsAppLog(label="Annonce", message="Bonjour", statut="envoyé"))
    session.commit()


def test_le_journal_nomme_le_canal_regle_dans_l_onglet(session):
    session.add(ConfigSite(cle="whatsapp_group_name", valeur="  Résidence — annonces  "))
    _journal_avec_un_envoi(session)

    lignes = list_whatsapp_logs(_Admin(), session)

    assert [ligne["canal"] for ligne in lignes] == ["Résidence — annonces"]


def test_sans_nom_de_canal_le_journal_ne_l_invente_pas(session):
    _journal_avec_un_envoi(session)

    lignes = list_whatsapp_logs(_Admin(), session)

    assert [ligne["canal"] for ligne in lignes] == [""]
