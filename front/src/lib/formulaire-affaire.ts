/**
 * **Le formulaire unique d'une affaire** — ce qu'il envoie, et ce qu'il éteint.
 *
 * ## Pourquoi ce module (23/09/2026, arbitré à l'écran avec maquette)
 *
 * Demandé : *« un seul “+ Nouvelle affaire” comprenant toutes les sections
 * Affaires et Actualités, avec une nouvelle catégorie Actualité qui apparaît en
 * premier ; selon le choix de la catégorie, les sections peuvent changer —
 * grisées, pliées, inactives et sans données pour celles inappropriées »*.
 *
 * `FormulaireTicket` et `FormulaireActualite` n'en font plus qu'un. Ce que la
 * NATURE de l'affaire change — quelles sections sont actives, quels champs
 * partent — s'écrit ici, pur et sans écran, et non en `{#if}` dispersés dans
 * le composant : c'est la même question posée à l'affichage et à l'envoi, et
 * deux écritures divergeraient au premier changement.
 *
 * ## « Sans données »
 *
 * Une section inactive n'est pas seulement grisée : ce qu'elle portait NE PART
 * PAS. `chargeUtileAffaire` n'emporte que ce que la nature appelle, et efface
 * ce qu'elle n'appelle plus (le public visé d'une actualité devenue affaire
 * suivie, le 🛡️ d'une affaire devenue actualité) — sinon l'objet garderait en
 * base une valeur qu'aucun écran ne montre plus.
 */
import { nombreOuNull } from '#lib/utils.ts';
import type { Ticket } from '#lib/api/index.ts';
import type { ConditionInactive, Etat, IdSection, NatureAffaire } from '#lib/entites/types.ts';
import { motifInactif } from '#lib/entites/types.ts';
import { TICKET } from '#lib/entites/ticket.ts';
import { concerneTousLesResidents } from '#lib/destinataires.ts';
import { lectureDe, titreLecture } from '#lib/lecture.ts';
import { lectureDuTicket, natureLue, perimetreRestreint } from '#lib/lecture-ticket.ts';
import { depuisChampLocal } from '#lib/date.ts';
import { lotDepuisSaisie, type SaisieSaisiPour } from '#lib/saisi-pour.ts';
import { CATEGORIES_TICKET, estActualite, optionsVersTicket } from '#lib/tickets.ts';
import { typeEquipementDuContrat } from '#lib/reporting.ts';
import type { ContratEnCours } from '#lib/prestataires.ts';
import type { Equipement } from '#lib/equipements.ts';

/** La nature d'une catégorie : Actualité informe, toute autre se suit. */
export function natureDe(categorie: string): NatureAffaire {
	return estActualite({ categorie }) ? 'actualite' : 'suivie';
}

/** Ce que l'affaire EST, pour sa Suite 🔄 — sa nature (`sectionDeLaSuite`). */
export function conditionsDeLaSuite(ticket: { categorie: string } | null): ConditionInactive[] {
	//  Les MÊMES que la création (#1321) : la Suite d'un bogue éteignait ni son
	//  Périmètre ni sa Diffusion, que la déclaration dit inactifs.
	return ticket ? conditionsDe(ticket.categorie) : [];
}

/** Les sections que la nature éteint — celles qui ont un motif déclaré. */
const SECTIONS_ETEIGNABLES: readonly IdSection[] = [
	'equipement',
	'suivi',
	'quand',
	'intervenant',
	'perimetre',
	'affaires_liees',
	'au_nom_de',
	'destinataires',
	'mise_en_avant',
	'diffusion',
];

/** Une catégorie du bâti — celles du carnet, au liseré doré (`carnet`). */
export function estBati(categorie: string): boolean {
	return CATEGORIES_TICKET.some((c) => c.value === categorie && c.carnet);
}

/** La catégorie d'un bogue du site : au gestionnaire seul (#1191). */
export const CATEGORIE_BUG = 'bug';

