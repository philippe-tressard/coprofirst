"""Deux clés, deux défauts, et la même décision partout.

Ce fichier couvre deux choses qu'aucune relecture ne garantit :

1. **La décision d'envoi** — qui reçoit quoi selon son bâtiment. Elle était lue à
   trois endroits (`email/__init__.py` deux fois, `utils/reponses.py`) avec
   chacun ses défauts : trois façons d'être en désaccord sur ce que l'utilisateur
   a demandé.
2. **L'accord des deux côtés** — le site coche des cases dont le serveur seul
   décide. Une clé recopiée de travers ne produirait aucune erreur : l'écran
   enregistrerait un réglage que le serveur ne lirait jamais.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.models.core import Utilisateur
from app.utils.preferences_mail import (
    AUTRES_BATIMENTS,
    DEFAUTS,
    MON_BATIMENT,
    lire,
    mail_autorise,
)

RACINE = Path(__file__).resolve().parents[2]


def _utilisateur(prefs: str | None = None, batiment_id: int | None = None) -> Utilisateur:
    u = Utilisateur(nom="X", prenom="Y", email="x@test.test", batiment_id=batiment_id, actif=True)
    if prefs is not None:
        u.preferences_notifications = prefs
    return u


# ── Les défauts ───────────────────────────────────────────────────────────────


def test_les_defauts_sont_recevoir_le_sien_pas_les_autres():
    """Personne n'a consenti aux autres bâtiments : le défaut ne peut pas être oui."""
    assert (DEFAUTS[MON_BATIMENT], DEFAUTS[AUTRES_BATIMENTS]) == (True, False)


def test_la_cloche_sonne_par_defaut_partout_et_se_regle_comme_le_courriel():
    """#1187 : la cloche est réglable ; ses défauts reproduisent l'existant."""
    from app.utils.preferences_mail import (
        AUTRES_BATIMENTS_APP,
        MON_BATIMENT_APP,
        cloche_autorisee,
    )

    assert (DEFAUTS[MON_BATIMENT_APP], DEFAUTS[AUTRES_BATIMENTS_APP]) == (True, True)

    class Compte:
        id = 1
        preferences_notifications = '{"mon_batiment_app": false}'

    assert cloche_autorisee(Compte()) is False, "la préférence de la cloche n'est pas lue"


def test_un_json_illisible_rend_les_defauts():
    """Une préférence règle un confort : sur une donnée abîmée, on n'ampute pas.

    C'est l'inverse exact d'une décision de visibilité, où un JSON corrompu
    REFUSE (`utils/visibility._codes_json_pour_acces`). Les deux sont volontaires :
    ici le mauvais côté de l'erreur serait de priver quelqu'un d'un e-mail qu'il
    avait demandé ; là-bas, d'ouvrir un contenu réservé.
    """
    for abime in ("{pas du json", "[]", "null", ""):
        assert lire(_utilisateur(abime)) == DEFAUTS, abime


# ── La décision ───────────────────────────────────────────────────────────────


def test_sans_batiment_connu_du_contenu_c_est_mon_batiment_qui_decide():
    """Rappel de mot de passe, validation de compte : ça s'adresse à moi."""
    coupe = json.dumps({MON_BATIMENT: False, AUTRES_BATIMENTS: True})
    assert mail_autorise(_utilisateur(), None) is True
    assert mail_autorise(_utilisateur(coupe), None) is False
    #  Un contenu à portée globale (aucun bâtiment visé) relève de la même règle.
    assert mail_autorise(_utilisateur(coupe), set()) is False


def test_le_contenu_de_mon_batiment_suit_ma_premiere_case(batiments):
    mien = _utilisateur(batiment_id=batiments[0])
    assert mail_autorise(mien, {batiments[0]}) is True

    coupe = _utilisateur(
        json.dumps({MON_BATIMENT: False, AUTRES_BATIMENTS: True}), batiment_id=batiments[0]
    )
    assert mail_autorise(coupe, {batiments[0]}) is False


def test_le_contenu_d_ailleurs_suit_la_seconde_case(batiments):
    """Décochée par défaut : le résident ne reçoit pas les autres bâtiments."""
    mien = _utilisateur(batiment_id=batiments[0])
    assert mail_autorise(mien, {batiments[2]}) is False

    accepte = _utilisateur(
        json.dumps({MON_BATIMENT: True, AUTRES_BATIMENTS: True}), batiment_id=batiments[0]
    )
    assert mail_autorise(accepte, {batiments[2]}) is True


