"""L'échéance d'un contrat se déduit, elle ne se saisit pas.

Signalé par l'utilisateur le 29/08/2026 : *« pour l'échéance d'assurance, si
celui-ci n'est pas stoppé, il est automatiquement reconduit — ne faudrait-il pas
supprimer l'année ? »*

La réponse retenue conserve l'année et la rend TOUJOURS juste, par report d'un an
tant que le terme est passé. Le raisonnement complet — et les trois valeurs
différentes que « échéance » désignait selon l'écran — est dans le module
`app/utils/echeance_contrat.py`.

⚠️ Tous les cas fixent `aujourdhui` : un test qui dépend de la date d'exécution
passe au vert ou au rouge selon le mois, et n'éprouve alors plus rien
(`standards/04` §1 — un contrôle qui ne mesure pas ce qu'on croit).
"""

from datetime import date

import pytest

from app.utils.echeance_contrat import echeance_du_contrat

REFERENCE = date(2026, 8, 29)


class _Contrat:
    #  `assurance` par défaut : le cas de la reconduction tacite, qui est la
    #  règle. Les cas du mandat de syndic passent le type explicitement — le
    #  lecteur voit alors tout de suite ce qui distingue le test.
    def __init__(
        self, debut, valeur=None, unite=None, type_equipement="assurance", resilie_le=None
    ):
        self.resilie_le = resilie_le
        self.date_debut = debut
        self.duree_initiale_valeur = valeur
        self.duree_initiale_unite = unite
        self.type_equipement = type_equipement


def test_sans_date_de_debut_aucune_echeance():
    """Le cas zéro : on ne devine pas un terme à partir de rien.

    ⚠️ Un repli sur « aujourd'hui + 1 an » afficherait une échéance INVENTÉE,
    que le CS prendrait pour une donnée. Rendre `None` fait disparaître la ligne,
    ce qui est le comportement honnête.
    """
    assert echeance_du_contrat(_Contrat(None), REFERENCE) is None


def test_un_terme_a_venir_n_est_pas_reconduit():
    """Mandat de trois ans commencé en 2024 : terme en 2027, jamais atteint."""
    e = echeance_du_contrat(_Contrat(date(2024, 6, 1), 3, "ans"), REFERENCE)
    assert e.date == date(2027, 6, 1)
    assert e.reconduit is False, "un terme non atteint n'est pas une reconduction"


def test_un_terme_passe_se_reporte_et_le_dit():
    """🔴 LE CŒUR DE LA DEMANDE. Assurance de 2020 : le terme court toujours.

    Sans le report, la fiche affichait « échéance 17/12/2020 » — une date passée
    depuis six ans, qui se lit comme un contrat EXPIRÉ alors qu'il est
    tacitement reconduit chaque année.
    """
    e = echeance_du_contrat(_Contrat(date(2020, 12, 17)), REFERENCE)
    assert e.date == date(2026, 12, 17), "l'anniversaire est conservé, l'année suit"
    assert e.reconduit is True


def test_le_report_franchit_l_annee_quand_l_anniversaire_est_deja_passe():
    """Anniversaire en février, on est en août : le terme est en février PROCHAIN.

    ⚠️ Le cas que le précédent ne couvre pas : là, le report doit dépasser
    l'année courante. Un `while` mal borné rendrait février 2026, déjà passé.
    """
    e = echeance_du_contrat(_Contrat(date(2019, 2, 3)), REFERENCE)
    assert e.date == date(2027, 2, 3)


def test_le_terme_du_jour_meme_est_reporte():
    """Une échéance qui tombe aujourd'hui est déjà arrivée : elle se reporte.

    La borne est `<=` et non `<`, et c'est délibéré : afficher « échéance
    aujourd'hui » sur un contrat que personne n'a dénoncé le fait passer pour
    une urgence alors qu'il vient d'être reconduit.
    """
    e = echeance_du_contrat(_Contrat(date(2025, 8, 29)), REFERENCE)
    assert e.date == date(2027, 8, 29)
    assert e.reconduit is True


@pytest.mark.parametrize(
    "debut,valeur,unite,attendu",
    [
        (date(2026, 1, 31), 1, "mois", date(2027, 2, 28)),
        (date(2024, 1, 31), 1, "mois", date(2027, 2, 28)),
        (date(2023, 8, 31), 6, "mois", date(2027, 2, 28)),
    ],
)
def test_un_jour_qui_n_existe_pas_dans_le_mois_cible_est_ramene(debut, valeur, unite, attendu):
    """31 janvier + 1 mois n'existe pas — sans ramené, la dérivation LÈVE.

    ⚠️ Un défaut qui ne se manifesterait que sur les contrats commencés un 29,
    30 ou 31 : sept jours de l'année, donc jamais en essai, et une page blanche
    en production le jour où quelqu'un saisit la bonne date.
    """
    assert echeance_du_contrat(_Contrat(debut, valeur, unite), REFERENCE).date == attendu


