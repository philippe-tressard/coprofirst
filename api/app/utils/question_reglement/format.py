"""Ce que l'assistant reçoit pour une question au règlement, et la forme de sa réponse.

| Partie | Qui l'écrit | Pourquoi |
|---|---|---|
| `CONSIGNE` | l'administration (prompt de l'usage, initialisé par la 0256) | la méthode du juriste se relit et s'adapte |
| `FORMAT_REPONSE` | **le code** — `lire_reponse` sait relire cette forme et aucune autre | ajouté à l'appel, jamais exposé à l'édition |
| le message | **le code** (`construire_message`) | le texte du règlement EN TÊTE, la question à la fin |

## Pourquoi le règlement passe avant la question

Le règlement ne change pas d'une question à l'autre, la question si. Placé en
tête, après une consigne elle aussi stable, il forme un préfixe identique que le
fournisseur garde en cache — OpenAI le fait seul au-delà de 1 024 jetons — et
chaque question suivante en paie une fraction (`appel_ia.jetons_cache`).

🔴 Ce module n'importe ni `llm` ni la base : `llm_usages` le lit pour son prompt
d'origine, et `llm` lit `llm_usages` — le moindre import en retour formerait un
cycle.
"""

from __future__ import annotations

from app.utils.description_format import ReponseIllisible, lire_objet

#: Le code de l'usage — lu par `llm_usages`, qui ne peut pas importer la production.
USAGE_QUESTION_REGLEMENT = "question_reglement"

#: Les verdicts, et leur libellé — la SEULE liste : l'écran le reçoit avec la réponse.
VERDICTS: dict[str, str] = {
    "oui": "Oui",
    "non": "Non",
    "sous_conditions": "Oui, sous conditions",
    "non_prevu": "Le règlement ne le prévoit pas",
    "incertain": "Incertain",
}

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu es juriste, spécialiste du droit français de la copropriété (loi n° 65-557 du "
    "10 juillet 1965, décret n° 67-223 du 17 mars 1967, jurisprudence). Le conseil "
    "syndical te transmet la question d'un résident et le texte de travail du règlement "
    "de copropriété de la résidence : état descriptif de division, règlement et leurs "
    "modificatifs, transcrits des actes notariés.\n"
    "\n"
    "Ta méthode :\n"
    "- Lis TOUT le texte avant de répondre : une règle posée dans un chapitre peut être "
    "précisée, restreinte ou modifiée ailleurs (destination de l'immeuble, usage des "
    "parties privatives et communes, charges, annexes, modificatifs).\n"
    "- Les actes se lisent dans l'ordre chronologique : un modificatif l'emporte sur "
    "l'acte qu'il modifie, pour ce qu'il modifie seulement.\n"
    "- Fonde ta réponse sur le règlement. Quand la loi impose autre chose — une clause "
    "réputée non écrite (article 43 de la loi de 1965), un droit que le règlement ne peut "
    "pas retirer, une décision qui relève de l'assemblée générale et de sa majorité —, "
    "dis-le dans les réserves, en distinguant toujours ce que dit le règlement de ce que "
    "dit la loi.\n"
    "- Si le règlement ne traite pas la question, dis-le franchement (verdict "
    "« non_prevu ») et indique ce qui s'applique alors, sans inventer de clause.\n"
    "- Si un passage décisif est marqué [?] ou [illisible], ou si deux clauses se "
    "contredisent, dis-le et ne tranche pas au-delà de ce que le texte permet (verdict "
    "« incertain » si la réponse en dépend).\n"
    "\n"
    "Les extraits :\n"
    "- Chaque affirmation sur le règlement s'appuie sur au moins un extrait.\n"
    "- Un extrait est recopié MOT POUR MOT depuis le texte fourni : même orthographe, même "
    "ponctuation, sans reformuler ni corriger la transcription. Ne recopie pas les repères "
    "de page ⟦ … ⟧. Si tu dois couper, marque la coupure par […].\n"
    "- Donne la référence de chaque extrait : l'acte (le livre), le chapitre ou l'article, "
    "et la page indiquée par le repère ⟦ … ⟧ qui le précède dans le texte.\n"
    "- Préfère des extraits courts et décisifs, d'une à trois phrases ; cinq au plus, "
    "sauf nécessité.\n"
    "\n"
    "La réponse :\n"
    "- En français, claire pour un non-juriste : commence par la réponse à la question, "
    "puis explique.\n"
    "- Ne cite aucun nom de personne figurant dans les actes : désigne chacun par sa "
    "qualité (le vendeur, le notaire, le syndic).\n"
    "- C'est un avis indicatif : ne promets rien au nom du syndicat des copropriétaires."
)