/**  Le paramètre qui ouvre la boîte de création d'une affaire sur UNE catégorie —
 *   l'avis sur l'application renvoie un problème vers un bogue (#2075). */
const PARAM_CATEGORIE = 'categorie';

/** L'adresse qui ouvre « + Nouvelle affaire » sur cette catégorie. */
export function lienNouvelleAffaire(categorie: string): string {
	return `/tickets?nouveau=1&${PARAM_CATEGORIE}=${encodeURIComponent(categorie)}`;
}

/** La catégorie demandée par l'adresse, si elle existe — `''` sinon. */
export function categorieDuLien(params: URLSearchParams): string {
	const demandee = params.get(PARAM_CATEGORIE) ?? '';
	return CATEGORIES_TICKET.some((c) => c.value === demandee) ? demandee : '';
}

/** La catégorie de la récurrence : un Entretien seul se répète (#1092). */
export const CATEGORIE_ENTRETIEN = 'entretien';

/**  Ce qui éteint des sections, pour cette catégorie et ce rôle — la création,
 *   la correction ET la Suite (#1321). */
export function conditionsDe(categorie: string, estCS = true): ConditionInactive[] {
	//  Dans l'ordre : la nature, puis le rôle, puis la catégorie (`motifInactif`).
	const conditions: ConditionInactive[] = [natureDe(categorie)];
	//  Le bogue d'abord : son motif dit mieux pourquoi que celui du rôle (#1191).
	if (categorie === CATEGORIE_BUG) conditions.push('bug');
	if (!estCS) conditions.push('resident');
	if (categorie && !estBati(categorie)) conditions.push('horsBati');
	return conditions;
}

/** Le motif de chaque section inactive, pour cet état, cette catégorie et ce rôle. */
export function sectionsInactives(
	etat: Etat,
	categorie: string,
	estCS = true,
): Partial<Record<IdSection, string>> {
	const conditions = conditionsDe(categorie, estCS);
	const inactives: Partial<Record<IdSection, string>> = {};
	for (const id of SECTIONS_ETEIGNABLES) {
		const motif = motifInactif(TICKET, etat, id, conditions);
		if (motif) inactives[id] = motif;
	}
	return inactives;
}

/** Tout ce que l'écran a saisi — la charge utile en est DÉRIVÉE, jamais recopiée. */
export interface SaisieAffaire {
	titre: string;
	description: string;
	assisteIA: boolean;
	categorie: string;
	statut: string;
	options: {
		epingle: boolean;
		urgente: boolean;
		brouillon: boolean;
		suiviKanban: boolean;
		suiviActualite?: boolean;
		etatSuivi?: string | null;
	};
	perimetreCible: string[];
	publicCible: string[];
	reservePerimetre: boolean;
	debut: string;
	fin: string;
	photosUrls: string[];
	fichiersUrls: string[];
	/** Les affaires liées retenues (#1342) — seuls leurs `id` partent. */
	affairesLiees: { id: number }[];
	destinataireSyndic: boolean;
	destinataireCs: boolean;
	partagerWhatsapp: boolean;
	envoyerAuteur: boolean;
	annonceHall: boolean;
	saisiPour: SaisieSaisiPour;
	prestataireId: number | null;
	/** Le contrat qui cadre l'intervention, `null` hors contrat (#1445). */
	contratId: number | null;
	/** Le code d'un équipement, ou `''` — posé par le conseil (#1097). */
	equipement: string;
	frequenceType: string;
	frequenceValeur: number | string | null;
}

/**
 * Ce que le formulaire envoie — à la création (`POST`) comme à la correction
 * (`PATCH`).
 *
 * ⚠️ Les droits ne se décident pas ici : le serveur refuse ou ignore ce qu'un
 * résident n'a pas le droit de poser. Ce module évite seulement d'envoyer ce
 * qui ferait échouer une correction légitime (un 403 sur `confidentiel`).
 *
 * 🔴 L'URGENCE part pour TOUT LE MONDE. Elle ne partait que pour le conseil à
 * la création : un résident cochait 🚨, l'avertissement « 15 · 17 · 18 »
 * s'affichait, et l'affaire arrivait en priorité normale — alors que le
 * serveur l'accepte de lui depuis #820. Trouvé en écrivant ce module.
 */
