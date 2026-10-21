"""La politique de confidentialité ANNONCE la conservation des affaires — case cochée (#2014).

Spec §11, arbitrage 1 : la phrase entre dans le texte servi quand l'administrateur
coche « Conservation des affaires », pas avant (coupée, rien n'est appliqué : les
durées annoncées seraient fictives, `standards/14`). Elle se compose de `DUREES`.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.core import ConfigSite, RoleUtilisateur
from app.seed.contenus_legaux import DEFAULT_LEGAL
from app.seed.contenus_legaux_conservation import AVANT_CONSERVATION, CONSERVATION_AFFAIRES
from app.utils import conservation_affaires as ca
from app.utils.conservation_politique import CLE, annoncer, politique_annonce
from app.utils.services import SERVICE_CONSERVATION, cle_actif
from tests.aides_http import base_http, client_http

GABARIT = DEFAULT_LEGAL[CLE]
CLE_CASE = cle_actif(SERVICE_CONSERVATION)


def _servi(session: Session) -> str:
    session.expire_all()
    return session.get(ConfigSite, CLE).valeur


def test_le_gabarit_ne_l_annonce_pas_et_porte_son_ancre_une_fois():
    """Case coupée à la livraison : le gabarit reste muet, mais l'ancre existe."""
    assert CONSERVATION_AFFAIRES not in GABARIT
    assert GABARIT.count(AVANT_CONSERVATION) == 1


def test_la_phrase_se_compose_de_la_table_des_durees():
    """Aucune durée recopiée : chaque type de `DUREES` y figure, avec son fondement."""
    for t in ca.TYPES:
        assert f"{t.exercices}\xa0exercices" in CONSERVATION_AFFAIRES
        assert t.fondement in CONSERVATION_AFFAIRES
    assert "sans limite de durée" in CONSERVATION_AFFAIRES
    assert "photo peut montrer des personnes" in CONSERVATION_AFFAIRES


def test_annoncer_insere_avant_l_ancre_une_seule_fois(session: Session):
    session.add(ConfigSite(cle=CLE, valeur=GABARIT))
    session.commit()
    assert not politique_annonce(session)
    assert annoncer(session) is True
    session.commit()
    texte = _servi(session)
    assert texte.count(CONSERVATION_AFFAIRES) == 1
    assert CONSERVATION_AFFAIRES + AVANT_CONSERVATION in texte
    assert annoncer(session) is True
    session.commit()
    assert _servi(session) == texte


def test_sans_ligne_en_base_elle_part_du_gabarit(session: Session):
    assert annoncer(session) is True
    session.commit()
    assert _servi(session) == GABARIT.replace(
        AVANT_CONSERVATION, CONSERVATION_AFFAIRES + AVANT_CONSERVATION
    )


def test_un_texte_retouche_n_est_pas_reecrit_et_le_dit(session: Session):
    retouche = GABARIT.replace(AVANT_CONSERVATION, "<li>Reformulé.</li>")
    session.add(ConfigSite(cle=CLE, valeur=retouche))
    session.commit()
    assert annoncer(session) is False
    assert _servi(session) == retouche
    assert not politique_annonce(session)


def test_cocher_la_case_annonce_et_pas_avant():
    """Le parcours entier, par l'API : rien avant la case, la phrase une fois après."""
    with base_http() as moteur:
        with Session(moteur) as s:
            s.add(ConfigSite(cle=CLE, valeur=GABARIT))
            s.commit()
        admin, _ = client_http(moteur, RoleUtilisateur.admin)

        assert admin.put("/config", json={"notify_ticket_bug_email": "0"}).status_code == 200
        avant = admin.get("/admin/conservation-affaires").json()
        assert avant["application_active"] is False and avant["politique_annonce"] is False
        with Session(moteur) as s:
            assert _servi(s) == GABARIT

        for _ in range(2):  # cocher deux fois ne l'écrit qu'une
            assert admin.put("/config", json={CLE_CASE: "1"}).status_code == 200
        apres = admin.get("/admin/conservation-affaires").json()
        assert apres["application_active"] is True and apres["politique_annonce"] is True
        with Session(moteur) as s:
            assert _servi(s).count(CONSERVATION_AFFAIRES) == 1

        #  Décocher ne retire rien : ce qui a été archivé reste vrai.
        assert admin.put("/config", json={CLE_CASE: "0"}).status_code == 200
        with Session(moteur) as s:
            assert _servi(s).count(CONSERVATION_AFFAIRES) == 1


def test_case_cochee_sur_un_texte_retouche_le_constat_le_dit():
    with base_http() as moteur:
        with Session(moteur) as s:
            s.add(ConfigSite(cle=CLE, valeur=GABARIT.replace(AVANT_CONSERVATION, "")))
            s.commit()
        admin, _ = client_http(moteur, RoleUtilisateur.admin)
        assert admin.put("/config", json={CLE_CASE: "1"}).status_code == 200
        lu = admin.get("/admin/conservation-affaires").json()
        assert lu["application_active"] is True and lu["politique_annonce"] is False