#: La méthode propre aux décisions d'AG (29/10/2026) — tenue par le CODE, comme le
#: format : le prompt de l'usage vit en base et l'administration l'a peut-être
#: repris ; cette méthode s'ajoute quand des décisions sont jointes, et seulement alors.
METHODE_AG = (
    "Les décisions des assemblées générales :\n"
    "- Le message porte aussi, après le règlement, le bloc DECISIONS_AG : les résolutions "
    "transcrites des procès-verbaux, une assemblée par titre « # Assemblée générale du … », "
    "de la plus ancienne à la plus récente.\n"
    "- Cherche-y tout ce qui touche la question : autorisation ou interdiction, règlement "
    "intérieur, travaux, modification du règlement, répartition des charges.\n"
    "- Pour chaque décision retenue, nomme l'assemblée (la date de son titre), le numéro de "
    "la résolution, la majorité et le résultat du vote quand ils figurent. Une résolution "
    "REJETÉE ne crée aucune règle.\n"
    "- Articule les deux sources : une décision d'assemblée s'applique dans les limites du "
    "règlement et de la loi. Elle ne MODIFIE le règlement que si elle a été votée à la "
    "majorité qu'exige la clause modifiée (articles 24 à 26 de la loi de 1965), et une "
    "modification n'est opposable aux acquéreurs qu'une fois publiée au fichier immobilier. "
    "Une autorisation donnée à un lot ou à un copropriétaire précis ne crée pas de droit "
    "pour les autres. Une décision plus récente l'emporte sur une plus ancienne de même "
    "objet. Une décision de moins de deux mois peut encore être contestée (article 42).\n"
    "- Si aucune décision ne traite la question, dis-le en une phrase.\n"
    "- Un extrait d'une décision se recopie mot pour mot, comme un extrait du règlement ; "
    "sa référence donne la date de l'assemblée et le numéro de la résolution."
)

#: La forme de la réponse — tenue par le code, ajoutée APRÈS le prompt.
#: En SECTIONS depuis le 29/10/2026 : d'après le règlement, d'après les AG, synthèse.
FORMAT_REPONSE = (
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour, à sept clés :\n"
    '{"verdict": "oui" | "non" | "sous_conditions" | "non_prevu" | "incertain", '
    '"reponse": "<la réponse à la question, en deux à quatre phrases, en HTML simple : '
    '<p>, <ul>, <li>, <strong>>", '
    '"selon_reglement": "<ce que dit le règlement, argumenté, en HTML simple>", '
    '"selon_ag": "<ce que disent les décisions des assemblées générales, chacune nommée '
    "par sa date et sa résolution, en HTML simple — chaîne vide si le message n'a pas "
    'de bloc DECISIONS_AG>", '
    '"synthese": "<comment le règlement et les décisions s\'articulent, et ce qui '
    "s'applique au final, en HTML simple — chaîne vide si le message n'a pas de bloc "
    'DECISIONS_AG>", '
    '"extraits": [{"citation": "<mot pour mot>", '
    '"reference": "<acte, chapitre ou article, page — ou assemblée et résolution>", '
    '"apport": "<ce que l\'extrait établit, en une phrase>"}], '
    '"reserves": "<HTML simple, ou chaîne vide>"}'
)

#: Les sections de l'avis, dans l'ordre de l'écran — vides dans un avis d'avant le
#: 29/10/2026, et `selon_ag` comme `synthese` sans décision d'AG jointe.
SECTIONS = ("selon_reglement", "selon_ag", "synthese")

