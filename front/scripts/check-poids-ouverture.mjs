#!/usr/bin/env node
/**
 *  **Ce qu'un écran télécharge AVANT de s'afficher** — et ce qui n'a pas à y être.
 *
 *  ## Pourquoi ce contrôle existe (04/10/2026)
 *
 *  La télémétrie (Admin › Télémétrie › Durées d'affichage) donnait plus d'une
 *  seconde à l'« Ouverture du site » sur `/residence`, `/sondages`,
 *  `/tickets/#`. Le serveur répondait en 70 ms : le temps se perdait dans le
 *  navigateur, à télécharger et exécuter le JavaScript de l'écran. Et la moitié
 *  de ce JavaScript était l'éditeur de texte riche — Tiptap et ProseMirror,
 *  121 Ko compressés sur 180 à 300 —, importé statiquement par `RichEditor`, donc
 *  chargé par tout écran qui CONTIENT un formulaire, même replié, même chez qui
 *  ne fait que lire.
 *
 *  `RichEditor` le charge désormais à la demande (`import()` dans `onMount`).
 *  Rien ne se voit si un import statique revient : l'écran marche, il est
 *  seulement plus lent — exactement le défaut qu'aucun test fonctionnel ne
 *  mesure. Ce contrôle lit donc le BUILD (le manifeste de Vite) et suit, pour
 *  chaque écran, ses imports STATIQUES : ce qui est atteint là est téléchargé
 *  avant l'affichage. Une bibliothèque de `A_LA_DEMANDE` qui y figure le fait
 *  échouer.
 *
 *  Cas zéro : la bibliothèque doit être TROUVÉE quelque part dans le build (dans
 *  son morceau chargé à la demande) — un marqueur qui ne mord plus rendrait le
 *  contrôle vert sans rien regarder.
 *
 *  Lancer APRÈS `npm run build` : node scripts/check-poids-ouverture.mjs [--selftest]
 */
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';

const CLIENT = new URL('../.svelte-kit/output/client', import.meta.url).pathname.replace(
	/^\/([A-Za-z]:)/,
	'$1',
);

/**  Ce qui ne se charge qu'au geste qui en a besoin, reconnu au CONTENU d'un
 *   morceau du build — les noms de morceaux sont des empreintes. */
export const A_LA_DEMANDE = {
	'Tiptap / ProseMirror (éditeur riche)': /ProseMirror/,
};

/**  Les écrans : un nœud de route de SvelteKit par fichier `nodes/N.js`. */
const estEcran = (cle) => /generated\/client[^/]*\/nodes\/\d+\.js$/.test(cle);

/**  La route d'un nœud, lue dans le fichier que SvelteKit génère pour lui —
 *   `nodes/19.js` ne dit rien à qui lit l'échec. */
function routeDe(cle) {
	const source = join(CLIENT, '..', '..', '..', cle);
	if (!existsSync(source)) return cle;
	const m = /src\/routes\/(.*?)\/?\+(?:page|layout)\.(?:svelte|ts)/.exec(
		readFileSync(source, 'utf8'),
	);
	return m ? `/${m[1]}` : cle;
}

/**  Les morceaux atteints par les imports STATIQUES de `cle` — ce que le
 *   navigateur télécharge avant d'afficher. Les `dynamicImports` n'y entrent pas. */
export function fermetureStatique(manifeste, cle, vus = new Set()) {
	if (vus.has(cle) || !manifeste[cle]) return vus;
	vus.add(cle);
	for (const i of manifeste[cle].imports ?? []) fermetureStatique(manifeste, i, vus);
	return vus;
}

/**  Les fautes : `[écran, bibliothèque]` pour chaque bibliothèque à la demande
 *   chargée d'emblée ; et les bibliothèques introuvables dans tout le build. */
export function juger(manifeste, contenuDe) {
	const fautes = [];
	const trouvees = new Set();
	for (const [nom, motif] of Object.entries(A_LA_DEMANDE)) {
		for (const cle of Object.keys(manifeste)) {
			if (motif.test(contenuDe(manifeste[cle].file))) trouvees.add(nom);
		}
	}
	for (const ecran of Object.keys(manifeste).filter(estEcran)) {
		const morceaux = [...fermetureStatique(manifeste, ecran)];
		for (const [nom, motif] of Object.entries(A_LA_DEMANDE)) {
			if (morceaux.some((m) => motif.test(contenuDe(manifeste[m].file)))) {
				fautes.push([ecran, nom]);
			}
		}
	}
	const absentes = Object.keys(A_LA_DEMANDE).filter((n) => !trouvees.has(n));
	return { fautes, absentes };
}

