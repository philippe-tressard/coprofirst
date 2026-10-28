"""Le vocabulaire des rôles et des statuts n'est pas RÉÉCRIT dans un écran.

Trois garde-fous de même forme, nés de trois incidents, et séparés de
`test_roles_libelles.py` le 08/09/2026 quand le plafond de modularité a refusé
de le laisser grossir. Le refus disait vrai : ce fichier-ci regarde le **front**,
l'autre le **serveur**, et ils ne partagent que la mécanique de lecture — qui vit
désormais dans `aides_roles_libelles_lecture.py`.

Les trois questions, dans l'ordre où on a appris à les poser :

1. chaque libellé a-t-il une TEINTE ? (#819)
2. une table de teintes est-elle réécrite dans un écran ? (#819)
3. une table de LIBELLÉS l'est-elle ? (#828)

⚠️ La troisième a existé un mois sans être vue, parce que les deux premières ne
pouvaient pas la voir : celle des libellés serveur cherche les chaînes
**canoniques**, et les copies fautives écrivaient des **abrégés**. Une copie qui
paraphrase devient invisible à un contrôle qui cherche le texte. D'où un contrôle
qui regarde la **forme** — les clés — et pas les valeurs.

Les trois questions tiennent en DEUX balayages pilotés par table (30/09/2026) :
`COLONNES` pour la première — chaque colonne de `roles.ts` couvre tous les
états —, `TABLES_INTERDITES` pour les deux autres — aucune table indexée par des
rôles ou des statuts hors de `roles.ts`. Chacun nomme tous ses écarts d'un coup ;
les deux auto-tests « refuse bien » restent à part, un par forme de valeur.
"""

from __future__ import annotations

from tests.aides_roles_libelles_lecture import (
    ROLES_TS,
    VALEUR_CHAINE,
    VALEUR_TEINTE,
    fichiers_du_front,
    table_ts,
    tables_par_cle,
)

#  ══════════════════════════════════════════════════════════════════════════
#  LA TEINTE — le second demi du vocabulaire, resté recopié jusqu'au 07/09/2026
#
#  #801 a fait de `roles.ts` la source unique des LIBELLÉS. La COULEUR, elle,
#  est restée écrite dans les écrans : `/admin` et `/profil` importaient tous
#  deux `libelleRole`, puis recopiaient la table des badges trois lignes plus
#  bas. Le contrôle ci-dessus ne pouvait pas le voir — il cherche des chaînes de
#  LIBELLÉ, et `badge-teal` n'en est pas une.
#
#  🔴 Ce que la copie coûtait déjà : `/profil` ne connaissait ni `propriétaire`
#  ni `externe`. Un compte portant l'un de ces rôles s'affichait en **gris** sur
#  son propre profil et en **teal** ou **jaune** dans l'administration. Le repli
#  `?? 'badge-gray'` rend un badge parfaitement normal : rien ne signalait
#  l'oubli, et c'est ce qui le rendait durable.
#  ══════════════════════════════════════════════════════════════════════════

#  Les fichiers du front autorisés à écrire `badge-<teinte>` en face d'une clé
#  de rôle ou de statut. Un seul, et c'est le sujet.
SOURCE_BADGES = "src/lib/roles.ts"


