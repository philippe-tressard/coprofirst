/**
 * **Qui LIT une affaire ou une actualité** — la pastille de lecture, calculée
 * une fois (lot 1, arbitré le 25/09/2026, maquette « Anneau de lecture »).
 *
 * ## Le besoin
 *
 * > « cet état est important pour connaître qui peut le voir (forcément le
 * >   lecteur, mais qui d'autre ?) »
 *
 * La réponse était éparpillée : la case 🔒 du Périmètre, les pastilles de
 * Destinataires, la case 🛡️ de Mise en avant — plus des règles du serveur que
 * rien n'affichait (une affaire n'est pas lue des locataires). La pastille les
 * RÉSUME en un seul objet : une ou des icônes, un libellé court (carte) ou long
 * (section), et le cadenas quand le périmètre est réservé.
 *
 * ## Trois restrictions, pas une de plus
 *
 * 1. **Confidentielle** — le conseil syndical seul. Elle passe outre tout le
 *    reste : une seule pastille « CS ».
 * 2. **Périmètre réservé** — oui ou non. LEQUEL, le 🔹 d'à côté le dit déjà.
 * 3. **Profils** — ceux que Destinataires vise (actualité), ou la règle des
 *    affaires : tous sauf les locataires.
 *
 * ⚠️ **Ce n'est qu'un résumé : c'est le serveur qui décide** (`ticket_visible`).
 * Les deux écritures sont tenues par UNE attente,
 * `api/tests/donnees/lecture_pastille.json` : `test_lecture_pastille.py`
 * l'exécute contre la règle, `npm run lint:lecture` contre ce fichier. Une
 * pastille qui annoncerait « Tous » là où les locataires ne lisent pas mentirait
 * à chaque lecteur, sans que rien casse — d'où le contrôle.
 *
 * 🔴 Ce module n'importe que `$lib/destinataires` et les états de
 * `$lib/tickets` : il doit s'exécuter HORS du site, dans le contrôle. Le périmètre lui arrive donc déjà tranché
 * (`perimetreRestreint`) — l'arbre des périmètres est un état chargé à
 * l'exécution, que le contrôle n'a pas.
 */
import {
	TOUS_LES_RESIDENTS,
	codesDestinataires,
	concerneTousLesResidents,
	reserveAuConseil,
} from '$lib/destinataires';
import { STATUTS_ETUDE_OUVERTE } from '$lib/tickets';

/**
 * Les PROFILS de lecteurs, au pluriel — la nomenclature arbitrée le 25/09/2026
 * (`ux-patterns` §2 bis). L'ordre est celui de l'affichage.
 *
 * `statut` est celui du compte (`StatutUtilisateur`) : c'est par lui que le
 * contrôle confronte ce résumé à la règle du serveur. Les « Bailleurs » sont les
 * comptes mandataires — agence, gestionnaire — qui louent par délégation d'un
 * copropriétaire ; les aidants n'en sont pas, ils héritent du droit de celui
 * qu'ils aident.
 */
export const PROFILS = [
	{
		code: 'occupants',
		statut: 'copropriétaire_résident',
		court: 'Occupants',
		long: 'Copropriétaires occupants',
		icone: 'home',
	},
	{
		code: 'copro_bailleurs',
		statut: 'copropriétaire_bailleur',
		court: 'Copro-bailleurs',
		long: 'Copropriétaires bailleurs',
		icone: 'building-2',
	},
	{
		code: 'bailleurs',
		statut: 'mandataire',
		court: 'Bailleurs',
		long: 'Bailleurs (mandataires)',
		icone: 'heart-handshake',
	},
	{
		code: 'locataires',
		statut: 'locataire',
		court: 'Locataires',
		long: 'Locataires',
		icone: 'user',
	},
] as const;

export type Profil = (typeof PROFILS)[number]['code'];

const TOUS_PROFILS: Profil[] = PROFILS.map((p) => p.code);

/**
 * Ce que chaque code de Destinataires fait LIRE — miroir de
 * `public_cible_visible` côté serveur. Un code inconnu ne fait lire personne :
 * la règle refuse ce qu'elle ne reconnaît pas. `conseil_syndical` non plus —
 * le conseil lit TOUT, ce n'est pas un profil qu'on ajoute.
 */
const PROFILS_DU_CODE: Record<string, Profil[]> = {
	résidents: TOUS_PROFILS,
	copropriétaires: ['occupants', 'copro_bailleurs'],
	copropriétaires_occupants: ['occupants'],
	bailleurs: ['copro_bailleurs'],
	mandataires: ['bailleurs'],
	locataires: ['locataires'],
};

/**
 * Une affaire suivie : les COPROPRIÉTAIRES seuls, occupants et bailleurs
 * (`ticket_visible`) — ni locataires, ni mandataires depuis #1311 (25/09/2026).
 * Datée ou non : la date les rouvrait aux locataires du 25/09 au 28/09 (#1269),
 * et leur montrait les contrats de maintenance (#1428).
 */
