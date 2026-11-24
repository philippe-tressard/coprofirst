"""Chaque exception de licence dit SA date d'analyse, et une validation tracée seulement (#2992).

## Pourquoi (audit du 23/11/2026)

`_compatible()` écrivait « analyse du 08/10/2026, validée par l'auteur » pour toutes les
exceptions. psycopg est entré le 09/10/2026, lightningcss le 25/10/2026 : l'inventaire
public (`docs/licences-tierces.md`) leur prêtait une validation antérieure à leur
arrivée, que rien ne trace.

## Ce que ce contrôle tient

- chaque exception déclare sa date d'ENTRÉE dans la politique (`entree`) ;
- une analyse n'est jamais antérieure à l'entrée de ce qu'elle juge ;
- « validée par l'auteur » ne s'écrit que pour une analyse inscrite dans
  `VALIDATIONS_DE_L_AUTEUR`, avec l'endroit où la décision est écrite.

⚠️ La date d'entrée est DÉCLARÉE : la CI clone sans historique, `git log` n'y lit rien.
Elle se pose en même temps que l'exception, par celui qui l'ajoute.
"""

from __future__ import annotations

import pathlib
import re
import sys
from datetime import date, datetime

_RACINE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "scripts" / "ci"))

import licences_politique as politique  # noqa: E402

_ANALYSE = re.compile(r"analyse du (\d{2}/\d{2}/\d{4})")


def _jour(texte: str) -> date:
    return datetime.strptime(texte, "%d/%m/%Y").date()


def test_chaque_exception_declare_son_entree():
    assert len(politique.EXCEPTIONS) >= 5, "trop peu d'exceptions lues : INCONNU"
    sans = [e["paquets"] for e in politique.EXCEPTIONS if "entree" not in e]
    assert not sans, f"exceptions sans date d'entrée (`entree`, AAAA-MM-JJ) : {sans}"


def test_aucune_analyse_n_est_anterieure_a_son_entree():
    """Le défaut exact : psycopg (09/10) et lightningcss (25/10) analysés « le 08/10 »."""
    fautes = []
    for e in politique.EXCEPTIONS:
        m = _ANALYSE.search(e["statut"])
        if m and _jour(m.group(1)) < date.fromisoformat(e["entree"]):
            fautes.append(f"  {e['paquets']} : entré le {e['entree']}, « analyse du {m.group(1)} »")
    assert not fautes, "Une analyse datée d'avant l'arrivée du composant :\n" + "\n".join(fautes)


def test_une_validation_de_l_auteur_est_tracee():
    fautes = [
        f"  {e['paquets']} : « {m.group(1)} » n'est pas dans VALIDATIONS_DE_L_AUTEUR"
        for e in politique.EXCEPTIONS
        if "validée par l'auteur" in e["statut"]
        and (m := _ANALYSE.search(e["statut"]))
        and m.group(1) not in politique.VALIDATIONS_DE_L_AUTEUR
    ]
    assert not fautes, "Validation de l'auteur affirmée sans trace :\n" + "\n".join(fautes)


def test_la_date_d_analyse_n_a_pas_de_defaut():
    """Cas témoin : sans date, `_compatible` refuse — c'est le défaut qui l'avait figée."""
    try:
        politique._compatible("motif")  # type: ignore[call-arg]
    except TypeError:
        pass
    else:
        raise AssertionError("`_compatible` accepte une exception sans date d'analyse")
    assert "non tracée" in politique._compatible("m", analyse="09/10/2026")
    assert "validée par l'auteur" in politique._compatible("m", analyse="08/10/2026")