def test_le_garde_fou_des_TEINTES_refuse_bien_une_reecriture():
    """Cas zéro : les deux sens, et surtout l'homonymie.

    Le troisième cas est celui que la première version du contrôle a signalé à
    tort : une table du reporting dont UNE clé porte le nom d'un rôle. Sans lui,
    le resserrement serait invérifiable — et un seuil qu'on ne peut pas éprouver
    est un seuil qu'on rabotera au prochain faux positif.
    """
    cles = {"locataire", "conseil_syndical", "copropriétaire_bailleur", "syndic", "ag"}

    copie = (
        "const roleBadge: Record<string, string> = {\n"
        "\tlocataire: 'badge-gray',\n"
        "\tconseil_syndical: 'badge-blue',\n"
        "\tcopropriétaire_bailleur: 'badge-purple',\n"
        "};\n"
    )
    assert len(tables_par_cle(copie, cles, VALEUR_TEINTE)) == 1

    homonymie = (
        "export const KANBAN_COLORS: Record<string, string> = {\n"
        "\tag: 'badge-purple',\n"
        "\tsyndic: 'badge-orange',\n"
        "\tfournisseur: 'badge-yellow',\n"
        "};\n"
    )
    #  `ag` et `syndic` sont ici des colonnes de kanban. Deux clés du jeu, mais
    #  la notion n'est pas la même — c'est la limite assumée du contrôle, et
    #  c'est pourquoi le cas zéro l'écrit noir sur blanc.
    assert len(tables_par_cle(homonymie, {"locataire", "conseil_syndical"}, VALEUR_TEINTE)) == 0

    ternaire = "<span\n\tclass=\"badge {u.statut === 'locataire' ? 'badge-gray' : ''}\"\n></span>\n"
    assert len(tables_par_cle(ternaire, cles, VALEUR_TEINTE)) == 0

    #  Un commentaire qui cite la forme ne la pose pas — `standards/04` §39, et
    #  deux contrôles s'y sont déjà pris eux-mêmes le 06/09/2026.
    commentaire = (
        "const x = {\n"
        "\t//  locataire: 'badge-gray' vivait ici avant #819\n"
        "\t//  conseil_syndical: 'badge-blue' aussi\n"
        "};\n"
    )
    assert len(tables_par_cle(commentaire, cles, VALEUR_TEINTE)) == 0


#  ══════════════════════════════════════════════════════════════════════════
#  LE LIBELLÉ ABRÉGÉ — le troisième demi, resté recopié jusqu'au 08/09/2026
#
#  🔴 `admin/+page.svelte` portait DEUX tables de libellés de statut, à trente
#  lignes d'écart et dans le même fichier : `statutLabels` et `statutLabelsAdmin`
#  (#828). Elles étaient identiques SAUF `admin_technique`, absent de la seconde
#  — si bien qu'une demande de profil émanant d'un compte technique affichait
#  `admin_technique`, la valeur brute de l'énumération. Un libellé manquant ne
#  lève pas, il s'imprime.
#
#  ⚠️ AUCUN des deux contrôles ci-dessus ne pouvait les voir, pour deux raisons
#  indépendantes — et la seconde est la leçon :
#
#    1. le premier ne scanne que `app/**.py`, côté serveur ;
#    2. surtout, il cherche les chaînes CANONIQUES (« Copropriétaire résident »),
#       et ces tables écrivaient des ABRÉGÉS (« Copro. résident »). Une copie qui
#       raccourcit le texte devient invisible à un contrôle qui cherche le texte.
#
#  D'où ce troisième contrôle, qui ne regarde pas les VALEURS mais la FORME : une
#  table dont plusieurs CLÉS sont des statuts, où qu'elle soit et quoi qu'elle
#  associe. C'est le seul angle sous lequel une paraphrase reste visible.
#  ══════════════════════════════════════════════════════════════════════════

#: Le seul fichier du front autorisé à déclarer une table indexée par des statuts.
SOURCE_LIBELLES = "src/lib/roles.ts"

#:  Les clés que `StatutUtilisateur` PARTAGE avec `TypeLien` — deux énumérations
#:  distinctes du produit, dont deux valeurs portent le même mot.
#:
#:  ⚠️ Elles sont retirées du jeu de recherche, et c'est nécessaire : `TypeLien`
#:  dit comment une personne est liée à un LOT (propriétaire, bailleur,
#:  locataire, mandataire), `StatutUtilisateur` ce qu'elle EST dans la
#:  copropriété. `TYPE_LIEN_LABEL` (`OngletImportLots.svelte`) est une table
#:  légitime de la première, et le seuil de deux ne suffisait pas à la
#:  distinguer puisque DEUX de ses clés sont homonymes.
#:
#:  🔴 Rien n'est perdu : une vraie table de statuts porte forcément l'un des
#:  cinq mots restants — `copropriétaire_résident`, `copropriétaire_bailleur`,
#:  `syndic`, `aidant`, `admin_technique`. Les deux copies trouvées le 08/09 en
#:  portaient chacune au moins trois. Exclure ces clés par NOM plutôt que
#:  d'excuser un FICHIER laisse le contrôle actif partout, y compris dans le
#:  fichier où l'homonymie vit.
_CLES_PARTAGEES_AVEC_TYPE_LIEN = {"locataire", "mandataire"}


