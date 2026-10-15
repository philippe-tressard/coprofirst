"""L'onglet « Installations » de la référence, et les services qu'il accorde (R4 #1880).

`routers/admin/installations.py` lit le registre et applique les gestes de
l'opérateur (`registre/decisions.py`) ; le bail les porte, et une RÉPLIQUE n'allume
que les services que son bail cru autorise (`utils/services.autorise_par_la_reference`).

Les deux côtés parlent pour de vrai (`aides_registre.installation_branchee`) : la
réplique s'inscrit, l'opérateur décide à la référence, la réplique renouvelle son
bail et constate.
"""

from __future__ import annotations

import pytest

from sqlmodel import Session, select

from app.config import get_settings
from app.inscription import client
from app.inscription.depot import Contact
from app.models.core import RoleUtilisateur
from app.models.roles import ROLE_OPERATEUR
from app.registre import conditions, migrer
from app.utils import installation
from app.utils.services import (
    SERVICE_IA,
    SERVICE_VERIF_VERSION,
    autorise_par_la_reference,
    cle_actif,
    service_actif,
)
from tests.aides_http import base_http, client_http
from tests.aides_registre import installation_branchee

CONTACT = Contact(prenom="Alix", nom="Durand", courriel="alix@example.org")
#: La référence s'inscrit la première dans son registre (id 1) : la réplique est la
#: deuxième ligne — comme en production, où la démo a reçu CF-000002.
REPLIQUE = "CF-000002"
IA_ALLUMEE = {cle_actif(SERVICE_IA): "1", cle_actif(SERVICE_VERIF_VERSION): "1"}


@pytest.fixture
def operateur(monkeypatch, tmp_path):
    """La référence (CF-000000), une réplique inscrite (`REPLIQUE`), l'opérateur connecté."""
    with installation_branchee(monkeypatch, tmp_path) as registre, base_http() as moteur:
        with Session(registre) as s:
            migrer.inscrire_reference(s)
        client.inscrire(CONTACT)
        http, ident = client_http(
            moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}"
        )
        yield http, ident


def _decider(http, geste: str, motif: str = "essai"):
    return http.post(
        f"/admin/installations/{REPLIQUE}/decisions", json={"geste": geste, "motif": motif}
    )


def test_registre_eteint_la_liste_le_dit_et_la_fiche_est_introuvable():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
        liste = http.get("/admin/installations")
        assert liste.status_code == 200
        assert liste.json()["actif"] is False and liste.json()["installations"] == []
        assert http.get(f"/admin/installations/{REPLIQUE}").status_code == 404


@pytest.mark.parametrize("roles", ["admin", "conseil_syndical"])
def test_seul_l_operateur_lit_le_registre(roles):
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=roles)
        assert http.get("/admin/installations").status_code == 403


def test_la_liste_et_la_fiche_montrent_l_inscription_et_son_contrat(operateur):
    http, _ = operateur
    liste = http.get("/admin/installations").json()
    assert liste["actif"] is True
    par_id = {i["identifiant"]: i for i in liste["installations"]}
    assert set(par_id) == {"CF-000000", REPLIQUE}
    assert par_id[REPLIQUE]["etat"] == "en_attente"
    assert par_id[REPLIQUE]["administrateur"] == "Alix DURAND"
    assert par_id[REPLIQUE]["services_autorises"] == []
    assert {s["code"] for s in liste["services_accordables"]} >= {SERVICE_IA}
    assert SERVICE_VERIF_VERSION not in {s["code"] for s in liste["services_accordables"]}

    fiche = http.get(f"/admin/installations/{REPLIQUE}").json()
    assert fiche["contact"]["courriel"] == "alix@example.org"
    #  Le contrat archivé est le texte EXACT accepté, sous l'identifiant (D26).
    version = conditions.version_en_vigueur()
    assert fiche["contrats"][0]["version"] == version
    assert fiche["contrats"][0]["texte"] == conditions.texte(version)
    assert [d["geste"] for d in fiche["decisions"]] == ["conditions_acceptees", "inscription"]
    assert http.get("/admin/installations/CF-000099").status_code == 404


