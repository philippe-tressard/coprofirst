/**
 * Le PRESTATAIRE, déclaré une fois — les sections du cadre, ce qu'elles portent, et
 * chaque divergence entre états avec son motif (R4).
 *
 * Huitième entité du cadre #430, déclarée le 12/09/2026 avec le contrat, sur le
 * même signalement (#910).
 *
 * ## Ce que la déclaration a fait apparaître
 *
 * ⚠️ Depuis le 25/09/2026 (#1327), la fiche porte une DESCRIPTION — demandée à
 * l'écran (« un champ commentaire aussi à l'entreprise ») — et l'adresse de
 * l'entreprise, dans les Contacts. Le paragraphe ci-dessous dit l'état d'avant.
 *
 * 🔴 **Six sections sur neuf sont sans objet.** Un prestataire n'est pas un
 * événement de la copropriété : c'est une entrée de carnet d'adresses. Rien à
 * situer, rien à diffuser, rien à dater — et c'est exactement pour cela que la
 * déclaration valait la peine : sans elle, on aurait pu croire qu'il manquait un
 * périmètre ou une description, alors que leur absence est la bonne réponse.
 *
 * ⚠️ La différence avec le CONTRAT est instructive : le contrat, lui, a un
 * périmètre (ce qu'il entretient) et une description (sa synthèse). Deux objets
 * voisins, deux formes — et le cadre rend la différence lisible au lieu de la
 * laisser à l'appréciation de l'écran.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `ChampsPrestataire.svelte` — la saisie (`sectionPresente`)
 */

import type { EntiteDeclaree } from './types';

export const PRESTATAIRE: EntiteDeclaree = {
	id: 'prestataire',
	libelle: 'Prestataire',
	libelleNouveau: 'Nouveau prestataire',
	libelleModifier: 'Modifier le prestataire',
	sections: [
		{
			id: 'titre',
			objet: 'Nom',
			requis: true,
			titreEcran: ['Nom'],
		},
		{
			//  🔴 Les sections STANDARD (24/09/2026, signalé à l'écran : « Prendre
			//  exemple sur l'UX d'Affaires »). « L'entreprise » mêlait le type, la
			//  spécialité et le courriel ; le type est la CATÉGORIE de l'entreprise,
			//  comme celle d'une affaire.
			id: 'nature',
			objet: 'Type',
			requis: true,
			titreEcran: ['Catégorie'],
		},
		{
			//  🔴 La « Spécialité » ÉTAIT l'équipement (24/09/2026, question posée à
			//  l'écran : « spécialité c'est équipement ? ») — même liste
			//  (les équipements, administrés depuis #2442), et le carnet s'en sert quand un contrat n'en
			//  désigne pas. Elle prend le nom et le rang de la section qui le porte
			//  partout ailleurs.
			id: 'equipement',
			objet: 'Équipement dont l’entreprise s’occupe',
			requis: true,
		},
		{
			id: 'suivi',
			sansObjet:
				"Un prestataire n'a pas d'états : il est référencé, ou il ne l'est plus. " +
				"L'archivage suffit, et il se fait d'un geste sur la carte — pas d'une " +
				'colonne à déplacer.',
		},
		{
			id: 'quand',
			sansObjet: "un prestataire est une fiche d'annuaire, pas un fait daté",
		},
		{
			//  Les personnes à joindre, le courriel et l'adresse de l'entreprise.
			//  🔴 FACULTATIVE depuis le 25/09/2026 (#1327), arbitré à l'écran : « le
			//  contact ne doit pas être obligatoire ». #1229 l'exigeait la veille.
			id: 'intervenant',
			objet: 'Courriel · adresse · contacts (prénom, nom, fonction · téléphone, courriel)',
			titreEcran: ['Contacts'],
			exceptionPliage:
				"Facultative mais DÉPLIÉE (arbitré le 25/09/2026, #1327) : une fiche d'annuaire " +
				"se lit par ses contacts, et c'est le premier geste après le nom — la plier " +
				'cacherait ce que la fiche sert à trouver.',
		},
		{
			id: 'perimetre',
			sansObjet:
				"Une entreprise n'est attachée à aucun lieu de la copropriété : c'est son " +
				"CONTRAT qui porte ce qu'elle entretient, et lui seul (déclaré dans " +
				'`entites/contrat`). Donner un périmètre au prestataire ferait deux endroits ' +
				'où le lire, donc deux occasions de les désaccorder.',
		},
		{
			//  🔴 ROUVERTE le 25/09/2026 (#1327) — « un champ commentaire aussi à
			//  l'entreprise ». Elle était déclarée sans objet : le type et
			//  l'équipement devaient suffire. Ce que l'écran a montré, c'est ce qu'ils
			//  ne disent pas (horaires, modalités, particularités). La NOTE garde le
			//  jugement ; la description dit ce qu'il faut savoir. Avec l'assistant ✨.
			id: 'description',
			objet: 'RichEditor — ce qu’il faut savoir de l’entreprise',
			pliee: true,
		},
		{
			id: 'pieces_jointes',
			sansObjet:
				"Un carnet d'adresses ne se photographie pas, et les documents appartiennent " +
				'au CONTRAT — le contrat signé, ses avenants, ses conditions générales. Les ' +
				"rattacher à l'entreprise les détacherait de ce qu'ils engagent.",
		},
		{
			id: 'affaires_liees',
			sansObjet:
				'Un carnet d’adresses ne se lie pas à une affaire : c’est l’affaire qui ' +
				'désigne son intervenant (#1342).',
		},
		{
			id: 'au_nom_de',
			sansObjet: 'Un carnet d’adresses se tient, il ne se saisit pas pour un tiers.',
		},
		{
			id: 'destinataires',
			//  🔴 OBLIGATOIRE, donc DÉPLIÉE (22/09/2026, signé à l'écran deux fois).
			//
			//  L'astérisque était écrite en dur par `SectionDestinataires` : la
			//  déclaration ne savait donc pas que la section était obligatoire, et
			//  `lint:etats` — qui CALCULE le pliage à partir d'elle — ne voyait
			//  aucune contradiction à la déclarer pliée. L'écran affichait donc
			//  « DESTINATAIRES* » sur une ligne fermée, ce que la règle interdit.
			requis: true,
			sansObjet:
				"Personne n'est destinataire d'une fiche de carnet d'adresses. Qui la " +
				'consulte relève des droits, pas de la saisie — la sécurité est centralisée.',
		},
		{
			id: 'mise_en_avant',
			sansObjet: 'Une fiche d’annuaire ne se met pas en avant : l’annuaire se lit par recherche.',
		},
		{
			id: 'diffusion',
			sansObjet:
				"Référencer une entreprise n'est pas un événement : rien à annoncer, ni au " +
				'syndic, ni au conseil syndical, ni sur WhatsApp.',
		},
	],
};
