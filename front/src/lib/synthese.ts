/**
 * La synthèse d'une affaire close (#1643) — ce que les cinq graphiques lisent.
 *
 * Les métriques sont CALCULÉES par le serveur et figées à la production
 * (`api/app/utils/synthese_affaire/metriques.py`) : ce module ne mesure rien,
 * il met en forme — jours au demi-jour, libellés d'étapes, proportions.
 *
 * ⚠️ « 22,5 j » s'écrit aussi côté serveur (`jours_ouvres.libelle_jours`, lu par
 * l'assistant) : les contextes de build `./api` et `./front` interdisent le
 * partage d'un fichier. Les deux disent la même chose, et chacun a son test.
 */
import { fmtNombre } from '#lib/utils.ts';
import { CATEGORIES_TICKET, STATUT_TICKET_LABELS } from '#lib/tickets.ts';
import type {
	EtapeMoyenne,
	EtapeSynthese,
	MetriquesSynthese,
	ResumeAffaires,
} from '#lib/api/index.ts';

/** Le temps passé close avant une réouverture — une étape à part (serveur). */
export const CLOSE_AVANT_REOUVERTURE = 'close_avant_reouverture';

/** « 22,5 j », « 3 j », « — » — des jours ouvrés, au demi-jour. */
export function fmtJours(jours: number | null | undefined): string {
	return jours == null ? '—' : `${fmtNombre(jours)} j`;
}

/** Le libellé d'une étape — celui du workflow, jamais réécrit ici. */
export function libelleEtape(statut: string | null | undefined): string {
	if (statut === CLOSE_AVANT_REOUVERTURE) return 'Close, avant réouverture';
	return STATUT_TICKET_LABELS[statut ?? ''] ?? statut ?? '';
}

/** Le nom d'une catégorie, sans son emoji — il se lit au milieu d'une phrase. */
export function nomCategorie(code: string): string {
	return CATEGORIES_TICKET.find((c) => c.value === code)?.label ?? code;
}

/** Une issue se dit au féminin : « résolue », « annulée ». */
export function libelleIssue(issue: string): string {
	return issue === 'annulé' ? 'annulée' : 'résolue';
}

/**
 * Les segments de la frise (M1) : chaque étape en part de la durée totale.
 *
 * Une étape d'une demi-journée garde une largeur minimale lisible ; la somme
 * peut alors dépasser 100 % de quelques points, ce que `flex` absorbe.
 */
export function segmentsFrise(m: MetriquesSynthese): Array<EtapeSynthese & { part: number }> {
	const total = m.etapes.reduce((s, e) => s + e.jours, 0) || 1;
	return m.etapes.map((e) => ({ ...e, part: Math.max(4, (e.jours / total) * 100) }));
}

/** La barre d'une valeur face à la plus grande des deux (M4), en pourcentage. */
export function partBarre(valeur: number | null, autre: number | null): number {
	const max = Math.max(valeur ?? 0, autre ?? 0);
	return max > 0 && valeur != null ? Math.max(2, (valeur / max) * 100) : 0;
}

/** « 2 semaines muettes sur 10 » — le compte que l'histogramme (M5) résume. */
export function libelleMuettes(m: MetriquesSynthese): string {
	const n = m.semaines_muettes;
	return `${n} semaine${n > 1 ? 's' : ''} muette${n > 1 ? 's' : ''} sur ${m.semaines.length}`;
}

/**
 * L'étape d'un ENSEMBLE d'affaires (#1645, #1646) — `null` quand aucune n'y est
 * passée : « Chez le prestataire » absente ne vaut pas « 0 j ».
 */
export function etapeMoyenne(r: ResumeAffaires, statut: string): EtapeMoyenne | null {
	return r.etapes.find((e) => e.statut === statut) ?? null;
}

/** « sur 1 affaire », « sur 3 affaires » — l'effectif d'une moyenne partielle. */
export function surAffaires(n: number): string {
	return `sur ${fmtNombre(n)} affaire${n > 1 ? 's' : ''}`;
}

/** « 1 affaire », « 3 affaires » — et « dont 1 annulée » quand il y en a. */
export function libelleAffaires(r: Pick<ResumeAffaires, 'nombre' | 'annulees'>): string {
	const n = r.nombre;
	const base = `${fmtNombre(n)} affaire${n > 1 ? 's' : ''} close${n > 1 ? 's' : ''}`;
	if (!r.annulees) return base;
	return `${base}, dont ${fmtNombre(r.annulees)} annulée${r.annulees > 1 ? 's' : ''}`;
}
