"""Une réponse typée n'a rien PERDU de ce que la lecture produisait (#2618).

Un `response_model` filtre : une clé que la lecture sert sans que le schéma la
déclare disparaît de la réponse, sans un mot. `ecarts(lu, servi)` compare, clé à
clé et en profondeur, ce que la fonction de lecture rend à ce que la route sert,
et nomme chaque perte. Le schéma peut AJOUTER une clé à `null` (une indication
qu'une portée ne calcule pas) : ce n'est pas une perte.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi.encoders import jsonable_encoder


def _normaliser(valeur):
    """Une date sort « …Z » de l'API (`UTCJSONResponse`) : on compare sans le suffixe."""
    if isinstance(valeur, str) and valeur.endswith("Z"):
        return valeur[:-1]
    if isinstance(valeur, (datetime, date)):
        return valeur.isoformat()
    return valeur


def ecarts(lu, servi, chemin: str = "$") -> list[str]:
    """Les clés ou valeurs de `lu` que `servi` n'a pas à l'identique."""
    lu = jsonable_encoder(lu)
    if isinstance(lu, dict):
        if not isinstance(servi, dict):
            return [f"{chemin} : objet attendu, {type(servi).__name__} servi"]
        pertes = []
        for cle, valeur in lu.items():
            if cle not in servi:
                pertes.append(f"{chemin}.{cle} : absente de la réponse")
            else:
                pertes += ecarts(valeur, servi[cle], f"{chemin}.{cle}")
        return pertes
    if isinstance(lu, list):
        if not isinstance(servi, list) or len(servi) != len(lu):
            return [f"{chemin} : liste de {len(lu)} attendue"]
        return [
            p for i, (a, b) in enumerate(zip(lu, servi)) for p in ecarts(a, b, f"{chemin}[{i}]")
        ]
    if _normaliser(lu) != _normaliser(servi):
        return [f"{chemin} : {lu!r} lu, {servi!r} servi"]
    return []
