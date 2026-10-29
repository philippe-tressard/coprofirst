"""`models/core.py` ne reçoit plus de classe : un modèle vit dans le module de son domaine.

## Pourquoi ce test, et pourquoi maintenant (28/09/2026, #779)

La consigne « jamais dans `core.py` » (`CLAUDE.md`, skill `api-scaffold`) ne
tenait que par le contrôle de modularité : `core.py` dépassait 500 lignes, et ce
contrôle refuse qu'un tel fichier grossisse. #779 l'a ramené à 490 lignes — et du
même coup rendu la consigne muette : un modèle de dix lignes y passerait sans un
mot, et le fichier remonterait au-dessus du plafond au lot suivant.

La liste ci-dessous est un **plafond décroissant** : elle ne fait que baisser.
Extraire une de ces classes vers son domaine, c'est la retirer d'ici ; le test
échoue si elle cesse de servir, pour qu'une exception éteinte ne reste pas écrite.
Suivi des huit restantes : #2316.
"""

from __future__ import annotations

import ast
import pathlib

_CORE = pathlib.Path(__file__).resolve().parents[1] / "app" / "models" / "core.py"

#  Ce qui reste dans `core.py` au 28/09/2026 : l'utilisateur et ce qui lui est
#  attaché (`TypeLien`, `UserLot`, `Mandat`), et quatre petites tables sans
#  domaine propre à ce jour.
CLASSES_ADMISES = {
    "TypeLien",
    "FaqItem",
    "Utilisateur",
    "UserLot",
    "Mandat",
    "RegleResidence",
    "Notification",
    "ConfigSite",
}


def _classes(source: str) -> set[str]:
    return {n.name for n in ast.parse(source).body if isinstance(n, ast.ClassDef)}


def test_aucune_classe_nouvelle_dans_core():
    en_trop = _classes(_CORE.read_text(encoding="utf-8")) - CLASSES_ADMISES
    assert not en_trop, (
        f"Classe(s) posée(s) dans models/core.py : {sorted(en_trop)}. Un modèle vit dans "
        "le module de son domaine (app/models/<domaine>.py), importé par models/__init__.py "
        "et ré-exporté par core.py."
    )


def test_chaque_classe_admise_sert_encore():
    disparues = CLASSES_ADMISES - _classes(_CORE.read_text(encoding="utf-8"))
    assert not disparues, (
        f"Plus dans core.py : {sorted(disparues)} — la retirer de CLASSES_ADMISES "
        "(la liste ne fait que baisser)."
    )


def test_le_releve_voit_une_classe_ajoutee():
    source = (
        _CORE.read_text(encoding="utf-8") + "\n\nclass Intrus(SQLModel, table=True):\n    pass\n"
    )
    assert _classes(source) - CLASSES_ADMISES == {"Intrus"}
