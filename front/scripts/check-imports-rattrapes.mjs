/**
 * Refuse un `import()` dont l'échec n'a PERSONNE pour le recevoir (#2683).
 *
 * ## Le défaut
 *
 * Un `import()` rend une promesse. S'il échoue et que rien ne l'attend, le
 * rejet devient une exception NON RATTRAPÉE de la page. Sous WebKit — le moteur
 * de Safari et de tous les iPhone — il échoue aussi quand la page S'EN VA
 * pendant le chargement : la navigation interrompt le module en vol, et la page
 * qui part lève « TypeError: Importing a module script failed. », sans pile.
 * Chromium, lui, se tait. Reproduit à coup sûr : retenir la requête du module,
 * naviguer, l'exception tombe (`e2e/import-interrompu.spec.ts`).
 *
 * Le 11/11/2026, la tranche WebKit de la CI est ainsi tombée sur
 * `admin-a-traiter` (run 43014391760, une fois sur ~47 passages) : le test fait
 * un `page.goto` à la cinquième seconde, quand `MajDisponible` charge
 * `virtual:pwa-register` (3 s après l'ouverture, au repos) sur un Vite encore
 * froid. Les `ECONNREFUSED` du journal n'y étaient pour rien : c'est le proxy
 * de `/telemetry/collect`, sans API derrière, à chaque test.
 *
 * ## La règle, lue sur l'arbre syntaxique
 *
 * Un `import()` est admis s'il a un destinataire :
 *   1. **rattrapé** — suivi de `.catch(…)`, ou de `.then(succès, échec)` ;
 *   2. **dans un `try`** — `await import(…)` sous un `try { }` de sa fonction ;
 *   3. **rendu** — corps d'une flèche (`() => import(…)`, un chargeur) ou
 *      `return import(…)` : l'appelant reçoit la promesse, et c'est à lui de
 *      répondre. Dans le balisage Svelte, seul `charger={() => import(…)}` est
 *      admis : `ChargementDiffere` rattrape et DIT l'échec ;
 *   4. **attendu dans une fonction NOMMÉE** — `await import(…)` dans une
 *      fonction déclarée, une méthode ou une constante : son échec remonte à
 *      qui l'appelle.
 * Le chaînage se suit : `import(…).then(f)` sans second argument, ou un élément
 * de `Promise.all([…])`, passe sa promesse à ce qui l'entoure.
 *
 * Refusés : l'instruction nue (`import(…).then(f);`) et `await import(…)` dans
 * une fonction ANONYME passée en argument — `onMount(async () => …)`,
 * `setTimeout`, `.then(async …)` : personne ne lit la promesse qu'elle rend.
 *
 * ⚠️ Ce contrôle ne suit pas les appelants (règles 3 et 4) : il juge le lieu de
 * l'`import()`, pas toute la chaîne. C'est l'e2e qui juge le comportement.
 *
 * Test : node front/scripts/check-imports-rattrapes.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import ts from 'typescript';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SRC = join(RACINE, 'src');

/**
 * Les `import()` tolérés sans destinataire, chacun avec sa raison. Vide : les
 * trois relevés le 11/11/2026 sont rattrapés. Une entrée qui ne sert plus fait
 * échouer.
 */
const EXCEPTIONS = [];

/**
 *  Les blocs `<script>` d'un composant, avec leur décalage dans le fichier.
 *  ⚠️ Lecture d'un source, pas un assainissement : on BLANCHIT par positions
 *  (`blanchir`), jamais par `.replace` — CodeQL y lirait un filtre de balises.
 */
const SCRIPT = /(<script\b[^>]*>)([\s\S]*?)<\/script\s*>/gi;
const COMMENTAIRE_HTML = /<!--[\s\S]*?-->/g;

function scripts(source) {
	return [...source.matchAll(SCRIPT)].map((m) => ({
		code: m[2],
		debut: m.index + m[1].length,
	}));
}

/** Le texte, chaque correspondance du motif remplacée par autant d'espaces (positions gardées). */
function blanchir(texte, motif) {
	let sortie = '';
	let fin = 0;
	for (const m of texte.matchAll(motif)) {
		sortie += texte.slice(fin, m.index) + ' '.repeat(m[0].length);
		fin = m.index + m[0].length;
	}
	return sortie + texte.slice(fin);
}

/** Le balisage d'un composant : sans ses scripts ni ses commentaires, positions gardées. */
const balisageDe = (source) => blanchir(blanchir(source, SCRIPT), COMMENTAIRE_HTML);