export function chargeUtileAffaire(
	s: SaisieAffaire,
	contexte: { creation: boolean; estCS: boolean },
): Record<string, unknown> {
	const actualite = natureDe(s.categorie) === 'actualite';
	const charge: Record<string, unknown> = {
		titre: s.titre.trim(),
		description: s.description,
		categorie: s.categorie,
		perimetre_cible: s.perimetreCible,
		photos_urls: s.photosUrls,
		fichiers_urls: s.fichiersUrls,
		urgente: s.options.urgente,
		//  « Je n'en dis rien » en correction : la marque ne s'efface pas.
		assiste_ia: contexte.creation ? s.assisteIA : s.assisteIA || undefined,
	};
	//  La diffusion part à la création pour tous (le serveur trie), et en
	//  correction pour le conseil seul — il est le seul à la voir rouverte.
	if (contexte.creation || contexte.estCS) {
		Object.assign(charge, {
			destinataire_syndic: s.destinataireSyndic,
			destinataire_cs: s.destinataireCs,
			partager_whatsapp: s.partagerWhatsapp,
		});
	}
	if (contexte.creation) charge.envoyer_auteur = s.envoyerAuteur;
	if (!contexte.estCS) return charge;
	//  Le conseil seul relie (30/09/2026) — le serveur refuse un lien posé par un
	//  autre ; ne pas l'envoyer évite ce 403 sur une correction légitime. Il ne
	//  remplace que les liens que le lecteur VOIT (#1342).
	charge.affaires_liees = s.affairesLiees.map((a) => a.id);

	Object.assign(charge, lotDepuisSaisie(s.saisiPour));
	//  « Quand » se planifie par le conseil seul (23/09/2026) : un autre ne
	//  l'envoie pas — la section lui est éteinte, le serveur l'ignorerait.
	Object.assign(charge, { debut: depuisChampLocal(s.debut), fin: depuisChampLocal(s.fin) });
	//  Intervenant et récurrence : envoyés à vide hors de leur catégorie — le
	//  serveur les efface de toute façon (`utils/intervenant`), l'écran le dit.
	//  Sous contrat, le rythme est celui du contrat (#1445) : il ne part pas.
	const entretien = s.categorie === CATEGORIE_ENTRETIEN && s.contratId === null;
	Object.assign(charge, {
		prestataire_id: estBati(s.categorie) ? s.prestataireId : null,
		contrat_id: estBati(s.categorie) ? s.contratId : null,
		equipement: estBati(s.categorie) ? s.equipement || null : null,
		frequence_type: entretien && s.frequenceType ? s.frequenceType : null,
		frequence_valeur: entretien && s.frequenceType ? nombreOuNull(s.frequenceValeur) : null,
	});
	if (actualite) {
		//  Pas de cycle : ni état ni kanban — effacés s'ils venaient d'une
		//  affaire suivie (son suivi, optionnel, est un repère à part). À qui l'on parle, l'Accès, l'affiche, oui — et 🛡️
		//  « Confidentielle », en tête de Destinataires pour les deux natures
		//  depuis le 25/09/2026 (le serveur l'honorait déjà : `ticket_visible`).
		Object.assign(charge, {
			epingle: s.options.epingle,
			confidentiel: s.options.brouillon,
			suivi_kanban: false,
			//  🔁 Son suivi, optionnel (10/10/2026) : la case du conseil, que le
			//  serveur lui réserve. L'état se change par une Suite.
			suivre_actualite: !!s.options.suiviActualite,
			suivi_actualite: (s.options.suiviActualite && s.options.etatSuivi) || undefined,
			public_cible: concerneTousLesResidents(s.publicCible) ? [] : s.publicCible,
			reserve_perimetre: s.reservePerimetre,
			annonce_hall: s.annonceHall,
		});
	} else {
		//  Une affaire suivie : son état, ses options et ses Destinataires — vides
		//  quand le conseil n'a rien changé à ceux de sa nature (#1343) — et sa
		//  réserve au périmètre, cochable depuis le 22/10/2026 (elle était
		//  montrée cochée mais partait `false` : la case ne protégeait rien).
		//  ⚠️ Une actualité repassée en suivi porte encore `publie`, que le
		//  serveur refuse à une affaire suivie (422) : elle repart « Ouvert ».
		Object.assign(charge, optionsVersTicket(s.options), {
			statut: s.statut === 'publie' ? 'ouvert' : s.statut,
			public_cible: s.publicCible,
			reserve_perimetre: s.reservePerimetre,
		});
	}
	return charge;
}

