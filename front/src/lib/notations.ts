/**
 * La note d'un prestataire — comment elle se calcule et comment elle s'écrit.
 *
 * ## Pourquoi ce module (#807, 06/09/2026)
 *
 * `avgNote()` et `starsDisplay()` vivaient dans `prestataires/+page.svelte`, à
 * côté du badge qui les affiche. En livrant la liste des avis, elles ont été
 * nécessaires **à deux endroits** — le badge de la carte et le détail de chaque
 * avis — et c'est le moment où une fonction se recopie.
 *
 * ⚠️ Elles ne sont pas montées ici « par précaution » : elles y sont montées
 * parce qu'un second appelant est apparu. Une fonction extraite avant d'avoir
 * deux usages est une indirection, pas une factorisation.
 */

//  🔴 `moyenneNotes` est PARTIE le 04/11/2026 (#2507) : la moyenne des avis est SERVIE
//  avec le prestataire (`note_moyenne`, `api/app/utils/notes_prestataires.py`), que
//  l'app iOS lit aussi. L'onglet Reporting en portait une seconde copie, à la main,
//  et la synthèse une troisième, dont l'arrondi différait.

/** `4.2` → `★★★★☆`. La note est arrondie à l'entier le plus proche. */
export function etoiles(note: number): string {
	const pleines = Math.max(0, Math.min(5, Math.round(note)));
	return '★'.repeat(pleines) + '☆'.repeat(5 - pleines);
}
