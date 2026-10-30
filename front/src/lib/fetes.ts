/**
 * Le calendrier des JOURS DE FÊTE — la seule écriture des dates du décor (#2312).
 *
 * Pendant chacune de ces périodes, `DecorFete` pose son décor dans le coin des
 * pages, si l'administration a activé le service « Décor des jours de fête »
 * (Admin › Services, lu par la clé publique `decor_fetes`).
 *
 * Les bornes sont INCLUSES et se lisent au jour de Paris (`jourIso`). Pâques se
 * calcule chaque année (`dimanchePaques`) : du Vendredi saint au lundi de Pâques.
 *
 * ⚠️ Quand deux périodes se recouvrent — le 1er avril tombe parfois dans le
 * week-end de Pâques (2029, 2040) —, la fête d'un seul jour l'emporte : elle ne
 * reviendrait pas avant un an, Pâques garde ses trois autres jours.
 */

export type CodeFete =
	| 'nouvel-an'
	| 'saint-valentin'
	| 'premier-avril'
	| 'paques'
	| 'fete-musique'
	| 'quatorze-juillet'
	| 'halloween'
	| 'noel';

/** Un jour du calendrier : [mois (1-12), jour]. */
type MoisJour = readonly [number, number];

interface PeriodeFixe {
	code: CodeFete;
	debut: MoisJour;
	fin: MoisJour;
}

/** Les fêtes à date fixe. Celles d'un seul jour passent avant Pâques, Pâques avant les autres. */
const FETES_FIXES: readonly PeriodeFixe[] = [
	{ code: 'premier-avril', debut: [4, 1], fin: [4, 1] },
	{ code: 'saint-valentin', debut: [2, 14], fin: [2, 14] },
	{ code: 'fete-musique', debut: [6, 21], fin: [6, 21] },
	{ code: 'quatorze-juillet', debut: [7, 13], fin: [7, 14] },
	{ code: 'halloween', debut: [10, 29], fin: [10, 31] },
	{ code: 'noel', debut: [12, 15], fin: [12, 26] },
	//  À cheval sur deux années : la borne de fin précède celle du début.
	{ code: 'nouvel-an', debut: [12, 29], fin: [1, 2] },
];

/** Le rang d'un jour dans l'année civile, comparable d'un mois à l'autre. */
const rang = ([mois, jour]: MoisJour): number => mois * 100 + jour;

function dans(jour: MoisJour, { debut, fin }: PeriodeFixe): boolean {
	const r = rang(jour);
	return rang(debut) <= rang(fin)
		? r >= rang(debut) && r <= rang(fin)
		: r >= rang(debut) || r <= rang(fin);
}

/** PURE. Le dimanche de Pâques d'une année grégorienne, en `AAAA-MM-JJ` (Meeus/Jones/Butcher). */
export function dimanchePaques(annee: number): string {
	const a = annee % 19;
	const b = Math.floor(annee / 100);
	const c = annee % 100;
	const d = Math.floor(b / 4);
	const e = b % 4;
	const f = Math.floor((b + 8) / 25);
	const g = Math.floor((b - f + 1) / 3);
	const h = (19 * a + b - d - g + 15) % 30;
	const i = Math.floor(c / 4);
	const k = c % 4;
	const l = (32 + 2 * e + 2 * i - h - k) % 7;
	const m = Math.floor((a + 11 * h + 22 * l) / 451);
	const mois = Math.floor((h + l - 7 * m + 114) / 31);
	const jour = ((h + l - 7 * m + 114) % 31) + 1;
	return `${annee}-${String(mois).padStart(2, '0')}-${String(jour).padStart(2, '0')}`;
}

/** L'écart en jours entre deux dates `AAAA-MM-JJ` — calcul en UTC, sans heure d'été. */
function ecartJours(de: string, a: string): number {
	const enJours = (iso: string) =>
		Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
	return Math.round((enJours(a) - enJours(de)) / 86_400_000);
}

/**
 * PURE. La fête du jour donné (`AAAA-MM-JJ`, jour de Paris), ou `null` hors des
 * périodes. Le décor ne s'affiche que ce jour-là.
 */
export function feteDuJour(jour: string): CodeFete | null {
	const moisJour: MoisJour = [+jour.slice(5, 7), +jour.slice(8, 10)];
	const unJour = FETES_FIXES.filter((p) => rang(p.debut) === rang(p.fin));
	const surPlusieurs = FETES_FIXES.filter((p) => rang(p.debut) !== rang(p.fin));
	const fixe = unJour.find((p) => dans(moisJour, p));
	if (fixe) return fixe.code;
	const ecart = ecartJours(dimanchePaques(+jour.slice(0, 4)), jour);
	if (ecart >= -2 && ecart <= 1) return 'paques';
	return surPlusieurs.find((p) => dans(moisJour, p))?.code ?? null;
}

