/**
 * Les consignes de la fiche arrivant — éditables par le conseil syndical (#1727).
 *
 * À part d'`administration.ts`, qui frôle le plafond de 500 lignes : le client et
 * son type vivent dans leur module, comme `services.ts`.
 *
 * Du TEXTE, jamais du HTML : `**gras**`, `{syndic}` (le nom du syndic, lu dans
 * le contrat au rendu) et `{site}` (l'adresse du site) sont les seules conventions — la fiche l'échappe
 * (`api/app/utils/consignes_arrivant.py`).
 */
import { api } from './client';

/** Une rubrique de la fiche : son titre, puis son texte. */
export interface ConsigneArrivant {
	titre: string;
	contenu: string;
}

/** `GET|PUT /admin/consignes-arrivant`. */
export interface ConsignesArrivant {
	consignes: ConsigneArrivant[];
	/** Faux tant que la résidence n'a rien saisi : c'est le gabarit du produit. */
	personnalisees: boolean;
	/** La phrase d'accueil, sous « Bonjour et bienvenue ! » — `{site}` y nomme l'adresse du site. */
	accueil: string;
}

export const consignesArrivant = {
	lire: () => api.get<ConsignesArrivant>('/admin/consignes-arrivant'),
	enregistrer: (consignes: ConsigneArrivant[], accueil: string) =>
		api.put<ConsignesArrivant>('/admin/consignes-arrivant', { consignes, accueil }),
};
