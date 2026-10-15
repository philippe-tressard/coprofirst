"""Une réponse à une relance groupée est CONSERVÉE, pas seulement notifiée.

Séparé de `test_courriel_reponse_ticket.py` au fil de l'eau : ce fichier avait
franchi les 500 lignes du plafond de modularité (rang 1 §4), et la couture est
réelle — là-bas on éprouve le rattachement à UN ticket et l'authentification,
ici la conservation d'une réponse qui parle de PLUSIEURS dossiers.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from app.models.courriel import RelanceCourriel, ReponseRelance
from app.utils.courriel_boite import traiter
from app.utils.courriel_entrant import nouveau_jeton as _jeton
from app.utils.courriel_ingestion import RELANCE
from tests.aides_purge import purger_ligne

#  La scène (ticket + comptes + fiche syndic) et les en-têtes d'une réponse
#  vivent dans `aides_courriel` (#1495) : plus aucun fichier de tests ne sert
#  de bibliothèque à un autre.
from tests.aides_courriel import (  # noqa: F401 — `scene` est une fixture
    _AUTH_OK,
    _entetes_reponse,
    _evolutions,
    scene,
)


# ── La réponse à une relance est CONSERVÉE, pas seulement notifiée ───────────


def test_une_reponse_a_une_relance_est_conservee_pour_etre_RELUE(scene):
    """🔴 Corrigé le 04/09/2026 : *« où sera affiché le retour syndic ? »*.

    La première version se contentait d'une notification portant le texte. Elle
    répondait à « le conseil est-il prévenu ? » et pas à « où le relit-on ? ».
    Une notification se lit une fois puis descend dans la pile ; passé quelques
    jours, la réponse était en base — dans un champ `corps` — et introuvable.

    ⚠️ C'est le défaut même que ce chantier corrige, déplacé de la boîte aux
    lettres vers une table de notifications. Ce n'est pas la même chose que le
    résoudre.
    """
    session, ticket, syndic, cs = scene
    #  ⚠️ Les tests voisins créent aussi des relances sans purger leurs réponses,
    #  dans la même base : sans ce nettoyage, on compterait les
    #  leurs. L'isolation appartient au test, pas à la chance.
    for vieille in session.exec(select(ReponseRelance)).all():
        purger_ligne(session, ReponseRelance, vieille.id)
    session.commit()

    relance = RelanceCourriel(jeton=_jeton(), tickets_json=f"[{ticket.id}]")
    session.add(relance)
    session.commit()
    session.refresh(relance)

    decision = traiter(
        session,
        _entetes_reponse(relance.jeton, de=syndic.email),
        "Le TK-1 est traité, le TK-2 attend le devis.",
        datetime(2026, 9, 4),
        authentification=_AUTH_OK,
    )
    #  RELANCE et non ACCEPTE : reçue et conservée, mais volontairement pas
    #  ventilée dans les fils. Le verdict dit ce qui a été FAIT.
    assert decision == RELANCE

    conservees = session.exec(
        select(ReponseRelance).where(ReponseRelance.relance_id == relance.id)
    ).all()
    assert len(conservees) == 1, "la réponse n'est conservée nulle part"
    assert "attend le devis" in conservees[0].contenu
    assert syndic.email in conservees[0].expediteur

    #  Et elle n'est TOUJOURS pas ventilée dans les fils : c'est la décision de
    #  fond, et la conserver ne la remet pas en cause.
    assert _evolutions(session, ticket) == []

    for r in conservees:
        purger_ligne(session, ReponseRelance, r.id)
    purger_ligne(session, RelanceCourriel, relance.id)
    session.commit()


def test_plusieurs_reponses_s_AJOUTENT_sans_ecraser(scene):
    """Le jeton ne s'épuise pas : le syndic peut répondre plusieurs fois.

    Écraser la précédente perdrait ce qu'on vient tout juste de sauver — un
    message par dossier, ou une précision le lendemain, sont le cas normal.
    """
    session, ticket, syndic, _cs = scene
    for vieille in session.exec(select(ReponseRelance)).all():
        purger_ligne(session, ReponseRelance, vieille.id)
    session.commit()

    relance = RelanceCourriel(jeton=_jeton(), tickets_json=f"[{ticket.id}]")
    session.add(relance)
    session.commit()
    session.refresh(relance)

    for texte in ("Premier point.", "Précision du lendemain."):
        traiter(
            session,
            _entetes_reponse(relance.jeton, de=syndic.email),
            texte,
            datetime(2026, 9, 4),
            authentification=_AUTH_OK,
        )

    conservees = session.exec(
        select(ReponseRelance).where(ReponseRelance.relance_id == relance.id)
    ).all()
    assert len(conservees) == 2, "la seconde réponse a écrasé la première"

    for r in conservees:
        purger_ligne(session, ReponseRelance, r.id)
    purger_ligne(session, RelanceCourriel, relance.id)
    session.commit()
