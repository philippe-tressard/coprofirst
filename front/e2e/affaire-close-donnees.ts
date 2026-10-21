/*
 *  **Une affaire close et son fil, en données de test** — partagées par la carte de la
 *  liste Affaires (`carte-affaire-close.spec.ts`) et la parité avec le fil d'activité
 *  (`fil-rubriques-affaire.spec.ts`, arbitrage n° 66) : la MÊME affaire, lue deux fois.
 *  Écrites ici une fois : un fil de test recopié diverge au premier champ ajouté.
 */
export const AFFAIRE = {
	id: 42,
	numero: 'TK-142',
	titre: 'Fuite d’eau au plafond du hall B',
	description: '<p>Une tache s’étend au plafond du hall.</p>',
	categorie: 'panne',
	statut: 'résolu',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	synthese_validee: true,
	natures: ['activite'],
	cree_le: '2026-10-12T09:00:00',
	mis_a_jour_le: '2026-10-21T09:00:00',
};

const entree = (id: number, jour: number, extra: Record<string, unknown>) => ({
	id,
	ticket_id: 42,
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: `2026-10-${String(jour).padStart(2, '0')}T10:00:00`,
	fichiers_urls: [],
	...extra,
});

export const FIL = [
	entree(1, 12, { type: 'commentaire', contenu: '<p>Signalée au gardien.</p>' }),
	entree(2, 13, { type: 'etat', ancien_statut: 'ouvert', nouveau_statut: 'en_cours' }),
	entree(3, 14, { type: 'commentaire', contenu: '<p>Le plombier passe jeudi.</p>' }),
	entree(4, 20, { type: 'commentaire', contenu: '<p>Raccord remplacé.</p>' }),
	entree(5, 21, { type: 'etat', ancien_statut: 'en_cours', nouveau_statut: 'résolu' }),
	entree(6, 21, { type: 'synthese' }),
];

const METRIQUES = {
	version: 1,
	issue: 'résolu',
	ouverte_le: '2026-10-12T09:00:00',
	close_le: '2026-10-21T10:00:00',
	duree_totale: 8,
	premiere_reponse_syndic: 1,
	relances: 0,
	suites: 5,
	etapes: [{ statut: 'en_cours', jours: 6 }],
	etape_plus_longue: 'en_cours',
	reaction_relance: null,
	semaines: [2, 2, 1],
	semaines_muettes: 0,
	chronologie: [],
	reouvertures: 0,
	comparaison: null,
};

export const ETAT_SYNTHESE = {
	produisible: false,
	en_attente: false,
	synthese: {
		id: 1,
		ticket_id: 42,
		evolution_id: 6,
		statut: 'validee',
		metriques: METRIQUES,
		synthese: '<p>Raccord de la colonne remplacé.</p>',
		difficultes: '<p>La clé de la gaine manquait.</p>',
		amelioration: null,
		prompt_complement: null,
		assiste_ia: false,
		motif_vide: null,
		produite_le: '2026-10-21T10:30:00',
		validee_le: '2026-10-22T11:00:00',
		validee_par_nom: 'CS Témoin',
	},
};
