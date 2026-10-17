"""Un modèle d'e-mail non désactivable part toujours (#2054).

Admin › Modèles e-mail laissait décocher « Actif » sur le mot de passe oublié, la
vérification d'adresse, l'avis de changement d'adresse et l'alerte système, et
`send_email` abandonnait alors l'envoi. Un clic suffisait à ce que plus personne
ne récupère son compte — contre la règle des courriels de sécurité, qu'aucun
interrupteur ne coupe (`services.COURRIELS_DE_SECURITE`).

`test_courriels_securite_hors_service.py` ne pouvait pas le voir : il lit le CODE
(un envoi de sécurité ne lit aucun interrupteur de service), et l'interrupteur
était ici une DONNÉE, la colonne `modele_email.actif`. Ce fichier-ci éprouve le
comportement : le courriel part, la case se refuse, l'écran reçoit la règle.

La règle se lit dans le code — `seed.emails.NON_DESACTIVABLES`, le cinquième
élément de chaque modèle — et non dans la colonne `desactivable`, qu'une ligne
ancienne peut contredire.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.models.core import ConfigSite, ModeleEmail
from app.routers.admin.communications import _modele_lu, update_modele_email
from app.seed import EMAIL_TEMPLATES
from app.seed.emails import NON_DESACTIVABLES, est_desactivable
from app.utils.services import COURRIELS_DE_SECURITE

#: Un contexte qui rend chaque courriel de sécurité (`EXPECTED_VARS`).
CONTEXTES = {
    "reinitialisation_mdp": {
        "destinataire": {"prenom": "Prénom", "nom": "Nom"},
        "lien": "https://exemple.fr/reinitialiser",
    },
    "verification_email": {
        "prenom": "Prénom",
        "lien": "https://exemple.fr/verifier",
        "expire_heures": 24,
    },
    "adresse_changement_avis": {
        "destinataire": {"prenom": "Prénom", "nom": "Nom"},
        "nouvelle_adresse": "nouvelle@exemple.fr",
        "par_un_administrateur": False,
    },
    "alerte_systeme": {
        "problemes": ["Sauvegarde absente"],
        "nb_problemes": 1,
        "date_controle": "17/10/2026",
    },
}


def test_les_courriels_de_securite_sont_non_desactivables():
    """Un courriel de sécurité ajouté au registre doit l'être aussi au seed."""
    oublies = COURRIELS_DE_SECURITE - NON_DESACTIVABLES
    assert not oublies, f"Courriels de sécurité désactivables dans le seed : {sorted(oublies)}"


def test_chaque_courriel_de_securite_a_son_contexte_ici():
    """Témoin : le test d'envoi ci-dessous couvre TOUS les courriels de sécurité."""
    assert set(CONTEXTES) == set(COURRIELS_DE_SECURITE)


@pytest.fixture
def faux_smtp(monkeypatch):
    """L'envoi réel remplacé : ce qui part est noté, rien ne sort."""
    partis: list = []

    class _FauxFastMail:
        def __init__(self, cfg):
            pass

        async def send_message(self, message):
            partis.append(message)

    monkeypatch.setattr("fastapi_mail.FastMail", _FauxFastMail)
    #  La connexion n'est pas ce qu'on éprouve : sa validation exigerait un serveur réel.
    monkeypatch.setattr("app.utils.email.connexion_smtp", lambda *a, **k: None)
    return partis


def _poser_modele(session, code: str, *, actif: bool) -> None:
    _code, libelle, sujet, corps, _ = next(t for t in EMAIL_TEMPLATES if t[0] == code)
    session.add(ModeleEmail(code=code, libelle=libelle, sujet=sujet, corps_html=corps, actif=actif))
    session.add(ConfigSite(cle="smtp_enabled", valeur="1"))
    session.commit()


@pytest.mark.parametrize("code", sorted(COURRIELS_DE_SECURITE))
def test_un_courriel_de_securite_decoche_part_quand_meme(session, faux_smtp, code):
    from app.utils.email import send_email

    _poser_modele(session, code, actif=False)
    parti = asyncio.run(send_email(code, "resident@exemple.fr", CONTEXTES[code], session))
    assert parti is True and len(faux_smtp) == 1


def test_un_modele_desactivable_decoche_ne_part_pas(session, faux_smtp):
    """La case garde son effet là où elle en a un."""
    from app.utils.email import send_email

    assert est_desactivable("compte_active")
    _poser_modele(session, "compte_active", actif=False)
    contexte = {"destinataire": {"prenom": "Prénom", "nom": "Nom"}}
    assert asyncio.run(send_email("compte_active", "r@exemple.fr", contexte, session)) is False
    assert faux_smtp == []


class _Session:
    """Une session qui rend LE modèle, et compte ce qui a été enregistré."""

    def __init__(self, modele):
        self._modele = modele
        self.commits = 0

    def get(self, _classe, _id):
        return self._modele

    def add(self, _objet):
        pass

    def commit(self):
        self.commits += 1

    def refresh(self, _objet):
        pass


class _Admin:
    id = 42


def _ligne(code: str) -> ModeleEmail:
    _code, libelle, sujet, corps, _ = next(t for t in EMAIL_TEMPLATES if t[0] == code)
    #  `desactivable=True` en base, exprès : c'est le CODE qui décide.
    return ModeleEmail(
        id=1, code=code, libelle=libelle, sujet=sujet, corps_html=corps, desactivable=True
    )


@pytest.mark.parametrize("code", sorted(NON_DESACTIVABLES))
def test_decocher_un_modele_non_desactivable_est_refuse(code):
    session = _Session(_ligne(code))
    with pytest.raises(HTTPException) as refus:
        update_modele_email(1, {"actif": False}, session, _Admin())
    assert refus.value.status_code == 422
    assert session.commits == 0


def test_le_reste_d_un_modele_non_desactivable_se_modifie():
    """Le refus ne vise que la case : le sujet se corrige comme ailleurs."""
    session = _Session(_ligne("reinitialisation_mdp"))
    update_modele_email(1, {"sujet": "Nouveau sujet", "actif": True}, session, _Admin())
    assert session.commits == 1


def test_decocher_un_modele_desactivable_reste_permis():
    session = _Session(_ligne("compte_active"))
    lu = update_modele_email(1, {"actif": False}, session, _Admin())
    assert lu["actif"] is False and session.commits == 1


def test_l_ecran_recoit_la_regle_du_code_pas_la_colonne():
    assert _modele_lu(_ligne("reinitialisation_mdp"))["desactivable"] is False
    assert _modele_lu(_ligne("compte_active"))["desactivable"] is True
