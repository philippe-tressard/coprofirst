/**
 * Garde-fou — **`{@html}` sans assainissement**.
 *
 * ## Pourquoi (#429, relevé du 17/08/2026)
 *
 * `CLAUDE.md` ouvre les « quatre règles qui ne se négocient pas » par celle-ci :
 * jamais `{@html contenu}`, toujours `{@html safeHtml(contenu)}`. Et **aucun
 * contrôle ne la vérifiait** : ni `npm run lint:*`, ni `api/tests/`. La règle la
 * plus critique du front reposait entièrement sur la vigilance de qui écrit la
 * ligne.
 *
 * `svelte/no-at-html-tags` — la règle eslint qui aurait pu servir de filet — avait
 * été désactivée en v2.70.0 : incapable de distinguer les usages voulus d'un usage
 * dangereux, elle interdisait tout ou ne gardait rien.
 *
 * ## Ce que ce contrôle cherche
 *
 * Toute expression `{@html …}` dont la racine n'est pas un **appel** à une fonction
 * d'assainissement **importée de `#lib/sanitize`**.
 *
 * 🔴 Les deux conditions comptent. Une fonction locale nommée `safeHtml` qui ne
 * ferait qu'un `return input` passerait le premier filtre : ce contrôle exige donc
 * que le nom vienne de l'import, pas de la portée du fichier. C'est exactement le
 * défaut qu'il faut savoir attraper — `renderContent` (tickets/[id]) était une copie
 * littérale de `safeDescription`, correcte par chance, et rien n'aurait signalé
 * qu'elle avait dérivé.
 *
 * ## La liste des fonctions n'est PAS écrite ici
 *
 * Elle est **lue dans `src/lib/sanitize.ts`** : tout `export function safe…()` en
 * fait partie. Une liste recopiée diverge au premier ajout — et c'est justement la
 * divergence entre la consigne et le dépôt qui a motivé ce ticket : `CLAUDE.md` ne
 * nommait que `safeHtml` quand trois fonctions étaient en service.
 *
 * ## Les exceptions sont nommées, motivées, et surveillées
 *
 * Deux fichiers rendent du balisage produit localement, jamais une donnée. Elles
 * sont déclarées dans `EXCEPTIONS` avec leur raison, et **une exception qui ne sert
 * plus fait échouer le contrôle** : une dérogation oubliée est une porte qu'on croit
 * fermée (`standards/04-fiabilite-des-controles.md`).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Fichiers autorisés à rendre du HTML non assaini, **avec la raison**.
 * Chemin relatif à `src/`, en séparateurs POSIX.
 */
const EXCEPTIONS = {
	'lib/components/Icon.svelte':
		'SVG codé en dur dans le composant : `icons[name]` est un littéral du dépôt, ' +
		"jamais une donnée d'utilisateur. `name` ne sert qu'à choisir une entrée.",
	'lib/components/QRCode.svelte':
		"SVG produit LOCALEMENT par `qrcode-generator` à partir d'une donnée encodée " +
		"en modules (carrés noirs et blancs) : la valeur n'est jamais interpolée dans " +
		'le balisage, elle est convertie en géométrie.',
};

/** Nombre minimal d'occurrences attendues — voir « cas zéro » plus bas. */
const PRISES_MINIMALES = 20;

function fichiersSvelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiersSvelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

