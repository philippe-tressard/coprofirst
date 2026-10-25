"""Les USAGES de l'assistant IA — ce que le produit demande à un modèle, et où
chacun règle son modèle, son prompt et son plafond.

## Pourquoi ce registre (17/09/2026, #984)

L'assistant n'avait qu'un usage — la synthèse d'un contrat — et sa
configuration était donc globale : un modèle, un plafond, une consigne écrite
en dur. Le second usage (retravailler une description, #985) n'a ni le même
modèle idéal, ni le même plafond (une synthèse demande 10 000 jetons, une
réécriture bien moins), ni la même consigne — et Philippe veut relire et
adapter ces consignes depuis l'administration.

D'où deux étages, arbitrés le 17/09/2026 :

| Commun (`llm_*`) | Par usage (`llm_<usage>_*`) |
|---|---|
| activation globale, fournisseur, clé, adresse, version d'API, délai | activation, **modèle** (obligatoire — pas de modèle commun), **prompt**, plafond de jetons |

## 🔴 Ce registre est la SEULE liste des usages

L'écran d'administration la lit par `GET /config/llm-usages` et rend un bloc
par entrée : ajouter un usage, c'est ajouter une ligne ici — pas un écran.
Une liste recopiée côté front divergerait au premier usage ajouté, et c'est le
défaut que ce dépôt connaît le mieux.

## Ce que ce module ne fait pas

Il ne lit pas la base et ne passe aucun appel : il DÉCRIT. La lecture de la
configuration vit dans `llm.py` (`config_llm(session, usage)`), la matière de
chaque usage chez son appelant (`synthese_contrat.py`, `assistant_description.py`).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.description_format import CONSIGNE_DEFAUT as CONSIGNE_DESCRIPTION
from app.utils.question_reglement.format import CONSIGNE as CONSIGNE_QUESTION_REGLEMENT
from app.utils.question_reglement.format import USAGE_QUESTION_REGLEMENT
from app.utils.etat_descriptif_ia import CONSIGNE as CONSIGNE_ETAT_DESCRIPTIF
from app.utils.etat_descriptif_ia import USAGE_LECTURE_ETAT_DESCRIPTIF
from app.utils.fusion_en_cours_ia import CONSIGNE as CONSIGNE_FUSION_AFFAIRES
from app.utils.fusion_en_cours_ia import USAGE_FUSION_AFFAIRES
from app.utils.reponse_courriel import CONSIGNE as CONSIGNE_REPONSE_COURRIEL
from app.utils.reponse_courriel import USAGE_REPONSE_COURRIEL
from app.utils.suivi_affaires.format import CONSIGNE as CONSIGNE_AFFAIRES_EN_COURS
from app.utils.suivi_affaires.format import USAGE_SYNTHESE_AFFAIRES_EN_COURS
from app.utils.synthese_affaire.format import CONSIGNE as CONSIGNE_SYNTHESE_AFFAIRE
from app.utils.synthese_affaire.format import USAGE_SYNTHESE_AFFAIRE
from app.utils.synthese_format import CONSIGNE as CONSIGNE_SYNTHESE
from app.utils.tarif_modele import CONSIGNE as CONSIGNE_TARIF
from app.utils.tarif_modele import USAGE_TARIF_MODELE


@dataclass(frozen=True)
class Usage:
    """Un usage de l'assistant, et ses valeurs d'origine."""

    code: str
    libelle: str
    #: Ce que l'écran d'administration dit de l'usage — où il sert, à qui.
    description: str
    #: Le prompt D'ORIGINE. Il initialise la valeur en base (migration) et sert
    #: de repli si la clé est vide ; « Rétablir le prompt d'origine » y revient.
    prompt_defaut: str
    #: Le plafond d'origine, pour la même raison.
    max_jetons_defaut: int
    #: Le délai d'attente PLANCHER de cet usage, en secondes — 0 : le délai
    #: commun suffit. Un usage qui envoie un long document à un modèle qui
    #: raisonne dépasse les 45 s communes ; relever le délai de tous pour lui
    #: ferait attendre une minute de plus un geste qui en demande dix.
    delai_min_s: int = 0
    #: Un geste de PERSONNE peut-il l'appeler ? `False` pour un usage purement
    #: automatique : la limite par heure et par personne n'y a pas de sens, et
    #: l'écran ne la propose pas (`llm_limites`, 04/10/2026).
    geste_manuel: bool = True
    #: L'usage peut-il s'OUVRIR aux copropriétaires ? (11/10/2026) — l'écran
    #: propose alors la case « Ouvert aux copropriétaires » (`CHAMP_COPROPRIETAIRES`),
    #: décochée par défaut. Le conseil et l'administration gardent l'usage quoi
    #: qu'il en soit : la case ne sert qu'à le refermer en cas d'abus.
    ouvrable_aux_coproprietaires: bool = False

    def cle(self, champ: str) -> str:
        """La clé `ConfigSite` d'un réglage de cet usage."""
        return f"llm_{self.code}_{champ}"


