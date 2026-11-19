/**
 * Garde-fou : un contrôle déclaré dans `package.json` doit être LANCÉ par la CI.
 *
 * ## Pourquoi il existe (#561, 28/08/2026 — et c'est arrivé le soir même)
 *
 * `lint:a11y` a été écrit, éprouvé en le déclenchant, déclaré dans
 * `package.json`… et son étape de CI **n'est pas partie dans le commit** : un
 * `git add -A front` ne prend pas `.github/`. Le contrôle existait, il était
 * juste, et **rien ne l'exécutait**.
 *
 * ⚠️ **SA PORTÉE ÉTAIT PLUS ÉTROITE QUE SA PROMESSE** (08/09/2026). Il ne
 * regardait que les scripts `lint:*`, quand la phrase ci-dessus dit « un contrôle
 * déclaré dans `package.json` ». `e2e` lui a donc échappé : seize tests de
 * navigateur écrits le 06/09, dans le dépôt, exécutés par personne pendant deux
 * jours. **Le garde-fou contre ce défaut avait exactement ce défaut** — et son
 * message de succès, « tous lancés par la CI », était faux sans mentir.
 *
 * La lecture est désormais une liste NOIRE : tout script compte, sauf ceux qu'on
 * écarte nommément. Un script ajouté demain est exigé par défaut.
 *
 * 🔴 C'est le pire des faux verts, parce qu'il ne ressemble pas à une panne :
 * `npm run lint:a11y` marche quand on le tape, la CI est verte, et le dépôt
 * n'est plus protégé. Le même défaut a déjà frappé ici deux fois — `--selftest`
 * exposé mais jamais lancé (`lib-analyse-styles`, #562), et `check-stack.sh`
 * retiré du cron d'un nœud (#301).
 *
 * ⚠️ Ce contrôle ne dit pas qu'un contrôle est BON. Il dit qu'il TOURNE. C'est
 * une question plus étroite, et c'est justement celle que personne ne posait.
 *
 * Usage : npm run lint:ci
 */
import { readFileSync } from 'node:fs';

const PACKAGE = new URL('../package.json', import.meta.url);
const WORKFLOW = new URL('../../.github/workflows/ci.yml', import.meta.url);

/**
 * Les contrôles déclarés que la CI ne lance PAS, chacun avec sa raison.
 *
 * ⚠️ Une entrée qui ne sert plus fait échouer : sinon la liste couvrirait un
 * contrôle redevenu câblé, et masquerait le prochain qui ne l'est pas.
 */
const EXCEPTIONS = {
	//  Vide depuis le 02/10/2026 (#1573). `lint:format` y a figuré sur une raison
	//  périmée (« #419, 51 fichiers à reformater ») alors que le job lançait déjà
	//  `npx prettier --check .` : la même commande, mais sous un nom que ce contrôle
	//  ne reconnaît pas. L'étape appelle désormais `npm run lint:format`.
};

function abandonner(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ lint:ci — ${message}\n`);
	process.exit(1);
}

let scripts;
try {
	scripts = JSON.parse(readFileSync(PACKAGE, 'utf8')).scripts ?? {};
} catch (e) {
	abandonner(`\`package.json\` illisible : ${e.message}`);
}

let workflow;
try {
	workflow = readFileSync(WORKFLOW, 'utf8');
} catch (e) {
	abandonner(
		`\`.github/workflows/ci.yml\` illisible (${e.message}). Sans lui, ce contrôle ne\n` +
			'  peut rien vérifier — et se taire vaudrait un vert.',
	);
}

/*  Les scripts qui ne VÉRIFIENT rien : ils construisent, servent, ou ouvrent une
    fenêtre. Les exiger en CI n'aurait aucun sens.

    🔴 Liste NOIRE et non liste blanche, et c'est tout le correctif du 08/09/2026.
    Ce contrôle ne regardait que les scripts `lint:*` — alors que son en-tête
    promet « un contrôle déclaré dans `package.json` doit être LANCÉ par la CI ».
    `e2e` lui a donc échappé : seize tests de navigateur écrits le 06/09, dans le
    dépôt, exécutés par personne pendant deux jours. Le garde-fou CONTRE ce
    défaut avait exactement ce défaut.

    Une liste blanche laisse passer tout ce qu'on n'a pas prévu ; une liste noire
    oblige à écarter chaque nouveau script explicitement — et le contrôle échoue
    si l'une de ses entrées disparaît. Le sens de l'oubli change : il va vers
    l'exigence, pas vers le silence. */
