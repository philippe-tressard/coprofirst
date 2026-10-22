"""La **synthèse IA d'une affaire close** (#1643).

Quand une affaire passe en résolu ou annulé, quelle que soit sa catégorie,
une synthèse est produite en différé, déposée dans une nouvelle Suite de
l'affaire, soumise au conseil pour relecture, puis validée — et alors visible
des ayants droit et dans le carnet.

| Module | Ce qu'il porte |
|---|---|
| `format` | le prompt d'origine, le format de réponse et sa relecture — sans base ni `llm` |
| `metriques` | les métriques, calculées par le code (jours ouvrés, étapes, rythme, moyenne) |
| `rassemblement` | ce qu'on lit de l'affaire, et le message envoyé à l'assistant |
| `production` | l'appel, la Suite, le remplacement, l'avis par courriel |
| `file` | l'inscription d'une demande et la tâche permanente |
| `lecture` | qui lit une synthèse (brouillon / validée), et sous quelle forme |
| `agregats` | les moyennes d'un ENSEMBLE d'affaires closes : bilan du carnet (#1645), fiche prestataire (#1646) |

L'éligibilité est `production.peut_etre_produite` : toute affaire close et non
absorbée (arbitré le 21/10/2026 ; « du carnet » jusque-là). Le paquet ne nomme
aucune catégorie (🔒 `test_synthese_eligibilite.py`) ; les moyennes du bilan du
carnet (`agregats`) gardent la règle du carnet, `contribue_au_carnet`.
"""
