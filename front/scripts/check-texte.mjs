#!/usr/bin/env node
/**
 *  Le dépliement Unicode qui retire les accents s'écrit dans `#lib/texte`, et
 *  nulle part ailleurs.
 *
 *  ## Pourquoi ce contrôle (18/09/2026)
 *
 *  `normalize('NFD')` suivi du retrait des signes combinants était recopié
 *  **cinq fois** : deux fois dans l'Espace CS (rapprochement d'un inscrit par
 *  son NOM, lecture d'un étage saisi « 1ER »), une fois dans la FAQ, et deux
 *  fois pour fabriquer un code — celui d'un type de compteur, celui d'un
 *  périmètre.
 *
 *  🔴 Et **deux copies avaient déjà divergé sur la forme la plus fragile qui
 *  soit** : quatre écrivaient la plage des signes combinants en échappements
 *  (la plage U+0300 à U+036F), la cinquième avec les caractères eux-mêmes — des
 *  accents flottants qu'aucun éditeur ne montre, qu'un changement d'encodage
 *  emporte sans un mot. Une plage vidée ne lève aucune erreur : elle ne retire
 *  plus rien, et « Périmètre » cesse simplement de correspondre à « perimetre ».
 *
 *  ## Ce que le contrôle mesure — DEUX choses, et il faut les deux
 *
 *  1. **Le comportement** des trois fonctions, sur le module que le site
 *     embarque et non sur une copie. Un garde-fou qui interdirait de recopier
 *     une mécanique que rien n'éprouve protégerait un endroit unique… et faux.
 *  2. **Qu'aucun fichier de `src/` ne déplie lui-même** : tout appel à
 *     `normalize('NFD')` hors de la source. C'est volontairement grossier — il
 *     ne juge pas ce qu'on en fait, seulement que ce n'est pas réécrit.
 *
 *  ⚠️ La liste d'exceptions est VIDE, et c'est le bon moment pour l'ouvrir : le
 *  dépôt est conforme aujourd'hui, les cinq copies ayant été converties dans le
 *  même lot. Une exception ajoutée plus tard devra dire pourquoi, et une
 *  exception qui ne sert plus fait échouer ce contrôle.
 *
 *  Lancer : node --experimental-strip-types scripts/check-texte.mjs [--selftest]
 *
 *  ⚠️ Le drapeau est passé explicitement : sans effet sur Node 24 (le poste),
 *  nécessaire sur les Node 22 antérieurs à 22.18.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

import { contientTousLesMots, replier, sansAccents, slug } from '../src/lib/texte.ts';

const RACINE = 'src';
/** Le fichier qui a le droit — et le devoir — de l'écrire. */
const SOURCE = 'lib/texte.ts';

/**  Le dépliement, sous la seule forme qui compte : l'appel à `normalize`.
 *   Viser la plage de caractères aurait manqué la copie qui l'écrit autrement —
 *   c'est-à-dire précisément celle qui motive ce contrôle. */
const DEPLIEMENT = /\.normalize\(\s*['"]NFD['"]\s*\)/;

/**
 *  Les fichiers autorisés à déplier eux-mêmes, avec leur motif.
 *
 *  🔴 VIDE au 18/09/2026. Une entrée devenue inutile fait échouer le contrôle :
 *  une exception reconduite « au cas où » masquerait la suivante.
 */
const EXCEPTIONS = {};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.ts')) acc.push(p);
	}
	return acc;
}

/**  La décision, PURE — testable sans toucher au disque.
 *   @returns {'ok'|'recopie'} */
