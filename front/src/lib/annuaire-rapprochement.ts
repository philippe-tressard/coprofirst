/**
 * **Rapprocher un membre de l'annuaire d'un inscrit et de son logement** — à
 * partir du NOM saisi dans sa fiche.
 *
 * Sorti d'`espace-cs/+page.svelte` le 29/09/2026 (#779) : le conseil syndical et
 * le syndic y deviennent deux composants, et ces règles servent aux deux. Les
 * laisser dans l'un aurait obligé l'autre à les recopier.
 *
 * Fonctions PURES : les données de référence sont passées, jamais lues dans un
 * store. `check-annuaire-rapprochement.mjs --selftest` les éprouve sur ce
 * module, pas sur une copie.
 */
import { replier, sansAccents } from '#lib/texte.ts';

/** Un inscrit, tel que l'écran le rapproche. */
export interface Inscrit {
	id: number;
	prenom: string;
	nom: string;
	email: string;
	telephone: string | null;
	batiment_id: number | null;
}

/** Un lot, tel que l'écran le rapproche. */
export interface LotRapproche {
	id: number;
	numero: string;
	type: string;
	etage: number | null;
	batiment_id: number | null;
	batiment_nom: string | null;
}

/** Une ligne d'import du registre des copropriétaires. */
export interface LigneImport {
	nom_coproprietaire?: string | null;
	type_raw?: string | null;
	etage_raw?: string | null;
	lot_id?: number | null;
	batiment_id?: number | null;
	batiment_nom?: string | null;
}

/** Ce qu'il faut pour localiser un membre : les imports, les lots, les bâtiments. */
export interface SourcesRapprochement {
	inscrits: Inscrit[];
	lots: LotRapproche[];
	imports: LigneImport[];
	/** `id` → « Bât. N ». */
	batiments: Record<number, string>;
}

export interface Localisation {
	batiment_id: number | null;
	batiment_nom: string | null;
	etage: number | null;
}

/** L'inscrit qui porte ce nom — casse et accents ignorés —, ou `null`. */
export function inscritParNom(inscrits: Inscrit[], nom: string): Inscrit | null {
	if (!nom || nom.length < 2) return null;
	const q = replier(nom);
	return inscrits.find((u) => replier(u.nom) === q) ?? null;
}

/** L'étage d'une ligne d'import (« RDC », « 1ER », « 2SS »…) — même table que le serveur. */
export function etageDepuisBrut(brut: string | null | undefined): number | null {
	if (brut == null) return null;
	//  La CASSE porte le sens ici (« 1ER », « RDC ») : `sansAccents` et non
	//  `replier`, qui rendrait la forme comparable en minuscules.
	const s = sansAccents(brut).trim().toUpperCase().replace(/\s+/g, ' ');
	const table: Record<string, number> = {
		RDC: 0,
		'0': 0,
		'1ER': 1,
		'1': 1,
		'2EME': 2,
		'2': 2,
		'3EME': 3,
		'3': 3,
		'4EME': 4,
		'4': 4,
		'5EME': 5,
		'5': 5,
		'6EME': 6,
		'6': 6,
		'7EME': 7,
		'7': 7,
		'1SS': -1,
		'-1': -1,
		'2SS': -2,
		'-2': -2,
	};
	return table[s] ?? null;
}

const sansPrefixe = (nom: string) => nom.replace(/^Bât\. /i, '');

/**
 * Le logement d'un copropriétaire, lu dans le registre importé par son nom.
 *
 * L'APPARTEMENT l'emporte : un parking ou une cave ne dit pas où l'on habite.
 * `null` si aucune ligne ne correspond.
 */
export function localisationParNom(
	sources: Pick<SourcesRapprochement, 'lots' | 'imports' | 'batiments'>,
	nom: string,
): Localisation | null {
	if (!nom || nom.length < 2) return null;
	const { lots, imports, batiments } = sources;
	const q = replier(nom);
	const hits = imports.filter(
		(imp) => imp.nom_coproprietaire && replier(imp.nom_coproprietaire).includes(q),
	);
	if (!hits.length) return null;
	const lotDe = (imp: LigneImport) =>
		imp.lot_id ? lots.find((l) => l.id === imp.lot_id) : undefined;
	// Exclure CA (cave) et PS (parking) via type_raw — fiable même si lot_id non résolu
	const hitsAppt = hits.filter((imp) => {
		const raw = (imp.type_raw ?? '').toUpperCase().trim();
		if (raw.startsWith('CA') || raw.startsWith('PS')) return false;
		const lot = lotDe(imp);
		return !(lot && lot.type !== 'appartement');
	});
	// Priorité : appartement résolu > non résolu > rien (parking/cave écarté)
	const hit =
		hitsAppt.find((imp) => lotDe(imp)?.type === 'appartement') ??
		hitsAppt.find((imp) => imp.lot_id) ??
		hitsAppt[0] ??
		null;
	if (!hit) return null;
	// Bâtiment : le lot résolu (nom de la table des bâtiments, sinon le sien),
	// puis la ligne d'import elle-même.
	let batiment_id: number | null = null;
	let batiment_nom: string | null = null;
	const lot = lotDe(hit);
	if (lot) {
		batiment_id = lot.batiment_id;
		const nomTable = lot.batiment_id ? (batiments[lot.batiment_id] ?? null) : null;
		batiment_nom = nomTable
			? sansPrefixe(nomTable)
			: lot.batiment_nom
				? sansPrefixe(lot.batiment_nom)
				: null;
	}
	if (!batiment_id) batiment_id = hit.batiment_id ?? null;
	if (!batiment_nom && hit.batiment_nom) batiment_nom = sansPrefixe(hit.batiment_nom);
	return { batiment_id, batiment_nom, etage: etageDepuisBrut(hit.etage_raw) };
}
