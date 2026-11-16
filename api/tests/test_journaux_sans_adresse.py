# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Aucune adresse e-mail entière dans les journaux — #777, verrouillé.

## Pourquoi ce test existe

Le correctif de #777 (05/09/2026) a masqué les adresses journalisées sur échec
d'envoi : ces lignes partent dans les **alertes du monitoring** et dans les
rapports qu'on recopie ailleurs, et c'est par là qu'une adresse de résident sort
du système. Il a été livré **sans aucun garde-fou** — constaté le 06/09 en
cherchant quoi vérifier pour clore le ticket.

Un défaut corrigé sans garde-fou revient : il y a eu trois récidives en deux mois
sur ce dépôt. Ici la régression serait particulièrement silencieuse — remettre
`trace` à la place de `_masquer(trace)` est une ligne, elle ne casse rien, et
personne ne relit les journaux d'erreur en se demandant s'ils en disent trop.

## Ce qu'il vérifie — et pourquoi les deux moitiés comptent

1. **La fonction masque**, y compris aux bords (adresse vide, sans arobase).
2. **Le point d'appel l'emploie** : une fonction correcte que personne n'appelle
   ne protège rien. C'est exactement le défaut que `test_emails_contexte_appel`
   avait trouvé pour les variables de gabarit — la fonction allait bien, l'appel
   ne fournissait pas ce qu'elle attendait.

⚠️ L'historique en base garde l'adresse **entière**, et c'est voulu : il répond à
« qui n'a pas reçu quoi ? », derrière une session admin. Ce test ne porte que sur
`logger`.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.utils.email import _masquer

SOURCE = Path(inspect.getfile(_masquer)).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "adresse, attendu",
    [
        ("paul.delmas@exemple.test", "p***@exemple.test"),
        ("a@b.test", "a***@b.test"),
        # Le domaine reste lisible : il suffit à diagnostiquer une panne de
        # délivrance chez un fournisseur, sans identifier personne.
        ("contact@5hostachy.fr", "c***@5hostachy.fr"),
        # Cas zéro et formes dégradées : jamais de renvoi vide, jamais l'entrée
        # rendue telle quelle.
        ("", "(vide)"),
        (None, "(vide)"),
        ("pas-une-adresse", "***"),
        ("@sans-tete.test", "***@sans-tete.test"),
    ],
)
def test_masquer_ne_laisse_pas_passer_l_adresse(adresse, attendu):
    assert _masquer(adresse) == attendu


@pytest.mark.parametrize(
    "adresse",
    ["paul.delmas@exemple.test", "un.tres.long.prenom@domaine.example"],
)
def test_la_partie_locale_ne_survit_pas_au_masquage(adresse):
    """Au-delà du format exact : la partie locale ne doit pas être reconstituable."""
    locale = adresse.split("@")[0]
    masquee = _masquer(adresse)
    assert locale not in masquee
    assert masquee.startswith(locale[0])  # une seule lettre, pour reconnaître


#: Les noms sous lesquels l'adresse voyage : la passer NUE à un journal est le
#: défaut de #777.
_NOMS_D_ADRESSE = {"trace", "to", "destinataire", "email"}


def _appels_logger_error(source: str) -> tuple[list[int], int, int]:
    """Dans `source` : les lignes des `logger.error` qui reçoivent une adresse nue,
    le nombre d'appels `logger.error` vus, et celui des arguments `_masquer(...)`."""
    fautifs: list[int] = []
    vus = masques = 0
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        if not (
            isinstance(cible, ast.Attribute)
            and cible.attr == "error"
            and isinstance(cible.value, ast.Name)
            and cible.value.id == "logger"
        ):
            continue
        vus += 1
        for argument in noeud.args:
            if isinstance(argument, ast.Name) and argument.id in _NOMS_D_ADRESSE:
                fautifs.append(noeud.lineno)
            if (
                isinstance(argument, ast.Call)
                and isinstance(argument.func, ast.Name)
                and argument.func.id == "_masquer"
            ):
                masques += 1
    return fautifs, vus, masques


def test_le_point_d_appel_masque_vraiment():
    """🔴 La fonction ne protège que si le `logger.error` l'emploie.

    Analyse du code, pas de la chaîne : on cherche l'appel `logger.error(...)`
    qui journalise une erreur d'envoi et on exige que l'argument portant
    l'adresse passe par `_masquer`. Un `grep` sur « _masquer » aurait été vert
    même si l'appel avait gardé `trace` à côté.
    """
    fautifs, vus, masques = _appels_logger_error(SOURCE)
    #  Cas zéro (#1496) : sans appel vu, « aucun fautif » ne prouvait rien — un
    #  journal renommé (`log.error`, `logger.exception`) rendait ce test vert.
    assert vus and masques, (
        f"{vus} appel(s) `logger.error` et {masques} `_masquer(...)` vus dans "
        f"{Path(inspect.getfile(_masquer)).name} : le point d'appel a changé de "
        "forme, et ce contrôle ne le regarde plus."
    )
    assert not fautifs, (
        "`logger.error` reçoit une adresse non masquée aux lignes "
        f"{fautifs} de {Path(inspect.getfile(_masquer)).name} — #777. "
        "Envelopper l'argument dans `_masquer(...)` : ces lignes partent dans "
        "les alertes du monitoring."
    )


def test_le_controle_refuse_l_adresse_nue():
    """Cas zéro du MOTIF : le défaut de #777, forgé, doit être vu."""
    forge = 'logger.error("Erreur envoi %s", trace)\nlogger.error("ok %s", _masquer(trace))\n'
    assert _appels_logger_error(forge) == ([1], 2, 1)
