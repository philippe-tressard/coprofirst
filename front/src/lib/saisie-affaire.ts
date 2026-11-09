/**
 * **La saisie d'une affaire : Essentielle ou Complète** (#2595, 08/11/2026).
 *
 * ## Ce que c'est
 *
 * Le même formulaire, montré de deux façons. **Complète** : toutes les sections, à
 * leur rang. **Essentielle** : les champs qu'il faut ; les autres se rangent dans
 * un groupe plié en fin de formulaire, « Plus de détails », et partent à leur
 * valeur par défaut. La charge utile ne change pas (`chargeUtileAffaire`).
 *
 * ## Qui décide du mode
 *
 * Le SERVEUR : `UserRead.saisie_affaire_effective` (`api/app/utils/saisie_affaire`),
 * le choix du profil sinon Essentielle, pour tous. Ce module le LIT, il ne le dérive pas
 * (`standards/09` §8, `lint:regles-partagees`).
 *
 * ## Les sections essentielles — une table, deux écritures
 *
 * `SECTIONS_ESSENTIELLES_PAR_CATEGORIE` est la copie de la table du serveur, servie
 * aussi par `GET /tickets/referentiels` à l'app iOS. Le front ne charge pas ce
 * référentiel (comme `tickets-categories.ts`, il se déclare) : 🔒
 * `test_saisie_affaire_concordance.py` les compare, dans les deux sens.
 *
 * ## Une section éteinte ne se range pas
 *
 * Une section que la nature, le rôle ou la catégorie ÉTEINT (`inactives`) n'a pas
 * d'objet ici : elle n'entre pas dans le groupe, au lieu d'y paraître grisée.
 * L'arbitrage n° 51 (grisée à son rang) vaut pour la saisie Complète.
 */
import { auth as authApi, type Ticket } from '#lib/api/index.ts';
import { currentUser, setUser } from '#lib/stores/auth.ts';
import { tenter } from '#lib/erreurs.ts';
import { get } from 'svelte/store';
import { sectionsDe, type Etat, type IdSection } from '#lib/entites/types.ts';
import { TICKET } from '#lib/entites/ticket.ts';
import { sectionsInactives } from '#lib/formulaire-affaire.ts';
import { modeDepuis } from '#lib/saisi-pour.ts';
import { concerneTousLesResidents } from '#lib/destinataires.ts';

export type ModeSaisie = 'essentielle' | 'complete';

/** Ce que le profil enregistre : l'un des deux modes. Sans choix, l'API sert Essentielle. */
export type ChoixSaisie = ModeSaisie;

/** Toujours montrées, quelle que soit la catégorie. */
export const SECTIONS_DE_BASE: readonly IdSection[] = [
	'titre',
	'nature',
	'perimetre',
	'description',
];

/**
 * Ce que chaque catégorie ajoute. Absente de la table = n'ajoute rien (question,
 * bogue). Le pourquoi de chaque ligne est celui du serveur
 * (`SECTIONS_ESSENTIELLES_PAR_CATEGORIE`) : la photo est la preuve d'une panne ou
 * d'un dégât ; une visite ou un dossier a une date ; une actualité dit quand, à qui,
 * par où.
 */
export const SECTIONS_ESSENTIELLES_PAR_CATEGORIE: Readonly<Record<string, readonly IdSection[]>> = {
	panne: ['pieces_jointes', 'mise_en_avant'],
	sinistre: ['pieces_jointes', 'mise_en_avant'],
	nuisance: ['pieces_jointes'],
	espaces_verts: ['pieces_jointes'],
	acces_accueil: ['pieces_jointes'],
	entretien: ['quand'],
	etude_travaux: ['quand'],
	actualite: ['quand', 'destinataires', 'diffusion'],
};

/** Les entrées du sélecteur du Profil, dans leur ordre d'affichage. */
export const OPTIONS_SAISIE: readonly { val: ChoixSaisie; label: string; desc: string }[] = [
	{ val: 'essentielle', label: 'Essentielle', desc: 'Les champs qu’il faut, rien de plus' },
	{ val: 'complete', label: 'Complète', desc: 'Toutes les sections, pour qualifier et suivre' },
];

