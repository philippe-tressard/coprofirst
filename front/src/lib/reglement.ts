/**
 * Les questions au règlement de copropriété — ce qui se déclare hors de l'écran.
 *
 * Le LIBELLÉ d'un verdict vient du serveur (`verdict_libelle`, une seule liste :
 * `utils/question_reglement/format.VERDICTS`) ; sa teinte, de `BADGES_DU_VERDICT`.
 */
import { ACCEPT_DOCUMENTS, LIBELLE_TYPES } from '#lib/fichiers.ts';

/**
 * Les fichiers du règlement : les documents de tout le site, PLUS le Markdown
 * que l'assistant lit (11/10/2026). Dérivés des constantes communes : une
 * extension ajoutée là-bas se retrouve ici sans y toucher.
 */
export const ACCEPT_FICHIERS_REGLEMENT = `${ACCEPT_DOCUMENTS},text/markdown,.md,.markdown`;
export const TYPES_FICHIERS_REGLEMENT = `${LIBELLE_TYPES.documents}, Markdown (.md)`;

/**
 * La teinte d'un état de transcription d'un PV d'AG (29/10/2026) — le LIBELLÉ
 * vient du serveur (`statut_libelle`, `transcription.STATUTS`).
 */
export const TEINTE_TRANSCRIPTION: Record<string, string> = {
	en_cours: 'badge-blue',
	a_relire: 'badge-orange',
	validee: 'badge-green',
	echec: 'badge-red',
};

/**
 * La teinte de la capsule d'un VERDICT, selon le ton que le serveur sert avec lui
 * (`format.TONS_VERDICT`, #2505). Un ton absent ou inconnu se lit incertain.
 *
 * 🔒 Table PUBLIÉE aux clients (`badgesDuVerdict`, #2773) — littérale. Elle vivait
 * dans `BadgeVerdict.svelte`, en conditions `class:` : les apps la recopiaient.
 * À ne pas confondre avec `TEINTE_DU_TON` (`journal-verdicts.ts`), autre table.
 */
export const BADGES_DU_VERDICT = {
	parTon: {
		succes: 'badge-green',
		danger: 'badge-red',
		alerte: 'badge-orange',
		neutre: 'badge-gray',
	},
	inconnu: 'badge-yellow',
};

/** La teinte d'un verdict de ce ton. */
export function teinteDuVerdict(ton: string | undefined | null): string {
	return (
		(BADGES_DU_VERDICT.parTon as Record<string, string>)[ton ?? ''] ?? BADGES_DU_VERDICT.inconnu
	);
}