const PROFILS_AFFAIRE: Profil[] = ['occupants', 'copro_bailleurs'];

type Vocable = { cle: string; icones: string[]; court: string; long: string; qui?: string };

/** Les combinaisons qui ont un NOM ; les autres se composent. */
const NOMMEES: (Vocable & { profils: Profil[] })[] = [
	{ cle: 'tous', profils: TOUS_PROFILS, icones: ['users-round'], court: 'Tous', long: 'Tous' },
	{
		cle: 'residents',
		profils: ['occupants', 'locataires'],
		icones: ['home', 'user'],
		court: 'Résidents',
		long: 'Résidents (occupants et locataires)',
	},
	//  🔴 UN ensemble, UN nom (#1311, 25/09/2026) : c'est désormais aussi celui
	//  d'une affaire suivie, qui disait « Tous sauf locataires » tant que les
	//  mandataires la lisaient. « Propriétaires » (actualités) et « Copropriétaires
	//  seuls » (demandé pour les affaires) auraient nommé deux fois les mêmes
	//  lecteurs ; arbitré : « Copropriétaires ».
	{
		cle: 'coproprietaires',
		profils: PROFILS_AFFAIRE,
		icones: ['key-round'],
		court: 'Copropriétaires',
		long: 'Copropriétaires (occupants et bailleurs)',
	},
	//  Une Panne sans choix du conseil (standard du 30/09/2026).
	{
		cle: 'copro_locataires',
		profils: [...PROFILS_AFFAIRE, 'locataires'],
		icones: ['key-round', 'user'],
		court: 'Copropriétaires + locataires',
		long: 'Copropriétaires et locataires',
	},
];

const CS: Vocable = {
	cle: 'cs',
	icones: ['shield-check'],
	court: 'CS',
	long: 'Conseil syndical seul',
};

/**  « Résident concerné » — la vignette dit ce que la pastille cochée dit
 *   (#1436, même leçon que #1434) : une affaire confidentielle ou fermée par sa
 *   catégorie. Les mêmes lecteurs que « CS », et l'auteur que ce mot nomme. */
const VOCABLE_CONCERNE: Vocable = {
	cle: 'concerne',
	icones: ['lock'],
	court: 'Concerné',
	long: 'Résident concerné',
};

/**
 * « Résident concerné » : l'auteur, la personne pour qui l'affaire a été
 * saisie, et le conseil. Un DÉFAUT, jamais un code envoyé : le conseil qui le
 * choisit coche `confidentiel`. Miroir de `CONCERNE` au serveur.
 */
export const CONCERNE = 'concerné';

/** Une catégorie que la table ne connaît pas : le conseil seul. Miroir serveur. */
export const DEFAUT_INCONNU = ['conseil_syndical'];

/**  « Tous les copropriétaires » — occupants et bailleurs. Dans un défaut, ils
 *   lisent l'affaire dans TOUTE la résidence (standard du 30/09/2026, Carnet =
 *   Affaires = Kanban) ; un locataire, dans le périmètre. Miroir de
 *   `lus_dans_toute_la_residence` au serveur. */
const CODES_COPROPRIETAIRES = ['copropriétaires_occupants', 'bailleurs'];

/** Une Panne sans choix : tous les copropriétaires et les locataires du périmètre. */
export const DEFAUT_PANNE = [...CODES_COPROPRIETAIRES, 'locataires'];

/**
 * Les Destinataires d'une affaire SANS choix du conseil, par catégorie (#1436,
 * arbitré le 28/09/2026 ; Étude & travaux au conseil seul le 29/09/2026 ;
 * Entretien aux copropriétaires, occupants et bailleurs, le 30/09/2026). La
 * Panne a sa règle (`DEFAUT_PANNE`), l'Étude & travaux son état
 * (`STATUTS_ETUDE_OUVERTE`) ; une catégorie absente, le conseil seul
 * (`DEFAUT_INCONNU`).
 *
 * ⚠️ Miroir de `DEFAUT_PAR_CATEGORIE` (`utils/visibility/defauts_affaire.py`), tenus
 * d'accord par `lecture_pastille.json` : un cas par catégorie.
 */
export const DEFAUT_PAR_CATEGORIE: Record<string, string[]> = {
	nuisance: [CONCERNE],
	acces_accueil: [CONCERNE],
	espaces_verts: [TOUS_LES_RESIDENTS],
	sinistre: [CONCERNE],
	etude_travaux: ['conseil_syndical'], // puis les copropriétaires : STATUTS_ETUDE_OUVERTE
	entretien: CODES_COPROPRIETAIRES,
	question: [CONCERNE],
	bug: [CONCERNE],
};