def test_le_garde_fou_des_LIBELLES_ABREGES_refuse_bien_une_reecriture():
    """Cas zéro, dans les deux sens — dont la PARAPHRASE, que rien d'autre ne voit.

    La deuxième copie est celle qui a échappé aux deux contrôles existants
    pendant un mois : mêmes clés, texte raccourci. Elle doit être refusée ici
    **sans** que le contrôle sache à quoi ressemble le texte canonique.
    """
    cles = {"copropriétaire_résident", "copropriétaire_bailleur", "syndic", "aidant"}

    canonique = (
        "const labels: Record<string, string> = {\n"
        "\tcopropriétaire_résident: 'Copropriétaire résident',\n"
        "\tsyndic: 'Syndic',\n"
        "};\n"
    )
    paraphrase = (
        "const statutLabelsAdmin: Record<string, string> = {\n"
        "\tcopropriétaire_résident: 'Copro. résident',\n"
        "\tcopropriétaire_bailleur: 'Copro. bailleur',\n"
        "};\n"
    )
    #  🔴 L'homonymie RÉELLE, celle qui a fait échouer ma première version :
    #  `TYPE_LIEN_LABEL` est une table de `TypeLien`, dont DEUX valeurs portent
    #  le même mot qu'un statut. Un seuil de deux ne la distinguait pas — c'est
    #  l'exclusion par NOM DE CLÉ qui la sauve.
    homonymie = (
        "const TYPE_LIEN_LABEL: Record<string, string> = {\n"
        "\tpropriétaire: 'Propriétaire',\n"
        "\tbailleur: 'Bailleur',\n"
        "\tlocataire: 'Locataire',\n"
        "\tmandataire: 'Mandataire',\n"
        "};\n"
    )

    assert len(tables_par_cle(canonique, cles, VALEUR_CHAINE)) == 1
    assert len(tables_par_cle(paraphrase, cles, VALEUR_CHAINE)) == 1, (
        "une copie qui RACCOURCIT le texte doit rester visible : c'est "
        "précisément ce qui a échappé aux deux contrôles existants."
    )
    assert len(tables_par_cle(homonymie, cles, VALEUR_CHAINE)) == 0, (
        "une table de `TypeLien` n'est pas une table de statuts — les deux mots "
        "communs ne doivent pas suffire à la condamner."
    )


#  ══════════════════════════════════════════════════════════════════════════
#  LES DEUX BALAYAGES — une table chacun, tous les écarts nommés d'un coup
#  ══════════════════════════════════════════════════════════════════════════

#: Chaque colonne de `roles.ts` couvre tous les états de sa colonne de
#: référence : (table, colonne de référence, colonne, minimum d'entrées).
#:
#: - une **teinte** manquante s'affiche en gris — ce qui se lit comme une
#:   décision, alors que c'est un oubli : c'est exactement ce qui était arrivé à
#:   `/profil`, deux rôles absents de sa copie, rendus gris par le repli (#819) ;
#: - un **abrégé** manquant n'est pas rendu vide — il s'imprime en brut
#:   (`admin_technique`) : le défaut exact de #828.
#:
#: Le minimum est le cas zéro de chaque ligne : un extracteur qui ne trouve plus
#: rien conclurait au vert sur zéro comparaison (`standards/04` §2).
COLONNES = (
    ("ROLE", "libelle", "badge", 5),
    ("STATUT", "libelle", "badge", 7),
    ("STATUT", "libelle", "abrege", 7),
)


