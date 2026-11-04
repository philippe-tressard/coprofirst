"""Périmètres — le RENDU : comment un périmètre s'écrit à l'écran.

⚠️ **Moitié « libellés » du paquet `app.utils.perimetres`** (découpé le
27/08/2026, seuil de modularité). Importe `arbre.py`, jamais l'inverse.

⚠️ **Ces règles sont écrites DEUX FOIS**, ici et dans
`front/src/lib/perimetres.ts` : les contextes de build sont `./api` et `./front`,
rien de la racine n'entre dans les images, et le partage d'un fichier est
impossible (mémoire `project_partage_front_api_impossible`). Le seul pattern
viable est la copie **plus un contrôle** — ils sont deux, et ils exigent la même
chaîne attendue :

  - `api/tests/test_perimetre_label_batiment.py` — exécute la forme serveur ;
  - `front/scripts/check-libelle-perimetre.mjs` — transpile et exécute la forme
    front, puis vérifie que le test ci-dessus attend la même chaîne.
"""

from __future__ import annotations

from typing import Optional

from .arbre import (
    _PREFIXE_BATIMENT,
    Noeud,
    _avec_defaut,
    arbre,
    est_perimetre_par_defaut,
    parse_json_perimetres,
)


#: Sépare deux éléments de même niveau : « Bât. 1 · Parking ».
SEPARATEUR_ELEMENT = " · "

#: Borne un GROUPE de plusieurs espaces partageant le même parent :
#: « Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès » (27/08/2026,
#: signalé à l'écran).
#:
#: Sans lui, le « · » qui sépare les deux espaces du bâtiment 4 se lit comme celui
#: qui introduit AFUL, et « AFUL › Voie d'accès » paraît être un troisième espace
#: du bâtiment. Il n'apparaît QUE là où le « · » deviendrait ambigu — c'est-à-dire
#: dès qu'un des deux groupes voisins compte plusieurs éléments. Deux groupes d'un
#: seul élément portent chacun leur chemin complet et se lisent sans lui :
#: « Bât. 3 › Toit · Bât. 4 › Toit » ne change pas.
SEPARATEUR_GROUPE = " — "


def _est_groupe_racine(n: Noeud) -> bool:
    """Un nœud d'ORGANISATION : une racine qui ne se cible pas (« Bâtiments »).

    Il ne qualifie pas ses enfants — « Bâtiments › Bât. 4 » n'apprend rien et
    allonge tout. C'est mot pour mot la définition qu'emploie le sélecteur
    (`front/src/lib/components/PerimetrePicker.svelte`, `estGroupeRacine`), et les
    deux doivent rester d'accord : ce qui fait une pastille de premier niveau à la
    saisie est exactement ce qui ne se préfixe pas à la lecture.
    """
    return n.parent is None and not n.selectionnable


def _parent_qualifiant(n: Noeud, noeuds: dict[str, Noeud]) -> Optional[Noeud]:
    """Le parent qui doit précéder ce nœud dans son libellé, s'il y en a un.

    🔴 **La qualification ne s'arrête PLUS aux bâtiments** (27/08/2026, signalé à
    l'écran). La version précédente exigeait `parent.batiment_id is not None`, en
    s'appuyant sur ceci, qui était écrit dans son commentaire : *« les enfants du
    parking, des espaces verts ou des locaux techniques portent déjà des libellés
    distincts (Places, Chaufferie…) : les préfixer allongerait sans lever
    d'ambiguïté »*.

    C'était vrai **du seed, et de lui seul**. Rien n'impose la même discipline aux
    nœuds créés depuis `/admin/patrimoine` : une « Voie d'accès » ajoutée sous AFUL
    s'affichait nue sur le fil, sur la carte de ticket et dans la relance syndic,
    alors que le sélecteur, lui, écrivait bien « AFUL › Voie d'accès ». Le même
    objet avait donc deux écritures contradictoires selon l'écran — ce que le cadre
    d'interface interdit — et devant cet écart c'est la lecture qui avait tort :
    elle perdait une information que la saisie affichait déjà.

    La condition porte donc sur ce que le parent EST — une cible, ou un simple
    regroupement — et non sur ce qu'il contient.
    """
    parent = noeuds.get((n.parent or "").strip().lower()) if n.parent else None
    if parent is None or _est_groupe_racine(parent):
        return None
    return parent