#: Les réglages qu'un usage porte, dans l'ordre de l'écran.
#: `appels_mois` et `appels_heure` (par personne ; vide = aucune limite) sont
#: lus par `llm_limites` — ils ont remplacé, le 04/10/2026, un plafond en
#: jetons que personne ne savait estimer. Les trois PRIX sont lus par
#: `llm_journal` : le suivi de ce que coûte l'usage (#1383). Ils sont en
#: DOLLARS par million de jetons, en texte décimal — comme les grilles des
#: fournisseurs (30/09/2026) ; `prix_cache` est celui de l'entrée lue en cache.
#:
#: ⚠️ `llm_<usage>_reference` (le premier essai) n'est PAS ici : le serveur
#: seul l'écrit, et l'écran renvoie les clés de cette liste à l'enregistrement.
CHAMPS_USAGE = (
    "actif",
    "modele",
    "prompt",
    "max_jetons",
    "appels_mois",
    "appels_heure",
    "prix_entree",
    "prix_sortie",
    "prix_cache",
    "effort",
)

#: Le réglage des seuls usages `ouvrable_aux_coproprietaires` : `"1"` ouvre
#: l'usage aux copropriétaires. Absent des autres usages — l'écran ne montre la
#: case que si l'usage la porte dans ses clés (`decrire`).
CHAMP_COPROPRIETAIRES = "coproprietaires"


def champs(u: "Usage") -> tuple[str, ...]:
    """PURE. Les réglages que CET usage porte — ceux de tous, plus les siens."""
    return CHAMPS_USAGE + ((CHAMP_COPROPRIETAIRES,) if u.ouvrable_aux_coproprietaires else ())


#: 🔴 L'EFFORT DE RAISONNEMENT (30/09/2026, demandé : « gpt-5.6-luna +
#: reasoning.effort=low = choix par défaut ? faut-il le paramétrer ? »). Un
#: modèle qui raisonne pense avant d'écrire, et ces jetons se paient comme la
#: réponse. Chaque usage règle le sien : mettre en forme un courriel n'a pas
#: besoin de la réflexion qu'exige la synthèse d'un contrat.
#:
#: (code stocké, libellé, valeur envoyée) — la même valeur chez OpenAI, Azure
#: (`reasoning_effort`) et Anthropic (`output_config.effort`). Une clé VIDE
#: n'envoie rien : le modèle prend son propre défaut. Un modèle qui ne connaît
#: pas le réglage le refuse, et l'appel repart sans lui (`Fournisseur.adapter`).
#: C'est la SEULE liste : l'écran la reçoit par `decrire()`.
EFFORTS: tuple[tuple[str, str, str], ...] = (
    ("faible", "Faible", "low"),
    ("moyen", "Moyen", "medium"),
    ("eleve", "Élevé", "high"),
)


def valeur_effort(code: str | None) -> str:
    """PURE. La valeur d'API d'un effort stocké — vide s'il est vide ou inconnu :
    un réglage illisible laisse le modèle à son défaut, il n'empêche pas l'appel."""
    return next((api for c, _, api in EFFORTS if c == (code or "").strip()), "")


USAGE_SYNTHESE_CONTRAT = "synthese_contrat"
USAGE_DESCRIPTION = "description"

