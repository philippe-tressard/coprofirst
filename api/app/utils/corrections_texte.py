"""Ce qu'une correction DIT — une phrase qui se comprend seule, jamais un nom de champ nu.

## Le défaut, signalé à l'écran le 05/10/2026

> *« Correction : Description => ça veut dire quoi ? Correction : Date de fin =>
>   y en avait pas, elle a été ajoutée, ou modifiée ? Correction : Documents =>
>   le doc X a été ajouté aurait été plus clair ! Correction : Saisi pour =>
>   pour qui ? »*

Le suivi d'une affaire nommait le champ touché et rien d'autre : le lecteur ne
savait ni s'il y avait eu ajout, modification ou retrait, ni de quoi à quoi.

## La règle

Chaque phrase dit **quel geste** (Ajout · Modification · Suppression) et **sur
quoi** — avec la valeur quand elle tient en une ligne : date, nom de personne,
nom de fichier, libellé de périmètre. Une valeur qui ne tient pas (le texte d'une
description) se cite par son début.

Les formes sont **nominales** (« Ajout de la date de fin ») : elles n'accordent
rien, donc une phrase vaut pour une date, un lieu, un document ou une photo.

⚠️ Ce module ne ÉCRIT rien et ne connaît ni session ni droit : ce sont des
fonctions pures, vérifiées par `--selftest`. Le préfixe « Correction : » et la
façon de recoller les phrases restent à `corrections.py` — ce qui reconnaît une
correction ne dépend pas de ce qu'elle raconte.

## Les anciennes entrées

Avant la fusion des événements en affaires (v2.23.0), le calendrier écrivait
« Correction : Date de fin » sans rien d'autre : ce qui a changé n'a **pas été
conservé**, et aucune migration ne peut l'inventer. `expliciter_ancienne` les
rend à la lecture avec une mention qui dit au moins cela — plutôt qu'un nom de
champ qui laisse croire que l'information existe.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional, Sequence

from app.utils.annonce_hall import texte_brut
from app.utils.corrections import MARQUES, SEPARATEUR_CORRECTION
from app.utils.dates_fr import date_courte
from app.utils.fichiers import nom_lisible

#: Longueur de la citation d'un texte long — assez pour le reconnaître.
APERCU_MAX = 80

#: Les deux natures de pièce, pour `pieces()` : (le singulier avec son article,
#: le pluriel sans article). Les noms de photos (`IMG_4021.jpg`) n'apprennent
#: rien : on les compte, on ne les liste pas.
DOCUMENTS = ("du document", "documents", True)
PHOTOS = ("de la photo", "photos", False)

#: Les noms nus que l'ancien calendrier écrivait (`CHAMPS_CORRIGEABLES`, retiré
#: en v2.23.0). Une partie de correction qui est EXACTEMENT l'un d'eux est une
#: ancienne entrée.
ANCIENS_LIBELLES = frozenset(
    {
        "Titre",
        "Type",
        "Lieu",
        "Date de début",
        "Date de fin",
        "Épinglage",
        "Périmètre",
        "Description",
        "Photos",
        "Documents",
        "Prestataire",
        "Saisi pour",
    }
)

#: Ce que dit une ancienne entrée à la place de ce qu'elle ne sait plus.
NON_CONSERVE = " — ancienne entrée : ce qui a changé n'a pas été conservé"


def _jour(valeur: date | datetime | None) -> str:
    """`16/10/2026`, et l'heure seulement quand elle dit quelque chose."""
    if valeur is None:
        return ""
    if isinstance(valeur, datetime) and (valeur.hour or valeur.minute):
        return f"{date_courte(valeur)} à {valeur:%H:%M}"
    return date_courte(valeur)


def citer(html: Optional[str]) -> str:
    """Le début d'un texte riche, en une ligne, entre guillemets français."""
    brut = texte_brut(html or "")
    if len(brut) > APERCU_MAX:
        brut = brut[: APERCU_MAX - 1].rstrip() + "…"
    return f"« {brut} »"


def modification(
    cible: str, avant: Optional[str], apres: Optional[str], *, citation: bool = False
) -> str:
    """« Modification de la date de fin : 15/10/2026 → 16/10/2026 ».

    :param cible: ce qui change, AVEC sa préposition et son article — « de la date de
        fin », « du lieu » : le français contracte « de le », on ne le fait pas ici.
    :param citation: les valeurs sont des textes longs : on n'affiche que le
        début du nouveau, jamais un avant → après qui ne tiendrait pas.
    """
    if not avant and apres:
        return f"Ajout {cible} : {citer(apres) if citation else apres}"
    if avant and not apres:
        return f"Suppression {cible}" + ("" if citation else f" (c'était : {avant})")
    if citation:
        return f"Modification {cible} (elle commence désormais par {citer(apres)})"
    return f"Modification {cible} : {avant} → {apres}"


