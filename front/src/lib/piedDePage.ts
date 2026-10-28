/**
 * Le PIED DE PAGE de l'application — ses éléments, et ceux que l'administration
 * peut masquer (Admin › Présentation › Connexion et pied de page, 08/10/2026).
 *
 * ## Ce qui se stocke : les éléments MASQUÉS, jamais les affichés
 *
 * La clé `pied_de_page_masques` liste ce que l'administrateur a retiré. Absente
 * ou vide, tout s'affiche, c'est-à-dire le pied de page d'avant ce réglage. Un
 * élément ajouté plus tard à `ELEMENTS_PIED` paraît donc d'office, au lieu de
 * rester invisible parce qu'aucune instance ne l'avait coché.
 *
 * ## 🔴 Quatre éléments ne se masquent pas
 *
 * La marque, et les trois liens que la loi ou la licence imposent. Ils sont
 * `verrouille`, avec leur raison : `lireMasques` les écarte de la
 * valeur lue, quelle que soit la configuration en base (une saisie directe par
 * l'API compte aussi). Le pied de page n'a donc pas à les tester un par un.
 * Le composant d'affichage est `PiedDePage.svelte`, celui du réglage est
 * `ReglagePiedDePage.svelte` (Admin › Présentation › Connexion et pied de page).
 *
 * ## L'année et le texte libre (arbitrés à l'écran, 08/10/2026)
 *
 * - **L'année** : « © 2026 » l'année de création, « © 2026–2027 » les suivantes.
 *   L'année de création se règle (`pied_de_page_annee_debut`) ; vide, seule
 *   l'année en cours s'affiche — une autre résidence règle la sienne.
 * - **Le texte libre** est un élément comme les autres, qui se masque ; vide,
 *   il ne s'affiche pas.
 *
 * ## L'ordre et le préfixe du nom (arbitrés à l'écran, 09/10/2026)
 *
 * - **Les éléments se réordonnent dans leur place** (ci-dessous), verrouillés
 *   compris : la loi et la licence imposent qu'ils SOIENT là, pas où. La
 *   marque seule ne bouge pas. L'ordre se stocke en entier
 *   (`pied_de_page_ordre`) ; un code inconnu s'ignore, un élément absent de la
 *   valeur — ajouté plus tard — se range en fin.
 * - **Un préfixe devant le nom** (`pied_de_page_prefixe_nom`) : « Résidence »
 *   donne « Résidence 5Hostachy », sans séparateur, et le nom du site reste
 *   « 5Hostachy » partout ailleurs (menu, courriels).
 *
 * ## La carte : trois places (maquette A, arbitrée le 15/10/2026)
 *
 * Le pied de page est une carte, sur le modèle de celui de coprofirst.fr :
 * - **la marque** — le logo et le nom de la résidence, en gras. Elle ne se
 *   masque ni ne se déplace : « la partie non négociable » ;
 * - **les mentions**, en petit sous le nom (année, texte libre, version, serveur) ;
 * - **les liens**, à droite (site de présentation et code source du logiciel,
 *   mentions légales, confidentialité). Depuis le 17/10/2026 (#2040), chaque
 *   lien déclare sa cible ici (`lien`) : le composant les rend tous pareil.
 *
 * Chaque élément déclare sa `place`. L'ordre réglé vaut À L'INTÉRIEUR d'une
 * place : il se stocke toujours en entier, si bien qu'un ordre enregistré avant
 * la carte se lit sans migration — chaque place y garde son ordre relatif.
 */
import { lienSource, NOM_PLATEFORME, SITE_PLATEFORME } from '#lib/plateforme.ts';

/** Où l'élément se rend dans la carte. */
export type PlacePied = 'marque' | 'mention' | 'lien';

/**
 * La cible d'un élément de la place `lien`, lue de l'empreinte du build (seul
 * le code source en dépend). Un lien qui SORT du site s'ouvre dans un nouvel
 * onglet, porte l'icône de sortie et une infobulle — obligatoire : « Logiciel
 * libre » ne dit pas « code », et l'AGPL veut une offre reconnaissable (#2040).
 */
export type LienPied = { cible: (empreinte: string) => string } & (
	{ externe: true; infobulle: string } | { externe?: false }
);

