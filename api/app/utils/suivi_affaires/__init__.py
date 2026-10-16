"""Le rapport « Suivi des affaires » du conseil syndical (Reporting CS, 16/10/2026).

Les affaires que la relance du syndic retient, en une liste synthétique — date
d'ouverture, titre, périmètre, résumé, catégorie —, leur nombre, leur répartition
par catégorie et un export PDF (maquette D2) ; et, en second mode de l'écran, de
quoi relancer le syndic (#2035).

| Module | Ce qu'il porte |
|---|---|
| `releve` | QUI entre au rapport et ce qu'on en montre — la seule écriture de la règle |
| `format` | ce que l'assistant reçoit et la forme de sa réponse (sans `llm` ni base) |
| `resumes` | l'appel à l'usage `synthese_affaires_en_cours` : le résumé de chaque affaire, gardé sur elle |
| `pdf` | le document imprimable |

L'écran, les résumés et le PDF lisent le MÊME relevé : l'écran le reçoit par
`GET /suivi-affaires`, il ne recalcule rien.
"""
