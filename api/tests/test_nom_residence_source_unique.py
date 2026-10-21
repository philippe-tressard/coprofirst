"""Le nom de la résidence n'a qu'une source : `site_nom` (#2056).

Deux champs portaient le libellé « Nom de la résidence » dans deux onglets
d'Admin : `site_nom` (Paramétrage site), que tout le site affiche, et
`copropriete.nom` (Fiche copropriété), que seule la fiche montrait. Arbitré le
17/10/2026 : un seul nom, saisi dans la fiche, rangé dans `site_nom`.

Ce que ce fichier tient :
- la fiche LIT `site_nom`, jamais la colonne ;
- la fiche ÉCRIT `site_nom`, et la colonne ne bouge plus ;
- `PUT /config` refuse `site_nom` : la fiche est la seule porte.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.core import ConfigSite, Copropriete
from app.routers.config import save_config
from app.routers.copropriete import CoproprieteUpdate, copropriete_lue, update_copropriete


def _fiche(session, *, nom_colonne: str = "Nom de la colonne") -> Copropriete:
    copro = Copropriete(nom=nom_colonne, adresse="1 rue de l'Exemple")
    session.add(copro)
    session.commit()
    session.refresh(copro)
    return copro


def test_la_fiche_lit_le_nom_du_site(session):
    copro = _fiche(session)
    session.add(ConfigSite(cle="site_nom", valeur="Les Tilleuls"))
    session.commit()
    assert copropriete_lue(session, copro).nom == "Les Tilleuls"


def test_sans_nom_du_site_la_fiche_dit_le_repli_neutre(session):
    """Jamais la colonne : elle porterait un second nom, que plus rien n'écrit."""
    copro = _fiche(session)
    assert copropriete_lue(session, copro).nom == "Ma Résidence"


def test_la_fiche_ecrit_le_nom_du_site_et_laisse_la_colonne(session):
    copro = _fiche(session)
    lue = update_copropriete(CoproprieteUpdate(nom="  Les Tilleuls  "), session, None)
    assert lue.nom == "Les Tilleuls"
    assert session.get(ConfigSite, "site_nom").valeur == "Les Tilleuls"
    session.refresh(copro)
    assert copro.nom == "Nom de la colonne"


def test_un_nom_vide_ne_s_ecrit_pas(session):
    _fiche(session)
    session.add(ConfigSite(cle="site_nom", valeur="Les Tilleuls"))
    session.commit()
    lue = update_copropriete(CoproprieteUpdate(nom="   ", adresse="2 rue"), session, None)
    assert lue.nom == "Les Tilleuls"


def test_put_config_refuse_le_nom(session):
    class _Admin:
        id = 1

    with pytest.raises(HTTPException) as refus:
        save_config({"site_nom": "Autre nom"}, _Admin(), session)
    assert refus.value.status_code == 422
    assert "Copropriété › Identité" in refus.value.detail