/** La phrase discrète du formulaire — elle dit le mode et où le changer. */
export const LIBELLE_MODE: Readonly<Record<ModeSaisie, string>> = {
	essentielle: 'Saisie essentielle',
	complete: 'Saisie complète',
};

/** Ce mode est-il celui qui range des sections dans « Plus de détails » ? */
export const estEssentielle = (mode: string | undefined | null): boolean => mode === 'essentielle';

/** La section est-elle essentielle pour cette catégorie ? */
export function sectionEssentielle(id: IdSection, categorie: string): boolean {
	return (
		SECTIONS_DE_BASE.includes(id) ||
		(SECTIONS_ESSENTIELLES_PAR_CATEGORIE[categorie] ?? []).includes(id)
	);
}

/**
 * Les sections rangées dans « Plus de détails », dans l'ordre du cadre.
 *
 * Vide en saisie Complète. En Essentielle : les sections de cet état qui ne sont
 * pas essentielles pour la catégorie, hors celles que la nature ou le rôle éteint.
 */
export function sectionsRepliees(
	mode: string | undefined | null,
	etat: Etat,
	categorie: string,
	estCS: boolean,
): IdSection[] {
	if (!estEssentielle(mode)) return [];
	const eteintes = sectionsInactives(etat, categorie, estCS);
	return sectionsDe(TICKET, etat)
		.map((s) => s.id)
		.filter((id) => !sectionEssentielle(id, categorie) && !eteintes[id]);
}

/**
 * Les sections rangées dont l'affaire PORTE une valeur autre que le défaut — celles
 * qui rouvrent le groupe : une correction ne cache jamais ce qui a été saisi.
 *
 * Lu sur l'affaire enregistrée, une fois à l'ouverture. La Diffusion n'y figure pas :
 * un envoi ne s'enregistre pas sur l'affaire.
 */
export function sectionsRenseignees(ticket: Ticket | null): IdSection[] {
	if (!ticket) return [];
	const renseignees: [IdSection, boolean][] = [
		['equipement', !!ticket.equipement],
		['suivi', !!ticket.statut && ticket.statut !== 'ouvert' && ticket.statut !== 'publie'],
		['quand', !!(ticket.debut || ticket.fin || ticket.frequence_type)],
		['intervenant', !!(ticket.prestataire_id || ticket.contrat_id)],
		['affaires_liees', !!ticket.affaires_liees?.length],
		['au_nom_de', modeDepuis(ticket) !== 'moi'],
		[
			'destinataires',
			!!ticket.confidentiel ||
				!!(ticket.public_cible?.length && !concerneTousLesResidents(ticket.public_cible)),
		],
		['mise_en_avant', !!ticket.epingle],
	];
	return renseignees.filter(([, oui]) => oui).map(([id]) => id);
}

/**
 * Où va chaque section en saisie Essentielle : `replies` (dans « Plus de détails »),
 * `masquees` (éteintes, ni montrées ni rangées) et `ouvert` (une correction ne cache
 * jamais ce qu'elle porte : le groupe s'ouvre d'office si une section rangée est remplie).
 */
export function repartition(
	mode: string | undefined | null,
	etat: Etat,
	categorie: string,
	estCS: boolean,
	ticket: Ticket | null,
): { replies: IdSection[]; masquees: IdSection[]; ouvert: boolean } {
	const replies = sectionsRepliees(mode, etat, categorie, estCS);
	const masquees = estEssentielle(mode)
		? (Object.keys(sectionsInactives(etat, categorie, estCS)) as IdSection[]).filter(
				(id) => !replies.includes(id),
			)
		: [];
	return {
		replies,
		masquees,
		ouvert: sectionsRenseignees(ticket).some((id) => replies.includes(id)),
	};
}

/**
 * Enregistre le choix sur le COMPTE (pour tous les appareils) et met l'utilisateur en
 * mémoire à jour — avec le mode effectif que l'API recalcule. `false` si le serveur refuse
 * (l'erreur est déjà montrée) : le compte n'a pas changé.
 */
export async function enregistrerSaisie(voulu: ChoixSaisie): Promise<boolean> {
	if (!get(currentUser)) return false;
	return tenter(
		async () => setUser(await authApi.updateMe({ saisie_affaire: voulu })),
		undefined,
		'Le réglage de la saisie n’a pas pu être enregistré',
	);
}