export function verdictTexte(source) {
	return DEPLIEMENT.test(source) ? 'recopie' : 'ok';
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = verdictTexte(src);
		if (r === attendu) console.log(`PASS  ${libelle} → ${r}`);
		else {
			console.error(`FAIL  ${libelle}  attendu=${attendu} obtenu=${r}`);
			ko = 1;
		}
	};
	//  🔴 LE cas qui donne sa raison d'être au contrôle : les cinq copies.
	t(
		'recopie directe',
		'recopie',
		"const s = x.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');",
	);
	t('recopie en guillemets doubles', 'recopie', 'x.normalize("NFD")');
	t('recopie espacée', 'recopie', "x.normalize( 'NFD' )");
	//  L'emploi de la source : c'est la forme attendue, et elle ne déclenche rien.
	t('emploi de #lib/texte', 'ok', "import { replier } from '#lib/texte.ts';\nreplier(u.nom)");
	//  ⚠️ Une autre normalisation Unicode n'est PAS le sujet : `NFC` recompose,
	//  il ne retire rien. Le confondre ferait un faux positif que le contrôle
	//  finirait par se voir désarmer.
	t('normalisation NFC', 'ok', "x.normalize('NFC')");
	//  Le cas zéro : une source vide ne peut pas être fautive.
	t('source vide', 'ok', '');
	//  Et le comportement des trois fonctions, dans le même passage : c'est la
	//  moitié que le motif ne peut pas voir.
	const { cas, echecs } = comportement();
	if (echecs.length) {
		console.error(echecs.join('\n'));
		ko = 1;
	} else console.log(`PASS  comportement → ${cas} cas`);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

/**  Les trois fonctions, éprouvées sur le module EMBARQUÉ par le site.
 *   @returns le nombre de cas exécutés, et les échecs. */
function comportement() {
	const echecs = [];
	//  Compté, jamais écrit en dur : un nombre recopié dans le message de succès
	//  devient faux au premier cas ajouté (`standards/04` §27).
	let cas = 0;
	const v = (nom, obtenu, attendu) => {
		cas++;
		if (obtenu !== attendu)
			echecs.push(`  ✗ ${nom}
      attendu ${JSON.stringify(attendu)}
      obtenu  ${JSON.stringify(obtenu)}`);
	};

	//  🔴 LE cas qui donne son sens au module : sans dépliement, les deux côtés
	//  d'une comparaison ne se rejoignent jamais.
	v('replier déplie les accents', replier('Périmètre'), 'perimetre');
	v('replier rabat la casse et les bords', replier('  ÉTÉ  '), 'ete');
	//  Le CAS ZÉRO d'une saisie : `normalizeStr` recevait un nom vide, la FAQ une
	//  catégorie absente. Les deux copies traitaient l'absence — la source aussi.
	v('replier sur rien', replier(null), '');
	v('replier sur vide', replier(''), '');

	//  ⚠️ `sansAccents` CONSERVE la casse : c'est ce qui le distingue de
	//  `replier`, et ce dont la lecture d'un étage a besoin (« 1ER », « RDC »).
	v('sansAccents garde la casse', sansAccents('1ER étage'), '1ER etage');

	v('slug d’un libellé simple', slug('Eau chaude sanitaire'), 'eau-chaude-sanitaire');
	//  L'apostrophe et les accents tombent ensemble, et deux séparateurs de suite
	//  n'en font qu'un : c'est ce que les deux copies faisaient, chacune de son côté.
	v(
		'slug avec apostrophe et tiret long',
		slug('Économie d’énergie — Nord'),
		'economie-d-energie-nord',
	);
	//  Le séparateur `_` du type de compteur, la seule différence entre les deux
	//  copies — et elle est VOULUE : les codes déjà stockés ne se réécrivent pas.
	v('slug en souligné', slug('Eau froide', '_'), 'eau_froide');
	v('slug sans séparateur aux bords', slug('  — Nord —  '), 'nord');
	//  Le cas zéro du slug : un libellé qui ne donne rien rend '', et l'appelant
	//  décide (les deux copies testaient `if (!slug) return ''`).
	v('slug sans rien à garder', slug('—'), '');
	v('slug sur rien', slug(null), '');

	//  La recherche des listes chargées (prestataires, imports, #2173) : TOUS les
	//  mots, n'importe où, sans accents ni casse — et le cas zéro laisse passer.
	v(
		'tous les mots, dans le désordre',
		contientTousLesMots('Bât. 3 Lot 12 DURAND', 'lot durand'),
		true,
	);
	v('un mot absent écarte', contientTousLesMots('Bât. 3 Lot 12', 'lot cave'), false);
	v('accents et casse rabattus', contientTousLesMots(['Électricité', null, 12], 'electr 12'), true);
	v('recherche vide laisse passer', contientTousLesMots('quoi que ce soit', '   '), true);
	v('texte absent, recherche posée', contientTousLesMots(null, 'x'), false);

	return { cas, echecs };
}

