#!/usr/bin/env node
/**
 * Garde-fou — **le registre des arbitrages d'interface** tient sa forme et ses
 * renvois (`.claude/skills/ux-patterns/ARBITRAGES.md`, 18/10/2026).
 *
 * ## Pourquoi il existe
 *
 * Le registre remplace le tableau « Ce qui est tranché » de la skill `ux-patterns` :
 * 65 décisions, chacune avec sa date, son ticket, son auteur, son pourquoi, ce qui
 * a été écarté et le contrôle qui la tient. Les numéros 1 à 21 sont cités ailleurs
 * (« arbitrage n° 21 », `CLAUDE.md`). Sans contrôle, trois choses dérivent au
 * premier lot (`standards/05`) :
 *
 *   • la **forme** — un titre qu'un `grep "^### n° [0-9]"` ne trouve plus, une
 *     entrée sans « Pourquoi » : l'arbitrage perd la raison qui le rendait
 *     discutable ;
 *   • les **numéros** — un trou, un doublon, ou une citation (« arbitrage n° 40 »
 *     dans une skill, un commentaire de composant) vers une entrée qui n'existe
 *     pas ou plus : la consigne renvoie alors à rien ;
 *   • le champ **« Tenu par »** — il nomme le contrôle qui fait respecter la
 *     décision. Un `npm run lint:xxx` renommé ou un test supprimé laisse une
 *     décision *affirmée tenue* qui ne l'est plus : le pire faux vert, celui qui
 *     se lit comme une garantie (`standards/04`).
 *
 * ## Ce qu'il refuse
 *
 *   1. un titre hors de la forme `### n° N · <statut> — <titre>`, avec statut ∈
 *      {en vigueur, révisé, remplacé par n° X, à arbitrer, ouvert} ;
 *   2. une numérotation non continue (1, 2, 3…), ou un numéro répété ;
 *   3. une entrée sans ligne de provenance (date · ticket · par · §), ou sans
 *      « Décidé », « Pourquoi », « Tenu par » — sauf `ouvert` et `remplacé par`,
 *      qui ne décident rien ou plus rien ;
 *   4. un `remplacé par n° X` vers une entrée absente (ou vers elle-même), et
 *      tout « n° N » du registre qui ne désigne aucune entrée ;
 *   5. tout « arbitrage n° N » cité dans le dépôt versionné (consignes, skills,
 *      code, tests) vers un numéro absent du registre ;
 *   6. un `npm run lint:xxx` (ou `lint:xxx`) nommé dans « Tenu par » qui n'est pas
 *      un script de `package.json`, et un fichier de test (`test_*.py`,
 *      `*.spec.ts`, `e2e/…`) qui n'existe pas.
 *
 * ## Qu'il ne juge pas
 *
 * Que le contrôle nommé soit **bon** : il dit seulement qu'il existe (même
 * limite que `lint:ci`). Les noms de composants (`CarteListe`…) ne sont pas
 * vérifiés — ni un « Tenu par » écrit « aucun garde-fou nommé », qui est une
 * réponse honnête.
 *
 * ## Fiabilité (`standards/04`)
 *
 * Cas zéro : un registre qui compte moins de 21 entrées (les n° 1 à 21 sont
 * figés), un dépôt dont le balayage lit moins de `FICHIERS_MINIMUM` fichiers, ou
 * un balayage qui ne retrouve plus la citation de `CLAUDE.md` (le témoin) **échouent** —
 * ils ne rendent jamais « aucune faute ». Git absent : INCONNU, pas OK.
 *
 * Lancer : node scripts/check-arbitrages.mjs [--selftest]
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE_DEPOT = fileURLToPath(new URL('../..', import.meta.url));
const REGISTRE = '.claude/skills/ux-patterns/ARBITRAGES.md';
const PACKAGE = 'front/package.json';

/** Les n° 1 à 21 viennent de l'ancien tableau et sont cités ailleurs : ils restent. */
const ENTREES_MINIMUM = 21;
/** Cas zéro du balayage des citations : un dépôt qui en lit moins n'est pas le dépôt. */
const FICHIERS_MINIMUM = 200;
/** Le fichier qui doit encore citer un arbitrage — sinon le balayage est aveugle. */
const TEMOIN = 'CLAUDE.md';
/**
 * Fichiers qui CITENT la forme refusée sans la porter — ce contrôle et son
 * auto-test. Une exception qui n'est plus lue par le balayage fait échouer.
 */
