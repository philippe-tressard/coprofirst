import type {
	CandidateFusion,
	ChoixConciliation,
	CodeConciliation,
	OptionConciliation,
} from '#lib/api/index.ts';

/**
 * **La CONCILIATION d'une fusion refusée pour fuite de lecture** — ce que l'écran
 * décide, sans rien recalculer : l'écart, les options et les noms viennent du
 * serveur (`utils/fusion_conciliation`), qui les mesure avec la règle d'accès.
 *
 * Une affaire refusée n'est plus un cul-de-sac : le conseil choisit, par
 * affaire, de la laisser hors de la fusion, d'**inverser** (l'autre absorbe),
 * de **restreindre** la principale à ce que les deux avaient en commun, ou de
 * l'**élargir** à l'union — ce dernier choix, comme tout geste qui fait lire à
 * quelqu'un ce qu'il ne lisait pas, se confirme NOMINATIVEMENT.
 */

/** Ce que le conseil a décidé pour une affaire refusée : l'option, et si les noms sont confirmés. */
export interface DecisionConciliation {
	option: CodeConciliation;
	confirme: boolean;
}

/** Les décisions, par identifiant d'affaire refusée — `null` : elle reste hors de la fusion. */
export type Decisions = Record<number, DecisionConciliation | null | undefined>;

export function optionDe(
	c: CandidateFusion,
	code: CodeConciliation,
): OptionConciliation | undefined {
	return c.conciliation?.options.find((o) => o.code === code);
}

/** Refusée, mais le conseil a au moins une façon de l'autoriser. */
export function conciliable(c: CandidateFusion): boolean {
	return !c.fusionnable && !!c.conciliation?.options.some((o) => o.disponible);
}

/** Choisie, disponible, et confirmée par ses noms quand elle l'exige. */
export function decisionPrete(
	c: CandidateFusion,
	d: DecisionConciliation | null | undefined,
): boolean {
	if (!d) return false;
	const o = optionDe(c, d.option);
	return !!o && o.disponible && (!o.consentement || d.confirme);
}

/** Une option est choisie mais ses noms ne sont pas confirmés : on ne continue pas. */
export function decisionIncomplete(
	c: CandidateFusion,
	d: DecisionConciliation | null | undefined,
): boolean {
	return !!d && !decisionPrete(c, d);
}

/** Ce que le corps de la requête envoie : restreindre / élargir, avec les noms montrés. */
export function choixPourServeur(
	candidates: CandidateFusion[],
	decisions: Decisions,
): ChoixConciliation[] {
	const rendu: ChoixConciliation[] = [];
	for (const c of candidates) {
		const d = decisions[c.id];
		if (!d || d.option === 'inverser' || !decisionPrete(c, d)) continue;
		rendu.push({
			affaire_id: c.id,
			option: d.option,
			confirmes: (optionDe(c, d.option)?.exposes ?? []).map((p) => p.id),
		});
	}
	return rendu;
}

/** L'affaire que le conseil a choisi de faire absorber, ou `null`. */
export function principaleInversee(
	candidates: CandidateFusion[],
	decisions: Decisions,
): number | null {
	return candidates.find((c) => decisions[c.id]?.option === 'inverser')?.id ?? null;
}

/**
 * Ce qu'un choix verrouille chez les AUTRES affaires refusées : une inversion
 * change la principale — les restreindre / élargir mesurés pour l'ancienne n'ont
 * plus de sens —, et inversement.
 */
export function verrous(candidates: CandidateFusion[], decisions: Decisions, id: number) {
	const autres = candidates.filter((c) => c.id !== id);
	return {
		/** Une autre affaire inverse déjà : celle-ci ne peut plus que rester hors de la fusion. */
		bloque: autres.some((c) => decisions[c.id]?.option === 'inverser'),
		/** Une autre affaire restreint ou élargit déjà : l'inversion n'est plus mesurée. */
		inversionInterdite: autres.some((c) => {
			const o = decisions[c.id]?.option;
			return o === 'restreindre' || o === 'elargir';
		}),
	};
}
