"""Des réglages lus sans écran, ou réglés sans être appliqués (#2060).

- **Accès fixes** (portillon, portail) : `acces_fixes_*` étaient lus par
  `utils/acces_choix` sans qu'aucun écran ne les écrive. Ils se cochent
  désormais sur le périmètre qu'ils nomment, et le serveur compose la liste.
- **Seuil « récent » de l'accueil** : l'écran lisait le délai d'archivage dans
  la configuration publique, où il n'est pas — il restait à 30 jours. Le fil
  l'envoie désormais.
- **Plancher de la relève des courriels** : il valait une date propre à
  5Hostachy ; absent, il est désormais posé au jour de la première relève.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.models.core import ConfigSite, RoleUtilisateur
from app.models.perimetre import Perimetre
from app.routers.patrimoine import PerimetreUpdate, lister_perimetres, modifier_perimetre
from app.utils import horloge
from app.utils.acces_choix import codes_autorises, fixer_acces
from app.utils.courriel_boite import plancher_de_releve
from app.utils.types_acces import TELECOMMANDE, TYPES_ACCES, VIGIK
from tests.aides_http import base_http, client_http


class _Admin:
    id = 1


def _noeud(session, code: str = "portillon") -> Perimetre:
    noeud = Perimetre(code=code, libelle="Portillon", description="")
    session.add(noeud)
    session.commit()
    session.refresh(noeud)
    return noeud


def _liste(session, cle: str) -> list[str]:
    ligne = session.get(ConfigSite, cle)
    return json.loads(ligne.valeur) if ligne else []


# ── Accès fixes ──────────────────────────────────────────────────────────────


def test_cocher_un_acces_fixe_sur_le_perimetre_le_rend_autorise(session):
    noeud = _noeud(session)
    lu = modifier_perimetre(
        noeud.id, PerimetreUpdate(acces_fixes=["telecommande"]), session, _Admin()
    )
    assert lu.acces_fixes == ["telecommande"]
    assert _liste(session, "acces_fixes_telecommande") == ["portillon"]
    assert "portillon" in codes_autorises(session, TELECOMMANDE)
    assert "portillon" not in _liste(session, "acces_fixes_vigik")


def test_decocher_retire_le_code_et_garde_les_autres(session):
    noeud = _noeud(session)
    session.add(ConfigSite(cle="acces_fixes_vigik", valeur=json.dumps(["portail", "portillon"])))
    session.commit()
    modifier_perimetre(noeud.id, PerimetreUpdate(acces_fixes=[]), session, _Admin())
    assert _liste(session, "acces_fixes_vigik") == ["portail"]


def test_la_liste_lue_dit_les_acces_fixes_de_chaque_noeud(session):
    _noeud(session)
    fixer_acces(session, "portillon", list(TYPES_ACCES))
    session.commit()
    lus = {p.code: p.acces_fixes for p in lister_perimetres(session, None)}
    assert sorted(lus["portillon"]) == sorted(TYPES_ACCES)


def test_un_type_d_acces_inconnu_est_refuse(session):
    with pytest.raises(HTTPException) as refus:
        fixer_acces(session, "portillon", ["cle_magique"])
    assert refus.value.status_code == 422


def test_sans_le_champ_les_acces_fixes_ne_bougent_pas(session):
    """Un PATCH qui ne dit rien des accès (l'ordre, un libellé) n'y touche pas."""
    noeud = _noeud(session)
    fixer_acces(session, "portillon", [VIGIK.cle])
    session.commit()
    modifier_perimetre(noeud.id, PerimetreUpdate(ordre=3), session, _Admin())
    assert _liste(session, "acces_fixes_vigik") == ["portillon"]


# ── Plancher de la relève ────────────────────────────────────────────────────


def test_sans_plancher_la_releve_commence_aujourd_hui_et_le_garde(session):
    plancher = plancher_de_releve(session, {})
    jour = horloge.aujourd_hui().isoformat()
    assert plancher == datetime.fromisoformat(jour)
    assert session.get(ConfigSite, "imap_plancher").valeur == jour


def test_un_plancher_saisi_est_respecte(session):
    plancher = plancher_de_releve(session, {"imap_plancher": "2026-09-02"})
    assert plancher == datetime(2026, 9, 2)
    assert session.get(ConfigSite, "imap_plancher") is None


# ── Seuil « récent » de l'accueil ────────────────────────────────────────────


def test_le_fil_envoie_le_delai_d_archivage_du_site():
    """Ce que l'accueil appelle « récent » suit le réglage, plus le défaut en dur."""
    with base_http() as moteur:
        with Session(moteur) as s:
            s.add(ConfigSite(cle="archivage_delai_jours", valeur="12"))
            s.commit()
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        assert http.get("/flux").json()["delai_recent_jours"] == 12