const EXCEPTIONS = {
	'front/scripts/check-arbitrages.mjs': 'ses cas d’auto-test citent un numéro absent exprès',
};
const EXTENSIONS_TEXTE = /\.(md|py|ts|mjs|js|svelte|css|sh|yml|yaml|json|html|toml|txt)$/;
const TAILLE_MAX = 2_000_000;

const STATUTS = /^(en vigueur|révisé|à arbitrer|ouvert|remplacé par n° (\d+))$/;
const TITRE = /^### n° (\d+) · (.+?) — (\S.*)$/;
const DATE = /^\d{1,2}(?:-\d{1,2})?\/\d{2}\/\d{4}/;
const CHAMP = /^- \*\*(Décidé|Pourquoi|Écarté|Tenu par|Historique)\*\*\s*:/;
const REQUIS = ['Décidé', 'Pourquoi', 'Tenu par'];
const CITATION = /arbitrages?\s+n°\s?(\d+(?:\s*(?:,|et)\s*\d+)*)/gi;

// ── 1. Le registre : forme, numéros, renvois ─────────────────────────────────

/** Les lignes du registre HORS blocs de code (le gabarit du « Format » y vit). PURE. */
function lignesHorsCode(texte) {
	let dansCode = false;
	return texte.split('\n').map((l, i) => {
		if (/^\s*```/.test(l)) {
			dansCode = !dansCode;
			return [i + 1, ''];
		}
		return [i + 1, dansCode ? '' : l.replace(/\r$/, '')];
	});
}

/** Les entrées du registre : titre, provenance, champs (texte continué jusqu'au suivant). PURE. */
function decouper(texte) {
	const entrees = [];
	const fautes = [];
	let cour = null;
	let champ = null;
	for (const [n, l] of lignesHorsCode(texte)) {
		if (/^###\s/.test(l)) {
			cour = { ligne: n, titre: l, numero: null, statut: null, provenance: null, champs: {} };
			champ = null;
			const m = TITRE.exec(l);
			if (!m || !STATUTS.test(m[2])) {
				fautes.push(
					`${REGISTRE}:${n} — titre hors forme « ${l.slice(0, 80)} » : attendu ` +
						'`### n° N · <en vigueur | révisé | remplacé par n° X | à arbitrer | ouvert> — <titre>`',
				);
			} else {
				cour.numero = Number(m[1]);
				cour.statut = m[2];
			}
			entrees.push(cour);
			continue;
		}
		if (!cour) continue;
		if (/^(##\s|---\s*$)/.test(l)) {
			cour = null;
			continue;
		}
		const c = CHAMP.exec(l);
		if (c) {
			champ = c[1];
			cour.champs[champ] = l;
		} else if (champ && l.trim() && !/^- \*\*/.test(l)) {
			cour.champs[champ] += ` ${l.trim()}`;
		} else if (!l.trim()) {
			champ = null;
		} else if (cour.provenance === null && !champ) {
			cour.provenance = l;
		}
	}
	return { entrees, fautes };
}

/**
 * Tous les `n° N` lus hors blocs de code, avec leur ligne. PURE.
 * (« Les n° 1 à 21 », « (n° 19) », « remplacé par n° 39 ».)
 */
