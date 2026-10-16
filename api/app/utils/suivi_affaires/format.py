"""Ce que l'assistant reçoit pour résumer les affaires en cours, et la forme de ce
qu'il rend (16/10/2026, refait par #2035).

## Un résumé par affaire, plus de synthèse d'ensemble

Le Suivi des affaires est né (#2034) avec une synthèse d'ENSEMBLE rédigée par
l'assistant. Philippe l'a retirée le jour même (#2035) : ce qui sert au conseil
— et au syndic, dans la relance —, c'est de savoir en une ou deux phrases où en
est CHAQUE affaire, sous son titre. Le résumé est rédigé à partir de toute la
matière de l'affaire — titre, périmètre, description, fil daté —, pas du seul
descriptif.

| Partie | Qui l'écrit |
|---|---|
| `CONSIGNE` | l'administration (prompt de l'usage — Admin › Assistant IA) |
| `FORMAT_REPONSE` | **le code** : `lire_reponse` sait relire cette forme et aucune autre |
| le message | **le code** (`construire_message`) : dates, anciennetés et états sont CALCULÉS |

🔴 La réponse est du TEXTE, jamais du HTML. L'écran l'affiche tel quel, le PDF
l'échappe, le courriel de relance aussi (`| e`).

🔴 Ce module n'importe ni `llm` ni la base : `llm_usages` le lit pour son prompt
d'origine, et `llm` lit `llm_usages` — le moindre import en retour formerait un
cycle.
"""

from __future__ import annotations

from app.utils.description_format import ReponseIllisible, lire_objet

#: Le code de l'usage — lu par `llm_usages`. Il garde son nom de naissance : les
#: réglages de l'usage (modèle, activation) sont déjà en base sous ce code.
USAGE_SYNTHESE_AFFAIRES_EN_COURS = "synthese_affaires_en_cours"

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu résumes, pour le conseil syndical d'une copropriété, chacune des affaires "
    "encore ouvertes. Chaque résumé s'affiche sous le titre de l'affaire dans le "
    "rapport « Suivi des affaires », et peut partir au syndic dans un courriel de relance.\n"
    "- Pour CHAQUE affaire : une ou deux phrases, en français, au présent, sur un ton "
    "factuel et sobre — où elle en est, ce qu'elle attend et de qui.\n"
    "- Appuie-toi sur toute sa matière : titre, périmètre, description et fil daté. "
    "Le dernier état du fil compte plus que la description d'origine.\n"
    "- Ne répète pas le titre. Les dates et les durées te sont DONNÉES : reprends-les "
    "telles quelles, n'en calcule et n'en invente aucune.\n"
    "- Ne cite aucun nom de personne, aucune adresse, aucun numéro de téléphone ; "
    "désigne les personnes par leur rôle (le syndic, le conseil syndical, l'auteur de "
    "l'affaire, un résident, le prestataire)."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour, à une clé :\n"
    '{"affaires": {"<numéro de l’affaire, tel que donné>": "<son résumé, texte sans '
    'balise>", "...": "..."}}\n'
    "Un résumé pour CHAQUE affaire listée, et aucune autre clé."
)

#: Ce qui part au modèle : au-delà, le message coûterait sans rien apprendre de plus.
MAX_AFFAIRES = 150
MAX_CARACTERES_DESCRIPTIF = 1_500
#: Le fil d'UNE affaire — ses dernières entrées comptent le plus.
MAX_CARACTERES_FIL = 4_000
#: Ce qui revient : une ou deux phrases par affaire.
MAX_CARACTERES_RESUME_AFFAIRE = 400


def construire_message(jour: str, affaires: list[dict]) -> str:
    """PURE. Le message envoyé : la date, le compte, puis un bloc par affaire.

    Chaque affaire est un dict à clés `numero`, `libelle_categorie`, `perimetre`,
    `titre`, `ouverte_le` (déjà formatée), `age_jours`, `libelle_statut`,
    `descriptif` et `fil` (les lignes datées, déjà écrites par rôle) — jamais un
    nom. Le numéro est la clé du résumé que le modèle rend.
    """
    lignes = [
        f"Date du rapport : {jour}.",
        f"Affaires ouvertes : {len(affaires)}.",
    ]
    if len(affaires) > MAX_AFFAIRES:
        lignes.append(f"Seules les {MAX_AFFAIRES} plus anciennes sont détaillées ci-dessous.")
    for a in affaires[:MAX_AFFAIRES]:
        lignes += [
            "",
            f"### {a['numero']} — « {a['titre']} »",
            f"Catégorie : {a['libelle_categorie']}"
            + (f" · périmètre : {a['perimetre']}" if a.get("perimetre") else "")
            + f" · ouverte le {a['ouverte_le']} ({a['age_jours']} jours)"
            + f" · état : {a['libelle_statut']}.",
        ]
        descriptif = (a.get("descriptif") or "").strip()
        if descriptif:
            lignes.append(f"Description : {descriptif[:MAX_CARACTERES_DESCRIPTIF]}")
        fil = (a.get("fil") or "").strip()
        if fil:
            #  Les DERNIÈRES entrées : c'est là qu'est l'état de l'affaire.
            lignes += ["Fil daté :", fil[-MAX_CARACTERES_FIL:]]
    return "\n".join(lignes)


def lire_reponse(texte: str) -> dict[str, str]:
    """Le résumé de chaque affaire, par numéro, relu et borné.

    Un résumé illisible est écarté, jamais une raison de refuser toute la
    réponse : l'affaire garde alors son descriptif. Une réponse sans la clé
    `affaires` est illisible.
    """
    affaires = lire_objet(texte).get("affaires")
    if not isinstance(affaires, dict):
        raise ReponseIllisible("Réponse du modèle sans résumé d'affaire.")
    return {
        str(numero).strip(): t.strip()[:MAX_CARACTERES_RESUME_AFFAIRE]
        for numero, t in affaires.items()
        if isinstance(t, str) and t.strip()
    }
