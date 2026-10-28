/**
 * Garde-fou — **une consigne qui énumère ce que le code déclare**.
 *
 * ## Le défaut (#482, trouvé le 19/08/2026 en traitant #429)
 *
 * `svelte/no-at-html-tags` étant désactivée, la règle XSS du projet repose sur une
 * liste de fonctions d'assainissement. Cette liste est écrite **six fois** : dans
 * `CLAUDE.md` (deux endroits), dans trois skills, et — la seule qui fasse foi —
 * dans `src/lib/sanitize.ts`.
 *
 * Le 19/08, **cinq de ces six copies ne nommaient qu'une fonction sur trois**. La
 * consigne décrivait un dépôt qui n'existait plus depuis la factorisation qui avait
 * créé `safeDescription` et `safeRichContent`.
 *
 * Ce n'est pas resté théorique. `svelte-patterns` déclarait `renderDesc` — le corps
 * exact de `safeDescription` — comme « le seul helper qui reste légitimement
 * local », alors que cette fonction avait justement été écrite pour le supprimer.
 * Résultat : une **troisième** copie est apparue dans `tickets/[id]` sous le nom
 * `renderContent`, et c'est un contrôle écrit six jours plus tard qui l'a trouvée.
 *
 * 🔴 **La consigne fabriquait la duplication.** C'est le résidu de factorisation le
 * plus nocif, parce que c'est le seul qui soit **actif** : les autres dorment,
 * celui-ci fait réécrire du code — par quelqu'un qui suit correctement la
 * documentation (`standards/02-factorisation.md` §5).
 *
 * ## Pourquoi aucun contrôle ne pouvait l'attraper
 *
 *   • `lint:html` regarde le **code**, et le code produit par la consigne était
 *     *correct* — c'est sa raison d'être qui était périmée ;
 *   • la CI ne lit ni `CLAUDE.md` ni `.claude/skills/` ;
 *   • une relecture ne voit pas une consigne fausse : elle décrit un dépôt
 *     plausible.
 *
 * ## Ce que ce contrôle vérifie
 *
 * **Tout fichier de consigne qui parle d'assainissement HTML doit nommer TOUTES
 * les fonctions que `sanitize.ts` exporte.** La liste attendue est lue à la source,
 * jamais recopiée — c'est le principe même de `lint:html`, retourné vers la
 * documentation : une liste recopiée ici retomberait dans le défaut qu'elle garde.
 *
 * « Parle d'assainissement » = cite au moins une des fonctions, ou la balise
 * `{@html`. Un fichier muet sur le sujet n'est pas concerné : ce contrôle vérifie
 * la **complétude** de ce qui est dit, jamais qu'il faille en parler.
 *
 * ⚠️ Volontairement limité à cette énumération-là. D'autres consignes énumèrent ce
 * que le code déclare (dépendances d'auth, `lint:*`, statuts de ticket), et elles
 * relèvent du même motif — mais un contrôle qui produirait des faux positifs sur du
 * texte libre serait désarmé dans la semaine (`standards/04`). On commence par
 * celle qui a coûté quelque chose.
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';
import { extraire } from './lib-lecture-source.mjs';
import { motifNombre, valeurNombre } from './lib-nombres-fr.mjs';

const RACINE_FRONT = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const RACINE_DEPOT = new URL('../..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** Nombre minimal de fichiers de consigne attendus — cas zéro. */
const CONSIGNES_MINIMALES = 3;

