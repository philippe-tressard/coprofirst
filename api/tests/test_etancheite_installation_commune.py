"""L'installation commune RÉELLE, de bout en bout : rien d'une copropriété chez l'autre (#2053).

Rien n'y est remplacé : une déclaration (`COPROPRIETES_FICHIER`), deux vraies
bases préparées par `utils/preparer_bases`, semées par le démarrage
(`app/demarrage`), et la copropriété résolue par le seul en-tête `Host` —
l'adresse dérivée de chacune. Une troisième, à la base injoignable, est le
témoin de l'isolement : 503 pour son hôte seul, les deux autres servent, ses
tâches sont sautées. Cas zéro : chacune se lit elle-même.

Séparé de `test_etancheite_coproprietes.py` (#2223) : sa fixture de module met
le processus entier en installation commune, que la fixture de l'autre refuse —
les deux ne tenaient ensemble que par l'ordre d'écriture des tests, et l'ordre
tiré au sort les a fait tomber.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import contexte
from app.installation_commune.bases_pretes import INDISPONIBLE
from app.main import app
from tests.aides_commune_reelle import installation_commune_reelle, sous
from tests.aides_etancheite import (
    MARQUE_A,
    MARQUE_B,
    MINIMUM_LECTURES_B,
    MINIMUM_REPONSES_200,
    chemins_get,
    fuites,
    temoins_dans,
)
from tests.aides_installation_commune import HOTE_COMMUN


@pytest.fixture(scope="module")
def commune(tmp_path_factory):
    """L'installation commune réelle (`tests/aides_commune_reelle`), A et B marqués."""
    with installation_commune_reelle(tmp_path_factory.mktemp("commune"), temoins_dans) as c:
        yield c


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_chaque_base_est_preparee_et_la_mauvaise_ne_bloque_pas(commune):
    """`start.sh` : la base injoignable, déclarée la première, n'arrête pas les autres."""
    assert commune["journal"][:3] == [
        "copropriete essai-c : illisible",
        "copropriete essai-a : posee",
        "copropriete essai-b : posee",
    ]
    assert commune["code"] == 0


def test_l_hote_seul_choisit_la_copropriete_cas_zero_et_temoin(commune):
    client = _client()
    for nom, marque in (("a", MARQUE_A), ("b", MARQUE_B)):
        jeton, _ident = commune["temoins"][nom]
        reponse = sous(client, "/auth/me", nom, jeton)
        assert reponse.status_code == 200 and marque in reponse.text, reponse.text
    #  Les identifiants sont identiques, les jetons ne passent pas d'une base à l'autre.
    assert commune["temoins"]["a"][1] == commune["temoins"]["b"][1]
    jeton_a, _ = commune["temoins"]["a"]
    chez_b = sous(client, "/auth/me", "b", jeton_a)
    assert chez_b.status_code == 401 and MARQUE_A not in chez_b.text


def test_aucune_reponse_servie_sous_l_hote_de_B_ne_porte_A(commune):
    client = _client()
    jeton_b, _ = commune["temoins"]["b"]
    reponses = {c: sous(client, c, "b", jeton_b) for c in chemins_get()}
    reussies = sum(1 for r in reponses.values() if r.status_code == 200)
    assert reussies >= MINIMUM_REPONSES_200, f"cas zéro : {reussies} réponse(s) 200"
    assert len(fuites(reponses, MARQUE_B)) >= MINIMUM_LECTURES_B, "témoin : B ne se lit pas"
    assert not fuites(reponses, MARQUE_A), (
        "Donnée de A servie sous l'hôte de B (#2053) :\n  "
        + "\n  ".join(fuites(reponses, MARQUE_A))
    )


def test_la_base_injoignable_n_isole_que_son_hote(commune):
    client = _client()
    chez_c = sous(client, "/config", "c")
    assert chez_c.status_code == 503 and chez_c.json() == {"detail": INDISPONIBLE}
    assert sous(client, "/config", "a").status_code == 200
    sante = client.get("/health", headers={"host": HOTE_COMMUN})
    assert sante.status_code == 200 and sante.json()["status"] == "degrade"
    assert "essai" not in sante.text  # ni nom ni identifiant : la route répond à tout hôte


def test_l_hote_commun_et_un_hote_inconnu_ne_servent_rien(commune):
    client = _client()
    jeton_a, _ = commune["temoins"]["a"]
    for hote in (HOTE_COMMUN, "inconnu.example", "localhost"):
        reponse = client.get("/auth/me", headers={"host": hote}, cookies={"access_token": jeton_a})
        assert reponse.status_code == 421, hote


def test_une_tache_tourne_pour_chacune_et_saute_la_base_injoignable(commune):
    vues: list[str] = []
    contexte.pour_chaque_copropriete(
        lambda: vues.append(contexte.courante().identifiant), "essai"
    )()
    assert vues == ["essai-a", "essai-b"]


def test_hors_requete_aucune_copropriete_n_est_devinee(commune):
    with pytest.raises(contexte.HorsCopropriete):
        contexte.courante()


def test_les_mesures_de_l_installation_ne_supposent_aucune_copropriete(commune):
    """Le rapport nocturne mesure l'installation hors requête : il nomme ses
    copropriétés une à une, il ne s'en remet pas à une « courante » (#2053)."""
    from app.inscription import rapport

    assert rapport.hebergement().moteur_base == "postgresql"
    assert rapport.posture().secret_suffisant is True