def test_chaque_colonne_de_roles_ts_couvre_tous_les_etats():
    ts = ROLES_TS.read_text(encoding="utf-8")
    ecarts = []
    for ancre, reference, colonne, minimum in COLONNES:
        attendus = table_ts(ts, ancre, reference)
        trouves = table_ts(ts, ancre, colonne)
        if len(attendus) < minimum or len(trouves) < minimum:
            ecarts.append(
                f"  {ancre}.{colonne} : extraction cassée ({len(attendus)} « {reference} », "
                f"{len(trouves)} « {colonne} », {minimum} attendus au moins)"
            )
        elif set(trouves) != set(attendus):
            ecarts.append(
                f"  {ancre}.{colonne} ne couvre pas les mêmes états que {ancre}.{reference} : "
                f"{sorted(set(attendus) ^ set(trouves))}"
            )
    assert not ecarts, (
        "Une colonne de `roles.ts` ne couvre pas tous les états — une teinte "
        "manquante rend un badge gris, un abrégé manquant s'imprime en brut :\n" + "\n".join(ecarts)
    )


def _cles_roles_et_statuts(ts: str) -> set[str]:
    return set(table_ts(ts, "ROLE", "libelle")) | set(table_ts(ts, "STATUT", "libelle"))


def _cles_statuts_sans_type_lien(ts: str) -> set[str]:
    return set(table_ts(ts, "STATUT", "libelle")) - _CLES_PARTAGEES_AVEC_TYPE_LIEN


#: Les tables qu'aucun écran ne réécrit : (ce que la table porte, seul fichier
#: autorisé, clés cherchées, forme de la valeur, minimum de clés, remède).
#:
#: ⚠️ La portée fait partie du contrôle : il ne cherche pas « badge- » ni une
#: chaîne en général — employées partout, légitimement —, mais une TABLE qui
#: associe plusieurs clés de rôle ou de statut à une valeur, c'est-à-dire la
#: forme exacte d'une copie. Une clé qui reçoit un badge dans un ternaire
#: (`x === 'actif' ? 'badge-green' : …`) n'est pas visée : c'est une condition
#: sur une valeur, pas une table.
TABLES_INTERDITES = (
    (
        "teintes de rôle ou de statut",
        SOURCE_BADGES,
        _cles_roles_et_statuts,
        VALEUR_TEINTE,
        12,
        "`badgeRole()` / `badgeStatut()`",
    ),
    (
        "libellés de statut",
        SOURCE_LIBELLES,
        _cles_statuts_sans_type_lien,
        VALEUR_CHAINE,
        5,
        "`libelleStatut()` ou `LIBELLES_STATUT_ABREGE`",
    ),
)


def test_aucune_table_de_role_ou_statut_n_est_REECRITE_dans_un_ecran():
    """Le garde-fou contre la troisième table de badges (#819) et la quatrième
    table de libellés de statut (#828) — un seul balayage du front."""
    ts = ROLES_TS.read_text(encoding="utf-8")
    fautifs = []
    for nature, source_unique, cles_de, valeur, minimum, remede in TABLES_INTERDITES:
        cles = cles_de(ts)
        if len(cles) < minimum:
            fautifs.append(
                f"  {nature} : extraction des clés cassée ({len(cles)} < {minimum}) — "
                "le contrôle ne mesurerait rien"
            )
            continue
        for relatif, source in fichiers_du_front(sauf=source_unique):
            for ligne, entrees in tables_par_cle(source, cles, valeur):
                fautifs.append(
                    f"  {nature} — {relatif}:{ligne} — {len(entrees)} clés : "
                    f"{entrees[0]}… → employer {remede}"
                )

    assert not fautifs, (
        "Une table indexée par des rôles ou des statuts est réécrite hors de "
        "`#lib/roles.ts` :\n" + "\n".join(fautifs)
    )
