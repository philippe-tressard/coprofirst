/**
 * Le SÉLECTEUR de périmètre — ce qu'un clic retient, et quelles rangées s'ouvrent.
 *
 * Sorti de `PerimetrePicker.svelte` le 10/11/2026, quand le niveau 3 l'a fait
 * passer au-delà de 500 lignes (`standards/02` §6). Demandé à l'écran : *« la
 * sélection peut se faire jusqu'au niveau 2, autoriser un niveau 3 similaire au
 * niveau précédent »* — Bâtiment 1 › Logement › Terrasses Balcons. Le composant
 * rend ; ce module décide, en fonctions pures sur l'arbre et la sélection.
 *
 * ## La règle, en entier — la même à chaque niveau
 *
 * | Clic sur | Sélection | Rangées |
 * |---|---|---|
 * | un nœud **qui a des espaces retenus** sous lui, non retenu lui-même | *inchangée* | la sienne s'ouvre |
 * | un nœud non retenu, sans espace retenu | il est **ajouté**, ses ancêtres retirés | la sienne s'ouvre |
 * | un nœud **retenu** | il est **retiré** | la sienne se ferme |
 * | « toute la copropriété » | tout est vidé | tout se ferme |
 *
 * Le détail et l'histoire de chaque ligne (18/08/2026 : « deux intentions ne
 * tiennent pas dans un seul geste ») sont dans le composant, au-dessus de son appel.
 */
import { joindreGroupes, type GroupeLibelles } from './libelles';
import type { Perimetre } from './arbre';

/** Le sélecteur ne descend pas au-delà : la rangée de niveau 3 n'a pas de chevron. */
export const NIVEAU_SAISI_MAX = 3;

/** L'arbre vu par le sélecteur : les nœuds actifs et les têtes de rangée. */
export interface ArbreSelection {
	parCode: Map<string, Perimetre>;
	actifs: Perimetre[];
	/** Les codes de premier niveau (`perimetresNiveau1`). */
	tetes: Set<string>;
}

/** Les ancêtres d'un code, du parent à la racine — bornés par `vus`. */
export function ancetres(code: string, arbre: ArbreSelection): string[] {
	const sortie: string[] = [];
	const vus = new Set<string>([code]);
	let parent = arbre.parCode.get(code)?.parent ?? null;
	while (parent && !vus.has(parent)) {
		vus.add(parent);
		sortie.push(parent);
		parent = arbre.parCode.get(parent)?.parent ?? null;
	}
	return sortie;
}

/** Le chemin d'un code depuis sa tête de rangée — `[tête, niveau 2, niveau 3]` —, ou `[]`. */
export function cheminDepuisTete(code: string, arbre: ArbreSelection): string[] {
	const chemin = [code, ...ancetres(code, arbre)];
	const i = chemin.findIndex((c) => arbre.tetes.has(c));
	return i < 0 ? [] : chemin.slice(0, i + 1).reverse();
}

/** Le niveau d'un code dans le sélecteur : 1 pour une tête, 0 hors de toute rangée. */
export function niveauSaisi(code: string, arbre: ArbreSelection): number {
	return cheminDepuisTete(code, arbre).length;
}

/** Les enfants proposables d'un nœud, dans l'ordre de l'arbre. */
export function enfantsSelectionnables(code: string, arbre: ArbreSelection): Perimetre[] {
	return arbre.actifs.filter((n) => n.parent === code && n.selectionnable);
}

/** Ce nœud ouvre-t-il une rangée — a-t-il des enfants, et n'est-il pas au dernier niveau ? */
export function ouvreUneRangee(code: string, arbre: ArbreSelection): boolean {
	const niveau = niveauSaisi(code, arbre);
	return niveau > 0 && niveau < NIVEAU_SAISI_MAX && enfantsSelectionnables(code, arbre).length > 0;
}

/** Les codes retenus SOUS ce nœud, à tout niveau. */
export function retenusSous(code: string, selection: Set<string>, arbre: ArbreSelection): string[] {
	return [...selection].filter((v) => v !== code && ancetres(v, arbre).includes(code));
}

