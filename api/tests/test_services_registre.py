"""Le registre des services est la seule lecture d'une activation (#1718).

Trois services — assistant IA, diffusion WhatsApp, réponses par courriel — se
lisaient chacun par sa propre règle, dont une plus large que les deux autres.
`utils/services` porte désormais la seule : ce fichier refuse qu'une clé
d'activation soit écrite ailleurs dans `app/`, et tient l'écran qui s'en déduit
(`GET /config/services`, routeur `config_services`).
"""

from __future__ import annotations

import ast
import json
import pathlib
import re

import pytest
from sqlmodel import Session

from app.models.core import ConfigSite, RoleUtilisateur
from app.utils.services import (
    CLES_ACTIVATION,
    ETAT_ACTIF,
    ETAT_COUPE,
    ETAT_INCOMPLET,
    INFRA_SMTP,
    SERVICE_DIFFUSION,
    SERVICE_IA,
    SERVICE_REPONSES_COURRIEL,
    SERVICES,
    cle_actif,
    etat,
    normaliser_activation,
    service_actif,
)
from tests.aides_http import base_http, client_http
from tests.aides_sources import chaines_du_code, module_app, modules_app

REGISTRE = "utils/services.py"
FRONT = pathlib.Path(__file__).resolve().parents[2] / "front/src/lib"
PAGES_ROLES = FRONT / "pages-roles.ts"
ICONES = FRONT / "icones-svg.json"


def _cles_ecrites(source: str) -> list[tuple[int, str]]:
    """Les clés d'activation écrites en littéral dans ce source — docstrings exclues."""
    return [
        (n.lineno, n.value)
        for n in chaines_du_code(ast.parse(source))
        if n.value in CLES_ACTIVATION
    ]


def test_le_controle_refuse_une_lecture_recopiee():
    """Le cas fautif d'abord : la forme exacte qui vivait dans `courriel_boite.py`."""
    fautif = 'def relever(cfg):\n    return (cfg.get("imap_enabled") or "").lower() == "1"\n'
    assert _cles_ecrites(fautif) == [(2, "imap_enabled")]
    #  … et une docstring qui NOMME la clé n'est pas une lecture.
    assert _cles_ecrites('def f():\n    """Lit `imap_enabled`."""\n') == []


def test_aucune_cle_d_activation_n_est_ecrite_hors_du_registre():
    ecarts = [
        f"app/{m.rel}:{ligne} — « {cle} »"
        for m in modules_app(minimum=100)
        if m.rel != REGISTRE
        for ligne, cle in _cles_ecrites(m.source)
    ]
    assert not ecarts, (
        "Une clé d'activation de service est lue hors de `utils/services` : passer par "
        "`service_actif(cfg, SERVICE_…)` ou `cle_actif(SERVICE_…)`.\n" + "\n".join(ecarts)
    )


def test_le_temoin_le_registre_porte_chaque_cle():
    """Le cas zéro : si le registre ne les écrivait plus, le contrôle ne verrait rien."""
    ecrites = {cle for _, cle in _cles_ecrites(module_app(REGISTRE).source)}
    assert (
        ecrites
        == CLES_ACTIVATION
        == {
            "llm_actif",
            "whatsapp_enabled",
            "imap_enabled",
            "verification_version_active",
            "conservation_affaires_active",
        }
    )


@pytest.mark.parametrize(
    "valeur, attendu",
    [("1", True), ("0", False), ("true", False), ("oui", False), ("", False), (None, False)],
)
def test_seul_1_vaut_active(valeur, attendu):
    cfg = {} if valeur is None else {"imap_enabled": valeur}
    assert service_actif(cfg, SERVICE_REPONSES_COURRIEL) is attendu


@pytest.mark.parametrize(
    "saisie, stocke",
    [("1", "1"), ("true", "1"), ("OUI", "1"), (" 1 ", "1"), ("0", "0"), ("", "0"), ("non", "0")],
)
def test_une_activation_s_ecrit_1_ou_0(saisie, stocke):
    assert normaliser_activation(saisie) == stocke


def test_une_infrastructure_ne_se_coupe_pas():
    assert SERVICES[INFRA_SMTP].coupable is False
    with pytest.raises(ValueError):
        cle_actif(INFRA_SMTP)


def test_un_service_active_sans_son_reglage_est_incomplet():
    ia = SERVICES[SERVICE_IA]
    assert etat({}, ia) == (ETAT_COUPE, [])
    assert etat({"llm_actif": "1"}, ia) == (ETAT_INCOMPLET, ["la clé d'API"])
    assert etat({"llm_actif": "1", "llm_api_key": "sk"}, ia) == (ETAT_ACTIF, [])
    smtp = SERVICES[INFRA_SMTP]
    assert etat({}, smtp, infra_active=True) == (ETAT_ACTIF, [])
    assert etat({}, smtp, infra_active=False) == (ETAT_COUPE, [])


