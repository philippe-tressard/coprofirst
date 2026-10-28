"""Les libellés de catégorie disent la MÊME chose des deux côtés de la frontière.

## Pourquoi ce test existe (31/08/2026)

Le courriel du syndic affichait `CategorieTicket.panne` : les libellés vivaient
uniquement dans `front/src/lib/tickets-categories.ts`, et le serveur n'avait rien
à rendre.

La table a donc été recopiée dans `app/utils/categories_ticket.py`, et **la
duplication est inévitable** : les contextes de construction Docker sont `./api`
et `./front`, rien de la racine n'entre dans les images. Le seul motif viable est
*copie + test de concordance* — le même que `perimetre_label`, dont la règle a
été corrigée d'un seul côté le 18/08/2026 et a mis neuf jours à se voir.

⚠️ Sans ce test, la copie diverge au premier libellé retouché — et c'est le
COURRIEL qui garde l'ancien, c'est-à-dire l'endroit que personne ne relit.

## Ce qu'il vérifie, et dans les deux sens

1. les valeurs de l'API couvrent exactement l'énumération `CategorieTicket` ;
2. les libellés de l'API sont exactement ceux du front.

Le point 1 attrape une catégorie ajoutée au modèle sans libellé — elle
s'afficherait alors en brut, ce qui est le défaut d'origine.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.models.tickets import CategorieTicket
from app.utils.carnet_entretien import CATEGORIES_BATI
from app.utils.categories_ticket import LIBELLES_CATEGORIE, libelle_categorie

#  ⚠️ `tickets-categories.ts` depuis le 21/09/2026 : la table a quitté
#  `tickets.ts`, qui dépassait 500 lignes. `#lib/tickets` la réexporte, donc
#  aucun écran n'a bougé — mais un test qui lit un FICHIER, si.
_FRONT = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "tickets-categories.ts"


def _libelles_du_front() -> dict[str, str]:
    """Les couples `value` / `label` de la table `CATEGORIES`.

    ⚠️ La lecture est délibérément littérale : on cherche `value: '…'` suivi de
    `label: '…'`, dans l'ordre où le fichier les écrit. Une analyse plus fine
    (TypeScript transpilé, comme `lint:libelle-perimetre`) coûterait plus qu'elle
    ne rapporte pour cinq couples — mais si le motif cesse de correspondre, le
    cas zéro plus bas le dit au lieu de conclure au vert.
    """
    source = _FRONT.read_text(encoding="utf-8")
    #  On se limite au bloc `CATEGORIES` : `STATUTS` a la même forme juste
    #  au-dessus, et l'englober ferait comparer des pommes et des poires.
    debut = source.index("export const CATEGORIES")
    bloc = source[debut:]
    couples = re.findall(r"value:\s*'([a-z]+)'\s*,\s*(?:\n\s*)?label:\s*'([^']+)'", bloc)
    return dict(couples)


def test_le_motif_de_lecture_trouve_encore_quelque_chose():
    """Cas zéro : un relevé vide se lirait « tout concorde ».

    C'est le faux vert de `standards/04` §27, et il s'est produit trois fois
    cette semaine sur d'autres contrôles.
    """
    front = _libelles_du_front()
    assert len(front) >= 5, (
        f"{len(front)} catégorie(s) lue(s) dans {_FRONT.name} — le motif ne "
        "correspond plus à la table du front. Ne pas lire ceci comme un succès."
    )


def test_l_api_couvre_exactement_l_enumeration():
    """Une catégorie ajoutée au modèle sans libellé s'afficherait en BRUT."""
    du_modele = {c.value for c in CategorieTicket}
    assert set(LIBELLES_CATEGORIE) == du_modele, (
        "La table des libellés et l'énumération divergent :\n"
        f"  sans libellé : {sorted(du_modele - set(LIBELLES_CATEGORIE))}\n"
        f"  libellé orphelin : {sorted(set(LIBELLES_CATEGORIE) - du_modele)}"
    )


