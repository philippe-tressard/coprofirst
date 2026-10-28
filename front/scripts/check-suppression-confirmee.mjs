#!/usr/bin/env node
/**
 *  Une suppression DÉFINITIVE se confirme par `confirmer(SUPPRESSION(…))`
 *  (`#lib/confirmation`) — jamais par une modale écrite à la main (#779,
 *  01/10/2026).
 *
 *  🔴 Deux modales « … Cette action est irréversible. » avaient survécu au lot
 *  qui avait retiré les vingt-deux autres : la suppression d'un bail (« Mes
 *  lots ») et celle d'un compte (Admin › Utilisateurs). Chacune avait sa mise
 *  en forme, ses styles en ligne et son ordre de boutons.
 *
 *  Ce contrôle refuse la phrase hors de `#lib/confirmation.ts` : c'est elle qui
 *  signe une confirmation recopiée.
 *
 *  Lancer : node scripts/check-suppression-confirmee.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  La phrase qui signe une confirmation de suppression recopiée. */
const COPIE = /Cette action est irréversible/;

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		temoin: 'src/lib/confirmation.ts',
		fautes: lignesPortant(COPIE),
		cas: [
			['\t\t\t\tCette action est irréversible.', 1],
			['\t\t\t>Cette action est irréversible.</span', 1],
			//  La forme voulue, jamais signalée.
			["\tawait confirmerPuis(SUPPRESSION('Le bail'), 'Bail supprimé', async () => {", 0],
			//  Le mot seul, ou la phrase citée en commentaire : hors portée.
			['\t\t<!--  La corbeille EN DERNIER parce qu’elle est irréversible. -->', 0],
			['\t//  « Cette action est irréversible. » était écrit ici à la main', 0],
		],
		ok: 'Suppressions définitives : confirmées par SUPPRESSION seul',
		ko: 'confirmation(s) de suppression écrite(s) à la main',
		conseil: 'Employer `confirmerPuis(SUPPRESSION(…), succès, action)` — `#lib/confirmation`.',
	}),
);
