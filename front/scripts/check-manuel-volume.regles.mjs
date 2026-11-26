/**
 *  Les PLAFONDS de `check-manuel-volume.mjs` — en mots, à la longueur mesurée le
 *  24/11/2026 (#3008), et qui ne font que baisser.
 *
 *  Séparés du script pour la même raison que `check-libelles-soumission.regles.mjs` :
 *  la table bouge à chaque carte reprise, la mesure presque jamais.
 *
 *  Cible (arbitrage du 07/09/2026, #651) : la partie « Démarrer » (`express`),
 *  puis une carte des écrans courte — le manuel comptait 3 042 mots ce jour-là.
 *  Le détail d'un écran vit dans l'application (aides d'écran, FAQ) : le manuel
 *  en donne l'essentiel.
 *
 *  25/11/2026, décision de Philippe sur #3008 (« option 2, et 1 si nécessaire ») :
 *  les outils du conseil et de l'administration — Prestataires, Espace CS, Admin —
 *  n'ont plus d'« En savoir plus » (−11 617 mots).
 *
 *  26/11/2026, décision de Philippe sur #3008 (« un manuel clair, simple et pas
 *  trop long pour éviter de faire peur aux users ») : AUCUNE carte n'a plus
 *  d'« En savoir plus » — `blocs: 0` —, et le manuel entier a été relu à ce
 *  critère (15 520 → 3 888 mots). Chaque écran tient en une ou deux phrases ;
 *  son détail vit dans l'application. Un plafond est un résumé : y remettre un
 *  détail le dépasse.
 */

/** L'écart toléré, en mots, entre un plafond et son compte avant d'exiger qu'il baisse. */
export const MARGE = 20;

export const PLAFONDS = {
	//  Le manuel entier : 27 137 mots le 24/11/2026, 15 520 le 25/11/2026,
	//  3 888 le 26/11/2026 — pour 3 042 le 07/09/2026.
	total: 3888,
	//  Les blocs dépliables (« En savoir plus ») : plus aucun depuis le 26/11/2026.
	blocs: 0,
	sections: {
		intro: 94,
		apropos: 208,
		express: 466,
		ecrans: 1221,
		affaire: 1350,
		icones: 311,
		'logiciel-libre': 120,
	},
	//  Par `data-page` : le résumé de chaque écran, sans bloc dépliable.
	cartes: {
		'/tableau-de-bord': 84,
		'/residence': 107,
		'/tickets': 90,
		'/mon-lot': 117,
		'/annuaire': 29,
		'/prestataires': 31,
		'/sondages': 83,
		'/faq': 23,
		'/espace-cs': 43,
		'/admin': 23,
		'/delegations': 58,
		profil: 63,
	},
};