def _court(n: Noeud) -> str:
    """Le libellé ABRÉGÉ (« Bât. 3 »), employé en position de préfixe.

    Le long (« Bâtiment 3 ») allongerait un badge déjà à deux niveaux, sur des
    cartes où il est posé à côté d'un état et d'un numéro.
    """
    return n.libelle_court or n.libelle


def _chemin_ordre(n: Noeud, noeuds: dict[str, Noeud]) -> tuple[int, ...]:
    """Le chemin d'`ordre` de la racine jusqu'au nœud — sa position dans l'arbre.

    ⚠️ `ordre` n'est unique qu'entre FRÈRES : le seed donne 0 à « Copropriété
    entière » comme au premier bâtiment. Trier sur ce seul entier mélangerait les
    niveaux. Le chemin, lui, se compare terme à terme comme un numéro de chapitre :
    `(10,)` < `(10, 0)` < `(20,)`. Un parent précède ses enfants, et deux enfants
    d'un même parent restent **contigus** — ce dont le regroupement de
    `perimetre_label` dépend entièrement.

    La remontée est bornée par `vus` : une boucle dans l'arbre ne doit pas figer une
    requête (même garde-fou que `_chaine`).
    """
    chemin: list[int] = []
    courant: Optional[Noeud] = n
    vus: set[str] = set()
    while courant is not None and courant.code.lower() not in vus:
        chemin.append(courant.ordre or 0)
        vus.add(courant.code.lower())
        suivant = (courant.parent or "").strip().lower()
        courant = noeuds.get(suivant) if suivant else None
    return tuple(reversed(chemin))


def perimetre_label_un(perim: str) -> str:
    """Libellé d'un périmètre isolé. Ne renvoie jamais un code brut à l'écran.

    🔴 **Un espace est QUALIFIÉ par son parent** — « Bât. 3 › Toit », « AFUL › Voie
    d'accès », « Parking › Portail d'accès ». Le gabarit pose les mêmes neuf espaces
    sous chaque bâtiment, si bien qu'un ticket visant les toits de deux bâtiments
    s'affichait « Toit · Toit », sans dire lesquels (18/08/2026) ; et un espace créé
    sous un nœud transverse s'affichait nu (27/08/2026). Le détail de la règle et de
    son élargissement est dans `_parent_qualifiant`.

    ⚠️ **Cette règle est écrite DEUX FOIS**, ici et dans `front/src/lib/perimetres.ts`,
    et ce n'est pas un oubli : les contextes de build sont `./api` et `./front`, rien
    de la racine n'entre dans les images, et le partage d'un fichier est impossible
    (mémoire `project_partage_front_api_impossible`). Le seul pattern viable est la
    copie — et elle se paie : la correction côté front, faite le matin même, n'a PAS
    atteint le fil d'activité, dont les libellés sont calculés **ici**. C'est le
    défaut que ce commentaire doit empêcher de reproduire une troisième fois.

    Le test `api/tests/test_perimetre_label_batiment.py` verrouille les deux formes.
    """
    noeuds = arbre()
    n = noeuds.get((perim or "").strip().lower())
    if n is not None:
        parent = _parent_qualifiant(n, noeuds)
        if parent is not None:
            return f"{_court(parent)} › {n.libelle}"
        return n.libelle
    #  Repli d'affichage pour un contenu qui cite un nœud supprimé depuis. Ce n'est
    #  **pas** une source de vérité : la convention `bat:N` est posée par le seed,
    #  l'arbre reste seul juge. Elle survit ici parce qu'un badge vide ou un
    #  `bat:5` brut sont deux façons de se voir en production.
    if perim and perim.lower().startswith(_PREFIXE_BATIMENT):
        return f"Bât. {perim[len(_PREFIXE_BATIMENT) :]}"
    return perim


