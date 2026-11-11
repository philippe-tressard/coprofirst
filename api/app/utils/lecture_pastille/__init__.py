"""**Qui LIT une affaire, une actualité ou un objet ciblé** — la pastille de lecture.

## Pourquoi au serveur (#2633, 11/11/2026)

La pastille RÉSUME en un objet qui lit : une ou des icônes, un libellé court
(carte) ou long (section), le cadenas d'un périmètre réservé, la phrase de
l'infobulle. Elle se composait dans le front (`lectureDe`, `#lib/lecture`) : l'app
iOS n'avait rien. Le serveur la SERT désormais — avec l'objet enregistré
(`lecture` d'une affaire, d'une ligne du fil, d'une annonce, d'une idée, d'un
sondage) et pour une saisie en cours (`POST /lecture/apercu`, arbitré le
11/11/2026) —, et les deux clients la LISENT.

⚠️ **Ce n'est qu'un résumé : c'est `ticket_visible` qui décide.** Une seule
attente tient les deux, `tests/donnees/lecture_pastille.json` :
`test_lecture_pastille.py` l'exécute contre la règle de visibilité ET contre
cette fonction. Une pastille qui annoncerait « Tous » là où les locataires ne
lisent pas mentirait à chaque lecteur, sans que rien casse.

## Trois restrictions, pas une de plus

1. **Confidentielle** — le conseil syndical seul ; elle passe outre tout le reste.
2. **Périmètre réservé** — oui ou non ; LEQUEL, le 🔹 d'à côté le dit.
3. **Profils** — ceux que Destinataires vise, ou la règle des affaires
   (`defauts_affaire`).

Le périmètre arrive déjà tranché (`perimetre_restreint`) : la fonction reste
PURE, l'appelant lit l'arbre (`perimetre_restreint_de`).
"""

#  Le paquet n'importe rien : `modele` (la forme servie), `vocabulaire` (les
#  profils et leurs noms), `regle` (`lecture_de`, PURE) et `objets` (appliquée à
#  un objet enregistré, l'arbre des périmètres lu) s'importent par leur nom — un
#  schéma qui ne veut que `modele.Lecture` ne charge pas la visibilité.