#: Une question, pas un dossier.
MAX_CARACTERES_QUESTION = 2_000
#: Au-delà, la réponse n'est plus un avis d'une page.
MAX_CARACTERES_CHAMP = 12_000
#: Un extrait se lit d'un coup d'œil ; au-delà, c'est une page recopiée.
MAX_CARACTERES_EXTRAIT = 2_000
MAX_EXTRAITS = 12


def consigne_complete(prompt: str, *, avec_ag: bool = False) -> str:
    """Le prompt de l'usage, la méthode des AG s'il y en a, puis le format — ce que
    l'administration ne peut pas retirer."""
    blocs = [prompt.rstrip()]
    if avec_ag:
        blocs.append(METHODE_AG)
    blocs.append(FORMAT_REPONSE)
    return "\n\n".join(blocs)


def construire_message(texte: str, question: str, decisions_ag: str = "") -> str:
    """PURE. Le règlement en tête, puis les décisions d'AG, la question à la fin —
    voir l'en-tête du module : ce qui change le moins passe le premier."""
    blocs = [
        "Texte de travail du règlement de copropriété (Markdown) :\n"
        f"<<<REGLEMENT\n{texte.strip()}\nREGLEMENT>>>"
    ]
    if decisions_ag.strip():
        blocs.append(
            "Décisions des assemblées générales (résolutions transcrites, Markdown) :\n"
            f"<<<DECISIONS_AG\n{decisions_ag.strip()}\nDECISIONS_AG>>>"
        )
    blocs.append(f"Question : {question.strip()[:MAX_CARACTERES_QUESTION]}")
    return "\n\n".join(blocs)


def _texte(charge: dict, cle: str, *, obligatoire: bool = False) -> str:
    brut = charge.get(cle)
    if brut is None:
        brut = ""
    if not isinstance(brut, str):
        raise ReponseIllisible(f"« {cle} » n'est pas un texte.")
    brut = brut.strip()[:MAX_CARACTERES_CHAMP]
    if obligatoire and not brut:
        raise ReponseIllisible(f"Réponse du modèle sans « {cle} ».")
    return brut


def lire_reponse(texte: str) -> dict:
    """PURE. Verdict, réponse, extraits bruts et réserves, relus dans la réponse.

    Un verdict inconnu n'est pas deviné : il devient « incertain », et la
    réponse argumentée reste — c'est elle qui fait foi, le verdict la résume.
    Les extraits sont rendus BRUTS (citation, référence, apport) : leur
    vérification contre le texte est l'affaire d'`extraits.verifier`.
    """
    charge = lire_objet(texte)
    verdict = charge.get("verdict")
    verdict = verdict.strip() if isinstance(verdict, str) else ""
    extraits = charge.get("extraits") or []
    if not isinstance(extraits, list):
        raise ReponseIllisible("« extraits » n'est pas une liste.")
    bruts = []
    for e in extraits[:MAX_EXTRAITS]:
        if not isinstance(e, dict) or not isinstance(e.get("citation"), str):
            continue
        citation = e["citation"].strip()[:MAX_CARACTERES_EXTRAIT]
        if not citation:
            continue
        bruts.append(
            {
                "citation": citation,
                "reference": str(e.get("reference") or "").strip()[:300],
                "apport": str(e.get("apport") or "").strip()[:600],
            }
        )
    return {
        "verdict": verdict if verdict in VERDICTS else "incertain",
        "reponse": _texte(charge, "reponse", obligatoire=True),
        **{cle: _texte(charge, cle) for cle in SECTIONS},
        "extraits": bruts,
        "reserves": _texte(charge, "reserves"),
    }


__all__ = [
    "CONSIGNE",
    "FORMAT_REPONSE",
    "MAX_CARACTERES_QUESTION",
    "METHODE_AG",
    "SECTIONS",
    "USAGE_QUESTION_REGLEMENT",
    "VERDICTS",
    "consigne_complete",
    "construire_message",
    "lire_reponse",
]
