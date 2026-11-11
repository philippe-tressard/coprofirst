/**
 * La pastille de lecture d'une affaire — ce que l'écran en LIT (#2633).
 *
 * « Qui la lit » est calculé au serveur (`api/app/utils/lecture_pastille`) : servi
 * avec l'objet enregistré (`lecture`, `destinataires_par_etat`), et pour une saisie
 * par l'aperçu (`#lib/apercu-lecture`). Ce module ne garde que ce qu'un écran
 * DEMANDE à ces champs : la nature d'une saisie (pour la demander), et deux
 * lectures de ce que l'affaire sert.
 *
 * 🔴 `lectureDe`, `lectureDuTicket`, `lueDuSeulConseil` et `#lib/lecture.ts` sont
 * PARTIS le 11/11/2026 : le front ne compose plus la pastille, l'app iOS la lit au
 * même endroit. 🔒 `npm run lint:regles-partagees` refuse leur retour.
 */
import { derived } from 'svelte/store';
import { apercuLecture } from '#lib/apercu-lecture.ts';
import { codesDestinataires } from '#lib/destinataires.ts';
import { estActualite } from '#lib/tickets.ts';
import type { Ticket } from '#lib/api/index.ts';

/** Ce que le FORMULAIRE sait de la nature — ce qu'il envoie à l'aperçu. */
export type NatureLue = {
	actualite: boolean;
	categorie?: string;
	/** Une Étude & travaux sort du conseil en AG (standard du 30/09/2026). */
	statut?: string;
};

/**  Ce qui décide de la lecture d'une affaire, hors de ses choix — d'un objet
 *   enregistré comme d'une saisie en cours (`FormulaireTicket`). */
export function natureLue(s: { categorie?: string | null; statut?: string | null }): NatureLue {
	return {
		actualite: estActualite(s),
		categorie: s.categorie ?? undefined,
		statut: s.statut ?? undefined,
	};
}

/**  Les Destinataires qu'une Suite présélectionne sur une AFFAIRE sans choix du
 *   conseil (#1343), selon l'état qu'elle lui donne — SERVIS avec l'affaire
 *   (`destinataires_par_etat`) ; `null` pour une actualité, qui a les siens. */
export function destinatairesParDefautDuTicket(t: Ticket): ((statut: string) => string[]) | null {
	const parEtat = t.destinataires_par_etat;
	return estActualite(t) || !parEtat ? null : (statut) => parEtat[statut || t.statut] ?? [];
}

/**  Personne d'autre que le conseil — et l'auteur — ne la lit : rien ne sort, ni
 *   sur le groupe ni au hall. Lu sur la pastille SERVIE (ses profils vides) ;
 *   inconnue, on ne tend pas la diffusion — le serveur décide de toute façon
 *   (`reservee_au_conseil`). */
export function ticketLuDuSeulConseil(t: Pick<Ticket, 'lecture'>): boolean {
	return !t.lecture || t.lecture.profils.length === 0;
}

/**  « Lue du seul conseil » d'une SAISIE — Confidentielle, Destinataires = Conseil
 *   syndical seul, ou fermée par sa catégorie (#1436) : rien ne sortira, ni groupe
 *   ni hall. SERVI par l'aperçu (`lue_du_seul_conseil`, #2633) ; tant qu'il n'a
 *   pas répondu, la diffusion ne se tend pas (`true`) — le serveur décide de toute
 *   façon (`reservee_au_conseil`). Le store vaut une fonction : le gabarit la relit
 *   quand la réponse arrive. */
export const lueDuSeulConseil = derived(
	apercuLecture,
	(lire) =>
		(
			categorie: string | null | undefined,
			statut: string | null | undefined,
			confidentiel: boolean,
			publicCible: string[] | string | null | undefined,
		): boolean =>
			lire(
				{ categorie, statut, confidentiel, public_cible: codesDestinataires(publicCible) },
				'formulaire-reservee',
			)?.lue_du_seul_conseil ?? true,
);
