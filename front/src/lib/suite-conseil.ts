/**
 * Ce que le CONSEIL pose dans une Suite 🔄 d'affaire — Équipement, Quand,
 * Intervenant (#1207) — et l'état que ces sections PARTAGENT.
 *
 * ## Pourquoi un module (#1326, 25/09/2026)
 *
 * Les trois sections vivaient dans un seul composant (`SectionsSuiteConseil`),
 * rendu dans UN créneau d'`EvolForm` : l'Équipement (rang 2) passait donc après
 * le Suivi (rang 3). Les rendre à leur rang les place dans DEUX créneaux —
 * avant et après le Suivi —, donc dans deux composants. Or l'Équipement propose
 * l'Intervenant, et la planification envoyée les rassemble : l'état vit ici, dans
 * le magasin qu'`EvolForm` fournit à ses créneaux (`partage`), un par formulaire.
 */
import type { Writable } from 'svelte/store';
import type { Ticket } from '#lib/api/index.ts';
import { pourChampLocal } from '#lib/date.ts';
import { estBati, natureDe } from '#lib/formulaire-affaire.ts';

export interface EtatSuiteConseil {
	equipement: string;
	prestataireId: number | null;
	contratId: number | null;
	debut: string;
	fin: string;
	pret?: boolean;
}

/** Le conseil pose-t-il quelque chose dans cette Suite ? Pas sur une actualité. */
export function conseilDansLaSuite(ticket: Ticket, estCS: boolean): boolean {
	return estCS && natureDe(ticket.categorie) !== 'actualite';
}

/** L'Équipement — et l'Intervenant qu'il propose — n'existent que pour le bâti. */
export function equipementDansLaSuite(ticket: Ticket, estCS: boolean): boolean {
	return conseilDansLaSuite(ticket, estCS) && estBati(ticket.categorie);
}

/**
 * L'état partagé, initialisé UNE fois depuis l'affaire par la première section
 * qui le lit — celle qui se rend la première ne change rien à la valeur.
 */
export function etatSuite(
	partage: Writable<Record<string, unknown>>,
	ticket: Ticket,
): Writable<EtatSuiteConseil> {
	partage.update((e) =>
		e.pret
			? e
			: {
					...e,
					pret: true,
					equipement: ticket.equipement ?? '',
					prestataireId: ticket.prestataire_id ?? null,
					contratId: ticket.contrat_id ?? null,
					debut: pourChampLocal(ticket.debut),
					fin: pourChampLocal(ticket.fin),
				},
	);
	return partage as unknown as Writable<EtatSuiteConseil>;
}
