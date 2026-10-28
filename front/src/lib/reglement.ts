/**
 * Les questions au règlement de copropriété — ce qui se déclare hors de l'écran.
 *
 * Le LIBELLÉ d'un verdict vient du serveur (`verdict_libelle`, une seule liste :
 * `utils/question_reglement/format.VERDICTS`) ; sa teinte, de `BadgeVerdict`.
 */
import { ACCEPT_DOCUMENTS, LIBELLE_TYPES } from '#lib/fichiers.ts';

/**
 * Les fichiers du règlement : les documents de tout le site, PLUS le Markdown
 * que l'assistant lit (11/10/2026). Dérivés des constantes communes : une
 * extension ajoutée là-bas se retrouve ici sans y toucher.
 */
export const ACCEPT_FICHIERS_REGLEMENT = `${ACCEPT_DOCUMENTS},text/markdown,.md,.markdown`;
export const TYPES_FICHIERS_REGLEMENT = `${LIBELLE_TYPES.documents}, Markdown (.md)`;