// ── 1. Les listes qui font foi, lues à leur source ───────────────────────────
//
//  🔴 Une notion par entrée, et c'est délibéré : ce contrôle ne portait QUE les
//  assainisseurs, et l'audit du 19/09/2026 a trouvé trois autres listes recopiées
//  dans les consignes, dont trois avaient divergé (#1051, #1052) — les crons root,
//  les tâches planifiées, les exceptions XSS. Écrire un second contrôle pour elles
//  aurait été la duplication que ce contrôle existe pour dénoncer.
//
//  `declencheur` répond à « ce fichier parle-t-il de la notion ? ». Il doit être
//  LARGE : un fichier qui en parle sans rien nommer est justement le cas à
//  attraper. `source` lit la vérité dans le dépôt, jamais dans une autre consigne.
/**
 * Ce fichier ÉNUMÈRE-t-il la liste, ou se contente-t-il d'en parler ?
 *
 * 🔴 La nuance décide de tout, et deux faux positifs l'ont montrée en écrivant ce
 * contrôle : « tâches planifiées » attrapait le tableau des CRONS de CLAUDE.md —
 * autre notion, l'ordonnanceur vit dans le process de l'API, les crons sur l'hôte —
 * et le seul mot « APScheduler » attrapait la phrase qui dit d'aller lire la skill.
 *
 * Le critère est donc **deux éléments ou plus** : citer un job pour l'expliquer est
 * légitime, en aligner deux est une table, et une table se périme. Un déclencheur
 * trop large ne rend pas un contrôle plus strict — il le rend faux, et un contrôle
 * faux finit désarmé.
 */
const enumere = (texte, attendus) => attendus.filter((x) => texte.includes(x)).length >= 2;

/**
 * Les TABLES et blocs de code d'un fichier Markdown — l'unité qui se périme.
 *
 * 🔴 L'unité examinée n'est pas le fichier. `infra-rpi` portait une table de trois
 * crons sur quatre, et citait le quatrième trente lignes plus haut dans une autre
 * phrase : un contrôle qui lit tout le fichier l'y trouve et déclare la table
 * complète. Il mesure alors la présence d'un mot, là où la question est la
 * complétude d'une table.
 *
 * ⚠️ C'est aussi ce qui autorise une consigne à DIRE quelque chose d'utile sur un
 * élément — « c'est `health_check` qui alerte » — sans être accusée de recopier la
 * liste. Une phrase n'est pas une table, et seule la table se périme.
 */
const tableauxEtBlocs = (texte) =>
	[...texte.matchAll(/```[\s\S]*?```|(?:^\|.*\|$\n?)+/gm)].map((m) => m[0]);

/**
 * Les PARAGRAPHES d'un fichier — pour une énumération écrite en prose.
 *
 * 🔴 Lu sur le fichier entier, le déclencheur des exceptions XSS rougissait sur
 * un `import Icon from '#lib/components/Icon.svelte'` d'exemple, parce que le mot
 * « exception » figurait trois cents lignes plus loin. C'est arrivé le 23/09/2026,
 * quand `svelte-patterns` a remplacé sa liste par un renvoi : le contrôle punissait
 * exactement le geste qu'il recommande (claude-config#122). Une liste d'exceptions
 * tient dans un paragraphe ; un paragraphe qui en nomme une sans l'autre est bien
 * le défaut visé.
 */
const paragraphes = (texte) => texte.split(/\r?\n[ \t]*\r?\n/);

