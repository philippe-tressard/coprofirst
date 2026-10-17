"""Les canaux, les vagues et la version cible portée par le bail (R5 #1881, §4.11 règle 6).

`registre/canaux.version_cible` est PURE : ses règles se jouent cas par cas, sans base.
Le reste — `replica` relu, les gestes de l'opérateur, le bail qui porte la version, la
mise à jour nocturne qui la lit — se joue de bout en bout dans
`test_registre_canaux_bail.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from app.registre import canaux
from app.registre.contrat import Bail
from app.registre.modeles import CanalDistribution, EtatInscription, Installation
from app.utils import taches

MAINTENANT = datetime(2026, 10, 20, 4, 20)


def _inst(**champs) -> Installation:
    defaut = dict(
        identifiant="CF-000002",
        etat=EtatInscription.active,
        canal="replica",
        vague=1,
        version_logicielle="2.170.0",
    )
    return Installation(**{**defaut, **champs})


def _canal(version="2.172.0", precedente="2.171.0", depuis=timedelta(days=5)) -> CanalDistribution:
    avance = None if depuis is None else MAINTENANT - depuis
    return CanalDistribution(
        nom="replica", version=version, version_precedente=precedente, avance_le=avance
    )


# ── Le format du bail ne s'étend pas ─────────────────────────────────────────


def test_le_bail_garde_ses_champs():
    """`Bail` refuse les champs inconnus : un champ neuf ferait REJETER le bail par toute
    installation pas encore à jour — plus de mise à jour automatique, donc jamais à jour.
    Ce que R5 décide voyage dans `version_cible`. Ajouter un champ ici, c'est ouvrir une
    nouvelle version du contrat ET prévoir comment les installations la rejoignent."""
    assert set(Bail.model_fields) == {
        "identifiant",
        "empreinte_cle",
        "etat",
        "canal",
        "version_cible",
        "services_autorises",
        "epoque",
        "delivre_le",
        "echeance",
    }


# ── La version cible (règles 3 à 6) ──────────────────────────────────────────


@pytest.mark.parametrize("etat", [EtatInscription.en_attente, EtatInscription.resiliee])
def test_sans_inscription_valide_aucune_version(etat):
    assert canaux.version_cible(_inst(etat=etat), _canal(), MAINTENANT) is None


def test_une_installation_suspendue_recoit_ses_correctifs():
    inst = _inst(etat=EtatInscription.suspendue)
    assert canaux.version_cible(inst, _canal(), MAINTENANT) == "2.172.0"


def test_epinglee_elle_recoit_sa_version_meme_plus_ancienne():
    """L'épinglage est le seul chemin d'un retour : l'ordre est signé avec le bail."""
    inst = _inst(version_epinglee="2.169.0")
    assert canaux.version_cible(inst, _canal(), MAINTENANT) == "2.169.0"


def test_sans_canal_ou_canal_non_lu_aucune_version():
    assert canaux.version_cible(_inst(), None, MAINTENANT) is None
    assert canaux.version_cible(_inst(), _canal(version=None), MAINTENANT) is None


@pytest.mark.parametrize(
    "vague, depuis, attendu",
    [
        (0, timedelta(hours=1), "2.172.0"),  # pilote : aussitôt
        (1, timedelta(hours=1), "2.171.0"),  # générale : pas avant J+1
        (1, timedelta(days=1), "2.172.0"),
        (2, timedelta(days=2), "2.171.0"),  # tardive : pas avant J+3
        (2, timedelta(days=3), "2.172.0"),
        (9, timedelta(hours=1), "2.171.0"),  # vague inconnue : la générale
    ],
)
def test_les_vagues(vague, depuis, attendu):
    inst = _inst(vague=vague)
    assert canaux.version_cible(inst, _canal(depuis=depuis), MAINTENANT) == attendu


def test_un_canal_jamais_avance_est_a_toutes_les_vagues():
    """Première lecture de `replica` : la version est promue depuis longtemps."""
    inst = _inst(vague=2)
    assert canaux.version_cible(inst, _canal(depuis=None), MAINTENANT) == "2.172.0"


def test_avant_son_tour_sans_version_precedente_aucune():
    inst = _inst(vague=2)
    canal = _canal(precedente=None, depuis=timedelta(hours=1))
    assert canaux.version_cible(inst, canal, MAINTENANT) is None


def test_le_canal_ne_fait_jamais_reculer():
    """Une installation en avance sur son canal y reste : reculer s'ordonne (épinglage)."""
    inst = _inst(version_logicielle="2.173.0")
    assert canaux.version_cible(inst, _canal(), MAINTENANT) == "2.173.0"
    #  Une version qui ne se compare pas (un commit) ne retient rien.
    inst = _inst(version_logicielle="5aa41dad0242")
    assert canaux.version_cible(inst, _canal(), MAINTENANT) == "2.172.0"


# ── `replica`, relu chaque nuit (règle 7) ────────────────────────────────────


class _Session:
    """Ce que `relire_replica` demande à une session : une ligne, ou l'ajout d'une ligne."""

    def __init__(self, canal=None):
        self.canal, self.ajoutes = canal, []

    def exec(self, _requete):
        canal = self.canal

        class _R:
            def first(self):
                return canal

        return _R()

    def add(self, objet):
        self.ajoutes.append(objet)


def test_la_premiere_lecture_pose_replica_sans_ouvrir_de_vague():
    s = _Session()
    assert "première fois" in canaux.relire_replica(s, "2.170.0", MAINTENANT)
    assert s.ajoutes[0].version == "2.170.0" and s.ajoutes[0].avance_le is None


def test_replica_avance_et_ouvre_les_vagues():
    canal = _canal(version="2.170.0", precedente=None)
    canaux.relire_replica(_Session(canal), "2.172.0", MAINTENANT)
    assert (canal.version, canal.version_precedente, canal.avance_le) == (
        "2.172.0",
        "2.170.0",
        MAINTENANT,
    )


@pytest.mark.parametrize("lue", ["2.169.0", "2.172.0", None, "404: Not Found"])
def test_replica_ne_recule_pas_et_une_lecture_illisible_ne_bouge_rien(lue):
    canal = _canal()
    avant = (canal.version, canal.version_precedente, canal.avance_le)
    canaux.relire_replica(_Session(canal), lue, MAINTENANT)
    assert (canal.version, canal.version_precedente, canal.avance_le) == avant


def test_lire_la_version_de_replica():
    vrai = lambda url, timeout: httpx.Response(200, json={"version": "2.172.0"})  # noqa: E731
    assert canaux.lire_version_replica(vrai) == "2.172.0"
    absent = lambda url, timeout: httpx.Response(404, text="404: Not Found")  # noqa: E731
    assert canaux.lire_version_replica(absent) is None

    def panne(url, timeout):
        raise httpx.ConnectError("injoignable")

    assert canaux.lire_version_replica(panne) is None
    assert canaux.URL_VERSION_REPLICA.endswith("/replica/front/package.json")


def test_la_lecture_de_replica_est_une_tache_de_la_plateforme():
    assert "canaux_registre" in taches.TACHES_PERMANENTES
    assert "canaux_registre" in taches.TACHES_DE_LA_PLATEFORME
