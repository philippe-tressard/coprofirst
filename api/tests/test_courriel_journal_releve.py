"""Le journal des messages relevés — chaque verdict y laisse sa ligne (#1447).

## 🔴 Pourquoi

Le 28/09/2026, un message relevé dans la boîte des réponses — sans doute celui
d'un membre du conseil, « absente cette semaine » — a été **ignoré sans qu'on
puisse dire pourquoi**. La relève ne gardait que des totaux (`écrites=1
relances=0 refusées=1 ignorées=1`), dans un journal de conteneur que deux MEP
le même jour avaient effacé. Les verdicts IGNORE étaient muets par construction.

Ce fichier exige, pour **chacun des quatre verdicts** de `traiter`, une ligne
de journal : expéditeur, objet, affaire, verdict et **motif non vide**. Et il
exige ce que la ligne ne porte PAS : le corps du message (`standards/14`).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.database import engine
from app.models.core import StatutTicket
from app.models.courriel import CourrielReleve, RelanceCourriel
from app.utils import horloge
from app.utils.courriel_boite import traiter
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.courriel_ingestion import A_CLASSER, ACCEPTE, IGNORE, REFUSE, RELANCE
from app.utils.courriel_journal import CONSERVATION_RELEVES_JOURS
from tests.aides_courriel import _AUTH_OK, _entetes_reponse, scene  # noqa: F401 — fixture
from tests.aides_purge import purger_ligne

_RECU = datetime(2026, 9, 3)


def _lignes(session: Session, adresse: str) -> list[CourrielReleve]:
    return session.exec(
        select(CourrielReleve).where(CourrielReleve.expediteur.contains(adresse))
    ).all()


#: Un expéditeur authentifié sans compte ni fiche du syndic : rien ne l'attend.
_INCONNU = "inconnu@ailleurs.test"


def _purger(session: Session, adresse: str) -> None:
    for ligne in _lignes(session, adresse):
        purger_ligne(session, CourrielReleve, ligne.id)
    session.commit()


def test_chacun_des_QUATRE_verdicts_laisse_sa_ligne(scene):  # noqa: F811
    session, ticket, syndic, _cs = scene
    relance = RelanceCourriel(jeton=nouveau_jeton(), tickets_json=json.dumps([ticket.id]))
    session.add(relance)
    session.commit()
    try:
        rendus = [
            traiter(
                session,
                _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
                "Jeudi.",
                _RECU,
                authentification=_AUTH_OK,
            ),
            traiter(
                session,
                _entetes_reponse(relance.jeton, de=syndic.email),
                "Pour le lot : jeudi.",
                _RECU,
                authentification=_AUTH_OK,
            ),
            #  Non authentifié : refusé.
            traiter(
                session, _entetes_reponse(ticket.jeton_courriel, de=syndic.email), "Fermez.", _RECU
            ),
            #  Ni jeton, ni référence, ni numéro, d'un correspondant connu : à
            #  classer par le conseil (#2555) — il était ignoré sans un mot.
            traiter(
                session,
                {"From": syndic.email, "Subject": "Bonjour"},
                "…",
                _RECU,
                authentification=_AUTH_OK,
            ),
        ]
        assert rendus == [ACCEPTE, RELANCE, REFUSE, A_CLASSER]

        lignes = sorted(_lignes(session, syndic.email), key=lambda ligne: ligne.id)
        assert [ligne.decision for ligne in lignes] == rendus
        for ligne in lignes:
            assert ligne.motif.strip(), f"verdict {ligne.decision} sans motif"
            assert ligne.releve_le is not None
            assert ligne.envoye_le == _RECU
        assert lignes[0].ticket_id == ticket.id and lignes[0].affaire == ticket.numero
        assert lignes[2].ticket_id == ticket.id, "un refus nomme l'affaire visée"
        assert lignes[3].ticket_id is None
        assert lignes[3].objet == "Bonjour"
    finally:
        _purger(session, syndic.email)
        purger_ligne(session, RelanceCourriel, relance.id)
        session.commit()


def test_les_IGNORE_disent_POURQUOI_et_pas_tous_la_meme_chose(scene):  # noqa: F811
    """Les trois silences du 28/09 : sans rapport, jeton inconnu, affaire close."""
    session, ticket, syndic, _cs = scene
    try:
        #  D'un INCONNU : d'un correspondant connu, ces deux messages attendraient
        #  d'être classés (#2555, `test_courriel_a_classer`).
        sans_rapport = traiter(
            session, {"From": _INCONNU, "Subject": "Pub"}, "…", _RECU, authentification=_AUTH_OK
        )
        inconnu = traiter(
            session,
            _entetes_reponse(nouveau_jeton(), de=_INCONNU),
            "…",
            _RECU,
            authentification=_AUTH_OK,
        )
        ticket.statut = StatutTicket.résolu
        session.add(ticket)
        session.commit()
        close = traiter(
            session,
            _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
            "Merci.",
            _RECU,
            authentification=_AUTH_OK,
        )
        assert [sans_rapport, inconnu, close] == [IGNORE] * 3

        lignes = _lignes(session, syndic.email) + _lignes(session, _INCONNU)
        motifs = [ligne.motif for ligne in lignes]
        assert len(motifs) == 3 and len(set(motifs)) == 3, motifs
        assert any(ticket.numero in m and "close" in m for m in motifs), motifs
    finally:
        _purger(session, syndic.email)
        _purger(session, _INCONNU)


def test_la_ligne_ne_porte_JAMAIS_le_corps_du_message():
    """Donnée personnelle et contenu privé : le journal dit ce qu'on a DÉCIDÉ.

    Le texte, s'il est accepté, vit dans le fil de l'affaire ; refusé ou ignoré,
    il reste dans la boîte de réception. Une colonne de plus, ici, en ferait une
    seconde copie que rien ne purge au même rythme.
    """
    assert set(CourrielReleve.model_fields) == {
        "id",
        "releve_le",
        "envoye_le",
        "expediteur",
        "objet",
        "decision",
        "motif",
        "ticket_id",
        "affaire",
    }


def test_le_journal_se_PURGE_a_duree_bornee():
    from app.utils.maintenance import purger

    adresse = f"ancien-{uuid.uuid4().hex[:8]}@exemple.test"
    maintenant = horloge.maintenant()
    with Session(engine) as session:
        for age in (CONSERVATION_RELEVES_JOURS + 1, CONSERVATION_RELEVES_JOURS - 1):
            session.add(
                CourrielReleve(
                    releve_le=maintenant - timedelta(days=age),
                    expediteur=adresse,
                    decision=IGNORE,
                    motif="essai",
                )
            )
        session.commit()
    try:
        comptes, erreurs = purger()
        assert not erreurs, erreurs
        assert comptes["releves"] >= 1
        with Session(engine) as session:
            restants = _lignes(session, adresse)
            assert len(restants) == 1, "seule la ligne dans la durée de conservation reste"
    finally:
        with Session(engine) as session:
            _purger(session, adresse)
