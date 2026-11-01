/**
 * Les ÉQUIPEMENTS à l'écran — un cache, rempli une fois, lu partout (#2442).
 *
 * Ils étaient une table écrite ici (`EQUIPEMENTS` de `#lib/prestataires`, émojis
 * compris) et une seconde pour la gouttière (`MARQUES_EQUIPEMENT`), recopies de
 * l'énumération du serveur. Ils vivent désormais en base, administrés dans
 * Admin › Copropriété › Équipements ; ce module en garde la DERNIÈRE lecture,
 * pour que `equipLabel()` reste synchrone au milieu d'un gabarit — le motif de
 * `#lib/perimetres` (`definirPerimetres`).
 *
 * ⚠️ Ce module n'importe pas le client : `stores/equipements.ts` charge, et lui
 * seul appelle `definirEquipements`. Un écran rendu avant l'arrivée de la liste
 * se repeint en citant `$equipementsStore` (`relire`, `#lib/utils`).
 *
 * 🔴 Ce que l'écran ne décide pas : `systeme` (assurance, syndic, autre — ni
 * retirés ni supprimés) et `pour_affaires` (assurance et syndic classent un
 * contrat, pas un équipement) viennent du SERVEUR (`utils/equipements`). Les
 * recopier ici referait la seconde liste que ce lot supprime.
 */
import type { ClasseGouttiere } from '#lib/gouttiere.ts';

/**  Un équipement tel que `GET /equipements` le rend (`routers/equipements.py`). */
export interface Equipement {
	id: number;
	code: string;
	libelle: string;
	abreviation: string | null;
	/** Un nom du catalogue au trait (`#lib/icones-svg.json`). */
	icone: string;
	description: string | null;
	ordre: number;
	/** Proposé à la saisie ; faux = retiré, toujours affiché sur ce qui le cite. */
	actif: boolean;
	systeme: boolean;
	pour_affaires: boolean;
	/** Les codes des périmètres où il se trouve. */
	perimetres: string[];
}

/**  Une option de sélecteur — la forme qu'attendent `SectionEquipement` et les listes. */
export type TypeEquipementOption = { val: string; label: string };

/**  Ce qu'un formulaire désigne : un contrat (tout), une affaire (sans assurance ni syndic). */
export type UsageEquipement = 'contrat' | 'affaire';

let liste: Equipement[] = [];
let parCode: Record<string, Equipement> = {};

/**  Remplit le cache. Appelé par `stores/equipements.ts`, nulle part ailleurs. */
export function definirEquipements(l: Equipement[]): void {
	liste = l;
	parCode = Object.fromEntries(l.map((e) => [e.code, e]));
}

/**  L'équipement d'un code — ou `null` s'il est inconnu (supprimé, texte libre). */
export function equipement(code: string | null | undefined): Equipement | null {
	return code ? (parCode[code] ?? null) : null;
}

/**  Le libellé d'un code.
 *
 *   ⚠️ Le repli rend le code BRUT plutôt qu'un tiret : un code inconnu — supprimé
 *   depuis, ou le texte libre d'une ancienne spécialité — reste lisible. */
export function equipLabel(code: string | null | undefined): string {
	if (!code) return '—';
	return parCode[code]?.libelle ?? code;
}

/**  Les options d'un sélecteur : les équipements PROPOSÉS à la saisie pour cet
 *   usage, plus `garder` — la valeur déjà posée, même retirée : un contrat dont
 *   l'équipement a été retiré se corrige sans qu'on lui en choisisse un autre.
 *
 *   `source` : passer `$equipementsStore` dans un gabarit, c'est ce qui repeint
 *   la liste quand elle arrive ; par défaut, le cache. */
export function optionsEquipements(
	pour: UsageEquipement,
	garder: string | null = null,
	source: readonly Equipement[] = liste,
): TypeEquipementOption[] {
	return source
		.filter((e) => e.code === garder || (e.actif && (pour === 'contrat' || e.pour_affaires)))
		.map((e) => ({ val: e.code, label: e.libelle }));
}

/**  Le classement d'un code dans la gouttière d'une carte : son icône au trait,
 *   son libellé, son mot abrégé — `null` s'il est inconnu (rien ne s'invente). */
export function classeEquipement(code: string | null | undefined): ClasseGouttiere | null {
	const e = equipement(code);
	if (!e) return null;
	return { icone: e.icone, libelle: e.libelle, abrege: abreviationDe(e) };
}

/**  Le mot de gouttière : l'abréviation saisie, sinon le PREMIER MOT du libellé —
 *   « Porte de garage » → « PORTE », jamais « PORTE DE », coupé au hasard de la
 *   largeur. Un mot trop long se coupe avec un point, comme les abréviations de
 *   départ (« EXTINC. »). */
export function abreviationDe(e: Pick<Equipement, 'abreviation' | 'libelle'>): string {
	const saisie = e.abreviation?.trim();
	if (saisie) return saisie.toUpperCase().slice(0, ABREVIATION_MAX);
	const mot = (e.libelle.trim().split(/\s+/)[0] ?? '').toUpperCase();
	return mot.length > ABREVIATION_MAX ? `${mot.slice(0, ABREVIATION_MAX - 1)}.` : mot;
}

