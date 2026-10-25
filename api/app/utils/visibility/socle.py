"""Primitives de visibilité — géographie et public visé.

⚠️ Fragment de `app/utils/visibility/` : le découpage en trois modules et sa couture
sont expliqués UNE fois, dans l'en-tête de `__init__.py` (#1564).
"""

from __future__ import annotations

import json
from typing import Optional

from app.utils.statuts_lus import statuts_lus
from app.models.core import (
    Utilisateur,
)
from app.utils.mes_batiments import batiments_de_l_utilisateur, perimetres_desservis
from app.utils.perimetres import a_portee_globale, batiments_cibles, sous_l_une_des_branches
from app.utils.roles_libelles import libelle_role
from app.auth.deps import est_moderateur

# ── Parseurs internes ─────────────────────────────────────────────────────────


def _parse_json_list(raw: Optional[str], default: list[str]) -> list[str]:
    """Parse un champ JSON stocké en base (ex: '["bat:1","bat:3"]')."""
    if not raw:
        return default
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
        return list(val) if isinstance(val, (list, tuple)) else default
    except Exception:
        return default


def _codes_json_pour_acces(raw: Optional[str]) -> Optional[list[str]]:
    """Codes de périmètre d'un champ JSON, pour une **décision d'accès**.

    Distingue trois états là où `utils/perimetres.parse_json_perimetres` n'en
    distingue que deux, et la nuance est une nuance de sécurité :

    - champ absent ou vide → `[]`, c'est-à-dire « aucune restriction ». C'était
      déjà le comportement, et il est conservé ;
    - JSON valide → les codes ;
    - JSON **illisible** → `None`, et l'appelant refuse.

    Ce dernier cas est un changement assumé. Jusqu'ici, un `perimetre_cible`
    corrompu retombait sur `["résidence"]` : une donnée abîmée **élargissait** la
    visibilité au lieu de la restreindre. Pour un badge à l'écran ce repli est
    bienvenu (cf. `parse_json_perimetres`) ; pour décider qui a le droit de lire,
    il est exactement à l'envers.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    if not isinstance(val, (list, tuple)):
        return None
    return [str(v) for v in val]


# ── Règles géographiques ──────────────────────────────────────────────────────


def perimetre_visible(
    perimetres: list[str], user: Utilisateur, *, ouvert_a_la_copropriete: bool = False
) -> bool:
    """
    Retourne True si le périmètre de l'item est accessible à l'utilisateur.

    - CS / Admin : toujours True.
    - Nœud à portée globale, ou dont un ancêtre l'est : True pour tout résident.
    - `ouvert_a_la_copropriete` : les contenus dont le bâtiment ne restreint plus
      la lecture — actualités et tickets (#339). Voir ci-dessous.
    - Sinon : True si le bâtiment du nœud (ou du plus proche ancêtre qui en porte
      un) est celui de l'utilisateur.
    - Liste vide : aucune restriction → True.

    ## `ouvert_a_la_copropriete` — ce que ce paramètre ouvre, et ce qu'il n'ouvre pas

    Il vaut **False par défaut**, et c'est le point important : le comportement
    d'hier reste celui de tout ce qui ne demande pas explicitement l'ouverture.
    Documents, sondages et événements d'AG ne la demandent pas, et leur accès est
    donc rigoureusement inchangé.

    Ce paramètre élargit l'axe **bâtiment**, jamais l'axe **public**. Cette
    fonction est combinée en ET avec `public_cible` (résidents, copropriétaires,
    bailleurs, locataires, CS), avec `ProfilAccesDocument` et avec les règles
    mandataire de `routers/bailleur.py` : l'ouvrir ne peut donc rien débloquer
    pour quelqu'un que ces règles refusent. C'est la moitié de la contrainte du
    14/08/2026 qui n'a jamais bougé, vérifiée couple par couple dans
    `tests/test_visibilite_ouverte.py`.

    ⚠️ L'autre moitié — *une agence, un bailleur ou un mandataire qui n'avaient
    pas de visibilité n'en gagnent aucune* — a été **levée le 02/09/2026**, sur
    arbitrage, et seulement sur l'axe bâtiment : voir « Mes bâtiments » dans le
    corps de la fonction.

    - Code introuvable : n'accorde **rien**. Un nœud supprimé, un arbre vidé ou une
      table illisible ne peuvent pas justifier un accès — ils ne permettent pas de
      décider, et un contrôle qui ne peut pas s'exécuter ne renvoie jamais OK
      (`standards/04`). La première écriture de cette fonction court-circuitait à
      `True` quand l'arbre était vide : `tests/test_documents_acces.py` l'a
      attrapée, une pièce jointe ciblée sur un autre bâtiment devenant lisible dès
      que la table manquait.

    L'ordre des tests reproduit exactement celui de la règle précédente, qui
    comparait des chaînes : `api/tests/test_perimetres_arbre.py` rejoue l'ancienne
    implémentation contre celle-ci sur tous les couples (périmètre × utilisateur)
    et exige des verdicts identiques.
    """
    if est_moderateur(user):
        return True
    if not perimetres:
        return True
    if a_portee_globale(perimetres):
        return True

    #  ── « Mes bâtiments » : UNE notion, UN endroit, deux cas zéro ────────────
    #
    #  🔒 LA RÈGLE D'ACCÈS RESTE CENTRALISÉE, ET CE BLOC N'EN INTRODUIT AUCUNE.
    #  La règle géographique vit dans cette fonction et nulle part ailleurs — ses
    #  appelants la composent, aucun ne la réécrit (`test_perimetres_liste_en_dur`
    #  refuse qu'une liste de périmètres réapparaisse, `test_autorisation` qu'un
    #  endpoint se passe de dépendance). Et « quels bâtiments sont les siens » a
    #  sa propre source unique, `utils/mes_batiments` : aucun rattachement, aucun
    #  lot, aucun identifiant de bâtiment ne se lit ici en direct. Le jour où
    #  cette notion changera — usufruit, mandat, lot indivis —, elle changera
    #  là-bas, et cette décision suivra sans être rouverte.
    #
    #  🔴 DEUX ARBITRAGES SUCCESSIFS DE L'UTILISATEUR, LE 02/09/2026. Ils ne
    #  disent pas la même chose, et le second lève une contrainte que le premier
    #  respectait :
    #
    #  1. *« Un utilisateur sans bâtiment ne doit rien voir car il n'est pas
    #     résident. »* — cette fonction portait depuis toujours un repli
    #     permissif : `user.batiment_id is None` → `True`, « accès résidence
    #     entière par défaut ». Deux tests l'épinglaient en disant, l'un et
    #     l'autre, « le jour où ce repli sera repris » : c'était ce jour-là.
    #
    #     Ce que ça referme dépasse les périmètres : la CONFIDENTIALITÉ passe par
    #     ce même chemin (`ouvert_a_la_copropriete=False`). Un compte sans
    #     bâtiment voyait les actualités confidentielles de TOUS les bâtiments, et
    #     rien ne le signalait — un contenu visible de trop de monde ne produit
    #     aucune plainte.
    #
    #  2. *« Un bailleur sans rattachement voit les bâtiments de ses lots »*, et à
    #     généraliser : les lots comptent pour TOUT LE MONDE, pas seulement pour
    #     qui n'a aucun rattachement.
    #
    #  ⚠️ LE POINT 2 LÈVE LA CONTRAINTE DU 14/08/2026 — *une agence, un bailleur
    #  ou un mandataire qui n'avaient pas de visibilité n'en gagnent aucune* — et
    #  il faut le dire, parce qu'un élargissement d'accès qu'on ne nomme pas est
    #  indistinguable d'un défaut. Un bailleur rattaché au bâtiment A et détenteur
    #  d'un lot en B voit maintenant B ; il ne le voyait pas hier.
    #
    #  La levée est BORNÉE à l'axe **bâtiment**, et c'est ce qui la rend tenable :
    #  l'axe **public** (`public_cible`), `ProfilAccesDocument` et les règles
    #  mandataire sont intacts, et cette fonction leur est combinée en ET. Une
    #  publication réservée aux locataires ne devient pas lisible d'un bailleur
    #  parce qu'il détient un lot. `test_visibilite_ouverte.py` le rejoue couple
    #  par couple.
    #
    #  Ce qu'on gagne au passage : la restriction volontaire et la décision
    #  d'accès emploient enfin la MÊME notion de « mes bâtiments ». Elles
    #  divergeaient — rattachement + lots ici, rattachement seul là —, et l'écart
    #  était invisible parce que chacune était juste de son côté.
    miens = batiments_de_l_utilisateur(user)
    #  🔴 « MES PÉRIMÈTRES » (#2214, spec `lots-et-perimetres.md` §5–6) : une place
    #  ou une cave est desservie par une circulation — l'ascenseur et l'escalier
    #  d'un bâtiment qui n'est pas forcément le sien. Ce qui est ciblé SOUS ces
    #  nœuds concerne qui les emprunte et les paie, résident ou copropriétaire
    #  extérieur. Jamais le bâtiment desservant en entier : arbitré le 24/10/2026,
    #  ses actualités confidentielles, son hall et son toit restent à ses résidents.
    #  C'est un ajout pur à l'intersection des bâtiments : qui n'a pas de lot
    #  desservi garde exactement ses verdicts d'hier (`test_perimetres_arbre`).
    desservis = perimetres_desservis(user)

    def _concerne() -> bool:
        return bool(miens & batiments_cibles(perimetres)) or sous_l_une_des_branches(
            desservis, perimetres
        )

    if ouvert_a_la_copropriete:
        if not getattr(user, "restreindre_a_mes_batiments", False):
            return True
        #  Cas zéro : rien de connu, donc rien à restreindre — renvoyer False
        #  laisserait un fil vide à qui a simplement coché une case.
        if not miens and not desservis:
            return True
        return _concerne()

    #  Même question, cas zéro INVERSE, et c'est toute la différence : ne pas
    #  savoir de quoi l'on parle n'a pas le même sens selon qu'on restreint un
    #  affichage ou qu'on décide d'un accès.
    if not miens and not desservis:
        return False
    return _concerne()


# ── Règle « à qui ça s'adresse » ──────────────────────────────────────────────

#: Le vocabulaire du public cible, dans l'ordre où il est proposé à l'écran.
#:
#: `résidents` n'y figure pas : ce n'est pas un profil mais l'ABSENCE de
#: restriction, et le sélecteur le rend par une pastille à part.
#:
#: ⚠️ Cette liste ne fait pas foi à elle seule — c'est `public_cible_visible`
#: ci-dessous qui décide. Elle sert à ce qu'un contrôle puisse comparer les deux
#: côtés : `tests/test_destinataires_vocabulaire.py` vérifie que chaque code
#: d'ici est réellement honoré par la fonction (donc que la liste ne ment pas),
#: ET que `front/src/lib/destinataires.ts` propose exactement les mêmes. Sans
#: cela, un code ajouté d'un seul côté produit une pastille qui ne cible rien,
#: ou une règle que personne ne peut choisir.
#:
#: 🔴 `copropriétaires` n'y est plus (#1301, 25/09/2026) : la pastille faisait
#: double emploi avec les deux suivants, et la migration 0221 a converti les
#: données. La règle ci-dessous le LIT encore — un client resté en cache peut
#: l'envoyer — mais aucun écran ne le propose.
#:
#: Les LIBELLÉS sont ceux de l'écran (`DESTINATAIRES`, même fichier front), et
#: le même test les tient d'accord : le serveur les écrit dans la Suite qui
#: change les Destinataires d'une affaire (`utils/trace_droits.py`, 29/09/2026).
LIBELLES_PUBLIC_CIBLE: dict[str, str] = {
    "copropriétaires_occupants": "Copropriétaires occupants",
    "bailleurs": "Copropriétaires bailleurs",
    "mandataires": "Bailleurs",
    "locataires": "Locataires",
    #  Un RÔLE : son libellé a sa source unique (`test_roles_libelles.py`).
    "conseil_syndical": libelle_role("conseil_syndical"),
}
CODES_PUBLIC_CIBLE: tuple[str, ...] = tuple(LIBELLES_PUBLIC_CIBLE)


def reserve_au_conseil(raw: Optional[str]) -> bool:
    """Le public visé est-il « Conseil syndical » SEUL ?

    🔴 Arbitré le 23/09/2026 (#1096) : l'option « 🛡️ Visibilité réservée au
    conseil syndical » disparaît de l'actualité — Destinataires = « Conseil
    syndical » seul en tient lieu, **avec le même effet** : ni groupe WhatsApp,
    ni affiche de hall. Sans cette règle, le groupe recevait un message restreint
    (titre + lien), et le titre d'un contenu réservé fuyait. Une seule écriture :
    la diffusion et les sources d'affiche l'appellent.
    """
    try:
        codes = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        return False
    return isinstance(codes, list) and [str(c) for c in codes] == ["conseil_syndical"]


def public_cible_visible(raw: Optional[str], user: Utilisateur) -> bool:
    """L'utilisateur fait-il partie du public visé par `raw` (JSON de codes) ?

    Écrite UNE fois : les publications et les sondages posent la même question,
    et le sondage y répondait avec son propre vocabulaire (des `StatutUtilisateur`
    bruts). Deux règles pour une notion, c'est deux règles qui divergent — celle
    du sondage ne connaissait ni « bailleurs », ni le conseil syndical.

    Vide ou absent = aucune restriction. Une valeur **non reconnue** ne donne
    jamais l'accès : c'est ce qui permet à la migration 0147 de laisser passer un
    résidu sans risque, puisqu'un résidu ne peut alors que restreindre.
    """
    #  🔴 UNE DONNÉE ILLISIBLE NE DONNE PAS L'ACCÈS (06/09/2026, #789).
    #
    #  `_parse_json_list` retombe sur son défaut — ici `[]`, c'est-à-dire
    #  « aucune restriction » — quand le JSON ne se lit pas. Une colonne
    #  `public_cible` corrompue rendait donc l'objet visible de TOUS : une
    #  publication réservée au conseil syndical se serait ouverte à la
    #  copropriété entière, sans message ni ligne de journal.
    #
    #  ⚠️ C'est **exactement** le défaut que `_codes_json_pour_acces` avait
    #  corrigé pour le périmètre, avec ces mots : « une donnée abîmée
    #  élargissait la visibilité au lieu de la restreindre é. Pour décider qui
    #  a le droit de lire, il est exactement à l'envers ». La correction n'avait
    #  pas traversé jusqu'à l'axe voisin — trouvé en écrivant la table des sens.
    #
    #  L'absence reste « tout le monde » : c'est le cas zéro, et il est légitime.
    #  C'est la donnée PRÉSENTE mais illisible qui refuse.
    if raw is not None and str(raw).strip() not in ("", "[]"):
        codes = _codes_json_pour_acces(raw)
        if codes is None:
            return False
        public = codes
    else:
        public = []
    if not public:
        return True

    if "résidents" in public:
        return True
    #  Les statuts au titre desquels il LIT : le sien, et pour un aidant ceux
    #  des personnes qu'il aide par une délégation active (#1303).
    statuts = statuts_lus(user)
    #  Héritage : plus proposé depuis #1301 (migration 0221), toujours lu.
    if "copropriétaires" in public and any(s.startswith("copropriétaire_") for s in statuts):
        return True
    if "locataires" in public and "locataire" in statuts:
        return True
    #  « Bailleurs » vise les copropriétaires qui LOUENT leur lot, et eux seuls ;
    #  « copropriétaires occupants » est son exact symétrique. `copropriétaires`
    #  ci-dessus couvre les deux statuts — mais rien ne permettait de s'adresser à
    #  l'un SANS l'autre, alors que des pans entiers du produit leur sont propres
    #  (baux et remise d'objets d'un côté, vie quotidienne de l'autre).
    if "bailleurs" in public and "copropriétaire_bailleur" in statuts:
        return True
    if "copropriétaires_occupants" in public and "copropriétaire_résident" in statuts:
        return True
    #  « Bailleurs » à l'écran (#1301, 26/09/2026) : celui qui loue PAR
    #  DÉLÉGATION d'un copropriétaire — agence, gestionnaire. Le code
    #  `bailleurs` ci-dessus était déjà pris par le copropriétaire bailleur, et
    #  il est stocké : le nouveau se nomme par le statut qu'il vise.
    if "mandataires" in public and "mandataire" in statuts:
        return True
    #  Le SEUL code du catalogue qui se décide sur le rôle et non sur le statut.
    #
    #  ⚠️ Cette branche manquait, et rien ne le montrait : les deux appelants
    #  (`publication_visible`, `sondage_accessible`) laissent sortir le CS et
    #  l'admin AVANT d'arriver ici, si bien qu'un contenu ciblé « conseil
    #  syndical » leur parvenait par ce chemin-là. Le comportement était donc
    #  juste — mais la fonction ne l'était pas, et un troisième appelant qui
    #  aurait oublié le court-circuit aurait caché au conseil syndical ce qui lui
    #  était explicitement adressé. Trouvé par `test_destinataires_vocabulaire.py`
    #  le 16/08/2026, qui interroge la règle SEULE.
    if "conseil_syndical" in public and est_moderateur(user):
        return True
    # Valeur non reconnue, ou public dont l'utilisateur ne fait pas partie
    return False


def cible_visible(
    perimetre_cible: Optional[str],
    public_cible: Optional[str],
    user: Utilisateur,
    *,
    ouvert_a_la_copropriete: bool = False,
    auteur_id: Optional[int] = None,
) -> bool:
    """**La** règle « cet objet ciblé est-il visible de cet utilisateur ? ».

    Les deux axes du ciblage, dans l'ordre, avec leurs cas de refus — écrits une
    seule fois :

    1. le conseil syndical et l'administration voient tout, et sortent d'abord :
       c'est ce qui leur laisse de quoi corriger un ciblage fautif ;
    2. le **périmètre** — où ça se passe ;
    3. le **public cible** — à qui ça s'adresse.

    ## Pourquoi cette fonction existe (06/09/2026)

    `publication_visible` et `sondage_accessible` posaient **exactement** ces
    trois questions, dans cet ordre, avec le même traitement du ciblage illisible
    — et divergeaient sur un seul point, `ouvert_a_la_copropriete`, qui est
    devenu le paramètre. Deux copies d'une règle d'accès se durcissent une fois
    sur deux, et la petite annonce et l'idée allaient en faire une troisième et
    une quatrième (#782).

    ⚠️ Une règle d'autorisation ne se recopie pas « parce que l'objet est
    différent » : c'est ce qui a produit `_require_bailleur`, doublon exact de
    `require_proprietaire` posé hors du module central, avec dix-sept endpoints
    dessus — et une spec qui le documentait comme officiel.

    `ouvert_a_la_copropriete` reste **faux par défaut**, et c'est le choix sûr :
    l'ouverture est une décision qui s'écrit chez l'appelant, jamais un effet de
    bord hérité. Une actualité ciblée sur un bâtiment reste lisible de toute la
    copropriété parce qu'elle **informe** (#339) ; un sondage fait **voter**, une
    annonce s'adresse à qui son auteur a choisi — les ouvrir changerait
    respectivement qui pèse sur le résultat et qui reçoit l'offre.

    🔴 `auteur_id` : **l'auteur voit toujours ce qu'il a écrit.** Sans ce
    court-circuit, un locataire qui ciblait son annonce sur les copropriétaires
    la faisait disparaître **pour lui-même** — plus de carte, donc plus de
    bouton, donc plus aucun moyen de corriger le ciblage. Un objet qu'on ne peut
    plus ni voir ni retirer est perdu, et rien ne l'aurait signalé (constaté le
    06/09/2026 en préparant #783, sur du code livré la veille par #782).

    ⚠️ Il est **optionnel**, et les publications comme les sondages ne le passent
    pas : leurs auteurs sont CS ou admin, donc déjà sortis à la ligne suivante.
    Le passer partout « au cas où » donnerait l'illusion d'une règle uniforme là
    où le besoin n'existe pas — et ferait croire, le jour où une entité changera
    de créateur, que la question a déjà été posée.
    """
    if auteur_id is not None and user.id == auteur_id:
        return True
    if est_moderateur(user):
        return True
    perims = _codes_json_pour_acces(perimetre_cible)
    if perims is None:
        #  Ciblage illisible : on refuse. Un contrôle qui ne peut pas s'exécuter
        #  ne renvoie jamais OK (`standards/04`), et le CS est déjà sorti plus
        #  haut — il garde donc de quoi corriger l'objet.
        return False
    if not perimetre_visible(perims, user, ouvert_a_la_copropriete=ouvert_a_la_copropriete):
        return False
    return public_cible_visible(public_cible, user)
