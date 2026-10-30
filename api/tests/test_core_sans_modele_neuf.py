"""`models/core.py` ne reçoit plus de classe : un modèle vit dans le module de son domaine.

## Pourquoi ce test, et pourquoi maintenant (28/09/2026, #779)

La consigne « jamais dans `core.py` » (`CLAUDE.md`, skill `api-scaffold`) ne
tenait que par le contrôle de modularité : `core.py` dépassait 500 lignes, et ce
contrôle refuse qu'un tel fichier grossisse. #779 l'a ramené à 490 lignes — et du
même coup rendu la consigne muette : un modèle de dix lignes y passerait sans un
mot, et le fichier remonterait au-dessus du plafond au lot suivant.

La liste ci-dessous a été un **plafond décroissant** (8 classes le 28/09/2026) ;
elle est CLOSE depuis le 30/10/2026 (#2316) : `core.py` porte l'utilisateur et
ce qui lui est attaché, et rien d'autre. Les y laisser est une décision, pas une
dette : `Utilisateur` est le centre des `Relationship` du modèle (lots,
affaires), et le déplacer recâblerait ses `back_populates` à travers les modules
pour un gain nul — `core` est, à la lettre, le noyau. Le test échoue toujours si
une classe neuve y entre, ou si l'une d'elles en sort sans qu'on la retire d'ici.
"""

from __future__ import annotations

import ast
import pathlib

_CORE = pathlib.Path(__file__).resolve().parents[1] / "app" / "models" / "core.py"

#  Ce qui reste dans `core.py` : l'utilisateur et ce qui lui est attaché
#  (`TypeLien`, `UserLot`, `Mandat`). Les quatre petites tables sans domaine
#  (`FaqItem`, `RegleResidence`, `Notification`, `ConfigSite`) sont parties le
#  30/10/2026 dans `residence`, `notifications` et `reglages` (#2316).
CLASSES_ADMISES = {
    "TypeLien",
    "Utilisateur",
    "UserLot",
    "Mandat",
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
