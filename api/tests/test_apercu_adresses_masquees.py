"""L'aperçu d'une diffusion ne sert pas les adresses du conseil à tout lecteur (#2155).

`POST /tickets/apercu-diffusion` et `POST /annonces-hall/apercu-diffusion` ne
demandent qu'une session : un locataire, ou un compte externe, cochait « prévenir
le conseil » sur un brouillon factice et repartait avec les adresses personnelles
de ses membres — que l'annuaire ne publie pas. Ce test lit la RÉPONSE, selon le
lecteur (`standards/03` §2).
"""

from __future__ import annotations

from app.models.core import StatutUtilisateur
from app.models.exploitation import ModeleEmail
from app.utils.apercu_diffusion import apercu_email
from tests.aides_base import compte


def _modele(session, code: str) -> None:
    """Un modèle sans variable : ce test lit les DESTINATAIRES, pas le corps."""
    session.add(ModeleEmail(code=code, libelle=code, sujet="Objet", corps_html="<p>Corps</p>"))
    session.commit()


def _apercu(session, lecteur, conseil, copie=None):
    return apercu_email(
        session,
        code_modele="ticket_syndic",
        contexte={},
        destinataires=[(conseil.id, conseil.email)],
        lecteur=lecteur,
        copie_auteur=copie,
    )


def test_un_locataire_ne_lit_pas_l_adresse_du_conseil(session):
    _modele(session, "ticket_syndic")
    conseil = compte(session, prefixe="conseil", roles_json="conseil_syndical")
    locataire = compte(session, prefixe="loc", statut=StatutUtilisateur.locataire)
    canal = _apercu(session, locataire, conseil, copie=locataire.email)
    assert canal.actif, canal.inactif_motif
    assert conseil.email not in " ".join(canal.destinataires), canal.destinataires
    assert any("***@" in d for d in canal.destinataires)
    #  Sa propre copie, il la connaît : elle reste lisible.
    assert f"{locataire.email} (copie)" in canal.destinataires


def test_le_conseil_lit_les_adresses_qu_il_verifie(session):
    _modele(session, "ticket_syndic")
    conseil = compte(session, prefixe="conseil", roles_json="conseil_syndical")
    autre = compte(session, prefixe="autre", roles_json="conseil_syndical")
    assert _apercu(session, autre, conseil).destinataires == [conseil.email]
