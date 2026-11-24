"""Chercher le TARIF du modèle d'un usage et l'enregistrer — l'usage `tarif_modele`
(30/09/2026).

## Demandé le 30/09/2026, en trois temps

> « créer un nouveau use case IA pour demander la tarification de l'IA
>   concernée. Ajouter l'icône IA à côté du modèle de tous les use case IA.
>   L'IA questionne et remplit ces 2 valeurs »
>
> « l'appel à l'IA de ce use case recherche le prix sur l'opérateur concerné du
>   modèle du use case concerné, remplit les prix et enregistre »
>
> « en interrogeant OpenAI, il y a 3 paramètres de coût et non 2 » — et les
>   prix en dollars, comme les grilles.

Les trois valeurs sont les prix de la section « Coût et limites » d'un usage —
jetons envoyés, jetons produits, jetons d'entrée lus en cache — en DOLLARS par
million de jetons, que lit `llm_journal` pour chiffrer la consommation (#1383).

## Qui fait quoi

| Étape | Qui | Pourquoi pas l'autre |
|---|---|---|
| lire la grille du fournisseur | le serveur (`tarif_sources`) | une adresse fixe, pas une recherche au hasard |
| trouver la ligne du modèle | l'assistant | « claude-haiku-4-5-20251001 » s'écrit « Claude Haiku 4.5 » dans la grille |
| enregistrer | le serveur | demandé : le geste finit le travail |

Rien à convertir : la grille est en dollars, les prix aussi.

## 🔴 Le modèle cherché est celui ENREGISTRÉ pour l'usage

C'est son prix qu'on enregistre. Si l'écran montre un autre modèle, pas encore
enregistré, on refuse plutôt que de poser sur l'un le prix de l'autre.

## Ce qui part

Vers le fournisseur de l'assistant : son nom, l'identifiant du modèle et la
grille publique. **Aucune donnée d'un résident, d'un contrat ou d'une affaire.**
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlmodel import Session

from app.utils.description_format import FORMAT_INATTENDU, ReponseIllisible, lire_objet

logger = logging.getLogger("hostachy.assistant")

USAGE_TARIF_MODELE = "tarif_modele"

#: Les trois prix, dans l'ordre de l'écran — les clés de `llm_usages.CHAMPS_USAGE`.
CHAMPS_PRIX = ("prix_entree", "prix_sortie", "prix_cache")

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu lis la grille tarifaire publique d'un fournisseur de modèles d'IA et tu "
    "y trouves le prix d'UN modèle, désigné par son identifiant d'API.\n"
    "- L'identifiant peut porter une date ou un suffixe que la grille n'écrit "
    "pas (« claude-haiku-4-5-20251001 » est « Claude Haiku 4.5 ») : retiens la "
    "ligne du même modèle, jamais celle d'un modèle voisin.\n"
    "- Retiens le tarif standard d'un appel par API : ni traitement par lots, "
    "ni priorité, ni contexte long s'il existe un palier ordinaire.\n"
    "- Donne trois prix par million de jetons, en dollars : les jetons envoyés "
    "(entrée), les jetons produits (sortie, raisonnement compris), et les jetons "
    "d'entrée lus en cache (« cached input » chez OpenAI, « cache hits » ou "
    "« cache reads » chez Anthropic — jamais l'écriture en cache).\n"
    "- Sur Azure, l'identifiant est un nom de déploiement : retiens le modèle "
    "qu'il désigne si son nom le laisse reconnaître.\n"
    "- Un prix que la grille ne donne pas pour ce modèle vaut null ; si elle ne "
    "porte pas ce modèle, les trois valent null. Ne devine jamais."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour :\n"
    '{"ligne": "<le nom du modèle tel que la grille l\'écrit, ou null>", '
    '"devise": "USD", '
    '"prix_entree": <nombre ou null>, "prix_sortie": <nombre ou null>, '
    '"prix_cache": <nombre ou null>}\n'
    "Les prix sont en dollars par million de jetons, en nombre décimal avec un point."
)

#: Au-delà, ce n'est plus un tarif mais une erreur d'unité (un prix par millier
#: pris pour un prix par million) : le modèle le plus cher reste très en deçà.
MAX_PAR_MILLION = Decimal(1_000)
MAX_CARACTERES_LIGNE = 120


@dataclass(frozen=True)
class Tarif:
    """Ce que l'assistant a lu dans la grille — et donc ce qui est ENREGISTRÉ :
    des dollars par million de jetons, en texte décimal (l'unité des champs) ;
    `None` pour un prix que la grille ne donne pas, et qui n'est pas touché."""

    ligne: str
    prix_entree: Optional[str]
    prix_sortie: Optional[str]
    prix_cache: Optional[str]

    def prix(self) -> dict[str, Optional[str]]:
        return {c: getattr(self, c) for c in CHAMPS_PRIX}


def construire_message(fournisseur: str, modele: str, grille: str) -> str:
    return (
        f"Fournisseur : {fournisseur}\nIdentifiant du modèle : {modele}\n\n"
        f"Grille tarifaire publiée par le fournisseur :\n\n{grille}"
    )


def _prix(valeur: object, champ: str) -> Optional[str]:
    """Un prix du JSON, rendu en texte décimal — lu par `str`, jamais par un
    flottant : 0.075 reste « 0.075 »."""
    if valeur is None:
        return None
    #  `True` est un `int` pour Python : un booléen n'est pas un prix.
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise ReponseIllisible(f"« {champ} » n'est pas un nombre.")
    prix = Decimal(str(valeur))
    if not 0 <= prix <= MAX_PAR_MILLION:
        raise ReponseIllisible(f"« {champ} » hors bornes : {valeur}.")
    return format(prix.normalize(), "f")


def lire_tarif(texte: str) -> Tarif:
    """PURE. La ligne retenue par l'assistant, relue et bornée.

    Trois `null` ne sont PAS illisibles : l'assistant dit que la grille ne porte
    pas ce modèle, et c'est à l'appelant de le dire. Une grille qui ne serait
    pas en dollars est refusée : rien ne convertit plus.
    """
    charge = lire_objet(texte)
    devise = str(charge.get("devise") or "USD").strip().upper()
    if devise != "USD":
        raise ReponseIllisible(f"Grille en « {devise} » : seuls les dollars sont pris en charge.")
    ligne = charge.get("ligne")
    return Tarif(
        ligne=(ligne.strip() if isinstance(ligne, str) else "")[:MAX_CARACTERES_LIGNE],
        **{c: _prix(charge.get(c), c) for c in CHAMPS_PRIX},
    )


def remarque(tarif: Tarif, url: str) -> str:
    """PURE. D'où vient le chiffre — écrite par le CODE, jamais par le modèle :
    c'est la phrase qui permet de vérifier ce qui a été enregistré."""
    libelles = {"prix_entree": "envoyés", "prix_sortie": "produits", "prix_cache": "en cache"}
    prix = ", ".join(
        f"{libelles[c]} {p.replace('.', ',')} $" for c, p in tarif.prix().items() if p is not None
    )
    source = url.removeprefix("https://").removesuffix(".md")
    return f"Grille {source}, ligne « {tarif.ligne or '?'} » : {prix} par million."


async def chercher_et_enregistrer(
    session: Session, usage: str, modele_affiche: str, *, demandeur: Optional[int]
) -> tuple[Tarif, str]:
    """Lit la grille du fournisseur, y fait trouver le modèle de `usage` et
    ENREGISTRE les prix trouvés. Rend le tarif et sa remarque. Lève `ErreurLLM`
    — jamais autre chose.
    """
    #  Import différé : `llm` lit `llm_usages`, qui lit la CONSIGNE ici — le
    #  geste de `reponse_courriel`.
    from app.models.core import ConfigSite
    from app.utils import tarif_sources
    from app.utils.llm import ErreurLLM, config_llm, demander
    from app.utils.llm_usages import USAGES

    if usage not in USAGES:
        raise ErreurLLM(f"Usage inconnu : « {usage} ».")
    cible = config_llm(session, usage)
    modele = cible.modele
    if not modele:
        raise ErreurLLM(
            "Enregistrez d'abord un modèle pour cet usage : c'est son tarif qui est cherché."
        )
    if (modele_affiche or "").strip() != modele:
        raise ErreurLLM(
            "Le modèle affiché n'est pas celui qui est enregistré : cliquez sur "
            "« Enregistrer », puis relancez ✨."
        )

    url = cible.fournisseur.page_tarifs
    try:
        grille = await tarif_sources.lire_grille(url)
    except tarif_sources.SourceIndisponible as exc:
        raise ErreurLLM(f"Grille de {cible.fournisseur.libelle} indisponible : {exc}") from exc

    cfg = config_llm(session, USAGE_TARIF_MODELE)
    reponse = await demander(
        session,
        usage=USAGE_TARIF_MODELE,
        consigne=cfg.prompt.rstrip() + "\n\n" + FORMAT_REPONSE,
        message=construire_message(cible.fournisseur.libelle, modele, grille),
        demandeur=demandeur,
    )
    try:
        tarif = lire_tarif(reponse.texte)
    except ReponseIllisible as exc:
        logger.warning("Assistant tarif : %s — %s", exc, reponse.texte[:300])
        raise ErreurLLM(FORMAT_INATTENDU) from exc
    if all(p is None for p in tarif.prix().values()):
        raise ErreurLLM(
            f"La grille de {cible.fournisseur.libelle} ne donne pas le tarif de « {modele} » : "
            "saisissez-le à la main."
        )

    #  🔴 L'enregistrement : seulement les prix TROUVÉS. Un prix absent de la
    #  grille laisse celui que l'administrateur avait saisi.
    u = USAGES[usage]
    for champ, valeur in tarif.prix().items():
        if valeur is None:
            continue
        cle = u.cle(champ)
        ligne = session.get(ConfigSite, cle) or ConfigSite(cle=cle, valeur="")
        ligne.valeur = valeur
        session.add(ligne)
    session.commit()
    return tarif, remarque(tarif, url)


__all__ = [
    "CHAMPS_PRIX",
    "CONSIGNE",
    "FORMAT_REPONSE",
    "Tarif",
    "USAGE_TARIF_MODELE",
    "chercher_et_enregistrer",
    "construire_message",
    "lire_tarif",
    "remarque",
]
