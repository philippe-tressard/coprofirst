/**
 * Détermine si un item est "Nouveau" (créé il y a moins de 48h et jamais mis à jour)
 * @param cree_le - date de création (ISO string)
 * @param mis_a_jour_le - date de mise à jour (ISO string ou null)
 * @returns true si l'item est considéré comme nouveau
 */
/**
 * Un item est "Nouveau" si :
 * - il a été créé il y a moins de 48h
 * - il n'a pas été mis à jour (mis_a_jour_le absent ou identique à cree_le)
 */
/**
 * « Nouveau » se juge sur la CRÉATION, et sur rien d'autre.
 *
 * 🔴 La règle exigeait auparavant que l'élément n'ait **jamais été modifié** :
 * `notUpdated && récent`. Corriger une faute de frappe deux heures après avoir
 * publié faisait donc disparaître la pastille — l'élément cessait d'être nouveau
 * parce qu'on l'avait relu.
 *
 * Signalé le 01/09/2026 : *« l'édition ne change pas la date de modification
 * (correction d'erreurs) »*. Une correction ne dit rien au lecteur ; elle ne
 * doit donc rien changer à ce qu'il voit.
 *
 * ⚠️ Le second paramètre a été **retiré**, pas ignoré : une quinzaine d'écrans
 * le passaient, et une signature qui accepte un argument sans s'en servir est un
 * mensonge poli — le prochain lecteur croirait que la date de modification
 * compte encore.
 */
export function isNouveau(cree_le: string): boolean {
	if (!cree_le) return false;
	const QUARANTE_HUIT_HEURES = 48 * 60 * 60 * 1000;
	return Date.now() - new Date(cree_le).getTime() < QUARANTE_HUIT_HEURES;
}
/**
 * Utilitaires de formatage de dates — Europe/Paris
 *
 * Toutes les fonctions forcent le fuseau Europe/Paris pour garantir
 * un affichage cohérent que le code tourne côté serveur (SSR, Docker UTC)
 * ou côté client (navigateur).
 */

const TZ = 'Europe/Paris';
const LOCALE = 'fr-FR';

/** "2 avr. 2026" */
export function fmtDate(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, {
		day: 'numeric',
		month: 'short',
		year: 'numeric',
		timeZone: TZ,
	});
}

/** "2 avril 2026" */
export function fmtDateLong(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, {
		day: 'numeric',
		month: 'long',
		year: 'numeric',
		timeZone: TZ,
	});
}

/** "10/04/2026" */
export function fmtDateShort(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, { dateStyle: 'short', timeZone: TZ });
}

/** "2 avr. 2026, 14:30" */
export function fmtDatetime(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleString(LOCALE, {
		day: 'numeric',
		month: 'short',
		year: 'numeric',
		hour: '2-digit',
		minute: '2-digit',
		timeZone: TZ,
	});
}

/** "10/04/2026 14:30" */
export function fmtDatetimeShort(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleString(LOCALE, {
		dateStyle: 'short',
		timeStyle: 'short',
		timeZone: TZ,
	});
}

/** "14:30" */
export function fmtTime(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleTimeString(LOCALE, {
		hour: '2-digit',
		minute: '2-digit',
		timeZone: TZ,
	});
}

/** "avril 2026" */
export function fmtMonthYear(d: string | Date | null | undefined): string {
	if (!d) return '—';
	const dt = typeof d === 'string' ? new Date(d) : d;
	return dt.toLocaleDateString(LOCALE, { month: 'long', year: 'numeric', timeZone: TZ });
}

/** Les douze mois, au nom français — l'ordre est celui du calendrier (index + 1). */
export const NOMS_MOIS = [
	'janvier',
	'février',
	'mars',
	'avril',
	'mai',
	'juin',
	'juillet',
	'août',
	'septembre',
	'octobre',
	'novembre',
	'décembre',
] as const;

/**  L'exercice comptable d'une copropriété, d'après son mois de début (#1643) :
 *   « année civile », « de juillet à juin ». `null` vaut janvier, comme au serveur. */
export function libelleExercice(moisDebut: number | null | undefined): string {
	const m = moisDebut && moisDebut >= 1 && moisDebut <= 12 ? moisDebut : 1;
	if (m === 1) return 'année civile';
	return `de ${NOMS_MOIS[m - 1]} à ${NOMS_MOIS[(m + 10) % 12]}`;
}