const NOTIONS = [
	{
		nom: 'assainisseurs HTML',
		source: () => {
			const src = readFileSync(join(RACINE_FRONT, 'lib', 'sanitize.ts'), 'utf8');
			return [...src.matchAll(/^export function (safe\w+)\s*\(/gm)].map((m) => m[1]);
		},
		ou: 'front/src/lib/sanitize.ts',
		declencheur: (texte, attendus) =>
			attendus.some((f) => texte.includes(f)) || texte.includes('{@html'),
		pourquoi:
			'la règle XSS repose sur cette liste ; cinq copies sur six ne nommaient ' +
			"qu'une fonction sur trois le 19/08/2026, et la consigne a fait naître une " +
			'quatrième copie du code (#429)',
		//  La règle XSS est la première des « quatre règles qui ne se négocient
		//  pas » : si plus aucune consigne ne la porte, c'est le contrôle qui a
		//  cessé de voir. Les trois autres notions sont des TABLES, dont on veut
		//  justement qu'il ne reste aucune copie.
		exigeUneMention: true,
	},
	{
		nom: 'exceptions à la règle XSS',
		source: () => {
			const src = readFileSync(join(RACINE_FRONT, '..', 'scripts', 'check-html.mjs'), 'utf8');
			const bloc = src.match(/const EXCEPTIONS = \{[\s\S]*?\n\};/);
			//  Avec l'extension : `Icon` seul matchait le composant `Icon`, les
			//  `icone` et jusqu'au mot « iconographie » — un faux positif sur toute
			//  skill qui parle d'interface.
			return bloc ? [...bloc[0].matchAll(/'[^']*\/(\w+\.svelte)'/g)].map((m) => m[1]) : [];
		},
		ou: 'front/scripts/check-html.mjs (EXCEPTIONS)',
		portions: paragraphes,
		declencheur: (texte, attendus) =>
			/exception/i.test(texte) && attendus.some((x) => texte.includes(x)),
		pourquoi:
			'une skill en déclarait UNE quand le contrôle en porte deux : un audit qui ' +
			'la suit signale `QRCode` comme un écart qui n’en est pas un',
	},
	{
		nom: 'crons root des deux nœuds',
		source: () => {
			const src = readFileSync(
				join(RACINE_DEPOT, 'infra', 'points-entree', 'cron-root.crontab'),
				'utf8',
			);
			//  Avec l'extension : `bascule` seul matchait « on bascule », et
			//  `maintenance` le composant `OngletMaintenance` — deux faux positifs.
			return [...src.matchAll(/\/([a-z-]+\.sh)/g)]
				.map((m) => m[1])
				.filter((v, i, t) => t.indexOf(v) === i);
		},
		ou: 'infra/points-entree/cron-root.crontab',
		//  🔴 L'unité examinée est le BLOC, pas le fichier. `infra-rpi` porte une
		//  table de trois crons sur quatre — et cite `check-reliability.sh` trente
		//  lignes plus haut, dans une autre phrase. Un contrôle qui lit le fichier
		//  entier le trouve donc, et déclare la table complète : il mesure la
		//  présence d'un mot là où la question est la complétude d'une table.
		portions: (texte) =>
			tableauxEtBlocs(texte).filter((b) => /[\d*/,]+ +[\d*/,]+ +\* +\* +[\d*/,]/.test(b)),
		declencheur: enumere,
		pourquoi:
			'une table en citait trois sur quatre — `check-reliability.sh`, qui décide ' +
			"d'alerter, manquait ; et les deux copies ignoraient la source versionnée",
	},
	{
		nom: 'tâches planifiées de l’API',
		source: () => {
			const src = readFileSync(join(RACINE_DEPOT, 'api', 'app', 'main.py'), 'utf8');
			return [...src.matchAll(/id="([a-z_]+)"/g)]
				.map((m) => m[1])
				.filter((v, i, t) => t.indexOf(v) === i);
		},
		ou: 'api/app/main.py (scheduler.add_job)',
		//  Même critère que les crons : une TABLE, pas une mention. « C'est
		//  `health_check` qui alerte, et `whatsapp_scheduled` quand sa fenêtre
		//  s'épuise » est une information qui ne se lit PAS dans le code ; aligner
		//  six jobs avec leurs heures est une copie qui se périme.
		portions: tableauxEtBlocs,
		declencheur: enumere,
		pourquoi:
			'un tableau en listait quatre sur six : le préchauffage du manuel et la ' +
			"relève des courriels n'y figuraient pas",
	},
];

// ── 2. Les fichiers de consigne ──────────────────────────────────────────────
function markdown(dir) {
	if (!existsSync(dir)) return [];
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...markdown(chemin));
		else if (nom.endsWith('.md')) sortie.push(chemin);
	}
	return sortie;
}