const { cas: casVus, echecs: echecsComportement } = comportement();
if (echecsComportement.length > 0) {
	console.error(`✗ texte — ${echecsComportement.length} cas en échec sur ${casVus} :
`);
	console.error(echecsComportement.join('\n'));
	process.exit(1);
}
if (casVus === 0) {
	console.error('✗ Aucun cas exécuté — le module ne s’importe plus. INCONNU, pas OK.');
	process.exit(2);
}

const tous = fichiers(RACINE);
const fautifs = [];
const exceptionsVues = new Set();

for (const f of tous) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	if (rel === SOURCE) continue;
	if (verdictTexte(readFileSync(f, 'utf8')) === 'ok') continue;
	if (rel in EXCEPTIONS) {
		exceptionsVues.add(rel);
		continue;
	}
	fautifs.push(rel);
}

let echec = false;

//  🔴 LE CAS ZÉRO (`standards/04` §2) : si le parcours n'a rien lu, ou si la
//  source elle-même a cessé de déplier, le contrôle n'a pas mesuré — il ne rend
//  pas OK. C'est l'erreur qui le rendrait silencieux le jour où `texte.ts` est
//  renommé ou vidé.
if (tous.length < 50) {
	console.error(
		`\n✗ INCONNU : ${tous.length} fichier(s) lus sous \`src/\` — le parcours ne décrit plus le dépôt.\n`,
	);
	process.exit(2);
}
let source = '';
try {
	source = readFileSync(join(RACINE, ...SOURCE.split('/')), 'utf8');
} catch {
	/* absente : traité juste en dessous */
}
if (!DEPLIEMENT.test(source)) {
	console.error(
		`\n✗ INCONNU : \`${SOURCE}\` ne déplie plus rien.\n\n` +
			"  Ce contrôle protège UN emplacement ; s'il a disparu, il ne mesure plus\n" +
			'  la règle, il constate un vide. Vérifier avant de croire le vert.\n',
	);
	process.exit(2);
}

if (fautifs.length) {
	echec = true;
	console.error(`\n✗ ${fautifs.length} fichier(s) déplient les accents eux-mêmes :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  `#lib/texte` porte les deux notions, et elles ne se confondent pas :\n' +
			'    • `replier(t)` — la forme COMPARABLE (sans accents, minuscules, sans bords)\n' +
			'    • `slug(t, sep)` — le CODE stocké, immuable une fois posé\n' +
			'    • `sansAccents(t)` — quand la casse porte un sens (« 1ER », « RDC »)\n' +
			'  → employer l’une des trois, ou inscrire le fichier dans `EXCEPTIONS`\n' +
			'    avec son motif.\n',
	);
}

const perimees = Object.keys(EXCEPTIONS).filter((f) => !exceptionsVues.has(f));
if (perimees.length) {
	echec = true;
	console.error('\n✗ Ces exceptions ne servent plus — les retirer :\n');
	for (const f of perimees) console.error(`  ${f}`);
	console.error('\n  Une exception reconduite « au cas où » masquerait la suivante.\n');
}

if (echec) process.exit(1);
console.log(
	`✓ Normalisation de texte : ${casVus} cas de comportement vérifiés, ${tous.length} fichier(s) lus, ` +
		`le dépliement Unicode ne s'écrit que dans \`${SOURCE}\` — ` +
		`${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s).`,
);