// ── 1. La liste des fonctions d'assainissement, lue à la source ──────────────
const SOURCE_SANITIZE = join(RACINE, 'lib', 'sanitize.ts');
let assainisseurs;
try {
	const source = readFileSync(SOURCE_SANITIZE, 'utf8');
	assainisseurs = new Set(
		[...source.matchAll(/^export function (safe\w+)\s*\(/gm)].map((m) => m[1]),
	);
} catch {
	console.error('✗ INCONNU : src/lib/sanitize.ts est illisible.');
	console.error("Sans la liste des fonctions d'assainissement, ce contrôle ne conclut pas.");
	process.exit(1);
}
if (assainisseurs.size === 0) {
	console.error('✗ Cas zéro : aucune fonction `export function safe…()` trouvée dans sanitize.ts.');
	console.error('Ne pas lire ceci comme un succès — le contrôle ne saurait rien reconnaître.');
	process.exit(1);
}

// ── 2. Le relevé ─────────────────────────────────────────────────────────────
const fichiers = fichiersSvelte(RACINE);
if (fichiers.length === 0) {
	console.error("✗ Cas zéro : aucun composant analysé — l'arborescence a changé.");
	console.error('Ne pas lire ceci comme un succès.');
	process.exit(1);
}

/** Extrait l'expression d'un `{@html …}` en équilibrant les accolades. */
function expression(texte, debut) {
	let profondeur = 0;
	let quote = null;
	for (let i = debut; i < texte.length; i++) {
		const c = texte[i];
		if (quote) {
			if (c === '\\') i++;
			else if (c === quote) quote = null;
			continue;
		}
		if (c === '"' || c === "'" || c === '`') quote = c;
		else if (c === '{') profondeur++;
		else if (c === '}') {
			profondeur--;
			if (profondeur === 0) return texte.slice(debut + 1, i);
		}
	}
	return null;
}

const erreurs = [];
const exceptionsServies = new Set();
let prises = 0;

for (const chemin of fichiers) {
	const relatif = relative(RACINE, chemin).replace(/\\/g, '/');
	const source = readFileSync(chemin, 'utf8');

	//  Les noms réellement IMPORTÉS de `#lib/sanitize` par ce fichier.
	const importes = new Set();
	for (const m of source.matchAll(/import\s*\{([^}]*)\}\s*from\s*['"]#lib\/sanitize\.ts['"]/g)) {
		for (const nom of m[1].split(',')) {
			const propre = nom
				.trim()
				.split(/\s+as\s+/)
				.pop()
				.trim();
			if (propre) importes.add(propre);
		}
	}

	//  🔴 Les commentaires sont NEUTRALISÉS avant la recherche (20/08/2026).
	//
	//  Le contrôle regardait auparavant si la portion de LIGNE précédant
	//  l'occurrence contenait `//`, `*` ou `<!--`. Cela ne voit qu'un commentaire
	//  ouvert sur la MÊME ligne : un commentaire Svelte de plusieurs lignes qui
	//  cite la balise en troisième ligne passait pour du rendu, et le contrôle
	//  refusait alors le fichier qui EXPLIQUE la règle.
	//
	//  Un contrôle qui interdit d'en parler oblige à taire la raison — et c'est
	//  la raison qui se perd en premier. Constaté sur `SectionDocuments.svelte`,
	//  dont le commentaire dit précisément pourquoi il n'emploie PAS cette balise.
	//
	//  ⚠️ Le contenu est remplacé par des espaces, jamais supprimé : les index et
	//  les numéros de ligne des occurrences RÉELLES doivent rester justes.
	const neutre = neutraliserCommentaires(source);

	const marqueur = /\{@html\b/g;
	let m;
	while ((m = marqueur.exec(neutre)) !== null) {
		prises++;
		const ligne = source.slice(0, m.index).split('\n').length;
		const brut = expression(source, m.index);
		if (brut === null) {
			erreurs.push(
				`${relatif}:${ligne} — accolade non refermée : expression illisible, donc INCONNU.`,
			);
			continue;
		}
		const expr = brut.replace(/^@html\s*/, '').trim();
		const appel = /^([A-Za-z_$][\w$]*)\s*\(/.exec(expr);

		if (appel && assainisseurs.has(appel[1]) && importes.has(appel[1])) continue;

		if (relatif in EXCEPTIONS) {
			exceptionsServies.add(relatif);
			continue;
		}

		if (appel && assainisseurs.has(appel[1])) {
			erreurs.push(
				`${relatif}:${ligne} — ${appel[1]}(…) porte le nom d'un assainisseur mais n'est PAS ` +
					"importé de `#lib/sanitize` : c'est une fonction locale, et rien ne dit ce qu'elle fait.",
			);
		} else {
			const apercu = expr.length > 60 ? expr.slice(0, 57) + '…' : expr;
			erreurs.push(
				`${relatif}:${ligne} — {@html ${apercu}} n'appelle aucun assainisseur ` +
					`(attendu : ${[...assainisseurs].join(', ')}).`,
			);
		}
	}
}

// ── 3. Cas zéro : un contrôle qui ne reconnaît presque rien ne conclut pas ────
if (prises < PRISES_MINIMALES) {
	console.error(
		`✗ Cas zéro : ${prises} occurrence(s) de {@html} reconnue(s), ${PRISES_MINIMALES} attendues au minimum.`,
	);
	console.error(
		'Le front en portait 50 le 18/08/2026. Un effondrement du relevé signale que le\n' +
			'contrôle a cessé de voir, pas que le défaut a disparu — ne pas lire ceci comme\n' +
			'un succès (`standards/04-fiabilite-des-controles.md` §2).',
	);
	process.exit(1);
}

// ── 4. Une exception qui ne sert plus est une porte qu'on croit fermée ────────
const mortes = Object.keys(EXCEPTIONS).filter((f) => !exceptionsServies.has(f));
if (mortes.length) {
	console.error('✗ Exception déclarée et jamais servie — la retirer de `EXCEPTIONS` :\n');
	for (const f of mortes) console.error(`  • ${f}`);
	console.error(
		"\nSoit le fichier n'existe plus, soit il a été mis en conformité. Dans les deux\n" +
			'cas la dérogation ne protège plus rien, et elle masquera le prochain écart.\n',
	);
	process.exit(1);
}

if (erreurs.length) {
	console.error('✗ {@html} sans assainissement — injection de HTML possible :\n');
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		'\n🔴 Règle : {@html X} où X est un appel à une fonction de `#lib/sanitize`\n' +
			`   (${[...assainisseurs].join(', ')}), et rien d'autre.\n` +
			'   Une exception se DÉCLARE dans `EXCEPTIONS` avec sa raison, et se répercute\n' +
			"   dans `CLAUDE.md` — sinon ce n'est pas une exception, c'est un oubli.\n",
	);
	process.exit(1);
}

// ── 5. L'assainisseur de SECOURS, éprouvé (#2159, #2882) ────────────────────
//  Tant que DOMPurify n'est pas chargé (rendu serveur, premier rendu), c'est lui
//  qui assainit — et un rendu fait par lui le reste. Il gardait
//  `href="javascript:…"` (#2159), puis se contournait en recollant un
//  gestionnaire (#2882) : seule la CSP l'arrêtait.
//
//  Hors navigateur, `safeHtml` n'a pas DOMPurify : c'est donc le secours qui
//  répond ici, importé tel quel (Node lit le TypeScript, aucune copie à tenir).
//  On n'y cherche pas des motifs interdits — on exige que CHAQUE sortie
//  appartienne à la grammaire fermée que le module promet :
//    - du texte sans `<` ni `>` ;
//    - `<balise attr="valeur">` ou `</balise>`, balise de `ALLOWED_TAGS`,
//      attribut de `ALLOWED_ATTR`, valeur sans `"`, `<` ni `>` ;
//    - un `href` / `src` qui commence par un début admis.
//  Une telle sortie, lue par un navigateur, ne peut porter ni gestionnaire ni
//  balise refusée. Corpus hostile, 20 000 entrées tirées (graine fixe),
//  contenus légitimes qui doivent survivre, et durée bornée sur une entrée longue.
let secours;
try {
	secours = await import(SOURCE_SANITIZE);
} catch (e) {
	console.error(`✗ INCONNU : l'assainisseur de secours ne se lit plus (${e.message}).`);
	process.exit(1);
}
const { safeHtml, safeRichContent, safeDescription, ALLOWED_TAGS, ALLOWED_ATTR } = secours;
let echecs = 0;
const BALISES = new Set(ALLOWED_TAGS);
const ATTRIBUTS = new Set(ALLOWED_ATTR);
const URL_ADMISE = {
	href: /^(?:https?:\/\/|mailto:|\/(?!\/)|#|\.{1,2}\/)/i,
	src: /^(?:https?:\/\/|\/(?!\/))/i,
};

/** La raison du refus, ou null si `html` appartient à la grammaire. */
function horsGrammaire(html) {
	//  Blancs avant `>` et casse admis À LA LECTURE : le nom lu se juge ensuite
	//  contre `ALLOWED_TAGS` (minuscules), donc `<SCRIPT>` ou `<p \n>` ne passent
	//  pas pour autant — et le motif ne se prend pas pour un filtre de balises.
	const jeton = /[^<>]+|<(\/?)([a-z][a-z0-9]*)((?: [a-z]+="[^"<>]*")*)\s*>/giy;
	let fin = 0;
	for (const m of html.matchAll(jeton)) {
		if (m.index !== fin) break;
		fin = m.index + m[0].length;
		if (!m[2]) continue;
		if (!BALISES.has(m[2])) return `balise refusée <${m[2]}>`;
		if (m[1] && m[3]) return `balise fermante avec attributs : ${m[0]}`;
		for (const [, nom, valeur] of m[3].matchAll(/ ([a-z]+)="([^"]*)"/g)) {
			if (!ATTRIBUTS.has(nom)) return `attribut refusé ${nom}`;
			if (URL_ADMISE[nom] && !URL_ADMISE[nom].test(valeur.trim()))
				return `URL refusée ${nom}="${valeur}"`;
		}
	}
	return fin === html.length
		? null
		: `hors grammaire à la position ${fin} : ${JSON.stringify(html.slice(fin, fin + 40))}`;
}

const HOSTILES = [
	'<img alt=">" src=x oonclick=""nerror=alert(1)>',
	'<p title=">" oonmouseover=""nmouseover=alert(1)>x</p>',
	'<a href="/x" title=">" oonclick=""nclick=alert(1)>lien</a>',
	'<scr<script>ipt>alert(1)</script>',
	'<script>alert(1)</script >',
	'<SCRIPT>alert(1)</SCRIPT>',
	'<script src=//x></script>',
	'<style>*{x:y}</style ><p>ok</p>',
	'<!--><img src=x onerror=alert(1)>-->',
	'<!-- a --!><img src=x onerror=alert(1)>',
	'<img src=x onerror=alert(1)//',
	'<img/src=x/onerror=alert(1)>',
	'<a href="javascript:alert(1)">x</a>',
	'<a href=" javascript:alert(1)">x</a>',
	'<a href="&#106;avascript:alert(1)">x</a>',
	'<a href=//evil.example>x</a>',
	'<img src="data:image/svg+xml,<svg onload=alert(1)>">',
	"<a title='\"><img src=x onerror=alert(1)>'>x</a>",
	'<svg><script>alert(1)</script></svg>',
	'<iframe srcdoc="<script>alert(1)</script>"></iframe>',
	'<p class=a onclick=alert(1)>x</p>',
	'<p\tonclick=alert(1)>x</p>',
	'<p onclick\n=alert(1)>x</p>',
	'<math><mi xlink:href="javascript:alert(1)">x</mi></math>',
	'<<p>>',
	'</p onclick=alert(1)>',
	'<a href="/ok" target=_blank rel=noopener>lien</a>',
	'<img src="javascript:alert(1)">',
	'<img src="data:text/html;base64,PHNjcmlwdD4=">',
	'<svg onload=alert(1)>',
];

const verifier = (entree, sortie) => {
	const raison = horsGrammaire(sortie);
	if (raison) {
		echecs++;
		console.error(
			`  ✗ ${JSON.stringify(entree)}\n      → ${JSON.stringify(sortie)}\n      ${raison}`,
		);
	}
};

for (const h of HOSTILES)
	for (const f of [safeHtml, safeRichContent, safeDescription]) verifier(h, f(h));

//  Fuzz : des fragments dangereux recollés au hasard (graine fixe, rejouable).
const FRAGMENTS = [
	'<',
	'>',
	'/',
	'"',
	"'",
	'=',
	' ',
	'on',
	'error',
	'click',
	'img',
	'a',
	'p',
	'script',
	'style',
	'src',
	'href',
	'alt',
	'x',
	'javascript:',
	'<!--',
	'-->',
	'--!>',
	'\n',
	'\t',
	'alert(1)',
	'o',
	'n',
];
let graine = 2882;
const hasard = (n) => (graine = (graine * 1103515245 + 12345) % 2147483648) % n;
for (let i = 0; i < 20000; i++) {
	let s = '';
	for (let j = 0, k = 1 + hasard(30); j < k; j++) s += FRAGMENTS[hasard(FRAGMENTS.length)];
	verifier(s, safeHtml(s));
}

//  Contenu légitime : il doit SURVIVRE (un assainisseur qui vide tout passerait la grammaire).
const LEGITIMES = [
	['<p>Bonjour <strong>à tous</strong></p>', '<p>Bonjour <strong>à tous</strong></p>'],
	[
		'<a href="https://exemple.test/a?b=1&amp;c=2" target="_blank">lien</a>',
		'<a href="https://exemple.test/a?b=1&amp;c=2" target="_blank">lien</a>',
	],
	['<img src="/uploads/x.webp" alt="Hall">', '<img src="/uploads/x.webp" alt="Hall">'],
	['3 < 4 et 5 > 2', '3 &lt; 4 et 5 &gt; 2'],
	['<ul><li>un</li><li>deux</li></ul>', '<ul><li>un</li><li>deux</li></ul>'],
	['<a href="/tickets/3">x</a>', '<a href="/tickets/3">x</a>'],
	['<a href="mailto:a@exemple.test">x</a>', '<a href="mailto:a@exemple.test">x</a>'],
];
for (const [entree, attendu] of LEGITIMES) {
	const obtenu = safeHtml(entree);
	if (obtenu !== attendu) {
		echecs++;
		console.error(
			`  ✗ contenu légitime altéré ${JSON.stringify(entree)}\n      attendu ${JSON.stringify(attendu)}\n      obtenu  ${JSON.stringify(obtenu)}`,
		);
	}
}

//  Durée : des motifs qui reculeraient sur une entrée longue.
for (const [nom, entree] of [
	['<aaaa… sans >', '<' + 'a'.repeat(200000)],
	['< répétés', '<a '.repeat(70000)],
	['guillemets ouverts', '<a "'.repeat(50000)],
	['commentaires ouverts', '<!--'.repeat(50000)],
]) {
	const t = performance.now();
	safeHtml(entree);
	const ms = performance.now() - t;
	if (ms > 1000) {
		echecs++;
		console.error(`  ✗ ${nom} : ${Math.round(ms)} ms (> 1000)`);
	}
}

if (echecs) {
	console.error(
		`\n✗ L'assainisseur de secours (\`_serverSanitize\`) est faux : ${echecs} échec(s) (#2882).`,
	);
	process.exit(1);
}

console.log(
	`✓ HTML : ${prises} occurrences de {@html} dans ${fichiers.length} composants — ` +
		`toutes assainies par ${[...assainisseurs].join('/')}, ` +
		`${Object.keys(EXCEPTIONS).length} exceptions déclarées et servies ; ` +
		`assainisseur de secours éprouvé (${HOSTILES.length} charges, 20 000 tirées, ${LEGITIMES.length} témoins, durée bornée).`,
);