function selftest() {
	const m = {
		'.svelte-kit/generated/client-optimized/nodes/1.js': { file: 'n1.js', imports: ['_a.js'] },
		'.svelte-kit/generated/client-optimized/nodes/2.js': {
			file: 'n2.js',
			imports: ['_a.js'],
			dynamicImports: ['_ed.js'],
		},
		'_a.js': { file: 'a.js', imports: [] },
		'_ed.js': { file: 'ed.js', imports: [] },
	};
	const contenus = { 'n1.js': '', 'n2.js': '', 'a.js': '', 'ed.js': 'class="ProseMirror"' };
	const lire = (f) => contenus[f];
	const ok = juger(m, lire);
	const cas = [
		['éditeur à la demande : aucune faute', ok.fautes.length === 0 && ok.absentes.length === 0],
	];
	m['_a.js'].imports = ['_ed.js'];
	cas.push(['import statique : deux écrans fautifs', juger(m, lire).fautes.length === 2]);
	contenus['ed.js'] = '';
	cas.push(['marqueur introuvable : signalé', juger(m, lire).absentes.length === 1]);
	const rates = cas.filter(([, v]) => !v);
	for (const [n, v] of cas) console.log(`${v ? '✓' : '✗'} ${n}`);
	process.exit(rates.length ? 1 : 0);
}

if (process.argv.includes('--selftest')) selftest();

const chemin = join(CLIENT, '.vite', 'manifest.json');
if (!existsSync(chemin)) {
	console.error(
		`\n✗ lint:poids-ouverture — ${chemin} absent : lancer \`npm run build\` d'abord.\n`,
	);
	process.exit(1);
}
const manifeste = JSON.parse(readFileSync(chemin, 'utf8'));
const cache = new Map();
const contenuDe = (f) => {
	if (!cache.has(f)) cache.set(f, f.endsWith('.js') ? readFileSync(join(CLIENT, f), 'utf8') : '');
	return cache.get(f);
};

const ecrans = Object.keys(manifeste).filter(estEcran);
if (!ecrans.length) {
	console.error(
		'\n✗ lint:poids-ouverture — aucun écran lu dans le manifeste : il ne mesure rien.\n',
	);
	process.exit(1);
}

const { fautes, absentes } = juger(manifeste, contenuDe);
if (absentes.length) {
	console.error(
		`\n✗ lint:poids-ouverture — introuvable(s) dans le build : ${absentes.join(', ')}.\n` +
			`  Le marqueur de \`A_LA_DEMANDE\` ne mord plus : le contrôle ne mesure rien.\n`,
	);
	process.exit(1);
}
if (fautes.length) {
	console.error(
		`\n✗ lint:poids-ouverture — ${fautes.length} écran(s) téléchargent d'emblée ce qui ` +
			`doit se charger à la demande :\n\n` +
			fautes.map(([e, n]) => `  ${routeDe(e)} — ${n}`).join('\n') +
			`\n\n  Un import statique l'a ramené dans le chargement initial : passer par\n` +
			`  \`import()\` au moment du geste (voir \`RichEditor.svelte\`).\n`,
	);
	process.exit(1);
}

//  Pour information : les cinq écrans les plus lourds à l'ouverture.
const poids = ecrans
	.map((e) => {
		let octets = 0;
		for (const m of fermetureStatique(manifeste, e)) {
			octets += gzipSync(contenuDe(manifeste[m].file)).length;
		}
		return [octets, routeDe(e)];
	})
	.sort((a, b) => b[0] - a[0]);
console.log(
	`✓ Ouverture des écrans : ${Object.keys(A_LA_DEMANDE).length} bibliothèque(s) chargée(s) ` +
		`à la demande, aucune d'emblée (${ecrans.length} écrans). Les plus lourds :`,
);
for (const [o, f] of poids.slice(0, 5)) console.log(`    ${Math.round(o / 1024)} Ko gz  ${f}`);