function renvoisInternes(texte) {
	const renvois = [];
	for (const [n, l] of lignesHorsCode(texte)) {
		if (/^###\s/.test(l)) continue; // le titre est jugé par `decouper`
		for (const m of l.matchAll(/\bn°\s?(\d+)/g)) renvois.push([n, Number(m[1])]);
	}
	return renvois;
}

/** Le script `lint:xxx` d'un jeton « Tenu par », ou null. */
function scriptNomme(jeton) {
	const m = /^(?:npm run )?(lint:[\w:-]+)$/.exec(jeton);
	return m ? m[1] : null;
}

/** Ce jeton désigne-t-il un FICHIER DE TEST ? Rend ses chemins candidats, ou null. */
function candidatsTest(jeton) {
	const j = jeton.replace(/^\.\//, '');
	if (/^e2e\/[\w.-]+$/.test(j)) {
		const avecExt = /\.spec\.ts$/.test(j) ? j : `${j}.spec.ts`;
		return [`front/${avecExt}`];
	}
	if (/(^|\/)(test_\w+\.py|[\w.-]+\.spec\.ts)$/.test(j)) {
		return j.includes('/') ? [j, `front/${j}`, `api/tests/${j}`] : [`api/tests/${j}`, `front/e2e/${j}`];
	}
	return null;
}

/**
 * Les fautes du registre. PURE : rien n'est lu ici.
 *
 * @param {string} texte          le registre
 * @param {{scripts: Record<string, string>, fichiers: Set<string>, minimum?: number}} monde
 */
export function fautesDuRegistre(texte, { scripts, fichiers, minimum = 0 }) {
	const { entrees, fautes } = decouper(texte);
	if (entrees.length < minimum) {
		fautes.push(
			`${REGISTRE} — ${entrees.length} entrée(s) lue(s), ${minimum} attendues au moins ` +
				'(les n° 1 à 21 sont figés) : registre vide ou illisible',
		);
	}

	// 2. Numérotation : continue, sans répétition.
	const vus = new Set();
	let attendu = 1;
	for (const e of entrees) {
		if (e.numero === null) {
			attendu++;
			continue;
		}
		if (vus.has(e.numero)) fautes.push(`${REGISTRE}:${e.ligne} — le n° ${e.numero} est répété`);
		else if (e.numero !== attendu) {
			fautes.push(
				`${REGISTRE}:${e.ligne} — numérotation non continue : le n° ${attendu} était attendu, ` +
					`le n° ${e.numero} est lu`,
			);
		}
		vus.add(e.numero);
		attendu = e.numero + 1;
	}

	for (const e of entrees) {
		if (e.numero === null) continue;
		const ou = `${REGISTRE}:${e.ligne} (n° ${e.numero})`;
		const remplace = /^remplacé par n° (\d+)$/.exec(e.statut);

		// 4. Le remplaçant existe, et n'est pas l'entrée elle-même.
		if (remplace) {
			const x = Number(remplace[1]);
			if (x === e.numero) fautes.push(`${ou} — « remplacé par » elle-même`);
			else if (!entrees.some((o) => o.numero === x)) {
				fautes.push(`${ou} — remplacé par le n° ${x}, qui n'est pas dans le registre`);
			}
		}

		// 3. Provenance : date · ticket · par · §.
		const champsProv = (e.provenance ?? '').split(' · ');
		if (e.provenance === null || champsProv.length < 4 || champsProv.some((c) => !c.trim())) {
			fautes.push(`${ou} — ligne de provenance absente ou incomplète (date · ticket · par · §)`);
		} else if (!DATE.test(champsProv[0])) {
			fautes.push(`${ou} — la provenance ne commence pas par une date (jj/mm/aaaa) : « ${champsProv[0]} »`);
		}

		// 3. Champs requis, sauf `ouvert` et `remplacé` (rien de décidé, ou plus rien).
		const dispense = e.statut === 'ouvert' || remplace;
		if (!dispense) {
			for (const nom of REQUIS) {
				if (!e.champs[nom]) fautes.push(`${ou} — champ « ${nom} » absent`);
			}
		}

		// 6. Le contrôle nommé existe.
		for (const m of (e.champs['Tenu par'] ?? '').matchAll(/`([^`]+)`/g)) {
			const jeton = m[1].trim();
			const script = scriptNomme(jeton);
			if (script) {
				if (!(script in scripts)) {
					fautes.push(`${ou} — « Tenu par » nomme \`${jeton}\` : aucun script « ${script} » dans package.json`);
				}
				continue;
			}
			const cands = candidatsTest(jeton);
			if (cands && !cands.some((c) => fichiers.has(c))) {
				fautes.push(`${ou} — « Tenu par » nomme \`${jeton}\` : fichier de test introuvable (${cands.join(' | ')})`);
			}
		}
	}

	// 4 bis. Tout « n° N » du registre désigne une entrée.
	for (const [n, num] of renvoisInternes(texte)) {
		if (!vus.has(num)) fautes.push(`${REGISTRE}:${n} — renvoi au n° ${num}, qui n'est pas dans le registre`);
	}
	return fautes;
}