/**
 * Ce qu'une correction EFFACE en changeant la nature de l'affaire — à dire
 * avant d'enregistrer (arbitré le 23/09/2026 : catégorie modifiable, données
 * des sections devenues inappropriées effacées après confirmation).
 *
 * Vide quand la nature ne change pas, ou quand il n'y avait rien à perdre.
 */
export function pertesAuChangement(avant: Ticket, apres: SaisieAffaire): string[] {
	const pertes: string[] = [];
	if (avant.prestataire_id && !estBati(apres.categorie)) pertes.push('l’intervenant');
	if (avant.equipement && !estBati(apres.categorie)) pertes.push('l’équipement');
	if (avant.contrat_id && !estBati(apres.categorie)) pertes.push('le contrat');
	if (avant.frequence_type && apres.categorie !== CATEGORIE_ENTRETIEN) pertes.push('la récurrence');
	const etait = natureDe(avant.categorie);
	if (etait === natureDe(apres.categorie)) return pertes;
	//  Le public visé n'est plus perdu (#1343) : une affaire a ses Destinataires,
	//  et ceux que l'écran montre sont ceux qui partent.
	if (etait === 'actualite') {
		if (avant.suivi_actualite) pertes.push('le suivi de l’actualité');
	} else {
		pertes.push('l’état de suivi');
		if (avant.suivi_kanban) pertes.push('l’inscription au kanban');
	}
	return pertes;
}

/**
 * Qui lira l'affaire APRÈS la correction, s'il change — `null` sinon.
 *
 * 🔴 Arbitré le 29/09/2026 : *« en édition, toutes les sections éditables à la
 * création sont modifiables, et l'application est rétroactive sur tout le fil,
 * avec une alerte »*. Les droits sont ceux de l'AFFAIRE (TK-124285) : changer
 * ses Destinataires, sa confidentialité, son périmètre ou sa catégorie change
 * qui lit l'affaire ET toutes ses suites, déjà écrites comprises. La Suite
 * l'écrit dans le fil (`visibility/trace_droits.py`) ; la correction le dit
 * AVANT d'enregistrer. Comparé sur la pastille de lecture — la même phrase
 * que la carte —, jamais sur les champs : une catégorie changée peut changer
 * les lecteurs sans qu'un seul Destinataire ait bougé.
 */
export function changementDeLecture(avant: Ticket, apres: SaisieAffaire): string | null {
	const ancienne = titreLecture(lectureDuTicket(avant));
	const nouvelle = titreLecture(
		lectureDe({
			...natureLue({ categorie: apres.categorie, statut: apres.statut }),
			confidentiel: apres.options.brouillon,
			publicCible: apres.publicCible,
			perimetreRestreint: perimetreRestreint(apres.perimetreCible),
			reservePerimetre: apres.reservePerimetre,
		}),
	);
	return ancienne === nouvelle ? null : `« ${ancienne} » → « ${nouvelle} »`;
}

/**
 * L'alerte d'une correction : ce qu'elle efface (`pertesAuChangement`) et qui
 * lira désormais (`changementDeLecture`) — une seule boîte, `null` si rien.
 */
