"""Le routeur `courriels_affaires` — l'onglet « Courriels » d'Espace CS (05/10/2026).

Qui lit le journal des relèves, et combien de lignes.

## 🔴 Pourquoi

Un transfert a été refusé (`TK-E000066` pour `TK-E00066`) et n'est resté visible
que de l'administrateur, dans Paramétrage › SMTP. Le journal est désormais lu par
le conseil syndical — mais **l'adresse d'un expéditeur est une donnée
personnelle** : le conseil n'en lit que le nom.

La vraie authentification est employée (`aides_http`) : un test qui surcharge
`require_cs_or_admin` ne verrait pas qu'un résident passe la porte.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.models.core import ConfigSite, RoleUtilisateur
from app.models.courriel import CourrielReleve
from app.utils import horloge
from app.utils.courriel_journal import (
    AFFICHES_MAX,
    AFFICHES_PAR_DEFAUT,
    CLE_AFFICHES,
    nombre_affiche,
)
from tests.aides_http import base_http, client_http

_ROUTE = "/courriels-affaires"
_EXPEDITEUR = "Gestionnaire <gestion@syndic.exemple.test>"


def _poser(moteur, n: int) -> None:
    maintenant = horloge.maintenant()
    with Session(moteur) as session:
        for i in range(n):
            session.add(
                CourrielReleve(
                    releve_le=maintenant - timedelta(minutes=n - i),
                    expediteur=_EXPEDITEUR,
                    objet=f"Message {i}",
                    decision="refuse",
                    motif="essai",
                )
            )
        session.commit()


def _regler(moteur, valeur: str) -> None:
    with Session(moteur) as session:
        session.add(ConfigSite(cle=CLE_AFFICHES, valeur=valeur))
        session.commit()


def test_un_anonyme_et_un_resident_sont_refuses():
    with base_http() as moteur:
        assert client_http(moteur, None)[0].get(_ROUTE).status_code == 401
        resident = client_http(moteur, RoleUtilisateur.résident)[0]
        assert resident.get(_ROUTE).status_code == 403


def test_le_conseil_lit_le_NOM_de_l_expediteur_pas_son_adresse():
    with base_http() as moteur:
        _poser(moteur, 1)
        http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        reponse = http.get(_ROUTE)
        assert reponse.status_code == 200, reponse.text
        ligne = reponse.json()["messages"][0]
        assert ligne["expediteur"] == "Gestionnaire"
        assert "syndic.exemple.test" not in reponse.text


def test_l_administrateur_lit_l_adresse_en_entier():
    with base_http() as moteur:
        _poser(moteur, 1)
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        assert http.get(_ROUTE).json()["messages"][0]["expediteur"] == _EXPEDITEUR


def test_le_parametre_borne_la_liste_et_la_plus_recente_vient_d_abord():
    with base_http() as moteur:
        _poser(moteur, 30)
        http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

        defaut = http.get(_ROUTE).json()
        assert defaut["limite"] == AFFICHES_PAR_DEFAUT == len(defaut["messages"])
        assert defaut["messages"][0]["objet"] == "Message 29", "le plus récent d'abord"

        _regler(moteur, "5")
        assert len(http.get(_ROUTE).json()["messages"]) == 5


def test_une_valeur_illisible_ou_hors_bornes_retombe_sur_une_valeur_sure():
    with base_http() as moteur:
        for brut, attendu in (
            ("abc", AFFICHES_PAR_DEFAUT),
            ("", AFFICHES_PAR_DEFAUT),
            ("0", 1),
            ("-4", 1),
            ("100000", AFFICHES_MAX),
        ):
            with Session(moteur) as session:
                ligne = session.get(ConfigSite, CLE_AFFICHES)
                if ligne:
                    ligne.valeur = brut
                else:
                    ligne = ConfigSite(cle=CLE_AFFICHES, valeur=brut)
                session.add(ligne)
                session.commit()
                assert nombre_affiche(session) == attendu, brut