def test_les_deux_cotes_disent_la_meme_chose():
    """Le front et l'API, mot pour mot."""
    front = _libelles_du_front()
    for valeur, libelle_front in front.items():
        assert valeur in LIBELLES_CATEGORIE, (
            f"« {valeur} » existe dans le front et pas dans l'API : le courriel "
            "l'affichera en brut."
        )
        assert LIBELLES_CATEGORIE[valeur] == libelle_front, (
            f"« {valeur} » : le front dit « {libelle_front} », l'API dit "
            f"« {LIBELLES_CATEGORIE[valeur]} ». Le destinataire du courriel lit "
            "autre chose que l'utilisateur de l'écran."
        )


def test_l_enumeration_ne_fuit_JAMAIS_telle_quelle():
    """Le défaut d'origine, rejoué : `CategorieTicket.panne` ne doit plus sortir.

    ⚠️ C'est la vérification qui compte le plus. Les trois autres comparent des
    tables ; celle-ci exerce la fonction sur l'objet RÉEL que le courriel reçoit.
    """
    rendu = libelle_categorie(CategorieTicket.panne)
    assert rendu == "Panne", rendu
    assert "CategorieTicket" not in rendu
    #  Et sur une chaîne nue — la forme que porte un brouillon d'aperçu.
    assert libelle_categorie("sinistre") == "Sinistre"
    #  Inconnue : la valeur brute, jamais rien.
    assert libelle_categorie("inventee") == "inventee"
    assert libelle_categorie(None) == ""


def test_une_categorie_RETIREE_ne_disparait_pas_de_l_ecran():
    """« urgence » a été retirée le 07/09/2026 (migration 0177).

    🔴 Un ticket qui aurait échappé à la migration — restauré d'une sauvegarde
    antérieure, par exemple — porte encore `'urgence'`. La fonction doit alors
    rendre le mot brut, jamais une chaîne vide : la ligne du courriel doit
    devenir LISIBLEMENT fausse, pas invisible.

    C'est la même règle que pour un libellé de rôle manquant, et c'est la version
    « affichage » du faux vert : une information absente qui se rend comme une
    absence d'information.
    """
    assert libelle_categorie("urgence") == "urgence"


def _carnet_du_front() -> set[str]:
    """Les catégories que l'écran MARQUE comme entrant au carnet d'entretien.

    Même lecture littérale que les libellés : `value: '…'` puis, dans le même
    objet, `carnet: true`. Le cas zéro est assuré par le test ci-dessous, qui
    exige un relevé non vide — un motif qui cesse de correspondre rendrait
    « aucune marque » et se lirait « tout concorde ».
    """
    source = _FRONT.read_text(encoding="utf-8")
    bloc = source[source.index("export const CATEGORIES_TICKET") :]
    #  Chaque entrée commence par `value:` : on découpe dessus, et `carnet: true`
    #  appartient alors sans ambiguïté à l'entrée qui le précède.
    marquees = set()
    for morceau in bloc.split("value: '")[1:]:
        valeur = morceau[: morceau.index("'")]
        corps = morceau.split("value: '")[0]
        if "carnet: true" in corps:
            marquees.add(valeur)
    return marquees


def test_l_ecran_marque_exactement_les_categories_du_carnet():
    """🔴 Demandé à l'écran le 21/09/2026.

    > « Identifie visuellement différemment les catégories qui sont prises en
    >   compte légalement dans le Carnet d'entretien »

    La marque est une **promesse faite au résident** : une affaire close dans
    cette catégorie apparaîtra dans un document qu'un acquéreur peut réclamer.
    Le filtre réel, lui, est `CATEGORIES_BATI` côté serveur.

    ⚠️ Vérifié dans LES DEUX SENS, et le second est le pire :
    - une catégorie marquée sans l'être côté serveur promet une inscription qui
      n'aura pas lieu ;
    - une catégorie du carnet NON marquée inscrit l'affaire sans l'avoir dit —
      c'est-à-dire sans que son auteur ait su ce qu'il rendait consultable.
    """
    front = _carnet_du_front()
    assert front, (
        "aucune catégorie marquée `carnet: true` dans tickets.ts — le motif de "
        "lecture ne correspond plus. Ne pas lire ceci comme un succès."
    )
    serveur = {c.value for c in CATEGORIES_BATI}
    assert front == serveur, (
        f"marquées à l'écran mais hors du carnet : {sorted(front - serveur)} ; "
        f"au carnet mais non marquées : {sorted(serveur - front)}"
    )