/** Le défaut est-il « Résident concerné » ? */
export const estConcerne = (codes: string[] | null | undefined): boolean =>
	!!codes && codes.length === 1 && codes[0] === CONCERNE;

const minuscule = (t: string) => t.charAt(0).toLocaleLowerCase('fr') + t.slice(1);

function vocableDe(profils: Profil[]): Vocable {
	const cle = [...profils].sort().join();
	const nommee = NOMMEES.find((n) => [...n.profils].sort().join() === cle);
	if (nommee) return nommee;
	const ps = PROFILS.filter((p) => profils.includes(p.code));
	return {
		cle: ps.map((p) => p.code).join('+'),
		icones: ps.map((p) => p.icone),
		court: ps.map((p) => p.court).join(' + '),
		long: ps.map((p, i) => (i ? minuscule(p.long) : p.long)).join(' et '),
		qui: 'les ' + ps.map((p) => minuscule(p.long)).join(' et les '),
	};
}

/** Ce que l'objet dit de ses lecteurs. */
export interface EntreeLecture {
	/** Une actualité (vrai) ou une affaire suivie. */
	actualite: boolean;
	/** 🛡️ Le conseil syndical seul (`ticket.confidentiel`). */
	confidentiel: boolean;
	/** Destinataires — une affaire ne les lit que s'ils ont été choisis (#1343). */
	publicCible: string[] | string | null | undefined;
	/** Le périmètre vise-t-il MOINS que la copropriété ? Tranché par l'appelant. */
	perimetreRestreint: boolean;
	/** 🔒 « Réservé au périmètre sélectionné » — une actualité comme une affaire (22/10/2026). */
	reservePerimetre: boolean;
	/** La catégorie d'une affaire, et son état — une Étude & travaux s'ouvre en AG. */
	categorie?: string;
	statut?: string;
	/** L'objet est masculin (un sondage) : « Lu par… », « ne le lit ». */
	masculin?: boolean;
}

export interface Lecture extends Vocable {
	/** Les profils qui lisent, dans l'ordre de `PROFILS`. Vide : le conseil seul. */
	profils: Profil[];
	/** Le cadenas : seuls ceux du périmètre lisent. */
	perimetreReserve: boolean;
	/**  Ceux qui lisent HORS du périmètre — tous sans périmètre restreint, aucun
	 *   sous le cadenas, les copropriétaires seuls d'une Panne au défaut. */
	horsPerimetre: Profil[];
	/** Ceux qui ne lisent que dans le périmètre, quand d'autres lisent partout. */
	duPerimetre: string;
	/** La phrase de l'infobulle : « Lue par… ». */
	phrase: string;
	/** Ceux qui ne lisent pas : « Pas les locataires, ni… ». */
	exclus: string;
	/** Personne n'est exclu : rien sur la carte, « Tous » dans la section. */
	parDefaut: boolean;
	/** Le piège d'une actualité : un périmètre choisi mais non réservé. */
	avertissement: string;
}

/** Le titre de la pastille longue : son libellé, et le cadenas en toutes lettres. */
export function titreLecture(l: Lecture): string {
	if (l.perimetreReserve) return l.long + ' · du périmètre seulement';
	return l.long + (l.duPerimetre ? ` · ${l.duPerimetre} du périmètre seulement` : '');
}

/**
 * Les Destinataires qu'une affaire a SANS choix du conseil (#1343) — ce que
 * sa nature décide, et que les pastilles présélectionnent : selon la
 * catégorie (`DEFAUT_PAR_CATEGORIE`, #1436), le conseil seul sinon
 * (`DEFAUT_INCONNU`), datée ou non (#1428) ; une Panne, les siens. Une
 * actualité : « Tous ».
 *
 * La règle vit au serveur (`ticket_visible`) ; `lecture_pastille.json` tient
 * les deux écritures d'accord.
 */
export function destinatairesParDefaut(n: {
	actualite?: boolean;
	/** La catégorie d'une affaire — une Panne a sa propre règle. */
	categorie?: string;
	/** L'état du suivi — une Étude & travaux sort du conseil en AG. */
	statut?: string;
}): string[] {
	if (n.actualite) return [TOUS_LES_RESIDENTS];
	//  Standard du 30/09/2026 (Carnet = Affaires = Kanban). Miroir de
	//  `destinataires_par_defaut` (`utils/visibility/defauts_affaire.py`).
	if (n.categorie === 'panne') return DEFAUT_PANNE;
	if (n.categorie === 'etude_travaux' && STATUTS_ETUDE_OUVERTE.includes(n.statut ?? ''))
		return CODES_COPROPRIETAIRES;
	return (n.categorie && DEFAUT_PAR_CATEGORIE[n.categorie]) || DEFAUT_INCONNU;
}