const candidats = [
	join(RACINE_DEPOT, 'CLAUDE.md'),
	...markdown(join(RACINE_DEPOT, '.claude', 'skills')),
].filter(existsSync);

if (candidats.length < CONSIGNES_MINIMALES) {
	console.error(
		`✗ Cas zéro : ${candidats.length} fichier(s) de consigne trouvé(s), ` +
			`${CONSIGNES_MINIMALES} attendus au minimum.`,
	);
	console.error(
		"L'arborescence des consignes a changé, ou le contrôle ne sait plus la lire —\n" +
			'ne pas lire ceci comme un succès (`standards/04` §2).',
	);
	process.exit(1);
}

// ── 3. Ceux qui en parlent doivent tout nommer ───────────────────────────────
const erreurs = [];
const textes = candidats.map((chemin) => ({
	relatif: relative(RACINE_DEPOT, chemin).replace(/\\/g, '/'),
	texte: readFileSync(chemin, 'utf8'),
}));

for (const notion of NOTIONS) {
	let attendus;
	try {
		attendus = notion.source();
	} catch {
		console.error(`✗ INCONNU : ${notion.ou} est illisible — ce contrôle ne conclut pas.`);
		process.exit(1);
	}
	//  Cas zéro : une source vide rendrait la notion toujours verte, sans rien
	//  mesurer — le faux vert par ensemble vide (`standards/04` §1 et §27).
	if (attendus.length === 0) {
		console.error(`✗ Cas zéro : rien à lire dans ${notion.ou} pour « ${notion.nom} ».`);
		console.error('Le motif de lecture est périmé — ne pas lire ceci comme un succès.');
		process.exit(1);
	}

	let concernes = 0;
	for (const { relatif, texte } of textes) {
		//  Une notion peut restreindre ce qu'on lit — une TABLE plutôt que tout le
		//  fichier. Par défaut, le fichier entier.
		for (const portion of notion.portions ? notion.portions(texte) : [texte]) {
			if (!notion.declencheur(portion, attendus)) continue;
			concernes++;
			const absents = attendus.filter((x) => !portion.includes(x));
			if (absents.length) {
				erreurs.push(
					`${relatif} — parle de « ${notion.nom} » sans nommer : ${absents.join(', ')}\n` +
						`      attendu (lu dans ${notion.ou}) : ${attendus.join(', ')}\n` +
						`      pourquoi : ${notion.pourquoi}\n` +
						`      → renvoyer à la source plutôt que de la recopier`,
				);
			}
		}
	}

	//  🔴 Le cas zéro ne vaut QUE pour les notions qu'une consigne doit porter.
	//
	//  Pour les autres — une table de crons, une liste de jobs — le but est
	//  précisément qu'il n'en reste AUCUNE copie : exiger qu'une consigne en
	//  énumère une reviendrait à interdire de la supprimer. Le contrôle a rougi
	//  ainsi dès que la première table a été remplacée par un renvoi, ce qui était
	//  le résultat attendu. Un cas zéro mal posé transforme le succès en alarme.
	if (notion.exigeUneMention && concernes === 0) {
		console.error(`✗ Cas zéro : aucune consigne ne parle de « ${notion.nom} ».`);
		console.error(
			"C'est une règle qu'une consigne DOIT porter : soit le déclencheur ne " +
				'reconnaît plus le sujet, soit la règle a disparu des consignes.',
		);
		process.exit(1);
	}
}