/** Le numéro de ligne d'une position. */
const ligneDe = (source, pos) => source.slice(0, pos).split('\n').length;

/** Le parent qui porte la promesse plus loin, sans y répondre. */
function suivant(n) {
	const p = n.parent;
	if (!p) return null;
	if (ts.isParenthesizedExpression(p) || ts.isAsExpression(p) || ts.isNonNullExpression(p))
		return p;
	//  `x.then(f)` ou `x.finally(f)` : un nouveau maillon, à juger à son tour.
	if (ts.isPropertyAccessExpression(p) && p.expression === n) return p;
	//  Un élément de `Promise.all([…])` : c'est l'appel qui porte la promesse.
	if (ts.isArrayLiteralExpression(p)) {
		const appel = p.parent;
		if (
			appel &&
			ts.isCallExpression(appel) &&
			/^Promise\.(all|allSettled|race|any)$/.test(appel.expression.getText())
		)
			return appel;
	}
	return null;
}

/** Vrai si l'expression `n` (une promesse) a un destinataire. */
function aUnDestinataire(n) {
	for (;;) {
		const p = n.parent;
		//  `n.catch(…)` / `n.then(a, b)` / `n.then(a)` / `n.finally(a)`
		if (ts.isPropertyAccessExpression(p) && p.expression === n) {
			const appel = p.parent;
			const methode = p.name.text;
			if (!ts.isCallExpression(appel) || appel.expression !== p) return false;
			if (methode === 'catch') return true;
			if (methode === 'then' && appel.arguments.length >= 2) return true;
			if (methode === 'then' || methode === 'finally') {
				n = appel;
				continue;
			}
			return false;
		}
		const plus = suivant(n);
		if (plus) {
			n = plus;
			continue;
		}
		//  Rendu : corps d'une flèche, ou `return` — sauf la flèche passée en
		//  ARGUMENT d'un appel : `apresOuverture(() => import(…))` ne lit pas ce
		//  qu'elle rend.
		if (ts.isArrowFunction(p) && p.body === n) return !passeeEnArgument(p);
		if (ts.isReturnStatement(p)) return true;
		if (ts.isAwaitExpression(p)) return attenteRattrapee(p);
		return false;
	}
}

/** Une fonction anonyme passée en argument d'un appel : personne ne lit ce qu'elle rend. */
function passeeEnArgument(f) {
	const anonyme = ts.isArrowFunction(f) || ts.isFunctionExpression(f);
	return anonyme && !!f.parent && ts.isCallExpression(f.parent) && f.parent.arguments.includes(f);
}

/** `await …` : sous un `try`, ou dans une fonction dont l'échec remonte à un appelant. */
function attenteRattrapee(attente) {
	for (let n = attente, p = n.parent; p; n = p, p = p.parent) {
		if (ts.isTryStatement(p) && p.tryBlock === n) return true;
		//  Une fonction anonyme passée en ARGUMENT : `onMount(async () => …)`.
		if (ts.isFunctionLike(p)) return !passeeEnArgument(p);
	}
	return false;
}

/** Les `import()` d'un bloc de code sans destinataire : leurs positions. PUR. */
export function importsSansDestinataire(code) {
	const sf = ts.createSourceFile('x.ts', code, ts.ScriptTarget.Latest, true);
	const fautes = [];
	const visiter = (n) => {
		if (ts.isCallExpression(n) && n.expression.kind === ts.SyntaxKind.ImportKeyword) {
			if (!aUnDestinataire(n)) fautes.push(n.getStart(sf));
		}
		ts.forEachChild(n, visiter);
	};
	visiter(sf);
	return fautes;
}