/** Le mois court d'un numéro (1 à 12) : "sept.", "oct." — légende d'un graphe par jour. */
export function fmtMoisCourt(mois: number): string {
	return new Date(Date.UTC(2000, mois - 1, 15, 12)).toLocaleDateString(LOCALE, {
		month: 'short',
		timeZone: TZ,
	});
}

/**
 * La date de `fmtDate` en TROIS morceaux — « 2 », « avr. », « 2026 » — pour une
 * mise en page qui les pose sur des lignes différentes : la gouttière d'une carte
 * d'affaire (maquette B, 10/10/2026), où le jour se lit en grand.
 *
 * Les morceaux viennent de `formatToParts`, avec le fuseau et la locale de tout
 * ce module : les recoller doit redonner `fmtDate`, et `e2e/gouttiere-nature`
 * le vérifie. `null` pour une date absente : la gouttière se tait
 * plutôt que d'afficher « — » sur trois lignes.
 */
export function partiesDate(
	d: string | null | undefined,
): { jour: string; mois: string; annee: string } | null {
	if (!d) return null;
	const parties = new Intl.DateTimeFormat(LOCALE, {
		day: 'numeric',
		month: 'short',
		year: 'numeric',
		timeZone: TZ,
	}).formatToParts(new Date(d));
	const lire = (type: Intl.DateTimeFormatPartTypes) =>
		parties.find((p) => p.type === type)?.value ?? '';
	return { jour: lire('day'), mois: lire('month'), annee: lire('year') };
}

/**
 * Le JOUR de Paris d'un instant, en `AAAA-MM-JJ` — la valeur d'un champ
 * `type="date"`. Sans argument, aujourd'hui : la date qu'un formulaire PROPOSE.
 *
 * ⚠️ Jamais `toISOString().slice(0, 10)` : c'est le jour UTC, faux d'un jour
 * entre minuit et deux heures (le pendant serveur est `horloge.aujourd_hui`).
 */
export function jourIso(d: string | Date = new Date()): string {
	return new Intl.DateTimeFormat('en-CA', {
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		timeZone: TZ,
	}).format(new Date(d));
}

/** "2 avril" (jour + mois long, sans année) */
export function fmtDayMonth(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, { day: 'numeric', month: 'long', timeZone: TZ });
}

/**
 * La salutation qui convient à l'heure qu'il est.
 *
 * ⚠️ À employer via `relire(donnees, salutation)` : dans un `$:` qui ne cite
 * aucune variable réactive, elle serait figée au montage et dirait « Bonjour »
 * à 20 h (`#lib/utils.relire`, #549).
 */
export function salutation(): string {
	const h = new Date().getHours();
	if (h < 6) return 'Bonne nuit';
	if (h < 12) return 'Bonjour';
	if (h < 18) return 'Bon après-midi';
	return 'Bonsoir';
}

/**
 * Un instant ISO vers la valeur d un champ `datetime-local`, et retour.
 *
 * Ajoutés le 20/09/2026 avec la section « Quand » (#1092). Le découpage
 * `slice(0, 16)` est trivial — et c est exactement pour ça qu il serait recopié
 * dans chaque écran qui porte une date, puis qu une copie oublierait le cas du
 * champ vide. Dates et montants sont les deux récidivistes de la duplication
 * ici (socle 02 §2) : le format vit dans ce fichier, et nulle part ailleurs.
 */
export function pourChampLocal(iso: string | null | undefined): string {
	if (!iso) return '';
	return String(iso).slice(0, 16);
}

/**
 * L'heure de Paris, maintenant, en valeur d'un champ `datetime-local`
 * (`AAAA-MM-JJTHH:MM`) — ce qu'un formulaire PROPOSE pour « quand » (#2041).
 *
 * ⚠️ Jamais `toISOString().slice(0, 16)` : c'est l'heure UTC, fausse d'une ou
 * deux heures selon la saison.
 */
export function champLocalMaintenant(): string {
	return new Intl.DateTimeFormat('sv-SE', {
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		timeZone: TZ,
	})
		.format(new Date())
		.replace(' ', 'T');
}

/** L inverse : la valeur du champ vers ce que l API attend, ou `null` si vide. */
export function depuisChampLocal(valeur: string | null | undefined): string | null {
	const v = (valeur ?? '').trim();
	return v ? v : null;
}