export function alerteCorrection(
	avant: Ticket,
	apres: SaisieAffaire,
): { titre: string; message: string } | null {
	const pertes = pertesAuChangement(avant, apres);
	const lecture = changementDeLecture(avant, apres);
	if (!pertes.length && !lecture) return null;
	const phrases: string[] = [];
	if (pertes.length) phrases.push(`Ce changement de catégorie efface ${pertes.join(', ')}.`);
	if (lecture)
		phrases.push(
			`Qui la lit change : ${lecture}. Cela vaut pour toute l’affaire et tout son fil, ` +
				'suites déjà écrites comprises.',
		);
	const nature = natureDe(apres.categorie) === natureDe(avant.categorie);
	return {
		titre: nature
			? 'Changer qui la lit'
			: natureDe(apres.categorie) === 'actualite'
				? 'En faire une actualité'
				: 'En faire une affaire suivie',
		message: phrases.join(' '),
	};
}

/**
 * L'intervenant que l'équipement PROPOSE (#1097) : le prestataire d'un contrat
 * actif qui couvre cet équipement — « Toiture » propose le couvreur sous
 * contrat. `null` sans contrat : on ne devine pas. Le contrat est proposé avec
 * lui (#1445) : c'est lui qui a fait proposer le prestataire.
 *
 * ⚠️ Une proposition, jamais une décision : l'écran ne l'applique que si aucun
 * intervenant n'est déjà désigné, et le conseil la change d'un geste.
 * L'équipement d'un contrat se lit par `typeEquipementDuContrat` — la règle de
 * tous les écrans, « autre » laissant parler la spécialité du prestataire.
 */
export function intervenantPropose(
	equipement: string,
	contrats: ContratEnCours[],
	prestataires: { id: number; specialite?: string | null }[],
	//  Déjà désigné : rien n'est proposé — la règle que les deux appelants
	//  recopiaient chacun devant l'appel.
	designe: number | null = null,
): { prestataireId: number; contratId: number } | null {
	if (!equipement || designe !== null) return null;
	const contrat = contrats.find(
		(c) => c.actif !== false && typeEquipementDuContrat(c, prestataires) === equipement,
	);
	return contrat ? { prestataireId: contrat.prestataire_id, contratId: contrat.id } : null;
}

/**
 * Le périmètre qu'un ÉQUIPEMENT propose (#2442) : le seul périmètre où il se
 * trouve, quand celui de l'affaire est encore le défaut. Plusieurs (Ascenseur A,
 * Ascenseur B) : rien — on ne devine pas lequel.
 *
 * ⚠️ Une proposition, comme celle de l'intervenant : jamais par-dessus un
 * périmètre déjà choisi, et le conseil la défait d'un geste.
 */
export function perimetrePropose(
	equipement: string,
	perimetre: readonly string[],
	estDefaut: (codes: string[]) => boolean,
	equipements: readonly Pick<Equipement, 'code' | 'perimetres'>[],
): string[] | null {
	if (!equipement || !estDefaut([...perimetre])) return null;
	const lieux = equipements.find((e) => e.code === equipement)?.perimetres ?? [];
	return lieux.length === 1 ? [lieux[0]] : null;
}

/**
 * L'équipement qu'un PÉRIMÈTRE propose (#2442) : le seul équipement proposé aux
 * affaires qui s'y trouve, quand aucun n'est encore désigné. « Bât. A ›
 * Ascenseur » propose l'ascenseur ; un périmètre qui en porte plusieurs, ou
 * aucun, ne propose rien.
 */
export function equipementPropose(
	perimetre: readonly string[],
	equipement: string,
	equipements: readonly Pick<Equipement, 'code' | 'actif' | 'pour_affaires' | 'perimetres'>[],
): string | null {
	if (equipement || perimetre.length !== 1) return null;
	const candidats = equipements.filter(
		(e) => e.actif && e.pour_affaires && e.perimetres.includes(perimetre[0]),
	);
	return candidats.length === 1 ? candidats[0].code : null;
}
