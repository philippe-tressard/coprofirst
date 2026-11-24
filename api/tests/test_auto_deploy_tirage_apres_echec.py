"""Après un secours échoué, le nœud retente de TIRER les images de la CI (#3033).

Le 23/11/2026, les images de la v3.122.5 ont été publiées 39 min après la fusion ;
l'actif avait cessé d'attendre à 30, tenté la construction de secours, échoué, et
noté `.images-echec`. La garde contre un build répété (`verdict_reconstruction`)
rendait alors `rien` : les images publiées neuf minutes plus tard n'étaient jamais
tirées, et le nœud est resté bloqué jusqu'à un geste à la main.

Les décisions sont des fonctions pures, éprouvées par leurs autotests
(`lib-parite.sh` : échec connu → `tirer` ; `lib-images-ci.sh` : tirage seul,
images absentes → `attendre`, jamais `construire`). Ce test tient le CÂBLAGE dans
`auto-deploy.sh`, que les autotests ne voient pas.
"""

import re

from tests.conftest import racine_depot

RACINE = racine_depot()
SCRIPT = (RACINE / "scripts" / "exploitation" / "auto-deploy.sh").read_text(encoding="utf-8")


def test_tout_verdict_autre_que_rien_passe_par_obtenir_images():
    #  L'ancienne forme ne laissait passer que `reconstruire` : `tirer` tombait.
    assert "= reconstruire ]; then" not in SCRIPT
    assert re.search(r'if \[ "\$VERDICT_IMAGES" != rien \]; then', SCRIPT)


def test_le_verdict_tirer_demande_le_tirage_seul():
    assert re.search(r'if \[ "\$VERDICT_IMAGES" = tirer \]; then TIRAGE_SEUL=1; fi', SCRIPT)
    assert "OBTENIR_TIRAGE_SEUL=$TIRAGE_SEUL obtenir_images" in SCRIPT


def test_la_decision_pure_connait_le_tirage_seul():
    lib = (RACINE / "scripts" / "lib" / "lib-images-ci.sh").read_text(encoding="utf-8")
    assert '"${OBTENIR_TIRAGE_SEUL:-0}"' in lib
    parite = (RACINE / "scripts" / "lib" / "lib-parite.sh").read_text(encoding="utf-8")
    assert "echo tirer" in parite