USAGES: dict[str, Usage] = {
    USAGE_SYNTHESE_CONTRAT: Usage(
        code=USAGE_SYNTHESE_CONTRAT,
        libelle="Synthèse de contrat",
        description=(
            "L'icône ✨ dans l'en-tête d'un contrat propose une synthèse au format "
            "du carnet d'entretien, à relire avant d'enregistrer."
        ),
        prompt_defaut=CONSIGNE_SYNTHESE,
        max_jetons_defaut=10_000,
    ),
    USAGE_DESCRIPTION: Usage(
        code=USAGE_DESCRIPTION,
        libelle="Rédaction d'une description",
        description=(
            "L'icône ✨ de la section Description — tickets, actualités, calendrier, "
            "sondages, idées, annonces, commentaires — retravaille le titre et le "
            "texte saisis. Réservé au conseil syndical et à l'administration."
        ),
        prompt_defaut=CONSIGNE_DESCRIPTION,
        max_jetons_defaut=4_000,
    ),
    #  Le seul usage AUTOMATIQUE (#1322, 25/09/2026) : aucun clic, il tourne à
    #  la relève des courriels. Coupé ou non réglé, le texte nettoyé sans IA
    #  entre dans le fil — `utils/reponse_courriel.mettre_en_forme`.
    USAGE_REPONSE_COURRIEL: Usage(
        code=USAGE_REPONSE_COURRIEL,
        libelle="Mise en forme des réponses par courriel",
        description=(
            "Automatique : quand le syndic répond par courriel à une affaire, sa "
            "réponse entre dans le fil débarrassée de la signature, des mentions "
            "légales et des lignes vides. Le texte reçu reste consultable sous "
            "« Message d'origine »."
        ),
        prompt_defaut=CONSIGNE_REPONSE_COURRIEL,
        max_jetons_defaut=2_000,
        geste_manuel=False,
    ),
    #  Un usage au service des AUTRES (30/09/2026) : son ✨ se tient à côté du
    #  modèle de chaque bloc, et remplit les deux prix de « Coût et limites ».
    USAGE_TARIF_MODELE: Usage(
        code=USAGE_TARIF_MODELE,
        libelle="Tarif d'un modèle",
        description=(
            "L'icône ✨ à côté du modèle de chaque usage lit la grille tarifaire "
            "publiée par le fournisseur, y fait trouver ce modèle par l'assistant et "
            "enregistre ses trois prix, en dollars comme la grille : jetons envoyés, "
            "produits et lus en cache. Seuls le fournisseur, le nom du modèle et la "
            "grille publique sont transmis."
        ),
        prompt_defaut=CONSIGNE_TARIF,
        #  La réponse fait cinq champs, mais un modèle qui raisonne dépense ses
        #  jetons avant d'écrire : 2 000 laisse la place au JSON après la
        #  réflexion (le piège du test de connexion à 16 jetons, `llm.tester`).
        #  La grille, elle, est en ENTRÉE : ce plafond ne la borne pas.
        max_jetons_defaut=2_000,
    ),
    #  Le second usage AUTOMATIQUE (#1643, 03/10/2026) : la tâche permanente
    #  le déclenche trente minutes après la clôture d'une affaire du carnet.
    #  Coupé, la Suite naît vide, en brouillon, et le conseil la rédige.
    #  L'effort d'origine (« moyen ») est posé par la migration 0255.
    USAGE_SYNTHESE_AFFAIRE: Usage(
        code=USAGE_SYNTHESE_AFFAIRE,
        libelle="Synthèse d'une affaire close",
        description=(
            "Automatique : trente minutes après la clôture d'une affaire du carnet "
            "d'entretien, l'assistant en rédige la synthèse — récit, difficultés, "
            "amélioration suggérée — à partir du fil et des métriques calculées. Le "
            "conseil syndical la relit, la relance ou la valide ; ni les messages "
            "internes ni les pièces jointes ne sont transmis."
        ),
        prompt_defaut=CONSIGNE_SYNTHESE_AFFAIRE,
        max_jetons_defaut=6_000,
    ),
    #  03/10/2026 : l'avis d'un juriste sur le règlement de copropriété. Tout le
    #  texte part à chaque question (≈ 60 000 jetons pour un recueil de trois
    #  actes), en tête de message pour être lu en cache. L'effort d'origine
    #  (« élevé ») est posé par la migration 0256 : c'est la précision qui est
    #  demandée, pas la vitesse.
    USAGE_QUESTION_REGLEMENT: Usage(
        code=USAGE_QUESTION_REGLEMENT,
        libelle="Question au règlement de copropriété",
        description=(
            "Ma résidence › Règlement : le conseil syndical — et les copropriétaires si "
            "la case ci-dessous est cochée — pose une question (« ai-je le droit de… ? ») ; "
            "l'assistant, en juriste, répond d'après le texte du règlement chargé sur "
            "cette page — verdict, réponse argumentée, extraits cités mot pour mot avec "
            "leur page, réserves. Le texte entier et la question sont transmis, jamais "
            "le nom de qui la pose. Délai d'attente d'au moins deux minutes."
        ),
        prompt_defaut=CONSIGNE_QUESTION_REGLEMENT,
        max_jetons_defaut=8_000,
        delai_min_s=120,
        ouvrable_aux_coproprietaires=True,
    ),
    #  16/10/2026 : le ✨ du rapport « Suivi des affaires » (Reporting CS). Né
    #  synthèse d'ensemble (#2034), il rédige depuis #2035 le RÉSUMÉ de chaque
    #  affaire en cours, à partir de toute sa matière — fil daté compris, par
    #  rôles, jamais un nom —, gardé sur l'affaire (`utils/suivi_affaires`). Le
    #  code garde son nom de naissance : les réglages sont déjà en base sous lui.
    USAGE_SYNTHESE_AFFAIRES_EN_COURS: Usage(
        code=USAGE_SYNTHESE_AFFAIRES_EN_COURS,
        libelle="Résumé des affaires en cours",
        description=(
            "Espace CS › Reporting › Suivi des affaires : « ✨ Résumer les affaires » "
            "rédige, pour chaque affaire ni résolue ni annulée, une ou deux phrases — où "
            "elle en est, ce qu'elle attend et de qui. Le résumé s'affiche sous son titre, "
            "part dans le PDF et dans le courriel de relance du syndic. Sont transmis le "
            "numéro, la catégorie, le périmètre, le titre, les dates, l'état, la "
            "description et le fil daté de chaque affaire, chaque personne désignée par "
            "son rôle ; jamais un nom, une pièce jointe ni un message interne au conseil. "
            "Réservé au conseil syndical et à l'administration."
        ),
        prompt_defaut=CONSIGNE_AFFAIRES_EN_COURS,
        #  #2035 : un résumé par affaire, et le fil de chacune en entrée.
        max_jetons_defaut=8_000,
        delai_min_s=120,
    ),
    #  20/10/2026 (#2083) : « Fusionner » des affaires liées au Suivi des
    #  affaires — l'assistant propose le titre et la description de l'affaire qui
    #  absorbe les autres ; le conseil relit avant de confirmer. Sans lui, une
    #  proposition est composée sans IA : la fusion n'en dépend pas.
    USAGE_FUSION_AFFAIRES: Usage(
        code=USAGE_FUSION_AFFAIRES,
        libelle="Fusion d'affaires liées",
        description=(
            "Espace CS › Reporting › Suivi des affaires : « Fusionner » des affaires liées "
            "fait proposer par l'assistant le nouveau titre et la nouvelle description de "
            "l'affaire qui absorbe les autres, à relire avant de confirmer. Sont transmis le "
            "numéro, la catégorie, le titre, les dates, l'état, la description, le fil daté "
            "et le nom des pièces jointes de chaque affaire, chaque personne désignée par son "
            "rôle ; jamais un nom, le contenu d'une pièce jointe ni un message interne au "
            "conseil. Réservé au conseil syndical et à l'administration."
        ),
        prompt_defaut=CONSIGNE_FUSION_AFFAIRES,
        max_jetons_defaut=4_000,
        delai_min_s=90,
    ),
    #  25/10/2026 (#2218) : du règlement versé au tableau de l'atelier de l'état
    #  descriptif — jamais une écriture dans le patrimoine (`utils/etat_descriptif_ia`).
    #  Une réponse de cent à deux cents lignes : un plafond de jetons et un délai
    #  à la mesure, l'appel tourne en tâche de fond.
    USAGE_LECTURE_ETAT_DESCRIPTIF: Usage(
        code=USAGE_LECTURE_ETAT_DESCRIPTIF,
        libelle="Lecture de l'état descriptif du règlement",
        description=(
            "Admin › Imports › État descriptif : « Remplir depuis le règlement » fait lire "
            "à l'assistant le règlement versé dans Ma résidence › Règlement, et poser dans "
            "l'atelier une ligne par lot — nature, bâtiment, porte ou place, niveau, "
            "circulation qui le dessert, tantièmes par clé, avec le passage d'où il les "
            "tient. Rien ne touche au patrimoine avant « Appliquer » : les contrôles de "
            "l'atelier jugent la lecture comme un fichier. Seul le texte du règlement est "
            "transmis. Réservé au conseil syndical et à l'administration ; l'appel dure "
            "plusieurs minutes."
        ),
        prompt_defaut=CONSIGNE_ETAT_DESCRIPTIF,
        max_jetons_defaut=32_000,
        delai_min_s=600,
    ),
}