def test_sans_batiment_de_rattachement_on_ne_coupe_rien(batiments):
    """Cas zéro : on ne peut pas dire que le contenu vient d'ailleurs."""
    inconnu = _utilisateur()
    assert mail_autorise(inconnu, {batiments[1]}) is True


# ── L'accord du site et du serveur ────────────────────────────────────────────


def test_le_site_emploie_exactement_les_memes_cles():
    """Une clé recopiée de travers n'échouerait nulle part — elle mentirait."""
    source = RACINE / "front" / "src" / "lib" / "preferences.ts"
    if not source.is_file():
        pytest.fail(f"Fichier attendu introuvable : {source}")
    contenu = source.read_text(encoding="utf-8")

    from app.utils.preferences_mail import AUTRES_BATIMENTS_APP, MON_BATIMENT_APP

    for nom, valeur in (
        ("MON_BATIMENT", MON_BATIMENT),
        ("AUTRES_BATIMENTS", AUTRES_BATIMENTS),
        ("MON_BATIMENT_APP", MON_BATIMENT_APP),
        ("AUTRES_BATIMENTS_APP", AUTRES_BATIMENTS_APP),
    ):
        motif = rf"export const {nom} = '([^']+)'"
        trouve = re.search(motif, contenu)
        assert trouve, f"{nom} introuvable dans preferences.ts"
        assert trouve.group(1) == valeur, f"{nom} : « {trouve.group(1)} » ≠ « {valeur} »"

    #  Et les défauts, qui décident de ce que voit un compte neuf.
    assert re.search(rf"\[MON_BATIMENT\]:\s*{str(DEFAUTS[MON_BATIMENT]).lower()}", contenu)
    assert re.search(rf"\[AUTRES_BATIMENTS\]:\s*{str(DEFAUTS[AUTRES_BATIMENTS]).lower()}", contenu)
    assert re.search(rf"\[MON_BATIMENT_APP\]:\s*{str(DEFAUTS[MON_BATIMENT_APP]).lower()}", contenu)
    assert re.search(
        rf"\[AUTRES_BATIMENTS_APP\]:\s*{str(DEFAUTS[AUTRES_BATIMENTS_APP]).lower()}", contenu
    )


def test_l_ecran_sait_dire_qu_un_reglage_est_HERITE():
    """🔴 Le défaut est `True` : personne n'a « choisi » de recevoir (#1147).

    Signalé à l'écran le 22/09/2026 : *« c'est le membre du CS nominativement qui
    a choisi cette option dans son profil qui sera notifié »*. Or `mon_batiment_mail`
    vaut `True` par défaut — un conseiller qui n'a jamais ouvert son profil reçoit
    sans avoir rien décidé, et voit une case cochée qui lui prête ce choix.

    Arbitré : le défaut reste, l'écran le DIT. `clesHeritees` est ce qui le
    permet, et elle doit lire le JSON **brut** — `lire()` applique les défauts et
    perd donc l'information.

    ⚠️ Ce test tient l'EXISTENCE de la fonction, pas son contenu : sans elle,
    l'écran retomberait sur les valeurs résolues et redirait « coché par vous »
    de ce qui est hérité — en silence, comme avant.
    """
    source = RACINE / "front" / "src" / "lib" / "preferences.ts"
    contenu = source.read_text(encoding="utf-8")

    assert "export function clesHeritees(" in contenu, (
        "`clesHeritees` a disparu de preferences.ts : l'écran du profil ne peut "
        "plus distinguer un réglage hérité d'un choix, et il prêtera de nouveau "
        "à l'utilisateur une décision qu'il n'a pas prise (#1147)."
    )
    #  Elle doit lire le brut, pas les valeurs déjà résolues : c'est toute la
    #  différence entre « jamais réglé » et « réglé à vrai ».
    assert "typeof lues[cle] !== 'boolean'" in contenu, (
        "`clesHeritees` ne mesure plus l'ABSENCE de la clé dans le JSON brut : "
        "une valeur résolue vaut toujours `true` ou `false`, donc rien ne "
        "paraîtrait jamais hérité."
    )

    ecran = RACINE / "front" / "src" / "lib" / "components" / "PreferencesAffichageNotifs.svelte"
    assert "heritees" in ecran.read_text(encoding="utf-8"), (
        "l'écran des préférences ne reçoit plus l'héritage : la fonction existe "
        "et personne ne l'écoute, ce qui est le cas le plus difficile à voir."
    )
