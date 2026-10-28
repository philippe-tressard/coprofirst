#!/usr/bin/env node
/**
 *  Le LIBELLÉ d'un état ne se recalcule pas en remplaçant le soulignement de sa
 *  valeur brute (#779, 01/10/2026).
 *
 *  🔴 « Mes lots » rendait le bail d'un locataire par `statut === 'actif' ?
 *  'Bail actif' : statut.replace('_', ' ')`, dans un badge TOUJOURS vert — alors
 *  que `BadgeStatutBail` porte le libellé ET la teinte de chaque état depuis le
 *  15/09/2026. Un bail « en cours de sortie » y serait sorti en vert, avec le
 *  libellé « en_cours sortie ».
 *
 *  Même famille que `lint:type-lot` : la forme d'une copie est le remplacement
 *  du soulignement, ici sur un champ `statut`. Les tables vivent dans `#lib`
 *  (`LIBELLE_STATUT_BAIL`, `#lib/roles`, `#lib/tickets`…).
 *
 *  Lancer : node scripts/check-statut-recalcule.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  `bail.statut.replace('_', ' ')`, `statut.replaceAll(/_/g, ' ')`… */
const COPIE = /\bstatut\s*\.\s*replace(?:All)?\(\s*(?:['"`]_['"`]|\/_\/g?)/;

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		fautes: lignesPortant(COPIE),
		cas: [
			["\t\t\t: monBailData.statut.replace('_', ' ')}</span", 1],
			['\t\t{bail.statut.replaceAll(/_/g, " ")}', 1],
			//  La forme voulue, jamais signalée.
			['\t\t<BadgeStatutBail statut={monBailData.statut} compact />', 0],
			//  Un `replace('_')` sur autre chose qu'un statut : hors portée.
			["\t\t{lot.numero.replace('_', '-')}", 0],
		],
		ok: "Libellés d'état : aucun recalculé depuis la valeur brute",
		ko: "libellé(s) d'état recalculé(s) depuis la valeur brute",
		conseil: 'Employer la table de son domaine (`BadgeStatutBail`, `LIBELLE_STATUT_BAIL`…).',
	}),
);