/** Le jour `AAAA-MM-JJ` décalé de `n` jours — en UTC, sans heure d'été. PURE. */
function decaler(jour: string, n: number): string {
	const d = new Date(Date.UTC(+jour.slice(0, 4), +jour.slice(5, 7) - 1, +jour.slice(8, 10) + n));
	return d.toISOString().slice(0, 10);
}

/** La période d'une fête : son code, et ses bornes incluses en `AAAA-MM-JJ`. */
export interface PeriodeFete {
	code: CodeFete;
	debut: string;
	fin: string;
	/** Le jour donné tombe-t-il dans la période ? */
	enCours: boolean;
}

/**
 * PURE. La fête en cours au jour donné, sinon la prochaine — lue sur `feteDuJour`,
 * jour après jour, pour ne jamais redire les règles (Pâques, recouvrements).
 * Ce que le Profil annonce sous le réglage du décor.
 */
export function feteEnCoursOuProchaine(jour: string): PeriodeFete | null {
	let debut = jour;
	//  Une année et un peu plus : chaque fête revient au moins une fois.
	for (let n = 0; n <= 400 && !feteDuJour(debut); n++) debut = decaler(jour, n + 1);
	const code = feteDuJour(debut);
	if (!code) return null;
	const enCours = debut === jour;
	if (enCours) while (feteDuJour(decaler(debut, -1)) === code) debut = decaler(debut, -1);
	let fin = debut;
	while (feteDuJour(decaler(fin, 1)) === code) fin = decaler(fin, 1);
	return { code, debut, fin, enCours };
}

/**
 * Un message de fête : un texte, ou une liste `[premier jour, texte]` dans l'ordre
 * de la période — un texte vaut de son premier jour jusqu'à la veille du suivant.
 */
export type MessageFete = string | readonly (readonly [MoisJour, string])[];

/**
 * La TABLE DES FÊTES : pour chacune, son nom tel que l'écran le dit et son
 * MESSAGE (#2312, proposition n° 3 du 30/10/2026), qui apparaît de temps en temps
 * là où s'arrête l'élément qui bouge (`DecorFeteMessage`). Lu au jour de Paris,
 * comme la période ; au plus `LONGUEUR_MAX_MESSAGE` caractères : le coin est étroit.
 */
export const FETES: Record<CodeFete, { libelle: string; message: MessageFete }> = {
	'nouvel-an': {
		libelle: 'Nouvel an',
		message: [
			[[12, 29], 'Bon réveillon'],
			[[1, 1], 'Bonne année'],
		],
	},
	'saint-valentin': { libelle: 'Saint-Valentin', message: 'Joyeuse Saint-Valentin' },
	'premier-avril': { libelle: '1er avril', message: 'Poisson d’avril' },
	paques: { libelle: 'Pâques', message: 'Joyeuses Pâques' },
	'fete-musique': { libelle: 'Fête de la musique', message: 'Bonne fête de la musique' },
	'quatorze-juillet': { libelle: '14 juillet', message: 'Bonne fête nationale' },
	halloween: { libelle: 'Halloween', message: 'Joyeux Halloween' },
	noel: { libelle: 'Noël', message: 'Joyeux Noël' },
};

/** Le nom d'une fête, tel que l'écran le dit — lu dans `FETES`. */
export const LIBELLES_FETES = Object.fromEntries(
	Object.entries(FETES).map(([code, { libelle }]) => [code, libelle]),
) as Record<CodeFete, string>;

/** Ce que le coin du décor laisse lire sur ordinateur. */
export const LONGUEUR_MAX_MESSAGE = 26;

/** PURE. Le message de la fête au jour donné (`AAAA-MM-JJ`, jour de Paris). */
export function messageDeFete(code: CodeFete, jour: string): string {
	const message = FETES[code].message;
	if (typeof message === 'string') return message;
	const r = rang([+jour.slice(5, 7), +jour.slice(8, 10)]);
	//  Le dernier texte commencé, en lisant l'année en boucle depuis le premier.
	const depuis = (mj: MoisJour) => (rang(mj) - rang(message[0][0]) + 1300) % 1300;
	const ecoule = (r - rang(message[0][0]) + 1300) % 1300;
	return message.filter(([debut]) => depuis(debut) <= ecoule).at(-1)?.[1] ?? message[0][1];
}
