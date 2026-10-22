"""L'archivage automatique — **la règle, écrite une seule fois** (#515 point 2).

## Pourquoi ce module

Sept objets du site ont vocation à quitter d'eux-mêmes les listes actives au
bout d'un délai. Avant ce module, ils étaient traités par **trois codes qui ne
se connaissaient pas** :

  - `publications/commun.py::_is_archived` — actualités, deux seuils ;
  - `annonces.py::est_archivee` — petites annonces, un `ARCHIVAGE_JOURS = 30`
    **codé en dur**, invisible depuis l'écran d'administration ;
  - `calendrier/+page.svelte` — son propre calcul, côté navigateur.

Et quatre objets (ticket, idée, sondage, affiche de hall) n'en avaient aucun.

🔴 **Le défaut n'était pas la duplication, c'était l'inévitabilité de la
divergence.** Le jour où le délai du site change, l'administration en affiche un
et les petites annonces suivent le leur, sans que rien ne le signale. C'est le
motif exact du ticket : *« sept implémentations séparées divergeraient au
premier ajustement »*.

⚠️ **Le piège du 17/07/2026, à ne pas refaire** : la règle doit être tranchée au
**même endroit** pour toutes les vues. Le jour où le fil d'activité et l'écran
des actualités ont décidé séparément, un élément apparaissait dans l'une et pas
dans l'autre.

## Ce que ce module ne fait pas

Il ne **stocke** rien. L'archivage automatique est une **conséquence du temps**,
pas une étape que quelqu'un choisit — en faire un état donnerait deux notions
pour la même chose, celle qu'on pose et celle qui arrive, libres de se
contredire. C'est l'arbitrage déjà pris pour les annonces (`StatutAnnonce`) et
les actualités ; il vaut ici pour les sept.

Il ne supprime rien non plus — et rien ne supprime une affaire d'office : seul
l'administrateur le fait, depuis les Archives. La purge des actualités annulées
à 48 h (`PURGE_ANNULE_HEURES`) est partie avec le module Publications (#1177,
30/09/2026) ; sa constante, que plus rien ne lisait, a été retirée le 16/10/2026.

## Test : `api/tests/test_archivage.py`

Il ne se contente pas d'éprouver la décision : il **confronte les déclarations
ci-dessous aux modèles réels** — chaque champ déclaré doit exister, chaque
statut déclaré doit être une valeur possible. Sans cela un statut mal
orthographié ne lèverait rien : la règle serait simplement **fausse en silence**
pour cet objet, et vraie pour les six autres. Le risque n'est pas théorique —
les statuts de ticket sont les seuls accentués de tout le site (`résolu`,
`annulé`), et le ticket #515 le signalait comme le piège principal.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from app.utils import horloge
from typing import Any, Optional
from app.utils.nature_affaire import est_actualite
from app.utils.valeurs import valeur

#: Le délai unique, en jours. Arbitré à l'écran le 19/08/2026 : *« un seul
#: champ, mais valable pour tous les types d'écran… 30 j »*. Surchargeable en
#: configuration (`archivage_delai_jours`), et par ce seul réglage.
ARCHIVAGE_DELAI_JOURS = 30


@dataclass(frozen=True)
class RegleArchivage:
    """Comment un type d'objet quitte les listes actives.

    Une ligne par type, et rien d'autre à écrire : c'est la déclaration qui
    varie, jamais l'algorithme. Un huitième objet s'ajoute ici, pas ailleurs.
    """

    #: Les dates candidates, **dans l'ordre de repli**. La première renseignée
    #: fait foi. Un objet en état terminal sans aucune de ces dates n'est PAS
    #: archivé : on ne sait pas dater la décision, donc on ne décide pas.
    champs_date: tuple[str, ...]
    #: Le champ qui porte l'état, s'il y en a un.
    champ_statut: Optional[str] = None
    #: Ce que vaut l'état quand il est `None` en base. Une actualité vaut
    #: « publie » par défaut ; un `None` hérité doit se lire pareil.
    statut_defaut: Optional[str] = None
    #: Archivage **immédiat**, sans délai. « Annulé = immédiat quel que soit le
    #: type » — arbitré à l'écran le 19/08/2026.
    statuts_immediats: tuple[str, ...] = ()
    #: Les états qui déclenchent le compte à rebours. Vide = **le temps seul
    #: décide** (sondage clos, événement passé, affiche envoyée).
    statuts_terminaux: tuple[str, ...] = ()
    #: L'archivage à la main. Décision humaine : elle prime sur tout.
    champ_archive_manuel: Optional[str] = None
    #: La même décision, portée par un booléen INVERSE hérité : `actif` faux =
    #: archivé (#1538). Prestataires et contrats l'avaient avant ce module ; le
    #: déclarer ici évite une migration ET une seconde lecture de la règle.
    champ_actif: Optional[str] = None
    #: L'épinglage : « garder en vue ». Il interdit l'archivage automatique.
    champ_epingle: Optional[str] = None
    #: Un brouillon n'est pas encore publié — il n'a rien à quitter.
    champ_brouillon: Optional[str] = None
    #: Le déclencheur en une phrase, destinée au manuel utilisateur. L'écrire
    #: ici plutôt que dans un ticket évite qu'il ne soit plus lisible que dans
    #: une issue fermée.
    declencheur: str = ""
    #: 🔴 Les dates qui font PERIMER l'objet, dans l'ordre de repli (#1093).
    #:
    #: La peremption n'est pas l'archivage : elle ne compte aucun delai. Une
    #: information cesse d'etre utile a une date, un point c'est tout — « coupure
    #: d'eau jeudi » n'interesse personne vendredi, et surement pas trente jours
    #: plus tard.
    #:
    #: ⚠️ Vide pour six objets sur sept, et c'est une DECISION : une affaire ne
    #: perime jamais, elle se clot. Une fuite d'eau ne cesse pas d'exister parce
    #: que personne n'a ecrit depuis trois mois.
    champs_peremption: tuple[str, ...] = ()


#  ── LES SEPT DÉCLARATIONS ───────────────────────────────────────────────────
#
#  Les sept déclencheurs ont été tranchés à l'écran le 19/08/2026. Ils sont
#  écrits ici, et **seulement** ici.
REGLES: dict[str, RegleArchivage] = {
    "ticket": RegleArchivage(
        champ_statut="statut",
        #  🔴 ACCENTUÉS, et seuls de tout le site à l'être (`StatutTicket`).
        #  Une règle générale qui compare des chaînes doit le savoir, sinon
        #  elle est vraie pour six objets et fausse pour un — silencieusement.
        #  C'est le test qui le tient, pas ce commentaire.
        statuts_immediats=("annulé",),
        statuts_terminaux=("résolu",),
        champs_date=("ferme_le", "mis_a_jour_le", "cree_le"),
        #  📦 Le conseil archive une affaire d'un geste (24/09/2026) : c'est ce qui
        #  remplace, dans la liste, la corbeille de l'administrateur — supprimer
        #  n'est plus proposé qu'aux Archives (`ux-patterns` §8).
        champ_archive_manuel="archive_manuel",
        declencheur=(
            "30 jours après le passage en « Résolu ». « Annulé » : immédiat. "
            "📦 Archivée par le conseil : immédiat."
        ),
    ),
    #  🔴 Une affaire de catégorie « Actualité » (#1091, 23/09/2026) : la règle
    #  de l'ancienne publication, sur les colonnes de l'affaire. Elle n'a pas de
    #  cycle — son seul état, `publie`, est terminal : trente jours après sa
    #  dernière modification, ou dès sa date d'événement passée. Choisie par
    #  `_regle_de`, jamais par l'appelant.
    "actualite": RegleArchivage(
        champ_statut="statut",
        statut_defaut="publie",
        statuts_terminaux=("publie",),
        champs_date=("mis_a_jour_le", "cree_le"),
        champ_archive_manuel="archive_manuel",
        champ_epingle="epingle",
        declencheur=(
            "30 jours après la publication. Une date d'événement la fait sortir dès le lendemain."
        ),
        #  🔴 `fin` d'abord, `debut` en repli : un événement qui dure reste
        #  utile jusqu'à sa fin, et un événement ponctuel n'a que son début.
        #
        #  ⚠️ Il y avait un troisième champ en tête, `visible_jusqu_au`, saisi par
        #  l'auteur — retiré le 22/09/2026, le jour de sa livraison : *« cette date
        #  est à enlever, elle est calculée par l'appli »* (migration 0205). La
        #  règle « publication » qui le portait est partie le 23/09/2026 avec
        #  l'entité : une actualité est une affaire (#1091).
        champs_peremption=("fin", "debut"),
    ),
    #  🔁 Une actualité dont le conseil a activé le SUIVI (10/10/2026) : arbitré
    #  « comme une affaire » — « Annulé » archive aussitôt, « Résolu » trente
    #  jours après sa clôture (`ferme_le`). « Ouvert » garde la règle de
    #  l'actualité : `ferme_le` y est vide, la date de repli est donc la même.
    #  L'épinglage et la péremption sont ceux de l'actualité.
    "actualite_suivie": RegleArchivage(
        champ_statut="suivi_actualite",
        statuts_immediats=("annulé",),
        statuts_terminaux=("ouvert", "résolu"),
        champs_date=("ferme_le", "mis_a_jour_le", "cree_le"),
        champ_archive_manuel="archive_manuel",
        champ_epingle="epingle",
        declencheur=(
            "Suivi « Ouvert » : comme une actualité. « Résolu » : 30 jours après. "
            "« Annulé » : immédiat."
        ),
        champs_peremption=("fin", "debut"),
    ),
    "annonce": RegleArchivage(
        champ_statut="statut",
        statuts_immediats=("annule",),
        #  « reserve » n'est pas terminal : une réservation peut tomber, et
        #  l'annonce doit rester sous les yeux de son auteur.
        statuts_terminaux=("vendu", "donne"),
        #  ⚠️ `statut_change_le` et non `mis_a_jour_le` : corriger une faute de
        #  frappe sur une annonce vendue repousserait sinon son archivage d'un
        #  mois, à chaque retouche.
        champs_date=("statut_change_le", "mis_a_jour_le", "cree_le"),
        declencheur="30 jours après « Vendu » ou « Donné ». « Annulé » : immédiat.",
    ),
    "idee": RegleArchivage(
        champ_statut="statut",
        #  Aucun immédiat : « le dernier état, pour laisser le temps de voir
        #  aux gens » — y compris pour une idée rejetée, dont l'auteur doit
        #  pouvoir constater la décision.
        statuts_terminaux=("retenue", "realisee", "rejetee"),
        #  `statut_change_le` n'existait pas sur `Idee` : la migration 0155
        #  l'ajoute. Sans elle, le repli sur `cree_le` aurait archivé d'un coup
        #  toutes les idées anciennes, décidées ou non — et c'est le test de
        #  concordance des champs qui a rendu ce manque visible, pas une
        #  relecture.
        champs_date=("statut_change_le", "cree_le"),
        declencheur="30 jours après la décision (retenue, réalisée ou rejetée).",
    ),
    "sondage": RegleArchivage(
        #  Pas de statut : un sondage a une date de clôture, c'est tout.
        #  `cloture_le` peut être dans le FUTUR — le calcul le gère sans cas
        #  particulier, l'écart est alors négatif.
        champs_date=("cloture_le",),
        declencheur="30 jours après la date de clôture.",
    ),
    #  « evenement » est partie le 23/09/2026 (#1092) : les événements sont des
    #  affaires, archivées par la règle « ticket » ou « actualite ».
    "annonce_hall": RegleArchivage(
        #  Pas envoyée = pas de date = pas d'archivage. Une affiche préparée et
        #  jamais affichée reste en préparation.
        champs_date=("envoye_le",),
        champ_archive_manuel="archivee",
        declencheur="30 jours après l'envoi.",
    ),
    #  📦 L'annuaire et ses contrats (#1538, 02/10/2026) : aucun archivage par le
    #  temps — une entreprise ne périme pas, un contrat se clôt par décision.
    #  `champs_date` vide = pas de date de référence = jamais d'archivage seul.
    #  Le geste du conseil passe par `PATCH …/archivage`, qui écrit `actif`.
    "prestataire": RegleArchivage(
        champs_date=(),
        champ_actif="actif",
        declencheur="📦 Archivé par le conseil : immédiat. Aucun archivage automatique.",
    ),
    "contrat": RegleArchivage(
        champs_date=(),
        champ_actif="actif",
        declencheur="📦 Archivé par le conseil : immédiat. Aucun archivage automatique.",
    ),
}


def _statut_de(objet: Any, regle: RegleArchivage) -> Optional[str]:
    """L'état de l'objet, `statut_defaut` compris. Accepte un enum ou une str."""
    if not regle.champ_statut:
        return None
    brut = getattr(objet, regle.champ_statut, None)
    if brut is None:
        return regle.statut_defaut
    #  `StatutTicket.résolu` est une `str` Enum : comparer l'objet enum
    #  fonctionnerait aujourd'hui et casserait au premier enum ordinaire.
    return valeur(brut)


def _date_de_reference(objet: Any, regle: RegleArchivage) -> Optional[datetime]:
    """La première date renseignée parmi les candidates, ou `None`."""
    for champ in regle.champs_date:
        lue = getattr(objet, champ, None)
        if isinstance(lue, datetime):
            return lue
    return None


def _regle_de(type_objet: str, objet: Any) -> str:
    """Le type EFFECTIF : une affaire de catégorie « Actualité » suit sa règle.

    Le seul endroit où la catégorie choisit la règle — l'appelant dit « ticket »,
    et n'a pas à savoir qu'il en existe deux (#1091).
    """
    if type_objet == "ticket" and est_actualite(objet):
        if getattr(objet, "suivi_actualite", None):
            return "actualite_suivie"  # son suivi décide, comme une affaire
        return "actualite"
    return type_objet


def perime_le(objet: Any, type_objet: str = "ticket") -> Optional[date]:
    """La date a partir de laquelle cet objet n'est plus utile — ou `None` (#1093).

        perime_le =  fin de l'evenement      si date d'evenement
              sinon  jamais

    🔴 **Derivee a la lecture, JAMAIS recopiee a l'ecriture.** Calculer la
    peremption a la creation laisserait un report d'evenement (jeudi -> mardi)
    derriere lui : la date stockee dirait encore jeudi, et l'actualite sortirait
    du fil le jour ou elle redevient utile. C'est le motif « deux copies qui
    divergent sur le cas limite », deja paye trois fois dans ce depot.

    **Pure** : elle ne lit que l'objet, pas d'horloge, pas de session — c'est
    ce qui la rend eprouvable sans base de test.

    ⚠️ Elle rend une `date` et non un `datetime`, et ce n'est pas une
    commodite : « visible jusqu'au 22 » designe le JOUR entier. Comparer a
    `datetime(2026, 9, 22, 0, 0)` ferait disparaitre l'information le matin meme,
    alors que l'auteur a ecrit une fin de validite, pas une heure de disparition.
    """
    type_objet = _regle_de(type_objet, objet)
    regle = REGLES.get(type_objet)
    if regle is None:
        return None
    for champ in regle.champs_peremption:
        lue = getattr(objet, champ, None)
        if isinstance(lue, datetime):
            return lue.date()
        if isinstance(lue, date):
            return lue
    return None


def est_perime(
    objet: Any,
    type_objet: str = "ticket",
    maintenant: Optional[datetime] = None,
) -> bool:
    """Ce jour-la est-il PASSE ? Le soir du jour dit, jamais son matin.

    Le jour de PARIS (#1565) : `maintenant` est l'instant de la base, en UTC, et
    son `.date()` laissait au fil jusqu'a deux heures du matin ce qui avait fini
    la veille.
    """
    echeance = perime_le(objet, type_objet)
    if echeance is None:
        return False
    maintenant = maintenant or horloge.maintenant()
    return horloge.jour_civil(maintenant) > echeance


def est_archivable(
    type_objet: str,
    objet: Any,
    seuil_jours: int = ARCHIVAGE_DELAI_JOURS,
    maintenant: Optional[datetime] = None,
) -> bool:
    """Cet objet a-t-il quitté les listes actives pour les Archives ?

    **Pure** : aucune session, aucune base, aucune horloge imposée — c'est ce
    qui la rend éprouvable pour les sept types sans monter une base de test.

    L'ordre des règles n'est pas cosmétique, chacune peut annuler la suivante :

    1. **archivage manuel** — décision humaine, elle ne se discute pas ;
    2. **brouillon** — pas encore publié, rien à quitter ;
    3. **périmé** — sa date de validité est passée (#1093). Elle passe **avant**
       l'épinglage : « garder en vue » n'a plus de sens pour une information
       qui n'est plus valable ;
    4. **épinglé** — « garder en vue » ; s'auto-archiver contredirait le
       marqueur (décision du 01/08/2026, prise avec le bandeau « Épinglé ») ;
    5. **état d'annulation** — immédiat, sans délai ;
    6. **état terminal** (s'il y en a) — sinon l'objet reste actif ;
    7. **délai écoulé** depuis la date de référence.
    """
    type_objet = _regle_de(type_objet, objet)
    regle = REGLES.get(type_objet)
    if regle is None:
        #  Un type inconnu ne s'archive pas : la règle ne le connaît pas, elle
        #  n'a donc rien constaté. Répondre « vrai » ferait disparaître des
        #  objets sur une déclaration manquante — `standards/04` §1.
        return False

    if regle.champ_archive_manuel and getattr(objet, regle.champ_archive_manuel, False):
        return True
    #  ⚠️ Défaut `True` : un objet sans la colonne n'est pas réputé archivé.
    if regle.champ_actif and not getattr(objet, regle.champ_actif, True):
        return True
    if regle.champ_brouillon and getattr(objet, regle.champ_brouillon, False):
        return False
    #  🔴 LA PEREMPTION PASSE AVANT L'EPINGLAGE (#1093), et c'est la seule
    #  regle qui le fasse apres la decision humaine d'archiver.
    #
    #  « Garder en vue » n'a plus de sens pour une information qui n'est plus
    #  valable : sans cet ordre, une coupure d'eau epinglee resterait en tete
    #  du fil indefiniment. C'est le seul cas ou l'epinglage nuit a celui qui
    #  l'a pose — et le seul ou la peremption le revoque.
    if est_perime(objet, type_objet, maintenant):
        return True
    if regle.champ_epingle and getattr(objet, regle.champ_epingle, False):
        return False

    statut = _statut_de(objet, regle)
    if statut is not None and statut in regle.statuts_immediats:
        return True
    if regle.statuts_terminaux and statut not in regle.statuts_terminaux:
        return False

    reference = _date_de_reference(objet, regle)
    if reference is None:
        #  🔴 On ne sait pas dater l'événement déclencheur. On ne décide donc
        #  PAS d'archiver : l'objet reste visible, ce qui se voit et se
        #  corrige. L'inverse — le faire disparaître faute d'information —
        #  serait une absence affirmée sans avoir été constatée.
        return False

    maintenant = maintenant or horloge.maintenant()
    return (maintenant - reference) >= timedelta(days=seuil_jours)


def seuil_archivage_jours(session: Any) -> int:
    """Le délai du site, lu **une seule fois** et au même endroit.

    `archivage_delai_jours`, sinon le défaut. Le repli sur l'ancien
    `publie_visibilite_jours` est retiré (#2059) : la migration 0155 l'a remplacé
    partout, personne ne l'écrit, et la base de production n'en porte aucune ligne
    (relevé du 21/10/2026).
    """
    from app.models.core import ConfigSite  # import local : évite un cycle

    row = session.get(ConfigSite, "archivage_delai_jours")
    if row and str(row.valeur).isdigit():
        return int(row.valeur)
    return ARCHIVAGE_DELAI_JOURS