def modification_date(
    cible: str, avant: date | datetime | None, apres: date | datetime | None
) -> str:
    """`modification()` pour une date — jour, et heure si elle est posée."""
    return modification(cible, _jour(avant), _jour(apres))


def modification_texte_riche(cible: str, avant: Optional[str], apres: Optional[str]) -> str:
    """`modification()` pour une description : « Modification de la description (… »."""
    return modification(
        cible,
        texte_brut(avant or "") or None,
        texte_brut(apres or "") or None,
        citation=True,
    )


def pieces(nature: tuple[str, str, bool], avant: Sequence[str], apres: Sequence[str]) -> list[str]:
    """Ce que l'enregistrement a fait des pièces : ajoutées, retirées, ou réordonnées.

    Une phrase par sens, jamais « modifiées » : « Ajout du document : devis.pdf »
    et « Retrait du document : brouillon.pdf » sont deux faits, et deux lignes
    qui se lisent seules.

    ⚠️ Le ré-ordonnancement est une modification **visible** — les pièces
    s'affichent dans l'ordre donné — mais ce n'est ni un ajout ni un retrait :
    il garde sa phrase, et ne s'annonce que si rien d'autre n'a bougé.
    """
    un, pluriel, nommees = nature
    ajoutees, retirees = ajouts_retraits(avant, apres)

    def phrase(geste: str, urls: Iterable[str]) -> str:
        liste = list(urls)
        sujet = un if len(liste) == 1 else f"de {len(liste)} {pluriel}"
        noms = ", ".join(nom_lisible(u) for u in liste)
        return f"{geste} {sujet}" + (f" : {noms}" if nommees else "")

    phrases = []
    if ajoutees:
        phrases.append(phrase("Ajout", ajoutees))
    if retirees:
        phrases.append(phrase("Retrait", retirees))
    if not phrases and list(avant) != list(apres):
        phrases.append(f"Nouvel ordre des {pluriel}")
    return phrases


def ajouts_retraits(avant: Sequence, apres: Sequence) -> tuple[list, list]:
    """Ce qui entre (dans l'ordre d'arrivée) et ce qui sort (dans l'ordre d'avant).

    Une seule écriture pour les pièces jointes et les prestataires d'une affaire
    (#2704) : deux listes comparées, deux sens, l'ordre seul n'en est aucun.
    """
    return [x for x in apres if x not in avant], [x for x in avant if x not in apres]


def prestataires(ajoutes: Sequence[str], retires: Sequence[str], reordonne: bool) -> list[str]:
    """« Prestataire ajouté : Otis » · « Prestataires retirés : A, B » (#2704).

    Une phrase par sens, comme `pieces` : un remplacement est un retrait et un
    ajout. Le nouvel ordre ne se dit que si rien d'autre n'a bougé.
    """

    def phrase(noms: Sequence[str], geste: str) -> str:
        s = "s" if len(noms) > 1 else ""
        return f"Prestataire{s} {geste}{s} : {', '.join(noms)}"

    phrases = []
    if ajoutes:
        phrases.append(phrase(ajoutes, "ajouté"))
    if retires:
        phrases.append(phrase(retires, "retiré"))
    if not phrases and reordonne:
        phrases.append("Nouvel ordre des prestataires")
    return phrases


def saisi_pour(avant: Optional[str], apres: Optional[str]) -> str:
    """« Saisi pour : Alix Fontaine (auparavant : son auteur) ».

    :param avant: le nom de la personne nommée AVANT, ou `None` (en son nom).
    :param apres: le nom de la personne nommée APRÈS, ou `None` (en son nom).

    Les deux noms se lisent dans l'entrée même : l'auteur du geste est déjà
    celui de la ligne, et c'est la PERSONNE concernée que le lecteur cherche.
    """
    if apres is None:
        return f"Saisi pour : retiré, de nouveau au nom de son auteur (auparavant : {avant})"
    if avant == apres:
        return f"Saisi pour : coordonnées de {apres} modifiées"
    return f"Saisi pour : {apres} (auparavant : {avant or 'son auteur'})"


def expliciter_ancienne(contenu: Optional[str]) -> Optional[str]:
    """Une ancienne correction « Correction : Date de fin » → une phrase honnête.

    Rend le contenu **inchangé** s'il n'a pas exactement la forme ancienne : une
    correction récente (« Modification de la date de fin : … ») ou un vrai
    commentaire ne se touche pas. Le préfixe est conservé, c'est lui que le fil
    reconnaît (`corrections.est_correction`).
    """
    for marque in MARQUES:
        if not (contenu or "").startswith(marque):
            continue
        parties = contenu[len(marque) :].split(SEPARATEUR_CORRECTION)
        if not all(p in ANCIENS_LIBELLES for p in parties):
            return contenu
        return contenu + NON_CONSERVE
    return contenu