// ── 2. Les citations « arbitrage n° N » du dépôt ─────────────────────────────

/** Les numéros cités par « arbitrage n° N », avec leur ligne. PURE. */
export function citations(texte) {
	const trouvees = [];
	texte.split('\n').forEach((l, i) => {
		for (const m of l.matchAll(CITATION)) {
			for (const num of m[1].match(/\d+/g)) trouvees.push([i + 1, Number(num)]);
		}
	});
	return trouvees;
}

/** Les fautes de citation de `contenus` (chemin → texte) contre les numéros connus. PURE. */
export function fautesDeCitation(contenus, numeros) {
	const fautes = [];
	for (const [chemin, texte] of Object.entries(contenus)) {
		if (chemin in EXCEPTIONS) continue;
		for (const [n, num] of citations(texte)) {
			if (!numeros.has(num)) {
				fautes.push(`${chemin}:${n} — cite l'arbitrage n° ${num}, absent du registre`);
			}
		}
	}
	return fautes;
}

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
const registre = (...es) => `# Registre\n\n\`\`\`\n### n° N · <statut> — gabarit\n\`\`\`\n\n---\n\n${es.join('\n\n')}\n`;

const MONDE = {
	scripts: { 'lint:carte-liste': 'node x', 'lint:etats': 'node y' },
	fichiers: new Set(['api/tests/test_exemple.py', 'front/e2e/depot.spec.ts']),
};
const SAIN = registre(entree(1), entree(2));