/**  Le plafond du mot de gouttière — celui du serveur (`routers/equipements.ABREVIATION_MAX`). */
export const ABREVIATION_MAX = 8;

/**  Les groupes d'une liste rangée par équipement : un par code CITÉ, dans
 *   l'ordre de l'administration, un code inconnu (liste pas encore arrivée,
 *   équipement supprimé) en dernier, sous son code — jamais perdu.
 *
 *   🔴 Les contrats se groupaient en parcourant la TABLE des équipements : un
 *   contrat dont le code n'y figurait pas n'apparaissait dans aucun groupe, donc
 *   nulle part. Une liste administrée rend ce cas ordinaire ; on parcourt donc
 *   ce que les objets citent. `liste` se passe (`$equipementsStore`) : c'est ce
 *   qui repeint les intitulés quand elle arrive. */
export function groupesParEquipement(
	codes: readonly string[],
	liste: readonly Equipement[],
): TypeEquipementOption[] {
	const rang = new Map(liste.map((e, i) => [e.code, i]));
	const libelle = new Map(liste.map((e) => [e.code, e.libelle]));
	return [...new Set(codes)]
		.sort(
			(a, b) => (rang.get(a) ?? Infinity) - (rang.get(b) ?? Infinity) || a.localeCompare(b, 'fr'),
		)
		.map((code) => ({ val: code, label: libelle.get(code) ?? code }));
}

/**  Les icônes proposées pour un équipement — des noms du catalogue au trait
 *   (`#lib/icones-svg.json`, `npm run lint:icones`), et ce qu'ils évoquent. */
export const ICONES_EQUIPEMENT: readonly { nom: string; libelle: string }[] = [
	{ nom: 'arrow-up-down', libelle: 'Ascenseur' },
	{ nom: 'flame', libelle: 'Chauffage' },
	{ nom: 'droplet', libelle: 'Eau, plomberie' },
	{ nom: 'zap', libelle: 'Électricité' },
	{ nom: 'lightbulb', libelle: 'Éclairage' },
	{ nom: 'trees', libelle: 'Espaces verts' },
	{ nom: 'sprout', libelle: 'Jardin' },
	{ nom: 'shield-half', libelle: 'Sécurité incendie' },
	{ nom: 'bell', libelle: 'Interphone, alarme' },
	{ nom: 'door-closed', libelle: 'Porte, menuiserie' },
	{ nom: 'key-round', libelle: 'Serrurerie, accès' },
	{ nom: 'lock', libelle: 'Contrôle d’accès' },
	{ nom: 'square-parking', libelle: 'Parking' },
	{ nom: 'car', libelle: 'Véhicules, recharge' },
	{ nom: 'home', libelle: 'Toiture, bâti' },
	{ nom: 'stairs', libelle: 'Escalier' },
	{ nom: 'warehouse', libelle: 'Local technique' },
	{ nom: 'box', libelle: 'Stockage, caves' },
	{ nom: 'settings', libelle: 'Machinerie, pompe' },
	{ nom: 'hard-hat', libelle: 'Travaux' },
	{ nom: 'shield', libelle: 'Assurance' },
	{ nom: 'building-2', libelle: 'Gestion, syndic' },
	{ nom: 'wrench', libelle: 'Entretien, autre' },
];

/**  Ce que la fiche d'un équipement saisit — création et correction. */
export interface FormulaireEquipement {
	libelle: string;
	abreviation: string;
	icone: string;
	description: string;
	ordre: number;
	perimetres: string[];
}

/**  Une fiche vierge, rangée après les autres. */
export function formulaireVierge(ordre = 0): FormulaireEquipement {
	return { libelle: '', abreviation: '', icone: 'wrench', description: '', ordre, perimetres: [] };
}

/**  La fiche d'un équipement existant, prête à corriger. */
export function formulaireDepuis(e: Equipement): FormulaireEquipement {
	return {
		libelle: e.libelle,
		abreviation: e.abreviation ?? '',
		icone: e.icone,
		description: e.description ?? '',
		ordre: e.ordre,
		perimetres: [...e.perimetres],
	};
}

/**  Ce qui part : textes nettoyés, et sans le périmètre par DÉFAUT — « toute la
 *   copropriété » n'est pas un lieu où se trouve un équipement, c'est l'absence
 *   de lieu, et elle ne doit rien proposer dans une affaire. */
export function chargeEquipement(f: FormulaireEquipement, estDefaut: (code: string) => boolean) {
	return {
		libelle: f.libelle.trim(),
		abreviation: f.abreviation.trim().toUpperCase() || null,
		icone: f.icone || 'wrench',
		description: f.description.trim() || null,
		ordre: f.ordre,
		perimetres: f.perimetres.filter((c) => !estDefaut(c)),
	};
}
