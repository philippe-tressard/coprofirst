#!/usr/bin/env node
/**
 *  Les **statuts d'un accès** (badge Vigik, télécommande) — libellé, badge et
 *  pictogramme — ne s'écrivent que dans `#lib/types-acces` (#1575, 02/10/2026).
 *
 *  🔴 `STATUTS_ACCES` les portait depuis #1345, et six écrans la lisaient. Une
 *  table locale survivait pourtant dans `FormulaireAcces` — les pastilles du
 *  choix d'état —, sans import de `types-acces`, avec son propre libellé :
 *
 *  | | `STATUTS_ACCES` | `FormulaireAcces` |
 *  |---|---|---|
 *  | actif | « Actif » | « ✅ Actif » |
 *  | suspendu | « Suspendu » | « ⏸️ Suspendu » |
 *  | perdu | « Perdu » | « 🔎 Perdu » |
 *
 *  `lint:tables-statuts` ne la voyait pas : il compare deux tables **du même
 *  fichier**, et celle-ci était seule dans le sien. La table la plus déployée a
 *  primé (`standards/02` §4 bis) et s'est enrichie du pictogramme ; le choix
 *  lit `STATUT_ACCES_OPTIONS`.
 *
 *  ## La forme refusée
 *
 *  Une ENTRÉE de table qui décrit `suspendu` : `val: 'suspendu'`, une clé
 *  `suspendu:`, un couple `['suspendu', …]`, un `case 'suspendu':`. C'est la
 *  valeur qui n'appartient qu'à `StatutAcces` côté serveur — `perdu` est aussi
 *  un état d'objet remis au locataire (`StatutObjet`, `InventaireBail`), `actif`
 *  se dit de cent choses. Une comparaison (`statut === 'suspendu'`) n'est pas
 *  une table : hors portée.
 *
 *  Lancer : node scripts/check-statuts-acces.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

const SOURCE = 'src/lib/types-acces.ts';

/**  Une entrée de table — objet, dictionnaire, couple ou `switch` — pour l'état
 *   `suspendu` d'un accès. */
const COPIE =
	/\b(?:val|value)\s*:\s*['"`]suspendu['"`]|^\s*['"]?suspendu['"]?\s*:|\[\s*['"`]suspendu['"`]\s*,|\bcase\s+['"`]suspendu['"`]/;

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		temoin: SOURCE,
		fautes: lignesPortant(COPIE),
		cas: [
			//  🔴 La copie telle qu'elle était écrite dans `FormulaireAcces`.
			["\t\t{ val: 'suspendu', label: '⏸️ Suspendu' },", 1],
			["\t{ value: 'suspendu', label: 'Suspendu', badge: 'badge-orange' },", 1],
			//  Un dictionnaire, puis un couple d'`Object.fromEntries`.
			["\t\tsuspendu: 'badge-orange',", 1],
			["\t\t'suspendu': { libelle: 'Suspendu' },", 1],
			["\t['suspendu', 'Suspendu'],", 1],
			["\t\tcase 'suspendu':", 1],
			//  Les formes voulues, jamais signalées.
			['\t<ChoixPastilles options={STATUT_ACCES_OPTIONS} bind:valeur={saisie.statut} />', 0],
			['\t{statutAccesLabel(item.statut)}', 0],
			//  Une comparaison n'est pas une table.
			["\tif (a.statut === 'suspendu') return;", 0],
			//  `perdu` est aussi un état d'objet remis (`StatutObjet`) : hors portée.
			["\t\tperdu: { libelle: 'Perdu', badge: 'badge-red' },", 0],
			//  Un commentaire qui cite la forme refusée.
			["\t// on écrivait { val: 'suspendu', label: '⏸️ Suspendu' } ici", 0],
		],
		ok: "Statuts d'accès : écrits dans `#lib/types-acces` seul",
		ko: "table(s) des statuts d'accès écrite(s) hors de `#lib/types-acces`",
		conseil:
			'Lire `STATUTS_ACCES`, `STATUT_ACCES_OPTIONS`, `statutAccesLabel` ou ' +
			'`statutAccesBadge` (`#lib/types-acces`) ; un attribut qui manque s’y ajoute.',
	}),
);