/** [description, registre, motif attendu dans les fautes (null = aucune), options]. */
const CAS_REGISTRE = [
	['registre sain', SAIN, null],
	['statut inconnu', registre(entree(1, { statut: 'validé' })), /titre hors forme/],
	['titre sans tiret long', registre(entree(1)).replace('Un titre', 'x').replace(' — x', ' - x'), /titre hors forme/],
	['numéro sauté', registre(entree(1), entree(3)), /numérotation non continue/],
	['numéro répété', registre(entree(1), entree(1)), /répété/],
	['sans provenance', registre(entree(1, { prov: null })), /provenance absente/],
	['provenance à trois champs', registre(entree(1, { prov: '18/08/2026 · #12 · l’utilisateur' })), /provenance absente/],
	['provenance sans date', registre(entree(1, { prov: 'hier · #12 · l’utilisateur · §3' })), /ne commence pas par une date/],
	['sans « Décidé »', registre(entree(1, { champs: ['Pourquoi', 'Tenu par'] })), /« Décidé » absent/],
	['sans « Pourquoi »', registre(entree(1, { champs: ['Décidé', 'Tenu par'] })), /« Pourquoi » absent/],
	['sans « Tenu par »', registre(entree(1, { champs: ['Décidé', 'Pourquoi'] })), /« Tenu par » absent/],
	['`ouvert` sans champs : admis', registre(entree(1, { statut: 'ouvert', champs: [] })), null],
	['`remplacé` sans champs : admis', registre(entree(1, { statut: 'remplacé par n° 2', champs: [] }), entree(2)), null],
	['remplacé par une entrée absente', registre(entree(1, { statut: 'remplacé par n° 9', champs: [] })), /n° 9, qui n'est pas/],
	['remplacé par lui-même', registre(entree(1, { statut: 'remplacé par n° 1', champs: [] })), /elle-même/],
	['renvoi interne vers une entrée absente', registre(entree(1), entree(2)).replace('du texte', 'voir n° 77'), /n° 77/],
	['renvoi interne vers une entrée présente', registre(entree(1), entree(2)).replace('du texte', 'voir n° 2'), null],
	['script lint absent', registre(entree(1, { tenu: '`npm run lint:fantome`' })), /aucun script « lint:fantome »/],
	['script lint sans « npm run » absent', registre(entree(1, { tenu: '`lint:fantome`' })), /aucun script « lint:fantome »/],
	['script lint présent', registre(entree(1, { tenu: '`npm run lint:etats`, `lint:carte-liste`' })), null],
	['test python absent', registre(entree(1, { tenu: '`test_fantome.py`' })), /fichier de test introuvable/],
	['test python présent', registre(entree(1, { tenu: '`test_exemple.py`' })), null],
	['e2e sans extension absent', registre(entree(1, { tenu: '`e2e/fantome`' })), /fichier de test introuvable/],
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
	['le fichier d’exception est ignoré', { 'front/scripts/check-arbitrages.mjs': 'arbitrage n° 99' }, 0],
];

function autotest() {
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

// ── 4. Le dépôt ──────────────────────────────────────────────────────────────

function inconnu(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ lint:arbitrages — INCONNU : ${message}\n`);
	return 1;
}

function controler() {
	let fichiers;
	try {
		fichiers = execFileSync('git', ['ls-files', '-z'], {
			cwd: RACINE_DEPOT,
			encoding: 'utf8',
			maxBuffer: 64 * 1024 * 1024,
		})
			.split('\0')
			.filter(Boolean);
	} catch (e) {
		return inconnu(`\`git ls-files\` impossible (${e.message.split('\n')[0]})`);
	}
	if (!existsSync(join(RACINE_DEPOT, REGISTRE))) return inconnu(`${REGISTRE} introuvable`);
	let scripts;
	try {
		scripts = JSON.parse(readFileSync(join(RACINE_DEPOT, PACKAGE), 'utf8')).scripts ?? {};
	} catch (e) {
		return inconnu(`${PACKAGE} illisible : ${e.message}`);
	}

	const texte = readFileSync(join(RACINE_DEPOT, REGISTRE), 'utf8');
	const ensemble = new Set(fichiers);
	const fautes = fautesDuRegistre(texte, { scripts, fichiers: ensemble, minimum: ENTREES_MINIMUM });
	const numeros = new Set(
		[...texte.matchAll(/^### n° (\d+) · /gm)].map((m) => Number(m[1])),
	);

	const contenus = {};
	for (const f of fichiers) {
		if (!EXTENSIONS_TEXTE.test(f)) continue;
		const abs = join(RACINE_DEPOT, f);
		if (!existsSync(abs) || statSync(abs).size > TAILLE_MAX) continue;
		contenus[f] = readFileSync(abs, 'utf8');
	}
	const lus = Object.keys(contenus).length;
	if (lus < FICHIERS_MINIMUM) {
		return inconnu(`${lus} fichier(s) lu(s) pour les citations, ${FICHIERS_MINIMUM} attendus au moins`);
	}
	if (citations(contenus[TEMOIN] ?? '').length === 0) {
		return inconnu(`${TEMOIN} ne cite plus aucun « arbitrage n° N » : le balayage serait aveugle`);
	}
	for (const f of Object.keys(EXCEPTIONS)) {
		if (!(f in contenus)) fautes.push(`exception « ${f} » : fichier absent du dépôt`);
	}
	fautes.push(...fautesDeCitation(contenus, numeros));

	if (fautes.length) {
		console.error('✗ Registre des arbitrages d’interface — forme ou renvois cassés :\n');
		for (const f of fautes) console.error(`  • ${f}`);
		console.error(
			`\n   Le format et les statuts sont décrits dans ${REGISTRE} (« Le format »).\n` +
				'   Un numéro ne se réutilise jamais, une entrée ne s’efface pas : elle passe\n' +
				'   `remplacé par n° X`.\n',
		);
		return 1;
	}
	console.log(
		`✓ Arbitrages : ${numeros.size} entrée(s) de forme valide et continue, « Tenu par » résolu, ` +
			`citations de ${lus} fichier(s) toutes présentes au registre.`,
	);
	return 0;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
	process.exit(process.argv.includes('--selftest') ? autotest() : controler());
}