def test_une_duree_inconnue_vaut_annuelle():
    """Convention conservée du reporting (#453), et elle est délibérée.

    Rendre `None` ferait DISPARAÎTRE des relances le contrat dont on ne connaît
    pas la durée — c'est-à-dire exactement celui qu'il faut regarder.
    """
    e = echeance_du_contrat(_Contrat(date(2026, 3, 15)), REFERENCE)
    assert e.date == date(2027, 3, 15)


#  Que l'assurance et le syndic reçoivent LE MÊME enrichissement d'échéance
#  (`_echeance_lue`) se vérifie avec le reste de l'invariant « même geste »,
#  dans `test_contrats_de_reference.py`.


# ── Ce qui NE se reconduit pas : le mandat de syndic (#628) ──────────────────
#
# 🔴 Signalé par l'utilisateur le 29/08/2026 : *« c'est l'assurance qui est
# reconduite tacitement, pas le syndic »*. La première version reportait le terme
# de TOUS les contrats — un mandat expiré s'affichait donc valide, et le seul
# signal qui appelle une assemblée générale disparaissait de la fiche.


def test_un_mandat_de_syndic_en_cours_affiche_son_terme_reel():
    """Mandat de trois ans voté en 2024 : terme en 2027, ni reconduit ni échu."""
    e = echeance_du_contrat(_Contrat(date(2024, 6, 1), 3, "ans", "syndic"), REFERENCE)
    assert e.date == date(2027, 6, 1)
    assert (e.reconduit, e.echu) == (False, False)


def test_un_mandat_de_syndic_expire_est_ECHU_et_ne_se_reporte_PAS():
    """🔴 LE CŒUR DE LA CORRECTION. Mandat 2021–2024 : il a cessé, il le dit.

    Avant, le report donnait 01/06/2027 avec `reconduit=True` — une date
    d'avenir sur un mandat mort depuis deux ans. C'est le contrat le plus
    important de la copropriété, et l'écran affirmait le contraire du vrai.
    """
    e = echeance_du_contrat(_Contrat(date(2021, 6, 1), 3, "ans", "syndic"), REFERENCE)
    assert e.date == date(2024, 6, 1), "le terme d'un mandat ne bouge pas"
    assert e.echu is True
    assert e.reconduit is False, "un mandat échu n'est pas un contrat reconduit"


def test_un_mandat_sans_duree_ne_rend_AUCUNE_echeance():
    """Le cas zéro du mandat : durée inconnue ⇒ terme inconnu, pas terme inventé.

    ⚠️ Le repli annuel serait ici une fausse alerte : il déclarerait « échu » un
    mandat de trois ans dès sa deuxième année. Ce repli n'est légitime que là où
    la date est un ANNIVERSAIRE qui revient — c'est-à-dire sous reconduction
    tacite, et nulle part ailleurs.
    """
    assert echeance_du_contrat(_Contrat(date(2022, 6, 17), None, None, "syndic"), REFERENCE) is None


def test_une_assurance_du_meme_age_est_reconduite_et_NON_echue():
    """Le témoin qui prouve que le test précédent mesure bien le TYPE.

    Même date de début, même durée : seul le type change. Sans ce couple, les
    trois tests ci-dessus passeraient aussi sur un code qui aurait simplement
    cessé de reporter TOUT LE MONDE.
    """
    syndic = echeance_du_contrat(_Contrat(date(2021, 6, 1), 3, "ans", "syndic"), REFERENCE)
    assurance = echeance_du_contrat(_Contrat(date(2021, 6, 1), 3, "ans", "assurance"), REFERENCE)
    assert (syndic.date, syndic.echu) == (date(2024, 6, 1), True)
    assert (assurance.date, assurance.reconduit, assurance.echu) == (date(2027, 6, 1), True, False)


def test_l_exception_est_ENUMEREE_et_le_cas_general_est_la_reconduction():
    """La liste des types sans reconduction reste courte — et non vide.

    ⚠️ Vidée, tous les contrats se reporteraient à nouveau et les trois tests
    ci-dessus tomberaient : celui-ci n'ajoute donc rien de ce côté. Il tient
    l'autre bord — qu'on n'y verse pas les types au fil de l'eau, ce qui
    reviendrait à faire de l'exception le cas général sans jamais le décider.
    """
    from app.utils.echeance_contrat import SANS_RECONDUCTION_TACITE

    assert SANS_RECONDUCTION_TACITE == {"syndic"}, (
        "la liste a changé : un type qui la rejoint doit d'abord dire POURQUOI "
        "il échappe à la reconduction tacite, qui est la règle."
    )