/** « les copropriétaires (occupants et bailleurs) », « les locataires »… */
const quiDe = (ps: Profil[]) => {
	const v = vocableDe(ps);
	return v.qui ?? 'les ' + minuscule(v.long);
};

export function lectureDe(e: EntreeLecture): Lecture {
	//  Une affaire lit ses Destinataires quand le conseil en a CHOISI (#1343) ;
	//  vides, ceux de sa nature — comme `ticket_visible`.
	const explicites = codesDestinataires(e.publicCible);
	const codes = e.actualite || explicites.length ? explicites : destinatairesParDefaut(e);
	const csSeul = e.confidentiel || reserveAuConseil(codes);
	let profils: Profil[] = [];
	if (!csSeul) {
		if (concerneTousLesResidents(codes)) profils = TOUS_PROFILS;
		else {
			const vises = new Set(codes.flatMap((c) => PROFILS_DU_CODE[c] ?? []));
			profils = TOUS_PROFILS.filter((p) => vises.has(p));
		}
	}
	//  Qui lit HORS du périmètre : une actualité, sauf réserve ; une affaire au
	//  défaut, ses copropriétaires (standard du 30/09/2026) sauf réserve
	//  (22/10/2026, `lus_dans_toute_la_residence`) ; un choix, personne.
	const auDefaut = !e.actualite && !explicites.length;
	const partout = !e.perimetreRestreint
		? profils
		: e.actualite
			? e.reservePerimetre
				? []
				: profils
			: auDefaut && !e.reservePerimetre
				? profils.filter((p) =>
						codes.some((c) => CODES_COPROPRIETAIRES.includes(c) && PROFILS_DU_CODE[c]?.includes(p)),
					)
				: [];
	const perimetreReserve = profils.length > 0 && e.perimetreRestreint && !partout.length;
	const seulsDuPerimetre = partout.length ? profils.filter((p) => !partout.includes(p)) : [];
	const concerne = !e.actualite && (e.confidentiel || estConcerne(codes));
	const v = profils.length ? vocableDe(profils) : concerne ? VOCABLE_CONCERNE : CS;
	const tous = v.cle === 'tous';

	let phrase: string;
	const pas: string[] = [];
	const lue = e.masculin ? 'Lu' : 'Lue';
	if (concerne) {
		phrase =
			'Lue par la personne concernée — son auteur, ou celle pour qui elle a été saisie — et par le conseil syndical, personne d’autre.';
	} else if (!profils.length) {
		phrase = `Personne d’autre que le conseil syndical ne ${e.masculin ? 'le' : 'la'} lit, à part son auteur.`;
	} else {
		const ou = perimetreReserve ? ', dans le périmètre seulement.' : '.';
		phrase = seulsDuPerimetre.length
			? `${lue} par ${quiDe(partout)} dans toute la copropriété, et par ${quiDe(seulsDuPerimetre)} du périmètre seulement.`
			: tous
				? `${lue} par tous${ou}`
				: `${lue} par ${quiDe(profils)}${perimetreReserve ? ou : ', dans toute la copropriété.'}`;
		for (const p of PROFILS) if (!profils.includes(p.code)) pas.push('les ' + minuscule(p.long));
		if (perimetreReserve) pas.push('les personnes hors du périmètre');
		if (seulsDuPerimetre.length) pas.push(`${quiDe(seulsDuPerimetre)} hors du périmètre`);
	}
	return {
		...v,
		profils,
		perimetreReserve,
		horsPerimetre: partout,
		duPerimetre: seulsDuPerimetre.length ? minuscule(vocableDe(seulsDuPerimetre).court) : '',
		phrase,
		exclus: pas.length ? `Pas ${pas.join(', ni ')}.` : '',
		parDefaut: tous && !perimetreReserve,
		avertissement:
			e.actualite && profils.length && e.perimetreRestreint && !e.reservePerimetre
				? 'Le périmètre est choisi mais pas réservé : toute la copropriété la lira.'
				: '',
	};
}

/**
 * Qui lit un objet CIBLÉ — petite annonce, idée, sondage (#1373, 27/09/2026).
 *
 * Miroir de `cible_visible` SANS ouverture à la copropriété : le périmètre
 * restreint toujours — on ne propose pas un lave-linge au voisin qu'on a
 * écarté, on ne fait pas voter celui d'un autre bâtiment —, et des
 * Destinataires vides valent « Tous ». C'est exactement la mécanique d'une
 * actualité RÉSERVÉE à son périmètre : on la réemploie, on ne la recopie pas.
 * Tenu contre le serveur par les cas `objet` de `lecture_pastille.json`.
 */
export function lectureCiblee(e: {
	publicCible: EntreeLecture['publicCible'];
	perimetreRestreint: boolean;
	masculin?: boolean;
}): Lecture {
	return lectureDe({ ...e, actualite: true, confidentiel: false, reservePerimetre: true });
}
