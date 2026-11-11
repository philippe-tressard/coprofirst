/**
 * **Le nom d'une personne en cours de SAISIE, rendu par le serveur** —
 * `POST /noms/affiche` (#2633), par le mécanisme commun `#lib/apercu-serveur`
 * (délai, réponse périmée ignorée, dernier nom gardé pendant l'attente et hors ligne).
 *
 * Un objet ENREGISTRÉ n'en a pas besoin : son nom est servi avec lui
 * (`nom_affiche`, `locataire_nom_affiche`…). Ne passent ici que les personnes
 * qu'un formulaire nomme avant de les enregistrer : un membre de l'annuaire qu'on
 * corrige, un invité ajouté au point du conseil.
 */
import { derived } from 'svelte/store';
import { noms, type NomRendu, type NomSaisi } from '#lib/api/index.ts';
import { apercuServi } from '#lib/apercu-serveur.ts';

const servi = apercuServi<NomSaisi, NomRendu>(
	(personne) => noms.affiche(personne),
	(personne) => JSON.stringify([personne.prenom ?? '', personne.nom ?? '']),
);

/** `$nomSaisi(personne, place)` — « Prénom NOM », ou le dernier rendu à cette
 *  place tant que le serveur n'a pas répondu ; `''` avant sa première réponse. */
export const nomSaisi = derived(
	servi.store,
	(lire) =>
		(personne: NomSaisi, place: string): string =>
			lire(personne, place)?.nom_affiche ?? '',
);

/** Les personnes dont le serveur a DÉJÀ servi le nom (`nom_affiche`) : un formulaire
 *  rouvert sur elles les nomme d'emblée, sans attendre ni demander (un invité repris). */
export function nomsConnus(
	personnes: readonly (NomSaisi & { nom_affiche?: string | null })[],
): void {
	for (const p of personnes) {
		if (p.nom_affiche != null) servi.connue(p, { nom_affiche: p.nom_affiche });
	}
}

/** Pour un geste qui attend le nom (un message, une confirmation) : sans délai,
 *  et `''` si le serveur ne répond pas — le geste n'est jamais bloqué. */
export async function nomSaisiImmediat(personne: NomSaisi): Promise<string> {
	try {
		return (await servi.immediat(personne)).nom_affiche;
	} catch {
		return '';
	}
}
