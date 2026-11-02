"""Les retraits ANNONCÉS du contrat de l'API (#2456) — sur le modèle de `CONTRACTIONS`.

Un client généré (l'app iOS) décode ce que le serveur rend ; une installation de la
vague Fixe garde longtemps l'ancienne version. Retirer une opération ou un champ de
réponse se fait donc en DEUX temps, jamais dans la même version :

1. **Annoncer** (version V) : la route prend `deprecated=True`, le champ
   `Field(json_schema_extra={"deprecated": True})`, et la cible s'écrit ici avec V,
   la version de l'application du lot (`front/package.json`, bumpée en dernier
   commit). Le contrat publié le dit : le générateur Swift l'avertit.
2. **Retirer**, dans une version ULTÉRIEURE à V : `--ecrire-reference` l'accepte, et
   la version du contrat prend une majeure.

Une cible : `"GET /chemin"` (l'opération) ou `"GET /chemin → $.champ"` (un champ de
réponse et tout ce qu'il porte). L'entrée reste après le retrait : c'est sa trace.
🔒 `test_contrat_api.py` refuse un retrait absent d'ici, ou retiré dans la version
qui l'annonce, et une annonce dont la cible servie n'est pas dépréciée.
"""

from __future__ import annotations

#: cible → (version de l'application qui l'annonce, pourquoi)
RETRAITS: dict[str, tuple[str, str]] = {}
