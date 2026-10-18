/**
 * Auto-test de `check-arbitrages.mjs` : le contrôle doit ÉCHOUER sur chaque
 * registre fautif et passer sur un registre sain (`standards/04` §2, cas zéro).
 * Ses cas citent exprès des numéros absents : il est déclaré dans `EXCEPTIONS`.
 */
import { fautesDeCitation, fautesDuRegistre } from './lib-arbitrages.mjs';

// ── 3. Auto-test : le contrôle doit ÉCHOUER sur chaque registre fautif ───────

const CHAMPS_PLEINS = ['Décidé', 'Pourquoi', 'Tenu par'];
/** Une entrée saine, avec de quoi la fausser. */
function entree(n, o = {}) {
	const statut = o.statut ?? 'en vigueur';
	const prov = 'prov' in o ? o.prov : '18/08/2026 · #12 · l’utilisateur · §3';
	const champs = o.champs ?? CHAMPS_PLEINS;
	const tenu = o.tenu ?? '`npm run lint:carte-liste`';
	const lignes = [`### n° ${n} · ${statut} — Un titre`];
	if (prov !== null) lignes.push(prov);
	for (const c of champs) lignes.push(`- **${c}** : ${c === 'Tenu par' ? tenu : 'du texte'}`);
	return lignes.join('\n');
}
const registre = (...es) =>
	`# Registre\n\n\`\`\`\n### n° N · <statut> — gabarit\n\`\`\`\n\n---\n\n${es.join('\n\n')}\n`;

const MONDE = {
	scripts: { 'lint:carte-liste': 'node x', 'lint:etats': 'node y' },
	fichiers: new Set(['api/tests/test_exemple.py', 'front/e2e/depot.spec.ts']),
};
const SAIN = registre(entree(1), entree(2));

/** [description, registre, motif attendu dans les fautes (null = aucune), options]. */
const CAS_REGISTRE = [
	['registre sain', SAIN, null],
	['statut inconnu', registre(entree(1, { statut: 'validé' })), /titre hors forme/],
	[
		'titre sans tiret long',
		registre(entree(1)).replace('Un titre', 'x').replace(' — x', ' - x'),
		/titre hors forme/,
	],
	['numéro sauté', registre(entree(1), entree(3)), /numérotation non continue/],
	['numéro répété', registre(entree(1), entree(1)), /répété/],
	['sans provenance', registre(entree(1, { prov: null })), /provenance absente/],
	[
		'provenance à trois champs',
		registre(entree(1, { prov: '18/08/2026 · #12 · l’utilisateur' })),
		/provenance absente/,
	],
	[
		'provenance sans date',
		registre(entree(1, { prov: 'hier · #12 · l’utilisateur · §3' })),
		/ne commence pas par une date/,
	],
	[
		'sans « Décidé »',
		registre(entree(1, { champs: ['Pourquoi', 'Tenu par'] })),
		/« Décidé » absent/,
	],
	[
		'sans « Pourquoi »',
		registre(entree(1, { champs: ['Décidé', 'Tenu par'] })),
		/« Pourquoi » absent/,
	],
	[
		'sans « Tenu par »',
		registre(entree(1, { champs: ['Décidé', 'Pourquoi'] })),
		/« Tenu par » absent/,
	],
	['`ouvert` sans champs : admis', registre(entree(1, { statut: 'ouvert', champs: [] })), null],
	[
		'`remplacé` sans champs : admis',
		registre(entree(1, { statut: 'remplacé par n° 2', champs: [] }), entree(2)),
		null,
	],
	[
		'remplacé par une entrée absente',
		registre(entree(1, { statut: 'remplacé par n° 9', champs: [] })),
		/n° 9, qui n'est pas/,
	],
	[
		'remplacé par lui-même',
		registre(entree(1, { statut: 'remplacé par n° 1', champs: [] })),
		/elle-même/,
	],
	[
		'renvoi interne vers une entrée absente',
		registre(entree(1), entree(2)).replace('du texte', 'voir n° 77'),
		/n° 77/,
	],
	[
		'renvoi interne vers une entrée présente',
		registre(entree(1), entree(2)).replace('du texte', 'voir n° 2'),
		null,
	],
	[
		'script lint absent',
		registre(entree(1, { tenu: '`npm run lint:fantome`' })),
		/aucun script « lint:fantome »/,
	],
	[
		'script lint sans « npm run » absent',
		registre(entree(1, { tenu: '`lint:fantome`' })),
		/aucun script « lint:fantome »/,
	],
	[
		'script lint présent',
		registre(entree(1, { tenu: '`npm run lint:etats`, `lint:carte-liste`' })),
		null,
	],
	[
		'test python absent',
		registre(entree(1, { tenu: '`test_fantome.py`' })),
		/fichier de test introuvable/,
	],
	['test python présent', registre(entree(1, { tenu: '`test_exemple.py`' })), null],
	[
		'e2e sans extension absent',
		registre(entree(1, { tenu: '`e2e/fantome`' })),
		/fichier de test introuvable/,
	],
	['e2e sans extension présent', registre(entree(1, { tenu: '`e2e/depot`' })), null],
	['composant nommé : non jugé', registre(entree(1, { tenu: '`CarteListe`' })), null],
	['cas zéro : registre vide', '# Registre\n', /0 entrée\(s\) lue\(s\)/, 21],
	['cas zéro : moins de 21 entrées', SAIN, /2 entrée\(s\) lue\(s\)/, 21],
];

const NUMEROS = new Set([1, 2]);
/** [description, contenus, nombre de fautes attendu]. */
const CAS_CITATION = [
	['citation d’un numéro présent', { 'a.md': 'voir arbitrage n° 2 de la skill' }, 0],
	['citation d’un numéro absent', { 'a.md': 'voir arbitrage n° 99' }, 1],
	['citation en liste, un absent', { 'a.md': 'les arbitrages n° 1 et 99' }, 1],
	['citation avec espace insécable', { 'a.md': 'arbitrage n° 99' }, 1],
	['« arbitrage 2 » d’un autre document : non jugé', { 'a.py': '(§9, arbitrage 98)' }, 0],
	[
		'le fichier d’exception est ignoré',
		{ 'front/scripts/check-arbitrages.selftest.mjs': 'arbitrage n° 99' },
		0,
	],
];

export function autotest() {
	let ko = 0;
	const rendre = (ok, d) => {
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${d}`);
		if (!ok) ko = 1;
	};
	for (const [d, texte, motif, minimum] of CAS_REGISTRE) {
		const fautes = fautesDuRegistre(texte, { ...MONDE, minimum });
		rendre(motif === null ? fautes.length === 0 : fautes.some((f) => motif.test(f)), d);
	}
	for (const [d, contenus, attendu] of CAS_CITATION) {
		rendre(fautesDeCitation(contenus, NUMEROS).length === attendu, d);
	}
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	return ko;
}
