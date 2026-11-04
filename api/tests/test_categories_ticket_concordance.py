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


#  ── La grille servie à l'app (#2508) ─────────────────────────────────────────
#
#  `GET /tickets/referentiels` sert l'ordre, le pictogramme et la description de
#  chaque catégorie, et les libellés des natures. Ils sont recopiés du front
#  (`CATEGORIES_TICKET`, `NATURES`) : la grille de l'app et celle du site doivent
#  rester la même grille.


def _decoder_js(texte: str) -> str:
    """`'\\u{1F6E0}️'` → le caractère : la table du front écrit ses pictogrammes échappés."""
    return re.sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), texte)


def _source_decodee() -> str:
    """La table du front, échappements décodés et commentaires retirés : `\\u{…}`
    porte une accolade, et un commentaire entre deux entrées en porterait d'autres."""
    source = _decoder_js(_FRONT.read_text(encoding="utf-8"))
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


def _grille_du_front() -> list[tuple[str, str, str]]:
    """`(value, emoji, description)` de chaque entrée de `CATEGORIES_TICKET`, dans l'ordre."""
    source = _source_decodee()
    debut = source.index("export const CATEGORIES_TICKET")
    bloc = source[debut : source.index("\n];", debut)]
    grille = []
    for entree in re.findall(r"\{[^{}]*?value:\s*'[a-z_]+'[^{}]*?\}", bloc, re.S):
        champ = lambda nom: re.search(rf"{nom}:\s*'([^']*)'", entree).group(1)  # noqa: E731
        grille.append((champ("value"), champ("emoji"), champ("description")))
    return grille


def test_la_grille_servie_est_celle_du_front_ordre_pictogramme_description():
    from app.utils.categories_ticket import GRILLE_CATEGORIES

    front = _grille_du_front()
    assert len(front) >= 8, f"{len(front)} entrée(s) lue(s) : le motif ne correspond plus."
    assert [c for c, _, _ in GRILLE_CATEGORIES] == [c for c, _, _ in front], "ordre"
    assert list(GRILLE_CATEGORIES) == front


def test_les_natures_servies_sont_celles_du_front():
    from app.utils.nature_affaire import LIBELLES_NATURE

    source = _source_decodee()
    debut = source.index("export const NATURES")
    bloc = source[debut : source.index("] as const", debut)]
    front = dict(re.findall(r"val:\s*'([a-z]+)'[^}]*?libelle:\s*'([^']+)'", bloc, re.S))
    assert len(front) == 3, f"{len(front)} nature(s) lue(s) : le motif ne correspond plus."
    assert list(LIBELLES_NATURE.items()) == list(front.items())
