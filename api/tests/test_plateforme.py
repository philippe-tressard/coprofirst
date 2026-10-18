"""La plateforme et les replis de la résidence s'écrivent pareil des deux côtés (#1725).

Les contextes de build `./api` et `./front` ne partagent aucun fichier : chaque
côté déclare donc les mêmes constantes (`app/utils/plateforme.py`,
`front/src/lib/plateforme.ts`), et ce test interdit qu'elles divergent — c'est
la nuance qui sépare une copie verrouillée de la duplication (`standards/02`).

Il lie aussi la licence NOMMÉE au texte de licence RÉEL : le jour où #1726
remplacera `LICENSE`, les mentions légales ne pourront pas continuer d'annoncer
l'ancienne.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.utils import plateforme
from app.utils.liens import NOM_SITE_PAR_DEFAUT
from app.utils.whatsapp_message import PIED_WHATSAPP_PAR_DEFAUT

RACINE = Path(__file__).resolve().parents[2]
FRONT_LIB = RACINE / "front" / "src" / "lib"


def _constante_ts(fichier: Path, nom: str) -> str:
    """La valeur d'un `export const NOM = '…'` (ou d'un champ `nom: '…'`)."""
    texte = fichier.read_text(encoding="utf-8")
    trouve = re.search(rf"\b{nom}\s*[:=]\s*(['`])(.*?)\1", texte)
    assert trouve, f"{fichier.name} ne déclare plus `{nom}` : la concordance ne se lit plus"
    return trouve.group(2)


@pytest.mark.parametrize(
    "nom", ["NOM_PLATEFORME", "DEPOT_SOURCE", "SITE_PLATEFORME", "LICENCE_SPDX", "LICENCE_NOM"]
)
def test_la_plateforme_est_la_meme_des_deux_cotes(nom):
    assert _constante_ts(FRONT_LIB / "plateforme.ts", nom) == getattr(plateforme, nom)


def test_le_lien_de_licence_est_le_meme_des_deux_cotes():
    gabarit = _constante_ts(FRONT_LIB / "plateforme.ts", "LICENCE_URL")
    assert gabarit.replace("${DEPOT_SOURCE}", plateforme.DEPOT_SOURCE) == plateforme.LICENCE_URL


def test_les_replis_de_la_residence_sont_les_memes_des_deux_cotes():
    config = FRONT_LIB / "configSite.ts"
    assert _constante_ts(config, "NOM_SITE_PAR_DEFAUT") == NOM_SITE_PAR_DEFAUT
    assert _constante_ts(config, "whatsapp_footer") == PIED_WHATSAPP_PAR_DEFAUT


def test_la_licence_nommee_est_celle_du_depot():
    """L'identifiant que REUSE.toml accorde, et le fichier que le lien vise.

    Lié au dépôt RÉEL depuis #1726 : les mentions légales ne peuvent pas
    annoncer une licence que le dépôt n'accorde plus — le titre du texte
    officiel, lui, est tenu par `test_gouvernance_depot.py`.
    """
    reuse = (RACINE / "REUSE.toml").read_text(encoding="utf-8")
    accorde = re.search(r'SPDX-License-Identifier\s*=\s*"([^"]+)"', reuse).group(1)
    assert accorde == plateforme.LICENCE_SPDX, (
        f"REUSE.toml accorde « {accorde} », les mentions légales annoncent "
        f"« {plateforme.LICENCE_SPDX} » : mettre à jour `utils/plateforme.py` ET "
        "`front/src/lib/plateforme.ts`."
    )
    fichier = plateforme.LICENCE_URL.rsplit("/", 1)[-1]
    assert (RACINE / fichier).is_file(), f"le lien de licence vise `{fichier}`, absent du dépôt"


def test_le_nom_de_la_plateforme_ne_nomme_aucune_residence():
    assert "hostachy" not in plateforme.NOM_PLATEFORME.casefold()