export interface ElementPied {
	code: string;
	/** Le nom de l'élément — dans le réglage de l'administration, et pour un
	 *  lien, le texte même du lien : un seul nom pour les deux écrans. */
	libelle: string;
	place: PlacePied;
	/** Pourquoi l'élément ne se masque pas. S'il est absent, il se masque. */
	verrouille?: string;
	/** Présent pour la place `lien`, et pour elle seule. */
	lien?: LienPied;
}

/** Les éléments du pied de page, dans leur ordre PAR DÉFAUT — que
 *  `pied_de_page_ordre` remplace. */
export const ELEMENTS_PIED: readonly ElementPied[] = [
	{
		code: 'residence',
		libelle: 'Logo et nom de la résidence',
		place: 'marque',
		verrouille: 'ils signent le pied de page',
	},
	{ code: 'annee', libelle: '© Année', place: 'mention' },
	{ code: 'texte', libelle: 'Texte libre', place: 'mention' },
	{ code: 'version', libelle: 'Version', place: 'mention' },
	{ code: 'serveur', libelle: 'Serveur (RPi)', place: 'mention' },
	{
		code: 'site',
		libelle: `À propos de ${NOM_PLATEFORME}`,
		place: 'lien',
		lien: {
			cible: () => SITE_PLATEFORME,
			externe: true,
			infobulle: `Le site de présentation de ${NOM_PLATEFORME}, le logiciel qui fait tourner ce site`,
		},
	},
	{
		code: 'source',
		libelle: 'Logiciel libre',
		place: 'lien',
		verrouille:
			'la licence AGPL impose d’offrir le code source de la version en service à qui utilise le site',
		lien: {
			cible: lienSource,
			externe: true,
			infobulle: 'Le code source de la version en service',
		},
	},
	{
		code: 'mentions',
		libelle: 'Mentions légales',
		place: 'lien',
		verrouille: 'elles doivent rester accessibles depuis chaque page (LCEN, art. 6)',
		lien: { cible: () => '/mentions-legales' },
	},
	{
		code: 'confidentialite',
		libelle: 'Confidentialité',
		place: 'lien',
		verrouille: 'l’information des personnes doit rester accessible (RGPD, art. 13)',
		lien: { cible: () => '/politique-de-confidentialite' },
	},
];

/** Chaque élément, par son code — le pied de page et son réglage les lisent là. */
export const ELEMENT_PIED = new Map(ELEMENTS_PIED.map((e) => [e.code, e]));

/** Les places qui se règlent dans l'administration, avec leur intitulé — la
 *  marque n'en est pas : elle ne bouge pas. */
export const PLACES_REGLABLES: readonly { place: PlacePied; titre: string }[] = [
	{ place: 'mention', titre: 'Sous le nom' },
	{ place: 'lien', titre: 'Liens, à droite' },
];

/** Les codes d'`ordre` qui se rendent à `place`, dans cet ordre. */
export function dansLaPlace(ordre: readonly string[], place: PlacePied): string[] {
	return ordre.filter((c) => ELEMENT_PIED.get(c)?.place === place);
}

/** La clé de configuration — publique : le pied de page la lit dans `/config`. */
export const CLE_PIED_MASQUES = 'pied_de_page_masques';

/** Les éléments masquables — les verrouillés se déplacent, ils ne se masquent pas. */
const ELEMENTS_MASQUABLES = ELEMENTS_PIED.filter((e) => !e.verrouille);
const MASQUABLES = new Set(ELEMENTS_MASQUABLES.map((e) => e.code));

/** Valeur stockée → codes masqués. Les codes inconnus ou verrouillés sont ignorés. */
export function lireMasques(valeur: string | undefined | null): string[] {
	return (valeur ?? '')
		.split(',')
		.map((c) => c.trim())
		.filter((c) => MASQUABLES.has(c));
}

/** Codes masqués → valeur stockée, dans l'ordre d'affichage et sans doublon. */
export function ecrireMasques(masques: readonly string[]): string {
	return ELEMENTS_MASQUABLES.filter((e) => masques.includes(e.code))
		.map((e) => e.code)
		.join(',');
}

/** Les clés de configuration du pied de page — publiques : le pied de page
 *  les lit dans `/config`. */
export const CLES_PIED = {
	masques: CLE_PIED_MASQUES,
	anneeDebut: 'pied_de_page_annee_debut',
	texte: 'pied_de_page_texte',
	ordre: 'pied_de_page_ordre',
	prefixeNom: 'pied_de_page_prefixe_nom',
} as const;