def usage(code: str) -> Usage:
    """L'usage demandé — `KeyError` si personne ne l'a déclaré ici."""
    return USAGES[code]


def decrire() -> list[dict]:
    """Ce que l'écran d'administration reçoit : les usages, leurs clés et
    leurs valeurs d'origine. Les VALEURS courantes, elles, viennent de
    `GET /config/admin` comme toute autre clé."""
    return [
        {
            "code": u.code,
            "libelle": u.libelle,
            "description": u.description,
            "prompt_defaut": u.prompt_defaut,
            "max_jetons_defaut": u.max_jetons_defaut,
            "geste_manuel": u.geste_manuel,
            "cles": {champ: u.cle(champ) for champ in champs(u)},
            "efforts": [{"val": c, "label": libelle} for c, libelle, _ in EFFORTS],
        }
        for u in USAGES.values()
    ]


__all__ = [
    "CHAMPS_USAGE",
    "CHAMP_COPROPRIETAIRES",
    "EFFORTS",
    "USAGES",
    "USAGE_DESCRIPTION",
    "USAGE_QUESTION_REGLEMENT",
    "USAGE_SYNTHESE_AFFAIRE",
    "USAGE_SYNTHESE_CONTRAT",
    "USAGE_TARIF_MODELE",
    "Usage",
    "champs",
    "decrire",
    "usage",
    "valeur_effort",
]
