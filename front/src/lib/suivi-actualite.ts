/**
 * **Le suivi d'une actualité** — optionnel, trois états, posé par le conseil seul.
 *
 * Demandé le 10/10/2026 : *« une affaire de type actualité possède un suivi
 * (optionnel) à trois états seulement, activable uniquement par le CS : Ouvert
 * (par défaut), Résolu ou Annulé »*. Arbitré le même jour : un **repère** (hors
 * kanban, relances et compteurs), l'archivage d'une affaire, une **case** au
 * formulaire puis l'état par une **Suite**.
 *
 * Le serveur porte la règle (`api/app/utils/suivi_actualite.py`) ; ce module en
 * est le miroir d'écran, et la seule écriture des trois questions que les écrans
 * posent. Les états eux-mêmes vivent dans `#lib/tickets`, avec le cycle ;
 * `test_suivi_actualite.py` tient leur concordance avec le serveur.
 */
import type { Ticket } from '#lib/api/index.ts';
import { ETATS_SUIVI_ACTUALITE, STATUT_TICKET_OPTIONS, estActualite } from '#lib/tickets.ts';

/** L'état d'un suivi qu'on active — `ETAT_SUIVI_DEFAUT` côté serveur : le premier. */
export const ETAT_SUIVI_DEFAUT = ETATS_SUIVI_ACTUALITE[0];

/** Leurs pastilles : celles des affaires, mêmes libellés et mêmes couleurs. */
export const SUIVI_ACTUALITE_OPTIONS = STATUT_TICKET_OPTIONS.filter((o) =>
	ETATS_SUIVI_ACTUALITE.includes(o.value),
);

type Suivable = Pick<Ticket, 'categorie' | 'statut' | 'suivi_actualite'>;

/** L'état que la carte et la fiche montrent : le statut d'une affaire, le suivi
 *  d'une actualité — `null` pour une actualité sans suivi, qui n'en montre aucun. */
export function etatAffiche(t: Suivable): string | null {
	return estActualite(t) ? (t.suivi_actualite ?? null) : t.statut;
}

/** L'état que la Suite fait avancer — pendant de `etat_de_la_suite`. */
export function etatDeLaSuite(t: Suivable): string {
	return etatAffiche(t) ?? t.statut;
}

/** Les états qu'une Suite propose : le cycle d'une affaire ; pour une actualité,
 *  ses trois états si le suivi est activé et que le conseil écrit — sinon aucun. */
export function etatsDeLaSuite(t: Suivable, estCS: boolean): { value: string; label: string }[] {
	if (!estActualite(t)) return STATUT_TICKET_OPTIONS;
	return estCS && t.suivi_actualite ? SUIVI_ACTUALITE_OPTIONS : [];
}

/** L'aide de la case, en création comme en correction. */
export const AIDE_SUIVI_ACTUALITE =
	'Elle part en « Ouvert », ou dans l’état choisi ci-dessus — « Résolu » si tout est déjà ' +
	'réglé. Une Suite trace ensuite son avancée au fil. Un repère seulement — ni kanban, ni ' +
	'relance. « Annulé » la range aussitôt aux archives, « Résolu » trente jours après.';
