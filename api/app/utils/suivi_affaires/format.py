"""Ce que l'assistant reçoit pour la synthèse des affaires en cours, et la forme
de ce qu'il rend (16/10/2026).

| Partie | Qui l'écrit |
|---|---|
| `CONSIGNE` | l'administration (prompt de l'usage — Admin › Assistant IA) |
| `FORMAT_REPONSE` | **le code** : `lire_reponse` sait relire cette forme et aucune autre |
| le message | **le code** (`construire_message`) : dates, anciennetés et nombres sont CALCULÉS |

🔴 La réponse est du TEXTE, jamais du HTML : un résumé et une liste de points.
L'écran l'affiche tel quel, le PDF l'échappe — aucun `{@html}`, aucun balisage
venu d'un modèle ne traverse le rapport.

🔴 Ce module n'importe ni `llm` ni la base : `llm_usages` le lit pour son prompt
d'origine, et `llm` lit `llm_usages` — le moindre import en retour formerait un
cycle.
"""

from __future__ import annotations

from app.utils.description_format import ReponseIllisible, lire_objet

#: Le code de l'usage — lu par `llm_usages`.
USAGE_SYNTHESE_AFFAIRES_EN_COURS = "synthese_affaires_en_cours"

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu rédiges, pour le conseil syndical d'une copropriété, la synthèse des affaires "
    "encore ouvertes (ni résolues ni annulées). Elle accompagne la liste détaillée du "
    "rapport « Suivi des affaires », qui peut être transmis au syndic ou présenté en "
    "assemblée générale.\n"
    "- Écris en français, au présent, sur un ton factuel et sobre, 200 mots au plus.\n"
    "- Un résumé de deux ou trois phrases, puis trois à six points : ce qui presse "
    "(pannes, sinistres, ce qui touche la sécurité ou beaucoup de résidents), ce qui "
    "attend une décision (assemblée générale, devis), ce qui traîne et mérite une "
    "relance, les affaires qui semblent liées et gagneraient à être traitées ensemble.\n"
    "- Les dates, anciennetés et nombres te sont DONNÉS : reprends-les tels quels, "
    "n'en calcule et n'en invente aucun.\n"
    "- Ne cite aucun nom de personne, aucune adresse, aucun numéro de téléphone ; "
    "désigne les personnes par leur rôle (le syndic, le conseil syndical, un résident, "
    "le prestataire)."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour, à deux clés :\n"
    '{"resume": "<deux ou trois phrases, texte sans balise>", '
    '"points": ["<un point, texte sans balise>", "..."]}'
)

#: Ce qui part au modèle : au-delà, le message coûterait sans rien apprendre de plus.
MAX_AFFAIRES = 150
MAX_CARACTERES_DESCRIPTIF = 600
#: Ce qui revient : une synthèse d'un paragraphe et de quelques points.
MAX_CARACTERES_RESUME = 2_000
MAX_POINTS = 8
MAX_CARACTERES_POINT = 600


def construire_message(jour: str, affaires: list[dict]) -> str:
    """PURE. Le message envoyé : la date, le compte, puis une ligne par affaire.

    Chaque affaire est un dict à clés `libelle_categorie`, `titre`, `ouverte_le`
    (déjà formatée), `age_jours`, `libelle_statut`, `descriptif` — jamais un nom.
    """
    lignes = [
        f"Date du rapport : {jour}.",
        f"Affaires ouvertes : {len(affaires)}.",
    ]
    if len(affaires) > MAX_AFFAIRES:
        lignes.append(f"Seules les {MAX_AFFAIRES} plus anciennes sont détaillées ci-dessous.")
    lignes.append("")
    for a in affaires[:MAX_AFFAIRES]:
        lignes.append(
            f"- [{a['libelle_categorie']}] « {a['titre']} » — ouverte le {a['ouverte_le']} "
            f"({a['age_jours']} jours), état : {a['libelle_statut']}."
        )
        descriptif = (a.get("descriptif") or "").strip()
        if descriptif:
            lignes.append(f"  Descriptif : {descriptif[:MAX_CARACTERES_DESCRIPTIF]}")
    return "\n".join(lignes)


def lire_reponse(texte: str) -> dict:
    """Le résumé et les points, relus dans ce que le modèle a rendu — bornés."""
    charge = lire_objet(texte)
    resume = charge.get("resume")
    points = charge.get("points")
    if not isinstance(resume, str) or not resume.strip():
        raise ReponseIllisible("Réponse du modèle sans résumé.")
    if not isinstance(points, list):
        points = []
    return {
        "resume": resume.strip()[:MAX_CARACTERES_RESUME],
        "points": [
            p.strip()[:MAX_CARACTERES_POINT] for p in points if isinstance(p, str) and p.strip()
        ][:MAX_POINTS],
    }