def test_chaque_onglet_de_reglages_existe_dans_l_administration():
    """Le lien « Réglages » de l'écran mène à un onglet déclaré — pas à une page vide."""
    texte = PAGES_ROLES.read_text(encoding="utf-8")
    onglets = set(re.findall(r"route: '/admin\?onglet=([a-z_]+)'", texte))
    assert len(onglets) >= 10, "les onglets d'administration ne sont plus lus"
    assert "services" in onglets, "l'onglet « Services » n'est pas déclaré"
    absents = {s.code: s.onglet for s in SERVICES.values() if s.onglet not in onglets}
    assert not absents, f"onglet de réglages inconnu : {absents}"


#: Le SEUL écran qui écrit une clé d'activation : l'interrupteur de chaque service.
ECRAN_INTERRUPTEUR = "OngletServices.svelte"


def test_seul_l_onglet_services_ecrit_une_activation():
    """Un service s'active dans Admin › Services, et nulle part ailleurs (14/10/2026).

    Les onglets IA, WhatsApp et la relève des réponses portaient chacun une
    seconde case, qui écrivait la même clé : leur « Enregistrer » rétablissait un
    service qu'on venait de couper. Une clé posée en objet (`llm_actif: …`) ou par
    indice (`['llm_actif'] = …`) hors de l'onglet Services est refusée ; la LIRE
    (`lues['llm_actif'] === '1'`) reste permis — l'onglet dit l'état.
    """
    racine = FRONT.parent
    fichiers = [f for f in racine.rglob("*") if f.suffix in (".svelte", ".ts")]
    assert len(fichiers) > 100, "le front n'est plus lu"
    assert (FRONT / "components" / ECRAN_INTERRUPTEUR).exists(), "l'interrupteur a disparu"
    ecritures = {}
    for f in fichiers:
        if f.name == ECRAN_INTERRUPTEUR:
            continue
        texte = f.read_text(encoding="utf-8")
        for cle in CLES_ACTIVATION:
            motif = rf"(?<!\w)['\"]?{cle}['\"]?\s*:|\[['\"]{cle}['\"]\]\s*=(?!=)"
            if re.search(motif, texte):
                ecritures.setdefault(f.relative_to(racine).as_posix(), []).append(cle)
    assert not ecritures, f"clé d'activation écrite hors d'Admin › Services : {ecritures}"


def test_seuls_les_onglets_dedies_se_grisent():
    """Griser l'onglet d'un service coupé n'est juste que s'il ne porte que lui :
    SMTP porte l'envoi des courriels, Maintenance la supervision."""
    dedies = {s.onglet for s in SERVICES.values() if s.onglet_dedie}
    assert dedies == {"ia", "whatsapp"}
    for s in SERVICES.values():
        if s.onglet_dedie:
            assert s.coupable
            partage = [a.code for a in SERVICES.values() if a.onglet == s.onglet and a is not s]
            assert not partage, f"onglet « {s.onglet} » déclaré dédié mais partagé : {partage}"


def test_chaque_icone_existe_dans_le_catalogue():
    """`Icon` retombe EN SILENCE sur un point d'interrogation pour un nom inconnu,
    et `lint:icones` ne lit pas un nom venu de l'API."""
    catalogue = json.loads(ICONES.read_text(encoding="utf-8"))
    assert len(catalogue) > 20
    inconnues = {s.code: s.icone for s in SERVICES.values() if s.icone not in catalogue}
    assert not inconnues, f"icône absente de #lib/icones-svg.json : {inconnues}"


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


@pytest.mark.parametrize("role", [None, RoleUtilisateur.résident, RoleUtilisateur.conseil_syndical])
def test_l_ecran_est_reserve_a_l_administration(moteur, role):
    http, _ = client_http(moteur, role)
    assert http.get("/config/services").status_code in (401, 403)


def test_l_ecran_recoit_chaque_service_sans_ses_secrets(moteur):
    with Session(moteur) as s:
        for cle, valeur in {
            "llm_actif": "1",
            "llm_api_key": "sk-secret-ne-sort-pas",
            "whatsapp_enabled": "1",
            "imap_enabled": "0",
        }.items():
            s.add(ConfigSite(cle=cle, valeur=valeur))
        s.commit()
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    reponse = http.get("/config/services")
    assert reponse.status_code == 200
    assert "sk-secret" not in reponse.text
    par_code = {s["code"]: s for s in reponse.json()}
    assert set(par_code) == set(SERVICES)
    assert par_code[SERVICE_IA]["etat"] == ETAT_ACTIF
    assert par_code[SERVICE_DIFFUSION]["etat"] == ETAT_INCOMPLET
    assert par_code[SERVICE_DIFFUSION]["manque"] == ["l'adresse du relais WhatsApp"]
    assert par_code[SERVICE_REPONSES_COURRIEL]["etat"] == ETAT_COUPE
    assert par_code[INFRA_SMTP]["cle_actif"] is None


def test_put_config_ramene_une_activation_a_1(moteur):
    """Une saisie « true » ne réintroduit pas en base la valeur que seule l'ancienne
    lecture IMAP acceptait."""
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert http.put("/config", json={"imap_enabled": "true"}).status_code == 200
    with Session(moteur) as s:
        assert s.get(ConfigSite, "imap_enabled").valeur == "1"