def _selftest() -> None:
    """Les cas qui se ressemblent, et celui qui se perd."""
    #  1. Les quatre cas du signalement.
    assert (
        modification_date("de la date de fin", None, datetime(2026, 10, 16))
        == "Ajout de la date de fin : 16/10/2026"
    )
    assert (
        modification_date("de la date de fin", datetime(2026, 10, 15), datetime(2026, 10, 16))
        == "Modification de la date de fin : 15/10/2026 → 16/10/2026"
    )
    assert (
        modification_date("de la date de fin", datetime(2026, 10, 15), None)
        == "Suppression de la date de fin (c'était : 15/10/2026)"
    )
    #  2. L'heure ne s'affiche que si elle est posée.
    assert _jour(datetime(2026, 10, 16, 9, 30)) == "16/10/2026 à 09:30"
    assert _jour(datetime(2026, 10, 16)) == "16/10/2026"
    #  3. Les pièces : un sens par phrase, noms lisibles sans le préfixe technique.
    uuid = "0123456789abcdef0123456789abcdef_"
    assert pieces(DOCUMENTS, [], [f"/uploads/{uuid}devis.pdf"]) == ["Ajout du document : devis.pdf"]
    assert pieces(DOCUMENTS, ["/uploads/a.pdf"], ["/uploads/b.pdf", "/uploads/c.pdf"]) == [
        "Ajout de 2 documents : b.pdf, c.pdf",
        "Retrait du document : a.pdf",
    ]
    assert pieces(PHOTOS, [], ["/uploads/x.jpg", "/uploads/y.jpg", "/uploads/z.jpg"]) == [
        "Ajout de 3 photos"
    ]
    assert pieces(DOCUMENTS, ["a", "b"], ["b", "a"]) == ["Nouvel ordre des documents"]
    assert pieces(DOCUMENTS, ["a"], ["a"]) == []
    #  3 bis. Les prestataires d'une affaire (#2704) : accord, deux sens, l'ordre seul.
    assert prestataires(["Otis"], [], False) == ["Prestataire ajouté : Otis"]
    assert prestataires(["A", "B"], ["C"], False) == [
        "Prestataires ajoutés : A, B",
        "Prestataire retiré : C",
    ]
    assert prestataires([], [], True) == ["Nouvel ordre des prestataires"]
    assert prestataires([], [], False) == []
    assert ajouts_retraits([1, 2], [2, 3]) == ([3], [1])
    #  4. Un texte long se cite par son début, balises retirées.
    long = "<p>" + "mot " * 40 + "</p>"
    assert len(citer(long)) <= APERCU_MAX + 4 and citer(long).endswith("… »")
    assert modification_texte_riche("de la description", "<p>a</p>", "<p>b c</p>") == (
        "Modification de la description (elle commence désormais par « b c »)"
    )
    #  5. Saisi pour : les quatre sens.
    assert saisi_pour(None, "Alix Fontaine") == (
        "Saisi pour : Alix Fontaine (auparavant : son auteur)"
    )
    assert saisi_pour("A B", "C D") == "Saisi pour : C D (auparavant : A B)"
    assert saisi_pour("A B", None).startswith("Saisi pour : retiré")
    assert saisi_pour("A B", "A B") == "Saisi pour : coordonnées de A B modifiées"
    #  6. Les anciennes entrées : expliquées, et seulement elles.
    assert expliciter_ancienne("Correction : Date de fin") == (
        "Correction : Date de fin — ancienne entrée : ce qui a changé n'a pas été conservé"
    )
    assert expliciter_ancienne("Correction : Description ; Documents").startswith(
        "Correction : Description ; Documents — ancienne entrée"
    )
    #  7. 🔴 Celles qui se perdraient : une correction récente, un commentaire, une
    #     entrée vide et un libellé inconnu restent tels quels.
    for intact in (
        "Correction : Modification de la date de fin : 15/10/2026 → 16/10/2026",
        "Correction : État : Ouvert → Chez le syndic ; Description modifiée",
        "Le nettoyage est reporté.",
        "Correction : Libellé inconnu",
        #  Déjà expliquée : relue, elle ne se double pas.
        "Correction : Date de fin" + NON_CONSERVE,
        "",
        None,
    ):
        assert expliciter_ancienne(intact) == intact, intact
    print("OK corrections_texte : cas verifies.")


if __name__ == "__main__":
    _selftest()