/** Le balisage d'un composant : seul `charger={() => import(…)}` y est admis. */
export function importsDuBalisage(source) {
	const sansCommentaires = balisageDe(source);
	const fautes = [];
	for (const m of sansCommentaires.matchAll(/\bimport\(/g)) {
		const avant = sansCommentaires.slice(Math.max(0, m.index - 40), m.index);
		if (!/\bcharger=\{\s*\(\s*\)\s*=>\s*$/.test(avant)) fautes.push(m.index);
	}
	return fautes;
}

/** Les fautes d'un fichier : `[{ ligne }]`, et le nombre d'`import()` vus. PUR. */
export function juger(source, chemin) {
	const fautes = [];
	let vus = 0;
	if (chemin.endsWith('.svelte')) {
		for (const { code, debut } of scripts(source)) {
			vus += (code.match(/\bimport\(/g) ?? []).length;
			for (const pos of importsSansDestinataire(code)) fautes.push(ligneDe(source, debut + pos));
		}
		vus += (balisageDe(source).match(/\bimport\(/g) ?? []).length;
		for (const pos of importsDuBalisage(source)) fautes.push(ligneDe(source, pos));
	} else {
		vus += (source.match(/\bimport\(/g) ?? []).length;
		for (const pos of importsSansDestinataire(source)) fautes.push(ligneDe(source, pos));
	}
	return { fautes, vus };
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src, chemin = 'x.ts') => {
		const r = juger(src, chemin).fautes.length;
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${r} faute(s)`);
		if (r !== attendu) ko = 1;
	};
	//  🔴 Les trois formes trouvées le 11/11/2026.
	t('instruction nue (sanitize, avant)', 1, "import('dompurify').then((m) => { x = m; });");
	t(
		'chargeur qui chaîne un then seul (MajDisponible, avant)',
		1,
		"const r = apres(() => import('virtual:pwa-register').then(({ registerSW }) => registerSW()));",
	);
	t(
		'await dans onMount(async) (RichEditor, avant) : chaque import',
		2,
		"onMount(async () => { const [a] = await Promise.all([import('a'), import('b')]); });",
	);
	//  Ce qui est admis.
	t('then à deux arguments', 0, "import('a').then((m) => m, () => {});");
	t('catch en bout de chaîne', 0, "import('a').then((m) => m).finally(f).catch(g);");
	t('chargeur nu', 0, "const charger = () => import('a');");
	t('chargeur dans une table', 0, "const T = { a: () => import('a') };");
	t('chargeur passé à setTimeout', 1, "setTimeout(() => import('a'), 10);");
	t('return', 0, "function c() { return import('a'); }");
	t('await sous try', 0, "onMount(async () => { try { await import('a'); } catch { e = 1; } });");
	t('await dans une fonction nommée', 0, "export async function f() { await import('a'); }");
	t('await dans une méthode', 0, "const o = { async f() { const { a } = await import('a'); } };");
	t('Promise.all rattrapé', 0, "Promise.all([import('a'), import('b')]).catch(() => {});");
	t('import de type : pas un appel', 0, "type T = typeof import('./a');");
	t(
		'balisage : charger={() => import()}',
		0,
		"<script>let x;</script>\n<ChargementDiffere charger={() => import('#lib/A.svelte')}>",
		'x.svelte',
	);
	t(
		'balisage : autre prop',
		1,
		"<script>let x;</script>\n<Bouton on:click={() => import('#lib/A.svelte')} />",
		'x.svelte',
	);
	t(
		'script de composant',
		1,
		'<script lang="ts">\n\timport(\'a\').then(f);\n</script>\n<p>x</p>',
		'x.svelte',
	);
	process.exit(ko);
}

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(SRC);
const relevees = [];
let vus = 0;
for (const chemin of tous) {
	const rel = relative(RACINE, chemin).replaceAll('\\', '/');
	const r = juger(readFileSync(chemin, 'utf8'), chemin);
	vus += r.vus;
	for (const ligne of r.fautes) relevees.push({ fichier: rel, ligne });
}

//  Cas zéro : le dépôt charge à la demande une soixantaine de modules. Si
//  presque aucun `import()` n'est vu, le contrôle ne lit plus rien.
if (vus < 30) {
	console.error(
		`✗ Cas zéro : ${vus} import() vu(s) dans ${tous.length} fichier(s), au moins 30 attendus.`,
	);
	process.exit(1);
}

let echec = 0;
for (const e of EXCEPTIONS) {
	if (!relevees.some((r) => r.fichier === e.fichier)) {
		console.error(`✗ Exception sans objet : ${e.fichier} (${e.raison}) — la retirer.`);
		echec = 1;
	}
}
const fautes = relevees.filter((r) => !EXCEPTIONS.some((e) => e.fichier === r.fichier));
for (const f of fautes) {
	console.error(
		`✗ ${f.fichier}:${f.ligne} — import() sans destinataire : son échec, ou une navigation ` +
			'pendant le chargement (WebKit), lève une exception non rattrapée. ' +
			'Le rattraper (.catch, try) ou le rendre à un appelant qui répond (#2683).',
	);
	echec = 1;
}
if (!echec) console.log(`✓ ${vus} import() lus, chacun a un destinataire.`);
process.exit(echec);
