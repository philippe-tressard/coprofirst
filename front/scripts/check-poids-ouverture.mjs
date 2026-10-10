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
 *  ## Les composants chargés à la demande (11/10/2026)
 *
 *  Même télémétrie, une semaine plus tard : `/admin` et `/espace-cs` importaient
 *  tous leurs onglets, et chaque carte d'affaire le formulaire de correction
 *  qu'on n'ouvre qu'au ✏️. Ils passent désormais par `ChargementDiffere`, qui
 *  reçoit un `import('$lib/components/….svelte')`. La liste n'est écrite nulle
 *  part : elle est LUE dans le source (`composantsDifferes`), donc un onglet
 *  différé demain est gardé sans qu'on y pense. Dans le build, chacun doit être
 *  une entrée dynamique du manifeste (cas zéro : un composant renommé ou fondu
 *  ailleurs est signalé) et n'apparaître dans le chargement initial d'AUCUN
 *  écran — un `import X from` statique ajouté n'importe où l'y ramènerait, et
 *  Vite ne le dit que par un avertissement que personne ne lit.
 *
 *  Lancer APRÈS `npm run build` : node scripts/check-poids-ouverture.mjs [--selftest]
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
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

/**  `charger={() => import('$lib/components/X.svelte')}` : un composant confié à
 *   `ChargementDiffere`. Un `import()` ailleurs ne promet rien sur l'ouverture
 *   (`$lib/fichiers.ts` importe `Toast` à la demande, que la page a déjà). */
const IMPORT_DIFFERE =
	/charger=\{\s*\(\)\s*=>\s*import\(\s*'\$lib\/components\/([^']+\.svelte)'\s*\)\s*\}/g;

/**  Les composants que le SOURCE charge à la demande, sous leur clé de manifeste
 *   (`src/lib/components/X.svelte`). */
export function composantsDifferes(sources) {
	const cles = new Set();
	for (const texte of sources) {
		for (const m of texte.matchAll(IMPORT_DIFFERE)) cles.add(`src/lib/components/${m[1]}`);
	}
	return [...cles].sort();
}

/**  Le texte de chaque `.svelte` et `.ts` de `src/`. */
function lireSources(dossier) {
	const textes = [];
	for (const e of readdirSync(dossier, { withFileTypes: true })) {
		const chemin = join(dossier, e.name);
		if (e.isDirectory()) textes.push(...lireSources(chemin));
		else if (/\.(svelte|ts)$/.test(e.name)) textes.push(readFileSync(chemin, 'utf8'));
	}
	return textes;
}

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

/**  Les fautes : `[écran, bibliothèque]` pour chaque bibliothèque ou composant à
 *   la demande chargé d'emblée ; et ceux qui sont introuvables dans le build. */
export function juger(manifeste, contenuDe, differes = []) {
	const fautes = [];
	const trouvees = new Set();
	//  Un composant passé à `import()` qui n'est pas une entrée dynamique du build
	//  a été FONDU dans un morceau commun : un import statique ailleurs l'y a mis.
	const fondus = differes.filter((c) => !manifeste[c]?.isDynamicEntry);
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
		for (const c of differes) if (morceaux.includes(c)) fautes.push([ecran, c]);
	}
	const absentes = Object.keys(A_LA_DEMANDE).filter((n) => !trouvees.has(n));
	return { fautes, absentes, fondus };
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
	contenus['ed.js'] = 'class="ProseMirror"';
	m['_a.js'].imports = [];
	const onglet = 'src/lib/components/OngletX.svelte';
	m['.svelte-kit/generated/client-optimized/nodes/2.js'].dynamicImports.push(onglet);
	m[onglet] = { file: 'x.js', imports: [], isDynamicEntry: true };
	contenus['x.js'] = '';
	cas.push([
		'source lu : le composant différé est trouvé',
		composantsDifferes(["charger={() => import('$lib/components/OngletX.svelte')}"])[0] === onglet,
	]);
	cas.push(['composant différé : aucune faute', juger(m, lire, [onglet]).fautes.length === 0]);
	m['.svelte-kit/generated/client-optimized/nodes/1.js'].imports.push(onglet);
	cas.push([
		'composant importé statiquement : fautif',
		juger(m, lire, [onglet]).fautes.length === 1,
	]);
	cas.push([
		'composant fondu dans un morceau commun : signalé',
		juger(m, lire, ['src/lib/components/Fondu.svelte']).fondus.length === 1,
	]);
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

const differes = composantsDifferes(lireSources(join(CLIENT, '..', '..', '..', 'src')));
if (!differes.length) {
	console.error(
		"\n✗ lint:poids-ouverture — aucun `charger={() => import('$lib/components/….svelte')}` lu dans src/ :\n" +
			'  le motif ne mord plus, ou le chemin des sources a changé. Il ne garde rien.\n',
	);
	process.exit(1);
}
const { fautes, absentes, fondus } = juger(manifeste, contenuDe, differes);
if (absentes.length) {
	console.error(
		`\n✗ lint:poids-ouverture — introuvable(s) dans le build : ${absentes.join(', ')}.\n` +
			`  Le marqueur de \`A_LA_DEMANDE\` ne mord plus : le contrôle ne mesure rien.\n`,
	);
	process.exit(1);
}
if (fondus.length) {
	console.error(
		`\n✗ lint:poids-ouverture — passé(s) à \`ChargementDiffere\` mais chargé(s) d'emblée :\n\n` +
			fondus.map((c) => `  ${c}`).join('\n') +
			`\n\n  Le build n'en fait pas une entrée dynamique : un \`import X from\` statique,\n` +
			`  ailleurs, l'a fondu dans un morceau commun. Le retirer, ou différer aussi cet appelant.\n`,
	);
	process.exit(1);
}
if (fautes.length) {
	console.error(
		`\n✗ lint:poids-ouverture — ${fautes.length} écran(s) téléchargent d'emblée ce qui ` +
			`doit se charger à la demande :\n\n` +
			fautes.map(([e, n]) => `  ${routeDe(e)} — ${n}`).join('\n') +
			`\n\n  Un import statique l'a ramené dans le chargement initial : passer par\n` +
			`  \`import()\` au moment du geste (\`RichEditor.svelte\`, \`ChargementDiffere.svelte\`).\n`,
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
	`✓ Ouverture des écrans : ${Object.keys(A_LA_DEMANDE).length} bibliothèque(s) et ` +
		`${differes.length} composant(s) chargés à la demande, aucun d'emblée ` +
		`(${ecrans.length} écrans). Les plus lourds :`,
);
for (const [o, f] of poids.slice(0, 5)) console.log(`    ${Math.round(o / 1024)} Ko gz  ${f}`);
