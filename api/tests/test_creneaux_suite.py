"""Dans une Suite 🔄, chaque section est posée dans le créneau de SON rang (#1326).

Signalé à l'écran le 25/09/2026 : « l'ordre de section d'une affaire n'est pas
le même en mode édition et en mode suite, par exemple la section Mise en
avant ». `EvolForm` n'avait qu'un créneau, `specifiques`, rendu après le Suivi
et avant le Périmètre : la Mise en avant y passait sept rangs trop tôt,
l'Équipement après le Suivi.

`EvolForm` en offre désormais trois, à leur rang (`#lib/evolutions.creneauDe`) :
`avant_suivi`, `specifiques`, `mise_en_avant`. `lint:ordre-sections` tient
l'ordre DANS `EvolForm` ; il ne peut pas voir qu'un écran hôte pose une section
dans le mauvais créneau — l'ordre de son propre fichier resterait croissant.
C'est ce que ce test regarde, chez chaque écran qui remplit un créneau.
"""

from __future__ import annotations

import pathlib
import re

_FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"

#: Le créneau où chaque section d'hôte doit être posée.
ATTENDU = {
    "SuiteConseilEquipement": "avant_suivi",
    "SectionsSuiteConseil": "specifiques",
    "OptionsEvolutionTicket": "mise_en_avant",
    "SectionOptionsPublication": "mise_en_avant",
}


def fragments(source: str) -> list[tuple[str, str]]:
    """(créneau, contenu) de chaque `<svelte:fragment slot="…">` d'un `<EvolForm>`."""
    resultat = []
    for evol in re.finditer(r"<EvolForm\b(.*?)</EvolForm>", source, re.S):
        for f in re.finditer(
            r'<svelte:fragment slot="(\w+)"[^>]*>(.*?)</svelte:fragment>', evol.group(1), re.S
        ):
            resultat.append((f.group(1), f.group(2)))
    return resultat


def poses_hors_rang(source: str) -> list[str]:
    fautes = []
    for creneau, contenu in fragments(source):
        for composant, attendu in ATTENDU.items():
            if re.search(rf"<{composant}\b", contenu) and creneau != attendu:
                fautes.append(f"{composant} dans « {creneau} » au lieu de « {attendu} »")
    return fautes


def test_chaque_section_d_hote_est_dans_le_creneau_de_son_rang():
    hotes = [f for f in _FRONT.rglob("*.svelte") if "<EvolForm" in f.read_text(encoding="utf-8")]
    assert hotes, "aucun écran ne rend EvolForm — le contrôle ne mesure rien"
    fautes = [
        f"{f.relative_to(_FRONT)} : {faute}"
        for f in hotes
        for faute in poses_hors_rang(f.read_text(encoding="utf-8"))
    ]
    assert not fautes, "Section posée hors de son rang dans une Suite :\n  " + "\n  ".join(fautes)


def test_le_controle_refuse_la_forme_d_avant():
    """La forme d'avant #1326 : la Mise en avant dans `specifiques`."""
    avant = (
        '<EvolForm x><svelte:fragment slot="specifiques" let:premiere>'
        "<SectionOptionsPublication {premiere} /></svelte:fragment></EvolForm>"
    )
    assert poses_hors_rang(avant) == [
        "SectionOptionsPublication dans « specifiques » au lieu de « mise_en_avant »"
    ]


def test_la_suite_d_une_actualite_suit_la_declaration_de_l_affaire():
    """🔴 Une actualité est une AFFAIRE de catégorie Actualité (v2.0.0) : sa Suite
    suit `TICKET`, comme son édition. Elle suivait `PUBLICATION` — deux
    déclarations pour un objet, qui ne diffèrent que par ce qu'une Suite ne rend
    pas (#1329). `PUBLICATION` garde ses libellés ; il ne gouverne plus un rendu."""
    fautes = [
        str(f.relative_to(_FRONT))
        for f in _FRONT.rglob("*.svelte")
        if re.search(r"entite=\{PUBLICATION\}", f.read_text(encoding="utf-8"))
    ]
    assert not fautes, "Une Suite gouvernée par PUBLICATION : " + ", ".join(fautes)


def test_le_badge_nouveau_ne_s_ecrit_qu_une_fois():
    """Le badge « Nouveau » d'une carte était écrit CINQ fois, avec deux mots
    (« NEW », « New ») et deux marges (#1329). `BadgeNouveau` le porte seul :
    aucun autre écran n'appelle `isNouveau(` pour le rendre."""
    fautes = [
        str(f.relative_to(_FRONT))
        for f in _FRONT.rglob("*.svelte")
        if f.name != "BadgeNouveau.svelte" and "isNouveau(" in f.read_text(encoding="utf-8")
    ]
    assert not fautes, "Badge « Nouveau » réécrit : " + ", ".join(fautes)


def test_le_titre_d_une_section_porte_son_identifiant_dans_ses_trois_etats():
    """Le contenu d'une section PLIÉE ou éteinte reste dans la page, et ce qui
    s'y rattache (`aria-labelledby="…-titre"`) pointait sur un identifiant
    absent : seul le titre OUVERT le portait (#1329, relevé en production sur la
    Description d'un prestataire). Les quatre rendus du titre — éteint, plié,
    `<label>`, `<h4>` — posent `idTitre`."""
    source = (_FRONT / "lib" / "components" / "SectionFormulaire.svelte").read_text(
        encoding="utf-8"
    )
    assert source.count("id={idTitre || undefined}") >= 4, (
        "un rendu du titre de section ne pose pas `idTitre`"
    )