/** Les rangées ouvertes pour le dernier nœud touché : sous sa tête, puis sous son niveau 2. */
export function rangeesOuvertes(
	touche: string | null,
	arbre: ArbreSelection,
): { parent: Perimetre; enfants: Perimetre[] }[] {
	if (!touche) return [];
	return cheminDepuisTete(touche, arbre)
		.filter((c) => ouvreUneRangee(c, arbre))
		.map((c) => ({ parent: arbre.parCode.get(c)!, enfants: enfantsSelectionnables(c, arbre) }));
}

/**
 * Le nœud dont les rangées s'ouvrent : le dernier touché s'il en ouvre une, sinon
 * le premier retenu qui a une tête — à l'ouverture d'un formulaire d'édition,
 * les rangées s'ouvrent sur ce qui est enregistré.
 */
export function noeudOuvert(
	touche: string | null,
	value: string[],
	arbre: ArbreSelection,
): string | null {
	if (touche && rangeesOuvertes(touche, arbre).length > 0) return touche;
	return value.find((v) => niveauSaisi(v, arbre) > 0) ?? null;
}

/**
 * Le résumé d'une pastille — ce qu'elle porte de retenu sous elle, écrit depuis
 * elle : « Logement › Terrasses — Jardin Bât. » sous « Bâtiment 1 ».
 * Les deux séparateurs suivent la règle de `perimetreLabel` (`joindreGroupes`).
 */
export function resumeSous(code: string, selection: Set<string>, arbre: ArbreSelection): string {
	const court = (c: string) => {
		const n = arbre.parCode.get(c);
		return n ? n.libelle_court || n.libelle : c;
	};
	const groupes: GroupeLibelles[] = [];
	for (const enfant of enfantsSelectionnables(code, arbre)) {
		if (selection.has(enfant.code)) groupes.push({ libelles: [court(enfant.code)] });
		const dessous = enfantsSelectionnables(enfant.code, arbre).filter((p) => selection.has(p.code));
		if (dessous.length > 0)
			groupes.push({ prefixe: court(enfant.code), libelles: dessous.map((p) => court(p.code)) });
	}
	return joindreGroupes(groupes);
}

/** Ce qu'un clic produit : la nouvelle sélection, et le nœud dont les rangées s'ouvrent. */
export interface Bascule {
	value: string[] | null;
	touche: string | null;
}

/**
 * Un clic sur une pastille, en mode multiple. `value: null` : la sélection ne
 * change pas (on vient revoir ce qui est retenu sous le nœud).
 *
 * `vide` : ce que vaut une sélection vidée — le périmètre par défaut, ou rien sous
 * restriction (une télécommande n'ouvre pas « Copropriété entière »).
 */
export function basculer(
	code: string,
	value: string[],
	defaut: string | null,
	vide: string[],
	arbre: ArbreSelection,
): Bascule {
	const s = new Set(value.filter((v) => v !== defaut));
	const parent = arbre.parCode.get(code)?.parent ?? null;
	const parentDansLeChemin = niveauSaisi(code, arbre) > 1 ? parent : null;

	if (!s.has(code) && retenusSous(code, s, arbre).length > 0) {
		//  1. Le nœud porte des espaces précisés : on vient les REVOIR.
		return { value: null, touche: code };
	}
	let touche: string | null;
	if (s.has(code)) {
		//  2. Retirer ce qui était retenu referme SA rangée ; celle de son parent,
		//     d'où l'on précise souvent plusieurs espaces à la suite, reste ouverte.
		s.delete(code);
		touche = parentDansLeChemin;
	} else {
		//  3. Un espace remplace ses ancêtres : « Bât. 2 › Hall » veut dire le hall,
		//     pas le bâtiment ET le hall.
		for (const a of ancetres(code, arbre)) s.delete(a);
		s.add(code);
		touche = code;
	}
	return { value: s.size > 0 ? [...s] : vide, touche };
}
