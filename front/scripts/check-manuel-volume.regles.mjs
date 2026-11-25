/**
 *  Les PLAFONDS de `check-manuel-volume.mjs` — en mots, à la longueur mesurée le
 *  24/11/2026 (#3008), et qui ne font que baisser.
 *
 *  Séparés du script pour la même raison que `check-libelles-soumission.regles.mjs` :
 *  la table bouge à chaque carte reprise, la mesure presque jamais.
 *
 *  Cible (arbitrage du 07/09/2026, #651) : la partie « Démarrer » (`express`),
 *  puis une carte des écrans courte — le manuel comptait 3 042 mots ce jour-là.
 *  Un « En savoir plus » se réduit au fil des lots qui touchent son écran : le
 *  détail part dans l'application (aides d'écran, FAQ) ou disparaît.
 *
 *  25/11/2026, décision de Philippe sur #3008 (« option 2, et 1 si nécessaire ») :
 *  les outils du conseil et de l'administration — Prestataires, Espace CS, Admin —
 *  n'ont plus d'« En savoir plus » (−11 617 mots). Leur plafond est leur résumé :
 *  y remettre un détail le dépasse.
 */

/** L'écart toléré, en mots, entre un plafond et son compte avant d'exiger qu'il baisse. */
export const MARGE = 20;

export const PLAFONDS = {
	//  Le manuel entier : 27 137 mots le 24/11/2026, 15 520 le 25/11/2026, pour
	//  3 042 le 07/09/2026.
	total: 15520,
	sections: {
		intro: 113,
		apropos: 682,
		express: 979,
		ecrans: 7546,
		affaire: 5185,
		icones: 753,
		'logiciel-libre': 124,
	},
	//  Par `data-page`. Les plus longues d'abord à reprendre : /residence, profil,
	//  /sondages, /mon-lot.
	cartes: {
		'/tableau-de-bord': 809,
		'/residence': 1631,
		'/tickets': 147,
		'/mon-lot': 1045,
		'/annuaire': 29,
		'/prestataires': 31,
		'/sondages': 1100,
		'/faq': 23,
		'/espace-cs': 43,
		'/admin': 69,
		'/delegations': 219,
		profil: 1299,
	},
};
