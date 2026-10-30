//  Les valeurs que l'API échange sous une forme TECHNIQUE, qui ne s'affichent
//  jamais telles quelles (#2358). Le type ne change rien à l'exécution : il dit
//  à `npm run lint:dates` (`scripts/check-nombres-bruts.mjs`) qu'un champ ainsi
//  déclaré se rend par son formateur, et le contrôle refuse le rendu brut.

/**
 * Un mois, sous sa clé `AAAA-MM` (« 2026-05 ») — il se lit « mai 2026 » par
 * `fmtMonthYear` (`#lib/date`). La télémétrie l'affichait tel quel
 * (« Record mois — 2026-05 »).
 */
export type MoisIso = string;
