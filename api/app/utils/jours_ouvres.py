"""Les **jours ouvrés** — combien de temps une affaire a réellement attendu (#1643).

## Pourquoi ce module

La synthèse d'une affaire close mesure des délais : durée totale, temps par
étape du kanban, première réponse du syndic, réaction après une relance. Les
compter en jours calendaires ferait dire qu'un syndic a mis « trois jours » à
répondre à un message envoyé le vendredi soir et traité le lundi matin. Le
délai qu'on lui oppose en assemblée générale est celui de ses heures de bureau.

Il n'existait **aucun** calendrier de jours fériés dans le dépôt : il naît ici,
et c'est la seule écriture de la notion.

## La règle, arbitrée le 03/10/2026

- une journée ouvrée va de **9 h à 17 h** (huit heures) ;
- ni le samedi, ni le dimanche, ni un **jour férié français métropolitain** ;
- les fériés sont **calculés**, jamais saisis : les huit dates fixes, et les
  trois que Pâques déplace (lundi de Pâques, Ascension, lundi de Pentecôte).
  Pas d'Alsace-Moselle (Vendredi saint, 26 décembre) : la résidence n'y est pas ;
- l'affichage est au **demi-jour** (« 22,5 j ») : une précision plus fine
  laisserait croire à une mesure que les horodatages ne portent pas.

## Ce que ce module ne fait pas

Il ne lit ni la base, ni l'horloge : il reçoit des heures **murales de Paris**
(naïves). La conversion depuis l'UTC de la base est celle de
`horloge.a_paris`, faite par l'appelant — un module pur se teste sans fuseau.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

#: Le début et la fin d'une journée ouvrée.
DEBUT_JOURNEE = time(9, 0)
FIN_JOURNEE = time(17, 0)
HEURES_PAR_JOUR = 8


def paques(annee: int) -> date:
    """Le dimanche de Pâques (calendrier grégorien) — algorithme de Meeus-Jones-Butcher."""
    a = annee % 19
    b, c = divmod(annee, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    mois, jour = divmod(h + ell - 7 * m + 114, 31)
    return date(annee, mois, jour + 1)


def jours_feries(annee: int) -> frozenset[date]:
    """Les onze jours fériés de la France métropolitaine (hors Alsace-Moselle)."""
    p = paques(annee)
    return frozenset(
        {
            date(annee, 1, 1),  # Jour de l'an
            p + timedelta(days=1),  # Lundi de Pâques
            date(annee, 5, 1),  # Fête du travail
            date(annee, 5, 8),  # Victoire 1945
            p + timedelta(days=39),  # Ascension
            p + timedelta(days=50),  # Lundi de Pentecôte
            date(annee, 7, 14),  # Fête nationale
            date(annee, 8, 15),  # Assomption
            date(annee, 11, 1),  # Toussaint
            date(annee, 11, 11),  # Armistice
            date(annee, 12, 25),  # Noël
        }
    )


def est_ouvre(jour: date) -> bool:
    """Un jour de semaine qui n'est pas férié."""
    return jour.weekday() < 5 and jour not in jours_feries(jour.year)


def heures_ouvrees(debut: datetime, fin: datetime) -> float:
    """Les heures ouvrées entre deux instants muraux de Paris (naïfs).

    Une fin antérieure au début rend 0 : un fil mal daté ne doit pas produire
    une durée négative, que l'écran dessinerait comme une barre inversée.
    """
    if fin <= debut:
        return 0.0
    total = 0.0
    jour = debut.date()
    while jour <= fin.date():
        if est_ouvre(jour):
            ouverture = datetime.combine(jour, DEBUT_JOURNEE)
            fermeture = datetime.combine(jour, FIN_JOURNEE)
            a, b = max(debut, ouverture), min(fin, fermeture)
            if b > a:
                total += (b - a).total_seconds() / 3600
        jour += timedelta(days=1)
    return total


def jours_ouvres(debut: datetime, fin: datetime) -> float:
    """Les jours ouvrés entre deux instants muraux, **au demi-jour** près."""
    return au_demi_jour(heures_ouvrees(debut, fin) / HEURES_PAR_JOUR)


def au_demi_jour(jours: float) -> float:
    """Arrondi au demi-jour le plus proche : 2,26 → 2,5 ; 2,24 → 2,0."""
    return round(jours * 2) / 2


def libelle_jours(jours: float | None) -> str:
    """« 22,5 j », « 3 j », « — » — la forme lue par l'assistant et dans les courriels.

    L'écran a la sienne (`#lib/synthese`), les contextes de build l'imposent ;
    elles disent la même chose, et `test_jours_ouvres.py` fixe celle-ci.
    """
    if jours is None:
        return "—"
    texte = f"{jours:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{texte} j"


__all__ = [
    "au_demi_jour",
    "est_ouvre",
    "heures_ouvrees",
    "jours_feries",
    "jours_ouvres",
    "libelle_jours",
    "paques",
]