/** Le texte libre ne fait qu'une ligne de pied de page. */
export const TEXTE_PIED_MAX = 120;
/** Le préfixe du nom est un mot ou deux (« Résidence », « Copropriété du »). */
export const PREFIXE_NOM_MAX = 40;

/** Le réglage du pied de page, tel que l'administration le saisit. */
export interface ReglagePied {
	masques: string[];
	/** L'année de création ; vide, seule l'année en cours s'affiche. */
	anneeDebut: number | null;
	texte: string;
	/** Tous les codes, dans l'ordre d'affichage. */
	ordre: string[];
	/** Écrit devant le nom de la résidence, sans séparateur. */
	prefixeNom: string;
}

const CODES = ELEMENTS_PIED.map((e) => e.code);

/** Une année plausible, ou null — une saisie vide ou fautive ne casse pas le pied de page. */
function lireAnnee(valeur: string | number | null | undefined): number | null {
	const n = Number(String(valeur ?? '').trim());
	return Number.isInteger(n) && n >= 1900 && n <= 9999 ? n : null;
}

/** Valeur stockée → ordre complet : codes connus, sans doublon, les absents en fin. */
export function lireOrdre(valeur: string | undefined | null): string[] {
	const lus = (valeur ?? '').split(',').map((c) => c.trim());
	const ordre = [...new Set(lus.filter((c) => CODES.includes(c)))];
	return [...ordre, ...CODES.filter((c) => !ordre.includes(c))];
}

/** Une ligne, bornée — la même règle pour le texte libre et le préfixe. */
function uneLigne(valeur: string | undefined | null, max: number): string {
	return (valeur ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, max);
}

/** Configuration stockée → réglage. Tout ce qui est inconnu retombe sur le défaut. */
export function lireReglagePied(cfg: Record<string, string | undefined>): ReglagePied {
	return {
		masques: lireMasques(cfg[CLES_PIED.masques]),
		anneeDebut: lireAnnee(cfg[CLES_PIED.anneeDebut]),
		texte: uneLigne(cfg[CLES_PIED.texte], TEXTE_PIED_MAX),
		ordre: lireOrdre(cfg[CLES_PIED.ordre]),
		prefixeNom: uneLigne(cfg[CLES_PIED.prefixeNom], PREFIXE_NOM_MAX),
	};
}

/** Réglage → configuration stockée. */
export function ecrireReglagePied(r: ReglagePied): Record<string, string> {
	return {
		[CLES_PIED.masques]: ecrireMasques(r.masques),
		[CLES_PIED.anneeDebut]: r.anneeDebut === null ? '' : String(lireAnnee(r.anneeDebut) ?? ''),
		[CLES_PIED.texte]: uneLigne(r.texte, TEXTE_PIED_MAX),
		[CLES_PIED.ordre]: lireOrdre(r.ordre.join(',')).join(','),
		[CLES_PIED.prefixeNom]: uneLigne(r.prefixeNom, PREFIXE_NOM_MAX),
	};
}

/** « © 2026 » l'année de création (ou sans elle), « © 2026–2027 » ensuite. */
export function mentionAnnee(debut: number | null, courante: number): string {
	return debut !== null && debut < courante ? `© ${debut}–${courante}` : `© ${courante}`;
}

/** Les codes affichés, dans l'ordre, une fois les masqués retirés — et le texte
 *  libre absent s'il est vide. */
export function elementsAffiches(r: ReglagePied): string[] {
	const retires = new Set(lireMasques(r.masques.join(',')));
	return lireOrdre(r.ordre.join(',')).filter(
		(c) => !retires.has(c) && (c !== 'texte' || r.texte.trim() !== ''),
	);
}

/** L'ordre, l'élément `code` échangé avec son voisin DE MÊME PLACE, avant (-1)
 *  ou après (+1) ; inchangé en bout de place. */
export function deplacer(ordre: readonly string[], code: string, sens: -1 | 1): string[] {
	const place = ELEMENT_PIED.get(code)?.place;
	const i = ordre.indexOf(code);
	let j = i + sens;
	while (j >= 0 && j < ordre.length && ELEMENT_PIED.get(ordre[j])?.place !== place) j += sens;
	if (i < 0 || place === undefined || j < 0 || j >= ordre.length) return [...ordre];
	const suite = [...ordre];
	[suite[i], suite[j]] = [suite[j], suite[i]];
	return suite;
}