const _INUTILES = ['dev', 'build', 'preview'];

/*  ⚠️ `e2e:ui` ouvre le mode interactif de Playwright : il ATTEND un humain, et
    le lancer en CI bloquerait le job jusqu'au délai d'attente. `e2e`, lui, est
    exigé — c'est la correction du 08/09.

    ⚠️ `lint` et `check` sont des AGRÉGATS : leurs contenus (`prettier --check`,
    `eslint`, `svelte-check`) sont déjà des étapes nommées de la CI. Les exiger par
    leur nom d'agrégat ferait tourner les mêmes contrôles deux fois. */
const _AGREGATS = ['lint', 'check', 'e2e:ui'];

const declares = Object.keys(scripts).filter(
	(n) => !_INUTILES.includes(n) && !_AGREGATS.includes(n),
);
//  Cas zéro : un `package.json` sans script à vérifier ne veut pas dire « tout
//  va bien », il veut dire que la lecture est cassée.
if (declares.length < 20) {
	abandonner(
		`${declares.length} script(s) de vérification lu(s), au moins 20 attendus.` +
			'\n  Le motif de lecture ne correspond plus au fichier.',
	);
}
//  ⚠️ Une entrée d'écartement qui ne correspond plus à aucun script est un reste :
//  elle masquerait un homonyme réintroduit plus tard.
const ecartees = [..._INUTILES, ..._AGREGATS].filter((n) => !(n in scripts));
if (ecartees.length) {
	abandonner(
		`ces scripts écartés n'existent plus : ${ecartees.join(', ')}.` +
			'\n  Retirer l’entrée de `_INUTILES` ou `_AGREGATS`.',
	);
}
//  Idem côté workflow : s'il ne cite aucun `npm run lint:`, ce n'est pas que la
//  CI n'en lance aucun, c'est qu'on ne lit pas le bon fichier.
if (!/npm run lint:/.test(workflow)) {
	abandonner(
		'aucun `npm run lint:` dans le workflow. Ce n’est pas un dépôt sans contrôles,\n' +
			'  c’est une lecture qui ne correspond plus à la CI.',
	);
}

const manquants = declares.filter(
	(n) => !new RegExp(`\\b${n}(\\s|$|"|')`).test(workflow) && !(n in EXCEPTIONS),
);
const perimees = Object.keys(EXCEPTIONS).filter(
	(n) => !declares.includes(n) || new RegExp(`\\b${n}(\\s|$|"|')`).test(workflow),
);

if (perimees.length) {
	console.error(
		'\n✗ lint:ci — ces exceptions ne servent plus :\n\n' +
			perimees.map((n) => `  ${n}\n      « ${EXCEPTIONS[n]} »`).join('\n') +
			'\n\n  Le contrôle est câblé, ou il a disparu. Retirer l’entrée.\n',
	);
	process.exit(1);
}

if (manquants.length) {
	console.error(
		`\n✗ lint:ci — ${manquants.length} contrôle(s) déclaré(s) que la CI ne lance PAS :\n\n` +
			manquants.map((n) => `  npm run ${n}`).join('\n') +
			'\n\n  Un contrôle qui existe et que rien n’exécute est le pire des faux verts :\n' +
			'  il marche quand on le tape, la CI est verte, et le dépôt n’est plus protégé.\n' +
			'  Ajouter son étape dans `.github/workflows/ci.yml` — ou, si c’est délibéré,\n' +
			'  le déclarer dans EXCEPTIONS avec sa raison.\n',
	);
	process.exit(1);
}

console.log(
	`✓ lint:ci — ${declares.length} contrôle(s) déclaré(s), tous lancés par la CI ` +
		`(${Object.keys(EXCEPTIONS).length} exception(s) nommée(s)).`,
);
