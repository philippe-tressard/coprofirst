"""Toute Suite d'AFFAIRE s'ouvre avec les pastilles d'état en tête (#1094).

Deux écrans ouvraient une Suite sur une affaire : la carte (`CarteTicket`) et la
fiche (`HistoriqueTicket`, retirée le 15/10/2026 : le lien d'une affaire rend sa
carte). La carte passait `statutOptions`, la fiche non : le
même geste montrait les pastilles ici et pas là (23/09/2026). La forme est celle
qu'a imposée #426 — on touche une pastille pour faire avancer, on n'y touche
pas pour une simple parole.

Ce test lit chaque `<EvolForm … entite={TICKET} …>` du front qui n'est pas une
CORRECTION (`editMode`) et exige `statutOptions`.

Depuis le 01/10/2026 (#1520), la Suite ET sa correction passent par UN montage,
`SuiteAffaire` : la carte et l'actualité le rendent, et c'est lui qui
porte les pastilles. Le test l'exige de lui, et exige des hôtes qu'ils le rendent.
"""

from __future__ import annotations

import pathlib
import re

_FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"

#: Ce qui emprunte `EvolForm` sur une affaire SANS être une Suite — déclaré, avec
#: sa raison ; le test échoue si l'exception cesse de servir.
_PAS_UNE_SUITE = {
    "lib/components/FilMessagesTicket.svelte": "« Répondre » poste un MESSAGE (`POST …/messages`), qui ne change aucun état",
}
_BALISE = re.compile(r"<EvolForm\b(.*?)>", re.S)
#: Le montage unique de la Suite d'affaire, et les écrans qui le rendent.
_MONTAGE = "lib/components/SuiteAffaire.svelte"
_HOTES = (
    #  Le corps déplié de la carte de liste (`CarteTicket`), chargé au geste (#1860).
    "lib/components/CorpsCarteTicket.svelte",
    "lib/components/ActualiteEnListe.svelte",
)


def _suites_sans_pastilles(texte: str) -> int:
    manques = 0
    for attributs in _BALISE.findall(texte):
        if "entite={TICKET}" in attributs and "editMode" not in attributs:
            if "statutOptions=" not in attributs:
                manques += 1
    return manques


def test_le_montage_unique_porte_les_pastilles_et_les_hotes_le_rendent():
    montage = (_FRONT / _MONTAGE).read_text(encoding="utf-8")
    balises = _BALISE.findall(montage)
    assert len(balises) == 1, f"{_MONTAGE} : {len(balises)} EvolForm, un attendu."
    #  Les états viennent de `etatsDeLaSuite` depuis le 10/10/2026 : le cycle d'une
    #  affaire, ou les trois états du suivi d'une actualité — la règle lue, pas recopiée.
    suivi = (_FRONT / "lib" / "suivi-actualite.ts").read_text(encoding="utf-8")
    assert "statutOptions=" in balises[0] and (
        "STATUT_TICKET_OPTIONS" in balises[0]
        or ("etatsDeLaSuite(" in balises[0] and "return STATUT_TICKET_OPTIONS" in suivi)
    ), f"{_MONTAGE} ne propose plus les pastilles d'état (#1094)."
    for hote in _HOTES:
        texte = (_FRONT / hote).read_text(encoding="utf-8")
        assert "<SuiteAffaire" in texte, f"{hote} ne rend plus la Suite par `SuiteAffaire`."
        assert not [a for a in _BALISE.findall(texte) if "entite={TICKET}" in a], (
            f"{hote} remonte un EvolForm à côté de `SuiteAffaire` : deux montages divergent."
        )


def test_chaque_suite_d_affaire_porte_les_pastilles():
    """Tout AUTRE `EvolForm` d'affaire, hors correction, porte les pastilles."""
    fichiers = [p for p in _FRONT.rglob("*.svelte")]
    fautes = {
        p.relative_to(_FRONT).as_posix()
        for p in fichiers
        if _suites_sans_pastilles(p.read_text(encoding="utf-8"))
    }
    assert not fautes - set(_PAS_UNE_SUITE), (
        f"Suite d'affaire sans pastilles d'état (#1094) : {sorted(fautes - set(_PAS_UNE_SUITE))}"
    )
    inutiles = set(_PAS_UNE_SUITE) - fautes
    assert not inutiles, f"Exception qui ne sert plus — la retirer : {sorted(inutiles)}"


def test_le_releve_voit_une_suite_sans_pastilles():
    assert _suites_sans_pastilles("<EvolForm\n  entite={TICKET}\n  titre='x'\n/>") == 1
    assert _suites_sans_pastilles("<EvolForm entite={TICKET} statutOptions={X} />") == 0
    assert _suites_sans_pastilles("<EvolForm entite={TICKET} editMode={true} />") == 0