def perimetre_label(perims: list[str]) -> str:
    """Le rendu commun à toutes les rubriques — trié, puis regroupé par parent.

    🔴 **L'ordre affiché ne suit plus l'ordre des clics** (27/08/2026, signalé à
    l'écran). Les codes sont stockés dans l'ordre où l'utilisateur a touché les
    pastilles (`PerimetrePicker`, `value = [...s]`), et personne ne les triait
    ensuite : deux espaces d'un même bâtiment se retrouvaient séparés par un
    périmètre étranger, et le bâtiment répété —

        Bât. 4 › Logement · Voie d'accès · Bât. 4 › Jardin Bâtiment

    On trie donc par la position dans l'arbre, on fusionne les éléments contigus qui
    partagent un parent qualifiant, et on rend :

        Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès

    C'est aussi, exactement, ce que le sélecteur affiche sur ses pastilles : un objet
    se lit partout de la même façon.

    Les codes INCONNUS de l'arbre (nœud supprimé depuis) sont conservés — un contenu
    ne perd pas son badge — mais rangés à la fin, dans leur ordre d'origine : ils
    n'ont pas de position dans un arbre où ils ne figurent plus.
    """
    noeuds = arbre()
    connus: list[Noeud] = []
    inconnus: list[str] = []
    for p in perims:
        n = noeuds.get((p or "").strip().lower())
        if n is not None:
            connus.append(n)
        else:
            inconnus.append(p)
    connus.sort(key=lambda n: _chemin_ordre(n, noeuds))

    #  Un « groupe » = des éléments CONTIGUS partageant le même parent qualifiant.
    #  Contigus suffit : le tri par chemin garantit qu'aucun nœud étranger ne peut
    #  s'intercaler entre deux enfants d'un même parent.
    groupes: list[tuple[Optional[Noeud], list[str]]] = []
    for n in connus:
        parent = _parent_qualifiant(n, noeuds)
        if groupes and parent is not None and groupes[-1][0] == parent:
            groupes[-1][1].append(n.libelle)
        else:
            groupes.append((parent, [n.libelle]))
    for p in inconnus:
        groupes.append((None, [perimetre_label_un(p)]))

    sortie = ""
    for i, (parent, libelles) in enumerate(groupes):
        if i > 0:
            #  Le séparateur fort UNIQUEMENT là où le « · » deviendrait ambigu :
            #  dès que l'un des deux groupes voisins en contient déjà un.
            ambigu = len(groupes[i - 1][1]) > 1 or len(libelles) > 1
            sortie += SEPARATEUR_GROUPE if ambigu else SEPARATEUR_ELEMENT
        corps = SEPARATEUR_ELEMENT.join(libelles)
        sortie += f"{_court(parent)} › {corps}" if parent is not None else corps
    return sortie


def perimetre_badge(codes: Optional[list[str]]) -> str:
    """Le libellé du badge 🔹 d'un contenu — `""` quand il ne se montre pas.

    La règle de `BadgePerimetre` (front) : le périmètre par défaut, ou une liste
    vide, se TAIT ; tout autre se nomme par `perimetre_label`. Servie avec chaque
    contenu (`perimetre_libelle`, #2505) pour que le site et l'app iOS montrent
    le même lieu sans recomposer l'arbre.
    """
    if est_perimetre_par_defaut(codes):
        return ""
    return perimetre_label(codes)


def perimetre_label_liste(codes: list[str]) -> str:
    """Comme `perimetre_label`, mais une liste VIDE vaut le périmètre par défaut.

    Pendant de `perimetre_label_json` pour les appelants qui tiennent déjà la liste
    de codes — l'annonce de hall, dont le titre doit dire « Copropriété entière »
    plutôt que rien quand aucun périmètre n'est précisé.
    """
    return perimetre_label(_avec_defaut(codes))


def perimetre_label_json(perimetre_cible: Optional[str], *, vide: str = "") -> str:
    """Libellé direct depuis un champ JSON.

    `vide` est rendu quand le champ est absent — l'e-mail de relance syndic
    n'affiche alors aucune ligne « périmètre », là où le fil affiche
    « Copropriété entière ». Deux besoins légitimes, un seul paramètre, plutôt
    que deux tables.
    """
    if not perimetre_cible:
        return vide
    return perimetre_label(parse_json_perimetres(perimetre_cible))