def test_valider_puis_accorder_un_service_l_allume_sur_la_replique(operateur):
    http, ident = operateur
    #  En attente : aucun service, sauf la vérification de la version.
    assert not service_actif(IA_ALLUMEE, SERVICE_IA)
    assert service_actif(IA_ALLUMEE, SERVICE_VERIF_VERSION)

    r = _decider(http, "valider", "inscription vérifiée")
    assert r.status_code == 200, r.text
    assert r.json()["etat"] == "active"
    assert r.json()["decisions"][0] == {
        **r.json()["decisions"][0],
        "geste": "valider",
        "motif": "inscription vérifiée",
        "auteur": f"opérateur #{ident}",
    }
    client.renouveler()
    assert client.constat_courant().etat == "active"
    #  Active, mais aucun service accordé : toujours coupé, et la raison se dit.
    assert not service_actif(IA_ALLUMEE, SERVICE_IA)
    assert autorise_par_la_reference(SERVICE_IA) == (False, "Non autorisé par la référence.")

    r = http.put(
        f"/admin/installations/{REPLIQUE}/services",
        json={"services": [SERVICE_IA], "motif": "démo"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["services_autorises"] == [SERVICE_IA]
    #  La référence ne pousse pas : rien ne change avant le renouvellement du bail.
    assert not service_actif(IA_ALLUMEE, SERVICE_IA)
    client.renouveler()
    assert service_actif(IA_ALLUMEE, SERVICE_IA)

    #  Suspendue : plus aucun service, même accordé.
    assert _decider(http, "suspendre", "impayé").status_code == 200
    client.renouveler()
    assert not service_actif(IA_ALLUMEE, SERVICE_IA)


@pytest.mark.parametrize(
    "geste, attendu",
    [("retablir", 409), ("suspendre", 409), ("valider", 200), ("resilier", 200)],
)
def test_les_transitions_sont_declarees(operateur, geste, attendu):
    http, _ = operateur
    assert _decider(http, geste).status_code == attendu


def test_une_decision_sans_motif_ou_sur_la_reference_est_refusee(operateur):
    http, _ = operateur
    assert _decider(http, "valider", "").status_code == 422
    assert _decider(http, "valider", "   ").status_code == 409
    sur_la_reference = http.post(
        "/admin/installations/CF-000000/decisions", json={"geste": "resilier", "motif": "x"}
    )
    assert sur_la_reference.status_code == 409
    inconnu = http.put(
        f"/admin/installations/{REPLIQUE}/services",
        json={"services": ["teleportation"], "motif": "x"},
    )
    assert inconnu.status_code == 409
    resilie = _decider(http, "resilier", "clé perdue")
    assert resilie.json()["etat"] == "resiliee"
    assert _decider(http, "valider").status_code == 409


def test_une_replique_ne_peut_pas_allumer_un_service_non_autorise(monkeypatch, tmp_path):
    """L'écran Services et `PUT /config` disent la même chose que la lecture."""
    monkeypatch.setattr(get_settings(), "installation_dir", str(tmp_path))
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        #  Un rôle inconnu n'est pas une réplique : rien ne change pour lui.
        assert http.put("/config", json={cle_actif(SERVICE_IA): "1"}).status_code == 200
        monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "replique")
        #  Déjà allumé : l'onglet de réglages qui renvoie la clé s'enregistre encore —
        #  et la lecture, elle, le dit coupé.
        assert http.put("/config", json={cle_actif(SERVICE_IA): "1"}).status_code == 200
        assert http.put("/config", json={cle_actif(SERVICE_IA): "0"}).status_code == 200

        refus = http.put("/config", json={cle_actif(SERVICE_IA): "1"})
        assert refus.status_code == 409
        assert "Non autorisé par la référence" in refus.json()["detail"]
        assert http.put("/config", json={cle_actif(SERVICE_IA): "0"}).status_code == 200
        assert http.put("/config", json={cle_actif(SERVICE_VERIF_VERSION): "1"}).status_code == 200

        services = {s["code"]: s for s in http.get("/config/services").json()}
        assert services[SERVICE_IA]["autorise"] is False
        assert "Non autorisé par la référence" in services[SERVICE_IA]["refus"]
        assert services[SERVICE_VERIF_VERSION]["autorise"] is True


def test_la_carte_et_la_fiche_portent_les_alertes_de_l_installation(operateur):
    """R4b #1960 : une installation muette le dit dans la liste ET dans la fiche."""
    from datetime import timedelta

    from sqlmodel import select

    from app.registre import base
    from app.registre.modeles import Installation
    from app.utils import horloge

    http, _ = operateur
    sain = {i["identifiant"]: i for i in http.get("/admin/installations").json()["installations"]}
    assert sain[REPLIQUE]["alertes"] == [] and sain["CF-000000"]["alertes"] == []

    with Session(base.moteur()) as s:
        inst = s.exec(select(Installation).where(Installation.identifiant == REPLIQUE)).one()
        inst.vue_le = horloge.maintenant() - timedelta(days=3)
        s.add(inst)
        s.commit()
    liste = {i["identifiant"]: i for i in http.get("/admin/installations").json()["installations"]}
    (alerte,) = liste[REPLIQUE]["alertes"]
    assert alerte["code"] == "muette" and alerte["grave"] is True
    assert alerte["libelle"] == "Installation muette"
    assert http.get(f"/admin/installations/{REPLIQUE}").json()["alertes"] == [alerte]


def _supprimer(http, motif: str = "essai terminé"):
    return http.post(f"/admin/installations/{REPLIQUE}/suppression", json={"motif": motif})


def test_seule_une_installation_resiliee_se_supprime(operateur):
    http, _ = operateur
    assert (
        "supprimer" not in http.get(f"/admin/installations/{REPLIQUE}").json()["gestes_possibles"]
    )
    assert _supprimer(http).status_code == 409
    assert (
        http.post("/admin/installations/CF-000000/suppression", json={"motif": "x"}).status_code
        == 409
    )
    _decider(http, "resilier", "fin de l'essai")
    assert http.get(f"/admin/installations/{REPLIQUE}").json()["gestes_possibles"] == ["supprimer"]
    assert _supprimer(http, "").status_code == 422


def test_supprimer_efface_ce_qui_peut_l_etre_et_garde_le_contrat(operateur):
    """Coordonnées et rapports effacés, contrat archivé gardé, ligne et journal aussi."""
    from app.registre import base
    from app.registre.modeles import (
        AcceptationConditions,
        ContactInstallation,
        DecisionRegistre,
        Installation,
    )

    http, _ = operateur
    _decider(http, "resilier", "fin de l'essai")
    assert _supprimer(http).status_code == 204
    restantes = [i["identifiant"] for i in http.get("/admin/installations").json()["installations"]]
    assert REPLIQUE not in restantes and "CF-000000" in restantes
    assert http.get(f"/admin/installations/{REPLIQUE}").status_code == 404
    assert _supprimer(http).status_code == 404
    with Session(base.moteur()) as s:
        inst = s.exec(select(Installation).where(Installation.identifiant == REPLIQUE)).one()
        assert inst.effacee_le is not None and inst.services_autorises == "[]"

        def lignes(modele):
            return s.exec(
                select(modele).where(modele.installation_id == inst.id).order_by(modele.id)
            ).all()

        assert lignes(ContactInstallation) == []
        assert len(lignes(AcceptationConditions)) == 1
        assert lignes(DecisionRegistre)[-1].geste == "supprimer"


def test_la_meme_cle_qui_revient_retrouve_son_identifiant(operateur):
    """Le numéro ne se réattribue pas : la réplique supprimée qui revient est revue, résiliée."""
    http, _ = operateur
    _decider(http, "resilier", "fin de l'essai")
    _supprimer(http)
    client.inscrire(CONTACT)
    fiche = http.get(f"/admin/installations/{REPLIQUE}").json()
    assert fiche["etat"] == "resiliee" and fiche["contact"]["courriel"] == CONTACT.courriel
    assert fiche["decisions"][0]["geste"] == "retour_apres_suppression"
