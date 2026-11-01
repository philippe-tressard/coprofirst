/**
 * L'ÉQUIPEMENT, déclaré une fois — les sections du cadre, ce qu'elles portent,
 * et pourquoi la plupart sont sans objet (R4).
 *
 * Entité née de #2442 (01/11/2026) : les équipements étaient une énumération du
 * code, ils s'administrent dans Admin › Copropriété › Équipements. Maquette C,
 * arbitrée par l'utilisateur : la fiche, et à côté l'APERÇU en direct (la
 * carte d'un contrat et sa gouttière, le badge d'un prestataire) et ce qui le CITE.
 *
 * ## Ce que la déclaration a fait apparaître
 *
 * Un équipement est une entrée de RÉFÉRENTIEL, comme un périmètre : il ne se
 * date, ne se diffuse, ne se destine à personne. Ses champs se rangent dans
 * cinq sections du cadre — obligatoires : le libellé, et l'icône (qui a toujours
 * une valeur).
 *
 * ⚠️ L'aperçu et le compteur d'usages ne sont PAS des sections : ils ne
 * saisissent rien, ils montrent ce que la saisie produira et ce qu'elle touche.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `ChampsEquipement.svelte` — la saisie (`sectionPresente`, `pliageDe`)
 *   • `CarteEquipement.svelte` — la carte et son crayon (`libelleModifier`)
 */

import type { EntiteDeclaree } from './types';

export const EQUIPEMENT: EntiteDeclaree = {
	id: 'equipement',
	libelle: 'Équipement',
	libelleNouveau: 'Nouvel équipement',
	libelleModifier: 'Modifier l’équipement',
	sections: [
		{
			id: 'titre',
			objet: 'Libellé — le code s’en déduit à la création, puis ne change plus',
			requis: true,
			titreEcran: ['Libellé'],
		},
		{
			//  Ce qui le fait RECONNAÎTRE : l'icône au trait et le mot abrégé de la
			//  gouttière. Ils avaient chacun leur table dans le code (#2442).
			//  Obligatoire, donc dépliée : l'icône a toujours une valeur (la clé par
			//  défaut), et c'est ce que l'aperçu montre d'abord (maquette C).
			id: 'nature',
			objet: 'Icône au trait · abréviation de la gouttière',
			requis: true,
			titreEcran: ['Icône et abréviation'],
		},
		{
			id: 'equipement',
			sansObjet: 'C’est l’objet lui-même : un équipement ne désigne pas un équipement.',
		},
		{
			id: 'suivi',
			sansObjet:
				'Un équipement n’a pas d’états : il est proposé à la saisie, ou retiré — et ' +
				'le retrait est un geste de la carte (📦), comme pour un contrat.',
		},
		{
			id: 'quand',
			sansObjet: 'Un référentiel ne se date pas.',
		},
		{
			id: 'intervenant',
			sansObjet:
				'L’intervenant d’un équipement se lit sur ses CONTRATS en cours — l’affaire le ' +
				'propose de là (`intervenantPropose`). Le saisir ici ferait une seconde source.',
		},
		{
			//  🔴 Le lien demandé (#2442) : choisir l'un, dans une affaire, propose
			//  l'autre. Facultatif — un équipement qui n'a pas de lieu (la
			//  plomberie, l'assurance) n'en porte aucun.
			id: 'perimetre',
			objet: 'Périmètres où se trouve l’équipement (plusieurs)',
			titreEcran: ['Périmètres concernés'],
			pliee: true,
		},
		{
			id: 'description',
			objet: 'Texte libre — ce qu’il faut savoir de l’équipement',
			titreEcran: ['Description'],
			pliee: true,
		},
		{
			id: 'pieces_jointes',
			sansObjet: 'Les documents d’un équipement appartiennent à ses CONTRATS et à ses affaires.',
		},
		{
			id: 'affaires_liees',
			sansObjet: 'Ce sont les affaires qui désignent leur équipement, pas l’inverse.',
		},
		{
			id: 'au_nom_de',
			sansObjet: 'Un référentiel s’administre, il ne se saisit pas pour un tiers.',
		},
		{
			id: 'destinataires',
			requis: true,
			sansObjet:
				'Personne n’est destinataire d’un référentiel : tout le monde le LIT, seul ' +
				'l’administrateur l’écrit — c’est la route qui en décide.',
		},
		{
			//  Le RANG dans les sélecteurs : ce qui met un équipement en avant d'un
			//  autre dans la liste qu'on parcourt.
			id: 'mise_en_avant',
			objet: 'Rang dans les sélecteurs',
			titreEcran: ['Ordre'],
			pliee: true,
		},
		{
			id: 'diffusion',
			sansObjet: 'Ajouter un équipement n’est pas un événement : rien à annoncer.',
		},
	],
};
