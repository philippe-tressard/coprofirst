"""Le rapport « Suivi des affaires » du conseil syndical (Reporting CS, 16/10/2026).

Toutes les affaires qui ne sont ni résolues ni annulées, en une liste synthétique
— date d'ouverture, titre, descriptif, catégorie —, leur nombre, leur répartition
par catégorie, une synthèse rédigée par l'assistant et un export PDF (maquette D2).

| Module | Ce qu'il porte |
|---|---|
| `releve` | QUI entre au rapport et ce qu'on en montre — la seule écriture de la règle |
| `format` | ce que l'assistant reçoit et la forme de sa réponse (sans `llm` ni base) |
| `synthese` | l'appel à l'usage `synthese_affaires_en_cours` |
| `pdf` | le document imprimable |

L'écran, la synthèse et le PDF lisent le MÊME relevé : l'écran le reçoit par
`GET /suivi-affaires`, il ne recalcule rien.
"""
