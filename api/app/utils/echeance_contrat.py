"""Quand un contrat arrive à échéance — UNE dérivation, pour tout le monde.

## Le défaut (relevé le 29/08/2026, signalé par l'utilisateur)

*« Pour l'échéance d'assurance, si celui-ci n'est pas stoppé, il est
automatiquement reconduit — ne faudrait-il pas supprimer l'année ? »*

La remarque désigne un défaut plus large que la question ne le laisse croire.
« Échéance » désignait **trois** valeurs différentes selon l'écran :

| Écran | Ce qu'il affichait | Ce que ça vaut |
|---|---|---|
| Fiche de la résidence, admin | `contrat.prochaine_visite` | une date de **visite**, posée à la main |
| Reporting → Renouvellements | `date_debut` + durée, **reportée** | la bonne, mais calculée dans le front |
| Tableau de bord → Prochaines échéances | `Copropriete.assurance_echeance` | la **colonne héritée**, hors circuit depuis #490 |

🔴 **Le champ affiché comme « échéance » sur la fiche s'appelle « Prochaine
visite » dans le formulaire.** C'est la bonne notion pour un contrat d'entretien
— une chaudière se visite — et la mauvaise pour une assurance ou un mandat de
syndic, qui n'ont pas de visite mais un terme. Une date de visite passée
s'affichait donc comme une échéance dépassée.

🔴 **Et le tableau de bord lisait une colonne que plus aucun écran n'alimente** :
`copropriete_lue` efface les colonnes `assurance_*` depuis #490, précisément
pour que la saisie libre ne réapparaisse pas derrière le contrat. La relance,
elle, continuait de lire la colonne — donc l'ancienne saisie, que personne ne
met plus à jour.

## La règle

L'échéance se **déduit**, elle ne se saisit pas :

    date de début + durée initiale, puis reportée d'un an tant qu'elle est passée

Le report est la **reconduction tacite** : un contrat qui n'a pas été dénoncé
court une année de plus. ⚠️ **Il ne vaut pas pour tous les contrats** — un mandat
de syndic est voté en AG pour un terme et ne se reconduit pas ; voir
`SANS_RECONDUCTION_TACITE`, corrigé le 29/08/2026 sur signalement. C'est ce qui répond à la remarque — l'année n'est pas
retirée, elle est **toujours juste**, et on dit quand le terme initial a été
dépassé. Un affichage sans année aurait perdu l'information utile : savoir si le
préavis tombe cette année ou la suivante.

⚠️ **Durée inconnue → reconduction annuelle.** C'est la convention déjà retenue
par le reporting depuis #453, conservée telle quelle : la majorité des contrats
de copropriété sont annuels, et rendre `None` ferait disparaître le contrat des
relances — un contrat sans échéance connue est justement celui qu'il faut
regarder.

⚠️ **Sans date de début, rien.** On ne devine pas un terme à partir de rien, et
un repli sur « aujourd'hui + 1 an » afficherait une échéance inventée. C'est le
cas zéro, et il rend `None`.
"""

from datetime import date
from app.utils import horloge
from typing import NamedTuple, Optional, Protocol
from app.utils.equipements import SYNDIC
from app.utils.valeurs import valeur


class _Contrat(Protocol):
    """Ce que la dérivation lit — trois champs, rien d'autre.

    Un protocole plutôt que `ContratEntretien` : les tests éprouvent la règle
    sans monter une base, et la fonction ne peut pas se mettre à dépendre d'un
    quatrième champ sans que la signature le dise.
    """

    date_debut: Optional[date]
    duree_initiale_valeur: Optional[int]
    duree_initiale_unite: Optional[str]
    type_equipement: object  # le code d'un équipement (`utils/equipements`)


#: 🔴 LES TYPES QUI NE SE RECONDUISENT PAS TACITEMENT.
#:
#: Corrigé le 29/08/2026, signalé par l'utilisateur : *« c'est l'assurance qui
#: est reconduite tacitement, pas le syndic »*. La première version reportait le
#: terme de TOUS les contrats, y compris le mandat de syndic — ce qui masquait
#: exactement le fait qu'il faut voir.
#:
#: Un mandat de syndic est **voté en assemblée générale pour une durée
#: déterminée** (trois ans au plus). Il ne se reconduit pas : à son terme, il
#: cesse, et la copropriété doit en voter un nouveau. Reporter sa date d'un an
#: affichait un mandat valide là où il était **échu** — et supprimait de la
#: fiche le seul signal qui appelait une AG.
#:
#: ⚠️ La liste est courte et le restera : la reconduction tacite est la règle
#: pour les contrats de la copropriété (assurance, entretien, ascenseur,
#: chaudière). C'est l'exception qui s'énumère, pas le cas général — l'inverse
#: obligerait à penser à chaque nouveau type, et c'est celui qu'on oublie.
SANS_RECONDUCTION_TACITE = frozenset({SYNDIC})


