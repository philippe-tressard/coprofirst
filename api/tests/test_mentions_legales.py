"""Les mentions légales identifient quelqu'un — et le gabarit ne peut pas revenir.

## 🔴 Le défaut, et pourquoi il n'avait aucun symptôme (03/09/2026)

`/mentions-legales` est une page **publique** : lisible sans compte, indexable.
Elle servait le gabarit générique du produit, qui disait en toutes lettres :

> « L'identité de l'éditeur correspond à la copropriété ou au syndic bénévole qui
>   gère cette instance. »

Ce n'est pas une mention, c'est une **instruction pour en rédiger une**. Elle
décrit ce qu'il faudrait écrire au lieu de l'écrire. Aucun lecteur ne pouvait
identifier l'éditeur, le directeur de la publication ni l'hébergeur — les trois
que la LCEN impose de pouvoir identifier.

Et rien ne le signalait : la page s'affiche, elle a l'air complète, personne ne
la lit jusqu'à ce que quelqu'un ait une raison de chercher qui contacter. C'est
un lecteur qui l'a vu, pas un contrôle.

## Ce que ce fichier tient

1. **Le gabarit se déclare comme tel.** `DEFAULT_LEGAL` reste générique — le seed
   porte le PRODUIT, réutilisable sous licence MIT, et y écrire un nom d'éditeur
   l'imposerait à tout autre déploiement. Mais il doit dire « À RENSEIGNER »,
   jamais faire semblant.

2. **La politique de confidentialité du gabarit ne ment pas** sur les transferts
   hors UE, et ne nomme aucun responsable.

Les textes réellement publiés ont été posés en base par les migrations 0170,
0171 et 0173, appliquées en production : elles ne se rejouent plus, et ce fichier
ne les teste donc plus.

## Ce qu'il ne peut pas vérifier

Que la page servie en PRODUCTION porte ces mentions : la base n'est pas
accessible depuis les tests, et une migration peut avoir été suivie d'une
retouche en administration. Le relevé se fait à la main :

    curl -s https://5hostachy.fr/api/config/legal

Une limite nommée vaut mieux qu'une limite tue — sans ce paragraphe, un vert ici
se lirait « le site est conforme », ce qu'il ne dit pas.
"""

from __future__ import annotations

import re

from app.seed.contenus_legaux import DEFAULT_LEGAL
from app.utils.textes_legaux.champs import rendre
from app.utils.textes_legaux.identite import IdentiteLegale


def _sans_identite(cle: str) -> str:
    """Le gabarit tel qu'une copropriété qui n'a rien renseigné le publie (#2065) :
    ses champs se rendent « À RENSEIGNER »."""
    return rendre(DEFAULT_LEGAL[cle], IdentiteLegale())


def _texte_nu(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def test_le_gabarit_du_seed_se_declare_comme_gabarit():
    """Il a le droit d'être vide, pas celui de faire semblant.

    Les trois rubriques que la LCEN impose doivent porter la marque, sans quoi la
    page publique paraîtrait complète en n'identifiant personne.
    """
    texte = _texte_nu(_sans_identite("mentions_legales"))
    assert texte.count("À RENSEIGNER") >= 3, (
        "le gabarit ne se signale pas sur les trois rubriques obligatoires "
        "(éditeur, directeur de la publication, hébergeur) :\n" + texte[:400]
    )


def test_le_gabarit_ne_pretend_plus_identifier_quelqu_un():
    """La formulation d'origine, mot pour mot, ne doit pas revenir."""
    texte = DEFAULT_LEGAL["mentions_legales"]
    for tournure in (
        "correspond à la copropriété ou au syndic bénévole",
        "l'organisation ou la personne physique",
        "l'administrateur désigné de l'instance",
    ):
        assert tournure not in texte, (
            f"le gabarit décrit à nouveau ce qu'il faudrait écrire : « {tournure} »"
        )


# ── La politique de confidentialité ──────────────────────────────────────────


def test_le_seed_n_affirme_plus_qu_aucune_donnee_ne_sort_de_l_UE():
    """🔴 L'affirmation était FAUSSE, et deux pages du site se contredisaient.

    Les mentions légales déclarent Cloudflare, Inc. (États-Unis) comme
    intermédiaire technique. La politique disait « Aucun transfert hors UE ». Le
    fait n'avait pas changé — seulement le moment où on l'a écrit quelque part.

    ⚠️ Le texte DÉCRIT le relais, il ne le QUALIFIE pas : savoir si cela
    constitue un transfert au sens du chapitre V est une question de droit, et
    `standards/14` interdit de l'improviser.
    """
    assert "Aucun transfert hors UE" not in DEFAULT_LEGAL["politique_confidentialite"]


def test_la_politique_du_seed_reste_un_gabarit_declare():
    """Le seed porte le PRODUIT : il ne nomme aucun responsable, et le dit."""
    politique = _sans_identite("politique_confidentialite")
    assert politique.count("À RENSEIGNER") >= 3, (
        "le gabarit de la politique ne se signale pas sur le responsable du "
        "traitement, l'hébergement et l'acheminement"
    )
    assert "Philippe Tressard" not in politique, (
        "le seed nomme un éditeur : tout autre déploiement publierait des "
        "mentions FAUSSES — le seed porte le produit, la base porte l'instance"
    )
