#!/usr/bin/env node
/**
 *  Tout paquet importé par un script, un test ou une config est DÉCLARÉ dans
 *  `package.json` — il ne vient pas « par ricochet » d'une autre dépendance.
 *
 *  ## Pourquoi (#2205, 24/10/2026)
 *
 *  `scripts/lib/charger-module.mjs` importe `esbuild` pour charger des modules
 *  TypeScript. Il ne l'avait jamais déclaré : Vite 6 l'apportait. Vite 8 (Rolldown)
 *  ne l'apporte plus, et douze contrôles du front sont tombés d'un coup en
 *  « Cannot find package 'esbuild' » — au rejeu de la CI, après la montée. Un
 *  paquet qui n'est pas déclaré n'est pas à soi : la prochaine montée de la
 *  dépendance qui l'apportait le retire sans prévenir.
 *
 *  ## Ce qu'il lit
 *
 *  Les `import … from 'x'`, `export … from 'x'` et `import('x')` de `scripts/`,
 *  `e2e/`, `src/` et des configs à la racine de `front/`. Sont écartés : les
 *  modules natifs (`node:`), les chemins relatifs, les alias du framework (`$lib`,
 *  `$app`, `$env`, `$service-worker`), les modules virtuels (`virtual:…`) et les
 *  noms construits à l'exécution. Les commentaires sont blanchis avant lecture.
 *
 *  Lancer : node scripts/check-imports-declares.mjs [--selftest]
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { builtinModules } from 'node:module';
import { join, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = fileURLToPath(new URL('..', import.meta.url));
const DOSSIERS = ['scripts', 'e2e', 'src'];
const EXTENSIONS = /\.(mjs|js|ts|svelte)$/;

/**  Le nom du paquet d'un specifier (`@a/b/c` → `@a/b`, `x/y` → `x`), ou `null`
 *   quand ce n'est pas un paquet. */
export function nomDePaquet(specifier) {
	if (/^(\.|\/|node:|data:|https?:|virtual:|\$)/.test(specifier)) return null;
	if (builtinModules.includes(specifier.split('/')[0])) return null;
	const morceaux = specifier.split('/');
	const nom = specifier.startsWith('@') ? morceaux.slice(0, 2).join('/') : morceaux[0];
	return /^(@[a-z0-9~_.-]+\/)?[a-z0-9~_.-]+$/.test(nom) ? nom : null;
}

/**  Le repère `index` d'une ligne tombe-t-il DANS une chaîne ? On compte, avant lui,
 *   les guillemets de chaque sorte : un nombre impair, c'est qu'une chaîne est ouverte.
 *   Écarte les imports que les autotests écrivent dans leurs jeux d'essai
 *   (`"import x from 'x'"`) sans écarter un vrai import. */
function dansUneChaine(ligne, index) {
	const avant = ligne.slice(0, index);
	return ["'", '"', '`'].some((g) => (avant.split(g).length - 1) % 2 === 1);
}

