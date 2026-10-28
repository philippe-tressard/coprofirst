#!/usr/bin/env node
/**
 *  Une valeur SAISIE se convertit en nombre par `nombreOuNull` (`#lib/utils`),
 *  jamais à la main (#1516, 01/10/2026).
 *
 *  🔴 Un `<input type="number" bind:value>` vidé rend `null` (Svelte), pas
 *  `''`. Les conversions écrites à la main ne testaient que l'un des deux :
 *
 *  | Forme | Champ vidé | Défaut |
 *  |---|---|---|
 *  | `v === '' ? null : Number(v)` | `Number(null)` = **0** | l'index d'un relevé enregistré à 0 m³, un nombre de lots à 0 (#779) |
 *  | `v ? Number(v) : null` | `null` | juste, mais un **0** saisi devient `null` |
 *  | `Number(v) \|\| null` | `null` | idem |
 *
 *  Dix copies, trois comportements pour une notion. Ce contrôle refuse la
 *  onzième : une conversion `Number` / `parseFloat` / `parseInt` gardée par un
 *  test de vide (`=== ''`, `!== ''`, ternaire sur la valeur, `|| null`).
 *  Une lecture de configuration avec repli (`parseInt(x) || 587`) n'est pas une
 *  saisie, et n'est pas visée.
 *
 *  Lancer : node scripts/check-nombre-saisi.mjs [--selftest]
 */
import { controler } from './lib-source-unique.mjs';

/**  Écarts déclarés, avec leur raison. Une entrée qui ne sert plus fait échouer. */
const EXCEPTIONS = {
	'src/lib/deepLink.ts': "un fragment d'adresse déjà filtré par une expression, pas une saisie",
};
const CONV = String.raw`(?:Number|parseFloat|parseInt)\(`;

/**  Les trois formes d'une conversion de saisie écrite à la main. */
const COPIES = [
	//  `v === '' ? null : Number(v)` · `v !== '' ? Number(v) : null`
	new RegExp(String.raw`[!=]==\s*''\s*\?\s*(?:null|undefined|${CONV})`),
	//  `v ? Number(v) : null|undefined`
	new RegExp(String.raw`\?\s*${CONV}[^()]*\)\s*:\s*(?:null|undefined)\b`),
	//  `Number(v) || null`
	new RegExp(String.raw`${CONV}[^()]*\)\s*\|\|\s*(?:null|undefined)\b`),
];

export function fautes(source) {
	//  Une expression coupée par Prettier se relit sur une ligne.
	const lignes = source.split('\n');
	const trouvees = [];
	for (let i = 0; i < lignes.length; i++) {
		const l = lignes[i].trim();
		if (l.startsWith('//') || l.startsWith('*')) continue;
		const fenetre = [l, (lignes[i + 1] ?? '').trim(), (lignes[i + 2] ?? '').trim()].join(' ');
		const suite = (lignes[i + 1] ?? '').trim();
		const coupee = /\?\s*$/.test(l) || suite.startsWith('?');
		//  Coupée : comptée sur sa PREMIÈRE ligne, et seulement si la suivante ne
		//  la porte pas déjà entière — sinon `...(cond` puis `? { a: v ? Number(v)
		//  : null }` compterait deux fois la même conversion.
		const entiere = (t) => COPIES.some((m) => m.test(t));
		if (entiere(l) || (coupee && entiere(fenetre) && !entiere(suite))) trouvees.push(i + 1);
	}
	return trouvees;
}

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		sources: ['src/lib/utils.ts'],
		exceptions: EXCEPTIONS,
		fautes,
		cas: [
			["\t\tindex: releveForm.index !== '' ? Number(releveForm.index) : null,", 1],
			["\t\tprestataireId = choix === '' ? null : Number(choix);", 1],
			['\t\tlot_id: editLot ? Number(editLot) : null,', 1],
			['\t\tannee: s.annee ? Number(s.annee) : undefined,', 1],
			["\t\tconst prixEnvoye = typeAnnonce === 'vente' && prix ? parseFloat(prix) : null;", 1],
			['\t\tfrequence_valeur: entretien ? Number(s.frequenceValeur) || null : null,', 1],
			//  Coupée par Prettier sur trois lignes.
			['\t\tduree: f.duree\n\t\t\t? Number(f.duree)\n\t\t\t: null,', 1],
			//  Entière sur la ligne qui suit un `...(cond` : comptée une fois.
			['\t\t...(avecAg\n\t\t\t? { annee: s.annee ? Number(s.annee) : undefined }\n\t\t\t: {}),', 1],
			//  La forme voulue, jamais signalée.
			['\t\tindex: nombreOuNull(releveForm.index),', 0],
			//  Une configuration lue avec repli : hors portée.
			["\t\tsmtpConfig.port = parseInt(lues['smtp_port'] ?? '587') || 587;", 0],
			['\t$: appelsMois = Number(valeurs[cles.appels_mois]) || 0;', 0],
			//  Un commentaire qui cite la forme refusée.
			["\t// on écrivait v === '' ? null : Number(v)", 0],
		],
		ok: 'Nombres saisis : convertis par nombreOuNull seulement',
		ko: 'conversion(s) de saisie en nombre écrite(s) à la main',
		conseil:
			"Employer `nombreOuNull(v)` (`#lib/utils`) : '', null et undefined donnent null, 0 reste 0.",
	}),
);