class Echeance(NamedTuple):
    """Le terme du contrat, et ce qu'il faut en comprendre.

    Les deux drapeaux s'excluent, et ce n'est pas un hasard : `reconduit` ne
    peut naître que d'un report, `echu` que de son absence.
    """

    date: date
    #: Le terme initial est passé et le contrat a couru une année de plus.
    reconduit: bool
    #: Le terme est passé et RIEN ne l'a prolongé — le mandat a cessé.
    echu: bool = False


def _ajouter_mois(depart: date, mois: int) -> date:
    """`depart` + `mois`, en ramenant le jour au dernier du mois s'il déborde.

    ⚠️ 31 janvier + 1 mois n'existe pas. Sans ce ramené, la dérivation lèverait
    `ValueError` sur un contrat commencé un 31 — un défaut qui ne se
    manifesterait que sur sept jours de l'année, donc jamais en essai.
    """
    total = (depart.year * 12 + depart.month - 1) + mois
    annee, mois_final = divmod(total, 12)
    dernier = [
        31,
        29 if (annee % 4 == 0 and annee % 100 != 0) or annee % 400 == 0 else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ][mois_final]
    return date(annee, mois_final + 1, min(depart.day, dernier))


def echeance_du_contrat(contrat: _Contrat, aujourdhui: Optional[date] = None) -> Optional[Echeance]:
    """Le terme du contrat, reporté d'un an tant qu'il est passé.

    `aujourdhui` est un paramètre pour que les tests n'aient pas à voyager dans
    le temps : un test qui dépend de la date du jour passe au vert ou au rouge
    selon le mois où on l'exécute, ce qui n'éprouve plus rien.

    @returns `None` si le contrat n'a pas de date de début.
    """
    if not contrat.date_debut:
        return None

    reference = aujourdhui or horloge.aujourd_hui()
    duree = contrat.duree_initiale_valeur
    unite = contrat.duree_initiale_unite
    type_ = valeur(contrat.type_equipement)
    tacite = type_ not in SANS_RECONDUCTION_TACITE

    if duree and unite == "ans":
        fin = _ajouter_mois(contrat.date_debut, 12 * duree)
    elif duree and unite == "mois":
        fin = _ajouter_mois(contrat.date_debut, duree)
    elif tacite:
        #  Durée inconnue → annuel. Voir l'avertissement du module.
        fin = _ajouter_mois(contrat.date_debut, 12)
    else:
        #  🔴 Durée inconnue ET pas de reconduction : on ne sait RIEN du terme.
        #
        #  Prendre l'annuel par défaut ferait déclarer « échu » un mandat de
        #  trois ans dès sa deuxième année — une fausse alerte, et sur le
        #  contrat le plus important de la copropriété. Le repli annuel n'est
        #  légitime que là où la date est un ANNIVERSAIRE qui revient ; ici elle
        #  serait une invention présentée comme un constat.
        return None

    if not tacite:
        #  Le terme ne bouge pas. Passé, il dit que le mandat a CESSÉ — c'est le
        #  signal que la copropriété doit voter, et le masquer serait le défaut.
        return Echeance(fin, reconduit=False, echu=fin <= reference)

    reconduit = False
    while fin <= reference:
        fin = _ajouter_mois(fin, 12)
        reconduit = True
    return Echeance(fin, reconduit)


def poser_echeance(lu, contrat):
    """Pose `date_fin` et `reconduit` sur un schéma lu, et le rend.

    Un helper plutôt qu'une boucle recopiée chez chaque appelant : c'est
    l'endroit où la dérivation rencontre le schéma, et il n'y a aucune raison
    qu'il existe en deux exemplaires. Il rend `lu` pour se poser en compréhension.
    """
    e = echeance_du_contrat(contrat)
    lu.date_fin, lu.reconduit, lu.echu = (
        (e.date, e.reconduit, e.echu) if e else (None, False, False)
    )
    return lu