/**  Les paquets importés par un texte — `Map<nom, extrait>`. */
export function paquetsImportes(texte) {
	const sans = neutraliserCommentaires(texte);
	const trouves = new Map();
	const motifs = [
		/\bfrom\s*(['"])([^'"\n]+)\1/g,
		/\bimport\s*\(\s*(['"])([^'"\n]+)\1\s*\)/g,
		/\bimport\s+(['"])([^'"\n]+)\1/g,
	];
	let debutLigne = 0;
	const lignes = sans.split('\n').map((l) => {
		const r = { l, debut: debutLigne };
		debutLigne += l.length + 1;
		return r;
	});
	for (const motif of motifs) {
		for (const m of sans.matchAll(motif)) {
			const ligne = lignes.findLast((x) => x.debut <= m.index);
			if (dansUneChaine(ligne.l, m.index - ligne.debut)) continue;
			const nom = nomDePaquet(m[2]);
			if (nom && !trouves.has(nom)) trouves.set(nom, m[0]);
		}
	}
	return trouves;
}

/**  Les paquets importés mais ni déclarés ni listés en exception : `[nom, fichier]`. */
export function nonDeclares(fichiers, declares) {
	const fautes = [];
	for (const { nom: fichier, contenu } of fichiers) {
		for (const [paquet] of paquetsImportes(contenu)) {
			if (!declares.has(paquet)) fautes.push([paquet, fichier]);
		}
	}
	return fautes;
}

function lister(dossier, acc = []) {
	for (const nom of readdirSync(dossier)) {
		if (nom === 'node_modules' || nom === '.svelte-kit' || nom === 'build') continue;
		const chemin = join(dossier, nom);
		if (statSync(chemin).isDirectory()) lister(chemin, acc);
		else if (EXTENSIONS.test(nom)) acc.push(chemin);
	}
	return acc;
}

function selftest() {
	let ko = 0;
	const t = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		console.log(
			`${ok ? 'PASS' : 'FAIL'}  ${libelle}${ok ? '' : ` — obtenu ${JSON.stringify(obtenu)}`}`,
		);
		if (!ok) ko = 1;
	};
	const noms = (s) => [...paquetsImportes(s).keys()];
	t('import nommé', noms("import { a } from 'esbuild';"), ['esbuild']);
	t('import dynamique', noms("const m = await import('esbuild');"), ['esbuild']);
	t('import nu', noms("import 'zone.js';"), ['zone.js']);
	t('paquet à portée, sous-chemin', noms("import x from '@tiptap/core/dist/y.js';"), [
		'@tiptap/core',
	]);
	t('sous-chemin d’un paquet simple', noms("import x from 'workbox-window/build/z';"), [
		'workbox-window',
	]);
	t(
		'module natif, relatif, alias, virtuel : écartés',
		noms(
			"import a from 'node:fs'; import b from './x.js'; import c from '$lib/x'; import d from 'virtual:pwa-register'; import e from 'fs';",
		),
		[],
	);
	t(
		'un commentaire n’importe rien',
		noms("// import x from 'esbuild';\n/* import('esbuild') */"),
		[],
	);
	const declares = new Set(['svelte']);
	t(
		'non déclaré : refusé, avec son fichier',
		nonDeclares(
			[{ nom: 'a.mjs', contenu: "import e from 'esbuild'; import s from 'svelte';" }],
			declares,
		),
		[['esbuild', 'a.mjs']],
	);
	t(
		'déclaré : admis',
		nonDeclares([{ nom: 'a.mjs', contenu: "import s from 'svelte';" }], declares),
		[],
	);
	console.log(
		ko === 0
			? '\n✓ Autotest : les imports sont lus, les non déclarés refusés.'
			: '\n✗ Autotest en échec',
	);
	return ko;
}

function mesurer() {
	const pkg = JSON.parse(readFileSync(join(RACINE, 'package.json'), 'utf8'));
	const declares = new Set([
		...Object.keys(pkg.dependencies ?? {}),
		...Object.keys(pkg.devDependencies ?? {}),
	]);
	const chemins = [
		...DOSSIERS.flatMap((d) => lister(join(RACINE, d))),
		...readdirSync(RACINE)
			.filter((n) => /\.config\.(ts|js|mjs)$/.test(n))
			.map((n) => join(RACINE, n)),
	];
	const fichiers = chemins.map((c) => ({
		nom: relative(RACINE, c).replace(/\\/g, '/'),
		contenu: readFileSync(c, 'utf8'),
	}));
	//  Cas zéro : sans fichier lu, ou sans aucun import de paquet, ce contrôle ne
	//  mesure rien — et le dire est le seul comportement honnête.
	const lus = fichiers.filter((f) => paquetsImportes(f.contenu).size > 0).length;
	if (fichiers.length === 0 || lus === 0) {
		console.error('✗ imports-declares : aucun import de paquet lu — le contrôle ne mesure rien.');
		return 1;
	}
	const fautes = nonDeclares(fichiers, declares);
	if (fautes.length > 0) {
		console.error(
			`✗ ${fautes.length} import(s) d'un paquet NON déclaré dans front/package.json :\n\n` +
				fautes.map(([p, f]) => `  ${p}  ← ${f}`).join('\n') +
				`\n\n  Un paquet apporté « par ricochet » disparaît à la prochaine montée de la dépendance` +
				`\n  qui l'apportait (esbuild, avec Vite 8 : douze contrôles tombés). Le déclarer\n` +
				`  (\`npm install -D <paquet>\`), ou retirer l'import.\n`,
		);
		return 1;
	}
	console.log(
		`✓ Imports déclarés : ${lus} fichier(s) importent des paquets, tous présents dans package.json.`,
	);
	return 0;
}

const _lance = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === _lance) {
	process.exit(process.argv.includes('--selftest') ? selftest() : mesurer());
}
