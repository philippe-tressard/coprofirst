"""Le guide d'installation et le README disent le mode limité que le code applique (#2968).

## Pourquoi (audit du 23/11/2026)

Le plafond de comptes et la lecture seule d'une suspension s'appliquent depuis le
16/11/2026 (`inscription/constat.py`). Le README l'a dit ; le guide d'installation
— celui que suit qui installe CoproFirst pour sa résidence, et vers lequel mène le
site du logiciel — disait encore l'état « n'est encore que constaté » : l'installateur
butait sur le sixième compte sans avoir été prévenu.

Le nombre se lit dans le code (`regime.PLAFOND_COMPTES_ACTIFS`), jamais recopié ici :
le jour où il change, les deux documents doivent changer avec lui.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.inscription.regime import PLAFOND_COMPTES_ACTIFS

RACINE = Path(__file__).resolve().parents[2]
DOCUMENTS = {
    "README.md": RACINE / "README.md",
    "deploiement/standard/LISEZMOI.md": RACINE / "deploiement" / "standard" / "LISEZMOI.md",
}

#: Ce que chaque document doit nommer du régime appliqué, au-delà du nombre.
NOTIONS = ("mode limité", "lecture seule", "REGISTRE_CONSTAT")

#: La phrase du 13/10/2026 : vraie alors, fausse depuis que le plafond s'applique.
AVANT = r"n'est encore que\s+(?:\*\*)?constaté"


def _texte(chemin: Path) -> str:
    assert chemin.exists(), f"{chemin} introuvable : le contrôle a perdu sa portée (INCONNU)"
    #  Le gras markdown coupe une expression (« **5 comptes actifs** ») : on le retire.
    return re.sub(r"\s+", " ", chemin.read_text(encoding="utf-8").replace("**", ""))


def test_chaque_document_dit_le_plafond_et_le_regime_appliques():
    assert PLAFOND_COMPTES_ACTIFS > 0
    fautes = []
    for nom, chemin in DOCUMENTS.items():
        texte = _texte(chemin)
        if f"{PLAFOND_COMPTES_ACTIFS} comptes actifs" not in texte:
            fautes.append(f"  {nom} : ne dit pas « {PLAFOND_COMPTES_ACTIFS} comptes actifs »")
        fautes += [f"  {nom} : ne nomme pas « {n} »" for n in NOTIONS if n not in texte]
        if re.search(AVANT, texte):
            fautes.append(f"  {nom} : dit encore l'état « seulement constaté »")
    assert not fautes, (
        "Le mode limité appliqué par le code (`inscription/regime.py`, `plafond.py`, "
        "`suspension.py`) n'est pas dit comme il est :\n" + "\n".join(fautes)
    )


def test_le_controle_refuse_la_phrase_d_avant():
    """Cas témoin (`standards/04` §2) : le passage du guide au 13/10/2026."""
    avant = (
        "L'état affiché — limitée, active, suspendue — n'est encore que **constaté**, "
        "sauf pour les **services**"
    )
    assert re.search(AVANT, avant)
    assert f"{PLAFOND_COMPTES_ACTIFS} comptes actifs" not in avant
