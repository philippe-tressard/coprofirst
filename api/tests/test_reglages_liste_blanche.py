"""`PUT /config` n'écrit que les réglages déclarés (#2055).

La route refusait trois clés et écrivait toutes les autres — le premier essai
d'un usage de l'IA, que le serveur seul doit écrire, les consignes aux arrivants
sans les bornes de leur route, toute faute de frappe. La liste blanche vit dans
`utils/reglages`.

Ce que ce fichier tient, dans les deux sens :
- **le refus** : une clé non déclarée, réservée au serveur ou qui a sa route
  dédiée est refusée, et la requête n'écrit RIEN — pas même ses clés valides ;
- **l'accord** : chaque clé que l'administration envoie réellement est déclarée.
  C'est le risque inverse, et le plus coûteux : un écran qui ne pourrait plus
  enregistrer. Les clés se lisent dans les charges du front (`configApi.save`)
  et dans les registres que l'écran reçoit (usages de l'IA, services).

Et la même faiblesse sur `PUT /admin/sauvegardes/config`, qui posait tout
attribut du modèle reçu, `id` compris (commentaire de #2055).
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import select

from app.models.core import ConfigSite
from app.routers.admin.exploitation import ConfigSauvegardeUpdate
from app.routers.config import save_config
from app.utils import reglages
from app.utils.llm_usages import USAGES, decrire
from app.utils.services import SERVICES

_FRONT_SRC = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"


class _Admin:
    id = 1


def _cles_en_base(session) -> set[str]:
    return {c.cle for c in session.exec(select(ConfigSite)).all()}


# ── Le refus ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cle",
    [
        "cle_inventee",
        "smtp_serveur",  # faute de frappe : `smtp_server`
        *sorted(reglages.RESERVEES_AU_SERVEUR),
        *sorted(reglages.REFUSEES),
        "page_config_",  # le préfixe sans page
        "page_config_<script>",
    ],
)
def test_une_cle_non_ecrivable_est_refusee_et_rien_n_est_ecrit(session, cle):
    with pytest.raises(HTTPException) as refus:
        save_config({"site_nom": "Résidence", cle: "1"}, _Admin(), session)
    assert refus.value.status_code == 422
    #  La clé valide de la même requête n'est pas écrite non plus.
    assert _cles_en_base(session) == set()


def test_le_premier_essai_d_un_usage_est_reserve_au_serveur():
    for u in USAGES.values():
        assert not reglages.est_ecrivable(u.cle("reference")), u.code


# ── L'accord ─────────────────────────────────────────────────────────────────


def test_une_requete_de_cles_declarees_s_ecrit(session):
    donnees = {
        "site_nom": "Résidence",
        "smtp_server": "smtp.exemple.fr",
        "imap_dossier": "INBOX",
        "whatsapp_api_url": "http://bridge:3000",
        "page_config_tableau-de-bord": "{}",
        "pages_order": "[]",
        "llm_synthese_contrat_modele": "modele-x",
    }
    save_config(donnees, _Admin(), session)
    assert _cles_en_base(session) == set(donnees)


def test_les_cles_des_usages_de_l_ia_que_l_ecran_recoit_sont_ecrivables():
    """L'onglet IA renvoie exactement les clés de `GET /config/llm-usages`."""
    for usage in decrire():
        for cle in usage["cles"].values():
            assert reglages.est_ecrivable(cle), cle


def test_les_interrupteurs_des_services_sont_ecrivables():
    """L'onglet Services écrit `cle_actif` de chaque service du registre."""
    for service in SERVICES.values():
        if service.cle_actif:
            assert reglages.est_ecrivable(service.cle_actif), service.cle_actif


#: Une charge envoyée à `PUT /config` : `payload` ou `charge` (le nom que les
#: onglets lui donnent), ou le corps de `ecrireConfigSite`.
_BLOC = re.compile(
    r"(?:const (?:payload|charge): Record<string, string> = \{"
    r"|ecrireConfigSite\(c: ConfigSite\): Record<string, string> \{\s*return \{)(.*?)\n\s*\};",
    re.S,
)
_CLE_LITTERALE = re.compile(r"^\s*([a-z][a-z0-9_]*):", re.M)
_CLE_INDEXEE = re.compile(r"\[\s*'([a-z][a-z0-9_]*)'\s*\]\s*=")
_SAVE_DIRECT = re.compile(r"configApi\.save\(\{\s*([a-z][a-z0-9_]*):")


def _cles_envoyees_par_le_front() -> dict[str, str]:
    """{clé: fichier} — ce que les écrans d'administration écrivent en dur."""
    trouvees: dict[str, str] = {}
    fichiers = [
        f
        for f in [*_FRONT_SRC.rglob("*.svelte"), *_FRONT_SRC.rglob("*.ts")]
        if "configApi.save(" in (t := f.read_text(encoding="utf-8")) or "ecrireConfigSite(c" in t
    ]
    for f in fichiers:
        texte = f.read_text(encoding="utf-8")
        cles = set(_SAVE_DIRECT.findall(texte)) | set(_CLE_INDEXEE.findall(texte))
        for bloc in _BLOC.findall(texte):
            cles |= set(_CLE_LITTERALE.findall(bloc))
        for cle in cles:
            trouvees[cle] = str(f.relative_to(_FRONT_SRC))
    return trouvees


def test_chaque_cle_envoyee_par_l_administration_est_ecrivable():
    envoyees = _cles_envoyees_par_le_front()
    #  Cas zéro : la lecture trouve bien les charges de chaque onglet.
    temoins = {
        "site_nom",
        "email_footer",
        "smtp_server",
        "smtp_password",
        "imap_server",
        "imap_password",
        "whatsapp_api_url",
        "llm_fournisseur",
        "llm_api_key",
        "reference_copro",
        "pages_order",
    }
    assert temoins <= set(envoyees), f"Charges non lues : {sorted(temoins - set(envoyees))}"
    refusees = {c: f for c, f in envoyees.items() if not reglages.est_ecrivable(c)}
    assert not refusees, (
        "Le front envoie des clés que PUT /config refuserait — déclarez-les dans "
        f"`utils/reglages.PAR_ONGLET` : {refusees}"
    )


# ── La sauvegarde ────────────────────────────────────────────────────────────


def test_la_sauvegarde_n_ecrit_que_l_heure_et_les_versions():
    corps = ConfigSauvegardeUpdate.model_validate(
        {"id": 99, "frequence": "mensuelle", "heure_execution": 4, "nb_versions_conservees": 5}
    )
    assert corps.model_dump(exclude_none=True) == {
        "heure_execution": 4,
        "nb_versions_conservees": 5,
    }


@pytest.mark.parametrize(
    "corps",
    [{"heure_execution": 24}, {"heure_execution": "abc"}, {"nb_versions_conservees": 0}],
)
def test_la_sauvegarde_refuse_une_valeur_hors_bornes(corps):
    with pytest.raises(ValidationError):
        ConfigSauvegardeUpdate.model_validate(corps)
