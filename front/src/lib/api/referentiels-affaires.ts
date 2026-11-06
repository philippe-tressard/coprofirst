/**
 *  Les tables d'une affaire servies par l'API (#2508) — `GET /tickets/referentiels`
 *  (`routers/tickets/referentiels.ReferentielsAffaires`). Le site y lit ce que
 *  l'app iOS y lit : l'état qui CLÔT une affaire (`statuts[].clos`, #2511).
 */
import { api } from './client';

export interface CategorieServie {
	code: string;
	libelle: string;
	emoji: string;
	description: string;
	/** 📒 Une affaire résolue dans cette catégorie entre au carnet d'entretien. */
	carnet: boolean;
	/** Réservée au conseil syndical. */
	reservee: boolean;
	/** Ce compte peut-il la poser ? */
	permise: boolean;
	/** Posée en tête de la grille, pleine ligne. */
	en_tete: boolean;
}

export interface StatutServi {
	code: string;
	libelle: string;
	/** Résolue ou annulée : l'affaire quitte le suivi (`etat_affaire.affaire_close`). */
	clos: boolean;
	/** La colonne du Kanban, `null` hors tableau. */
	colonne_kanban: string | null;
	/** Offert dans une Suite. */
	proposable: boolean;
}

export interface ColonneKanbanServie {
	code: string;
	libelle: string;
	libelle_court: string;
}

export interface NatureServie {
	code: string;
	libelle: string;
}

export interface ReferentielsAffaires {
	categories: CategorieServie[];
	statuts: StatutServi[];
	colonnes_kanban: ColonneKanbanServie[];
	natures: NatureServie[];
}

export const lireReferentielsAffaires = () =>
	api.get<ReferentielsAffaires>('/tickets/referentiels');