// ── 4. Les NOMBRES recopiés (#1541) ──────────────────────────────────────────
//
//  🔴 Une liste qu'on ne recopie plus se recopie encore par son COMPTE. CLAUDE.md
//  disait « treize » sections, `ux-patterns` « les treize sections » et « les 10
//  sections » : le code en comptait quatorze depuis six jours (#1342), et les
//  deux consignes renvoyaient pourtant à `SECTIONS_ORDRE`. Le renvoi était juste,
//  le nombre posé à côté de lui ne l'était plus.
//
//  Ce contrôle refuse donc le nombre lui-même, JUSTE OU FAUX : un compte exact
//  aujourd'hui diverge à la prochaine section, et rien ne le relit alors. Une
//  consigne dit où se lit la liste (`standards/13` §1), pas combien elle porte.
//
//  ⚠️ Seuil : la moitié du compte réel. « Trois sections entrent », « deux
//  sections fusionnées » racontent un CHANGEMENT et restent permis ; un nombre
//  qui prétend couvrir le cadre entier est une copie de son compte. Un seuil
//  plus bas rougirait sur l'histoire ; aucun seuil n'attraperait plus rien.
const NOMBRES = [
	{
		nom: 'sections de formulaire',
		ou: 'front/src/lib/entites/types.ts (SECTIONS_ORDRE)',
		compte: () => {
			const chemin = join(RACINE_FRONT, 'lib', 'entites', 'types.ts');
			const echec = (m) => {
				throw new Error(m);
			};
			return extraire(readFileSync(chemin, 'utf8'), 'SECTIONS_ORDRE', chemin, { echec }).length;
		},
		//  « les 10 sections », « les treize sections », et un nombre en lettres
		//  sur la ligne même du renvoi — « **treize**, dans l'ordre de
		//  `SECTIONS_ORDRE` » (CLAUDE.md), où le mot « sections » n'est pas écrit.
		motifs: [
			new RegExp(`${motifNombre()}[*_]*\\s+sections?\\b`, 'giu'),
			new RegExp(`^.*SECTIONS_ORDRE.*$`, 'gmu'),
		],
		dansLaLigne: new RegExp(motifNombre({ chiffres: false }), 'giu'),
	},
];

for (const notion of NOMBRES) {
	let compte;
	try {
		compte = notion.compte();
	} catch (e) {
		console.error(
			`✗ INCONNU : ${notion.ou} est illisible (${e.message}) — ce contrôle ne conclut pas.`,
		);
		process.exit(1);
	}
	if (!compte) {
		console.error(
			`✗ Cas zéro : ${notion.ou} ne porte aucun élément — le motif de lecture a dérivé.`,
		);
		process.exit(1);
	}
	const seuil = Math.ceil(compte / 2);
	for (const { relatif, texte } of textes) {
		const lus = [];
		const [adjacent, ligneDuRenvoi] = notion.motifs;
		for (const m of texte.matchAll(adjacent)) lus.push([m[1], m[0]]);
		for (const ligne of texte.matchAll(ligneDuRenvoi)) {
			for (const m of ligne[0].matchAll(notion.dansLaLigne)) lus.push([m[1], ligne[0].trim()]);
		}
		for (const [nombre, contexte] of lus) {
			if ((valeurNombre(nombre) ?? 0) < seuil) continue;
			erreurs.push(
				`${relatif} — recopie le nombre de « ${notion.nom} » : « ${contexte.slice(0, 90)} »\n` +
					`      le code en compte ${compte} (${notion.ou}) — juste ou faux, ce nombre se périme\n` +
					`      → dire où se lit la liste, sans son compte (\`standards/13\` §1, #1541)`,
			);
		}
	}
}

if (erreurs.length) {
	console.error('✗ Consigne incomplète — elle décrit un dépôt qui n’existe pas :\n');
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		'\n🔴 Une consigne périmée est le seul résidu de factorisation qui RÉGÉNÈRE le\n' +
			'   défaut : elle fait réécrire à la main ce que le dépôt a mutualisé, par\n' +
			'   quelqu’un qui la suit correctement. C’est ainsi que `renderContent` est né\n' +
			'   (#429), et personne ne pouvait le voir — le code produit était correct.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Consignes : ${NOTIONS.length} notion(s) confrontée(s) à leur source sur ` +
		`${candidats.length} fichier(s) de consigne — aucune liste recopiée n'a dérivé, ` +
		`aucun compte de ${NOMBRES.map((n) => n.nom).join(', ')} recopié.`,
);
