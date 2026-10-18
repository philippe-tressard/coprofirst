/**
 * L'AVIS sur l'application, déclaré une fois — ses sections et chaque
 * divergence entre états avec son motif (R4). #2075, arbitrages du 18/10/2026.
 *
 * ## Ce que la déclaration décide
 *
 * - **La note avant la description** — demandé : sous 3 étoiles, l'avis dit ce
 *   qui a manqué, et cette remarque doit se poser avant qu'on raconte le reste.
 *   La section 1 reste le titre SEUL (`ux-patterns` §0) : la note qualifie
 *   l'avis, elle est donc en section 2, « Nature », avant la Description.
 * - **Paraître sur coprofirst.fr est une DIFFUSION** : un canal qui fait
 *   sortir l'avis de l'application. La question n'apparaît qu'à partir de 4
 *   étoiles, et elle exige une réponse — Oui ou Non, sans réponse par défaut.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireAvis.svelte` — le dépôt et la correction (`sectionPresente`)
 */

import type { EntiteDeclaree } from './types';
import { DIFFUSION_NE_SE_LIT_PAS } from './types';

export const AVIS: EntiteDeclaree = {
	id: 'avis',
	libelle: 'Avis',
	libelleNouveau: 'Donner mon avis',
	libelleModifier: "Modifier l'avis",
	sections: [
		{
			id: 'titre',
			objet: 'Titre',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "La réponse du gestionnaire se rattache à l'avis ; elle ne le réécrit pas.",
				},
			},
		},
		{
			id: 'nature',
			objet: 'NoteEtoiles — la note de 1 à 5 ; sous 3 étoiles, ce qui a manqué',
			titreEcran: ['Note', 'Ce qui vous a manqué'],
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "La réponse du gestionnaire se rattache à l'avis ; elle ne le réécrit pas.",
				},
			},
		},
		{
			id: 'equipement',
			sansObjet: "Un avis porte sur l'application, pas sur le bâti.",
		},
		{
			id: 'suivi',
			sansObjet:
				"Un avis n'a pas d'étapes : il se donne, se corrige, se retire. Ce que le " +
				'gestionnaire en fait — répondre, le retenir pour coprofirst.fr — se fait depuis sa carte.',
		},
		{
			id: 'quand',
			sansObjet: "Un avis ne se passe pas à une date : il date du jour où on l'a donné.",
		},
		{
			id: 'intervenant',
			sansObjet: "Personne n'intervient sur un avis.",
		},
		{
			id: 'perimetre',
			sansObjet: "L'avis porte sur l'application entière, pas sur un lieu de la résidence.",
		},
		{
			id: 'description',
			objet: 'RichEditor — ce que vous en pensez',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "La réponse du gestionnaire se rattache à l'avis ; elle ne le réécrit pas.",
				},
			},
		},
		{
			id: 'pieces_jointes',
			sansObjet: "Un avis se raconte ; une capture d'un problème relève d'une affaire « Bogue ».",
		},
		{
			id: 'affaires_liees',
			sansObjet: "Un avis ne se lie pas à une affaire : un problème s'ouvre en affaire, à part.",
		},
		{
			id: 'au_nom_de',
			sansObjet: "Un avis se donne en son nom — c'est le sien, signé « Prénom N. ».",
		},
		{
			id: 'destinataires',
			sansObjet: 'Un avis se lit de tous les comptes de la copropriété ; il ne se cible pas.',
		},
		{
			id: 'mise_en_avant',
			sansObjet:
				"Un avis ne se met pas en avant : c'est le gestionnaire qui retient ceux qui paraissent.",
		},
		{
			id: 'diffusion',
			objet: "L'accord de l'auteur pour coprofirst.fr — Oui ou Non, à partir de 4 étoiles",
			titreEcran: 'Diffusion sur coprofirst.fr',
			absente: {
				affichage: DIFFUSION_NE_SE_LIT_PAS,
				evolution: {
					motif: 'hérité',
					explication: "La réponse du gestionnaire se rattache à l'avis ; elle ne le réécrit pas.",
				},
			},
			exceptionPliage:
				"Facultative (elle ne vient qu'à 4 étoiles) mais dépliée : quand elle vient, elle " +
				"exige une réponse, et pliée elle cacherait ce qui empêche d'enregistrer.",
		},
	],
};
