"""Supprimer définitivement ne s'offre qu'aux ARCHIVES (24/09/2026).

Question de l'utilisateur, devant la boîte « Supprimer définitivement » ouverte
depuis la liste des affaires : « c'est une suppression ou pas ? ». Ça l'était —
l'actualité entière, sans retour. `ux-patterns` §8 le disait déjà : archiver
dans la vue principale, supprimer depuis les Archives seulement. Les deux
rangées d'icônes ne le respectaient pas.

Le contrôle lit la condition qui ouvre le bloc du bouton : elle doit exiger
`archive`, jamais `!archive`.

🔴 **Étendu aux prestataires et aux contrats le 02/10/2026 (#1538).** Le contrôle
ne lisait que les deux rangées où la règle venait d'être corrigée — et les deux
cartes qui ne la suivaient pas portaient un 🗑️ intitulé « Archiver », sur la vue
principale, pour tout le conseil : l'icône disait « supprimer », la boîte
« archiver », la route `DELETE`. Un garde-fou qui ne regarde que ce qu'on vient
de réparer ne voit jamais la copie d'à côté.
"""

from __future__ import annotations

import pathlib
import re

import pytest

_COMPOSANTS = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "components"

#: Les rangées d'icônes qui suppriment définitivement — aux Archives seulement.
_QUI_SUPPRIMENT = ["ActionsTicket.svelte", "ActionsActualite.svelte"]

#: Toute carte qui offre le geste 📦. Une entité qu'on archive s'ajoute ici.
#: Depuis #1539 (02/10/2026), le prestataire et le contrat tiennent ce geste de
#: `CarteModifiable`, qui porte leur squelette commun : c'est lui qu'on lit, et
#: `_MONTENT_CARTE_MODIFIABLE` vérifie que les deux cartes passent bien par lui.
_QUI_ARCHIVENT = _QUI_SUPPRIMENT + ["CarteModifiable.svelte"]

#: Les cartes dont le geste 📦 vit dans `CarteModifiable` — elles doivent la
#: monter, sans quoi le contrôle ci-dessus lirait un fichier qu'elles n'emploient plus.
_MONTENT_CARTE_MODIFIABLE = ["CartePrestataire.svelte", "CarteContrat.svelte"]

#: La corbeille et le carton, littéraux, en entité HTML, ou AU TRAIT : depuis le
#: 10/10/2026 (#1819, la page Affaires devenue le standard du site), une action se
#: dessine par `<IconeAction icone="…" />` — `trash-2` et `archive`.
_CORBEILLE = re.compile(r'🗑|&#x1F5D1;|icone="trash-2"', re.IGNORECASE)
_CARTON = re.compile(r'📦|&#x1F4E6;|\\u\{1F4E6\}|icone="archive"', re.IGNORECASE)


def _sans_commentaires(source: str) -> str:
    """Le balisage RENDU : un 🗑️ cité dans un commentaire ne s'affiche pas."""
    source = re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", source)


def _condition_qui_garde(source: str, position: int) -> str | None:
    """La dernière condition ouverte avant `position`, ou `None`."""
    conditions = re.findall(r"\{(?:#if|:else if) ([^}]*)\}", source[:position])
    return conditions[-1] if conditions else None


def _exige_archive(condition: str) -> bool:
    return bool(re.search(r"(?<!!)\barchive\b", condition)) and "!archive" not in condition


@pytest.mark.parametrize("fichier", _QUI_SUPPRIMENT)
def test_la_corbeille_n_est_offerte_qu_aux_archives(fichier):
    source = (_COMPOSANTS / fichier).read_text(encoding="utf-8")
    i = source.find("Supprimer définitivement")
    assert i > 0, (
        f"{fichier} : le bouton de suppression a disparu — ce contrôle ne mesure plus rien"
    )
    derniere = _condition_qui_garde(source, i)
    assert derniere, f"{fichier} : la corbeille n'est gardée par aucune condition"
    assert _exige_archive(derniere), (
        f"{fichier} : la corbeille s'offre hors des Archives (condition « {derniere} »)"
    )


@pytest.mark.parametrize("fichier", _QUI_ARCHIVENT)
def test_aucune_corbeille_hors_des_archives(fichier):
    """Chaque 🗑️ RENDU par la carte est gardé par une condition qui exige `archive`.

    La forme générale de la règle : la carte d'un prestataire ou d'un contrat n'a
    aucune suppression définitive, elle n'a donc aucun 🗑️ à garder.
    """
    source = _sans_commentaires((_COMPOSANTS / fichier).read_text(encoding="utf-8"))
    for m in _CORBEILLE.finditer(source):
        condition = _condition_qui_garde(source, m.start())
        assert condition and _exige_archive(condition), (
            f"{fichier} : un 🗑️ s'affiche hors des Archives "
            f"(condition « {condition} ») — `ux-patterns` §8"
        )


@pytest.mark.parametrize("fichier", _QUI_ARCHIVENT)
def test_la_liste_offre_l_archivage(fichier):
    """Le bouton « Archiver » existe, et son icône est 📦 — jamais 🗑️ (#1538)."""
    source = _sans_commentaires((_COMPOSANTS / fichier).read_text(encoding="utf-8"))
    i = source.find('aria-label="Archiver"')
    assert i > 0, f"{fichier} : plus de 📦 dans la liste"
    bouton = source[source.rfind("<button", 0, i) : source.find("</button", i)]
    assert _CARTON.search(bouton) and not _CORBEILLE.search(bouton), (
        f"{fichier} : le bouton « Archiver » ne montre pas 📦 — l'icône dit "
        "« supprimer » quand la boîte dit « archiver »"
    )


@pytest.mark.parametrize("fichier", _MONTENT_CARTE_MODIFIABLE)
def test_les_cartes_archivables_passent_par_carte_modifiable(fichier):
    """Le prestataire et le contrat montent `CarteModifiable`, et lui transmettent
    l'état d'archive et le geste — sinon 📦 / ↩️ ne s'y rendraient pas (#1539)."""
    source = _sans_commentaires((_COMPOSANTS / fichier).read_text(encoding="utf-8"))
    assert "<CarteModifiable" in source, f"{fichier} : ne monte plus `CarteModifiable`"
    assert "{archive}" in source and "onArchiver={" in source, (
        f"{fichier} : `archive` ou `onArchiver` n'est plus transmis à `CarteModifiable` — "
        "📦 et ↩️ ne suivraient plus l'état de la fiche"
    )
