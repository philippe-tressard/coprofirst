#!/usr/bin/env node
/**
 *  Une carte de liste rend son haut par `EnteteCarte` — sans exception.
 *
 *  ## Pourquoi ce contrôle (12/09/2026)
 *
 *  `EnteteCarte` existe depuis le 18/08/2026 et porte trois décisions qu'on ne
 *  peut pas reprendre carte par carte :
 *
 *    • le TITRE occupe sa ou ses propres lignes, et rien ne le pousse. Sur un
 *      téléphone, une ligne en `flex` partagée avec des badges de largeur fixe
 *      réduit le titre à trois points — on lit une liste sans savoir de quoi
 *      elle parle. C'est **R1** : la responsivité appartient au squelette.
 *    • le geste est ASYMÉTRIQUE — repliée, toute la carte ouvre ; dépliée, seul
 *      le titre referme, pour qu'on puisse lire et copier le corps.
 *    • l'ordre de lecture : tags à gauche, date puis actions puis chevron à
 *      droite.
 *
 *  🔴 Onze cartes l'employaient. DEUX ne l'employaient pas — `CarteContrat` et
 *  `CartePrestataire` — et elles portaient exactement les défauts qu'il supprime,
 *  y compris l'ancien `role="button"` sur le conteneur, remplacé partout ailleurs
 *  le 18/08. Personne ne l'a vu pendant un mois : rien ne relit une carte qu'on
 *  ne touche pas, et les deux étaient cohérentes *entre elles*.
 *
 *  Signalé à l'écran : *« le comportement et l'UX ne doivent pas diverger »*.
 *
 *  ## Ce que le contrôle mesure
 *
 *  Tout fichier qui rend une carte de liste — `<CarteListe>`, seul conteneur
 *  depuis le 10/10/2026 ; avant, `class="carte-liste"` écrit à la main — doit
 *  importer `EnteteCarte`. C'est volontairement grossier : il ne vérifie pas
 *  QUE l'en-tête est bien composé, seulement qu'il n'est pas réécrit. Un
 *  contrôle qui prétendrait juger la composition rendrait des verdicts qu'on
 *  finirait par ignorer.
 *
 *  ⚠️ La liste d'exceptions est VIDE, et c'est le bon moment pour l'ouvrir : le
 *  dépôt est conforme aujourd'hui. Une exception ajoutée plus tard devra dire
 *  pourquoi, et une exception qui ne sert plus fait échouer ce contrôle.
 *
 *  ## Et le corps déplié porte `carte-corps` (#1579, 02/10/2026)
 *
 *  `.carte-liste .carte-corps` (`composants.css`) est ce qui fait ENTRER le corps :
 *  fondu de 200 ms au montage, désactivé sous `prefers-reduced-motion`. Sans la
 *  classe, le corps « apparaît sec, sans un mot » — et rien ne le disait : la
 *  checklist Frontend de `CLAUDE.md` l'écrivait, aucun contrôle ne la tenait, et
 *  `CarteModifiable` (contrats, prestataires) portait `carte-modifiable-corps`
 *  seul. Tout fichier qui rend `.carte-liste` doit donc écrire `carte-corps` dans
 *  un `class="…"` — comme `EnteteCarte`, le contrôle est grossier : il ne juge pas
 *  QUEL élément la porte, seulement qu'elle est posée.
 *
 *  ## Et la ligne de méta a UNE taille (#1308, 25/09/2026)
 *
 *  Signalé à l'écran, capture à l'appui : « Ouvert » et le périmètre en petit,
 *  « Tous sauf locataires » et « #TK-121048 » nettement plus grands, l'auteur
 *  entre les deux. Trois causes, une par élément : un `font: inherit` sur la
 *  pastille de lecture (le raccourci RÉINITIALISE la taille du `.badge`), un
 *  numéro sans taille en monospace, un auteur à 0,78 rem.
 *
 *  La taille se pose une fois, sur `.ec-tags` d'`EnteteCarte`. Dans le slot
 *  `tags` d'une carte — et dans les composants qu'il rend —, une classe ne
 *  déclare pas de taille, ou déclare CELLE-LÀ ; le raccourci `font:` y est
 *  refusé. Les écarts légitimes se déclarent dans `TAILLE_LIBRE`.
 *
 *  Lancer : node scripts/check-entete-carte.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';

/**  Le marqueur d'une carte de liste : son conteneur, `CarteListe` — le seul
 *   qui écrive `.carte-liste` depuis le 10/10/2026 (`lint:carte-liste`). */
const CARTE = /<CarteListe\b/;
/** L'emploi du composant — par l'IMPORT, qu'une portée locale ne peut pas feindre. */
const EMPLOI = /import\s+EnteteCarte\s+from/;
/** Le corps déplié : la classe qui le fait entrer, dans un `class="…"` (#1579). */
const CORPS = /class="[^"]*(?<![\w-])carte-corps(?![\w-])/;

/**
 *  Les fichiers qui rendent `.carte-liste` sans `EnteteCarte`, avec leur motif.
 *
 *  🔴 VIDE au 12/09/2026 — le dépôt est entièrement conforme. Toute entrée
 *  ajoutée ici doit porter sa raison, et une entrée devenue inutile fait échouer
 *  le contrôle : une exception reconduite « au cas où » masquerait la suivante.
 */
const EXCEPTIONS = {
	'lib/components/ApercuEquipement.svelte':
		'un APERÇU (#2442) : la carte montre la gouttière d’un équipement en cours de saisie, elle ne se déplie pas — elle n’a pas de corps',
};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

/**  Un chevron rendu par la carte elle-même.
 *
 *   🔴 SIX cartes remplissaient un `slot="chevron"` avec la même ligne, et deux
 *   d'entre elles y écrivaient `expanded || enEdition` là où les quatre autres
 *   écrivaient `expanded` — deux façons de dire « cette carte est dépliée »,
 *   pour une classe que l'appelant pose DÉJÀ sur la carte. `EnteteCarte` rend
 *   le chevron depuis le 18/09/2026, et sa rotation se lit sur
 *   `.carte-liste.expanded`. */
const CHEVRON_RECOPIE = /slot=["']chevron["']|class=["']chevron["']/;

/**  La décision, PURE — testable sans toucher au disque.
 *   @returns {'ok'|'sans-entete'|'chevron-recopie'|'sans-corps'|'hors-sujet'} */
export function verdictCarte(source) {
	if (!CARTE.test(source)) return 'hors-sujet';
	if (!EMPLOI.test(source)) return 'sans-entete';
	if (CHEVRON_RECOPIE.test(source)) return 'chevron-recopie';
	return CORPS.test(source) ? 'ok' : 'sans-corps';
}

/**  Les classes de la ligne de méta qui gardent LEUR taille, avec la raison.
 *   Une entrée qui ne sert plus fait échouer. */
const TAILLE_LIBRE = {
	'pa-cat': 'pictogramme de catégorie en tête de ligne (PastillesAffaire) — un émoji, pas du texte',
	'infobulle-bulle':
		'la bulle de PastilleLecture (Infobulle), ouverte au toucher, posée SOUS la ligne',
	//  `NotationsPrestataire` a deux modes : `resume` (le badge ★, dans la ligne)
	//  et la liste des avis, rendue dans le CORPS de la carte. Le contrôle lit le
	//  composant entier ; ces trois classes n'appartiennent qu'au second mode.
	'not-entete': 'liste des avis (NotationsPrestataire sans `resume`), dans le corps',
	'not-date': 'liste des avis (NotationsPrestataire sans `resume`), dans le corps',
	'not-commentaire': 'liste des avis (NotationsPrestataire sans `resume`), dans le corps',
	//  `Badge` (#1571) se rend dans la ligne SANS `compact` : le cran `--fs-2xs`
	//  ne sert qu'aux listes denses hors carte (Accès, baux). Le contrôle lit le
	//  composant entier, comme pour `NotationsPrestataire`.
	compact: 'cran `--fs-2xs` de `Badge`, réservé aux listes denses hors carte (Accès, baux)',
};

/** Le fragment du slot `tags`, ou la chaîne vide. */
export function fragmentTags(source) {
	const m = source.match(/<svelte:fragment slot="tags">([\s\S]*?)<\/svelte:fragment>/);
	return m ? m[1] : '';
}

/** Les classes STATIQUES d'un balisage (hors expressions `{…}`). */
export function classesDe(balisage) {
	const acc = new Set();
	for (const m of balisage.matchAll(/\bclass="([^"]*)"/g))
		for (const c of m[1].replace(/\{[^}]*\}/g, ' ').split(/\s+/))
			if (/^[a-z][\w-]*$/.test(c)) acc.add(c);
	for (const m of balisage.matchAll(/\bclass:([a-z][\w-]*)/g)) acc.add(m[1]);
	return acc;
}

/** Les composants (`<Majuscule`) rendus par un balisage. */
export function composantsDe(balisage) {
	return new Set([...balisage.matchAll(/<([A-Z]\w+)/g)].map((m) => m[1]));
}

/**  Les écarts de taille d'un `<style>` pour un ensemble de classes, PUR.
 *   @returns {{classe: string, decl: string}[]} */
export function ecartsTaille(source, classes, reference) {
	const style = (source.match(/<style[^>]*>([\s\S]*?)<\/style>/) ?? [])[1] ?? '';
	const sansCommentaires = style.replace(/\/\*[\s\S]*?\*\//g, '');
	const ecarts = [];
	for (const m of sansCommentaires.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const [selecteur, corps] = [m[1], m[2]];
		for (const c of classes) {
			if (!new RegExp(`\\.${c}(?![\\w-])`).test(selecteur)) continue;
			const raccourci = corps.match(/(?:^|[;\s])font\s*:[^;]*/);
			const taille = corps.match(/font-size\s*:\s*([^;]+)/);
			if (raccourci) ecarts.push({ classe: c, decl: raccourci[0].trim() });
			else if (taille && taille[1].trim() !== reference)
				ecarts.push({ classe: c, decl: `font-size: ${taille[1].trim()}` });
		}
	}
	return ecarts;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = verdictCarte(src);
		if (r === attendu) console.log(`PASS  ${libelle} → ${r}`);
		else {
			console.error(`FAIL  ${libelle}  attendu=${attendu} obtenu=${r}`);
			ko = 1;
		}
	};
	t(
		'carte conforme',
		'ok',
		'import EnteteCarte from \'./EnteteCarte.svelte\';\n<CarteListe><div class="carte-corps">',
	);
	t(
		'carte conforme (class:)',
		'ok',
		'import EnteteCarte from \'./x\';\n<CarteListe archive={a}><div class="carte-corps tk-body">',
	);
	//  🔴 #1579 : l'état exact de `CarteModifiable` avant le 02/10/2026 — un corps
	//  sous sa propre classe, qui n'entre pas en fondu.
	t(
		'corps sans carte-corps',
		'sans-corps',
		'import EnteteCarte from \'./x\';\n<CarteListe><div class="carte-modifiable-corps">',
	);
	//  Un voisin de nom ne vaut pas la classe : `carte-corps-x` n'est pas `carte-corps`.
	t(
		'classe voisine',
		'sans-corps',
		'import EnteteCarte from \'./x\';\n<CarteListe><div class="carte-corps-x">',
	);
	//  🔴 LE cas qui donne sa raison d'être au contrôle : c'est l'état exact dans
	//  lequel `CarteContrat` et `CartePrestataire` sont restées un mois.
	t('carte qui réécrit son en-tête', 'sans-entete', '<CarteListe expanded>');
	//  Un fichier qui ne rend aucune carte n'est ni bon ni mauvais : sans objet.
	t('fichier sans carte', 'hors-sujet', '<div class="autre-chose">');
	//  ⚠️ Le mot dans un COMMENTAIRE qui raconte la règle ne doit pas déclencher
	//  un import : c'est le faux positif que trois contrôles de ce dépôt ont déjà
	//  rencontré. Ici il est ACCEPTÉ comme carte — le motif est volontairement
	//  grossier — mais l'import suffit alors à le satisfaire.
	t(
		'mention en commentaire, avec import',
		'ok',
		'import EnteteCarte from \'./x\';\n// <CarteListe>\n<div class="carte-corps">',
	);
	//  🔴 Le second cas que ce contrôle refuse depuis le 18/09/2026.
	t(
		'carte qui rend son propre chevron',
		'chevron-recopie',
		`import EnteteCarte from './x';
<CarteListe><span class="chevron">›</span>`,
	);
	t(
		'carte qui remplit le slot chevron',
		'chevron-recopie',
		`import EnteteCarte from './x';
<CarteListe><svelte:fragment slot="chevron">`,
	);
	const e = (libelle, attendu, src, classes) => {
		const r = ecartsTaille(src, new Set(classes), '0.75rem').map((x) => x.classe);
		if (JSON.stringify(r) === JSON.stringify(attendu)) console.log(`PASS  ${libelle} → [${r}]`);
		else {
			console.error(`FAIL  ${libelle}  attendu=[${attendu}] obtenu=[${r}]`);
			ko = 1;
		}
	};
	//  🔴 Les trois formes exactes d'avant #1308.
	e('raccourci font: inherit', ['b'], '<style>.b { border: none; font: inherit; }</style>', ['b']);
	e('taille propre', ['a'], '<style>.a { font-size: 0.78rem; }</style>', ['a']);
	e('taille de référence', [], '<style>.a { font-size: 0.75rem; }</style>', ['a']);
	e('sans taille', [], '<style>.a { color: red; }</style>', ['a']);
	e('font-family seul', [], '<style>.b { font-family: inherit; }</style>', ['b']);
	e('classe voisine ignorée', [], '<style>.a-b { font-size: 2rem; }</style>', ['a']);
	e('commentaire ignoré', [], '<style>/* .a { font: x } */ .a { color: red; }</style>', ['a']);
	const frag = fragmentTags(
		'<svelte:fragment slot="tags"><span class="x {y}">1</span><Pastille /></svelte:fragment>',
	);
	if (
		!classesDe(frag).has('x') ||
		classesDe(frag).has('{y}') ||
		!composantsDe(frag).has('Pastille')
	) {
		console.error('FAIL  classes et composants du fragment');
		ko = 1;
	} else console.log('PASS  classes et composants du fragment');
	//  Le cas zéro : une source vide ne rend pas « ok », elle rend « hors-sujet ».
	t('source vide', 'hors-sujet', '');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const tous = fichiers(RACINE);
const fautifs = [];
const chevrons = [];
const sansCorps = [];
const exceptionsVues = new Set();
let cartes = 0;

for (const f of tous) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const verdict = verdictCarte(readFileSync(f, 'utf8'));
	if (verdict === 'hors-sujet') continue;
	cartes++;
	if (verdict === 'ok') continue;
	if (rel in EXCEPTIONS) {
		exceptionsVues.add(rel);
		continue;
	}
	(({ 'chevron-recopie': chevrons, 'sans-corps': sansCorps })[verdict] ?? fautifs).push(rel);
}

//  La taille de référence se LIT dans `EnteteCarte` : une valeur recopiée ici
//  divergerait au premier ajustement.
const entete = readFileSync(join(RACINE, 'lib/components/EnteteCarte.svelte'), 'utf8');
const REFERENCE = (entete.match(/\.ec-tags\s*\{[^}]*font-size:\s*([^;]+);/) ?? [])[1]?.trim();
if (!REFERENCE) {
	console.error('\n✗ INCONNU : `.ec-tags` ne porte plus de `font-size` dans EnteteCarte.\n');
	process.exit(2);
}
const tailles = new Set();
const libresVues = new Set();
let lignesMeta = 0;
for (const f of tous) {
	const source = readFileSync(f, 'utf8');
	const frag = fragmentTags(source);
	if (!frag) continue;
	lignesMeta++;
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const cibles = [[rel, source, classesDe(frag)]];
	//  🔴 TRANSITIF (27/09/2026) : la ligne des affaires est passée dans
	//  `PastillesAffaire`, qui rend `PastilleLecture`. Lu sur un seul niveau, le
	//  contrôle a cessé de voir cette pastille — sans un mot, sinon par
	//  l'exception devenue « inutile ». Un composant rendu par un composant de la
	//  ligne est dans la ligne.
	const aLire = [...composantsDe(frag)];
	const lus = new Set();
	while (aLire.length) {
		const nom = aLire.shift();
		if (lus.has(nom)) continue;
		lus.add(nom);
		try {
			const src = readFileSync(join(RACINE, 'lib/components', `${nom}.svelte`), 'utf8');
			cibles.push([`lib/components/${nom}.svelte`, src, classesDe(src)]);
			aLire.push(...composantsDe(src));
		} catch {
			/* composant d'ailleurs (icône, bibliothèque) : hors de la ligne */
		}
	}
	for (const [fichier, src, classes] of cibles)
		for (const { classe, decl } of ecartsTaille(src, classes, REFERENCE)) {
			if (classe in TAILLE_LIBRE) {
				libresVues.add(classe);
				continue;
			}
			tailles.add(`${fichier}  .${classe} { ${decl} }`);
		}
}
if (lignesMeta === 0) {
	console.error('\n✗ INCONNU : aucun slot `tags` trouvé — la ligne de méta a changé de forme.\n');
	process.exit(2);
}

let echec = false;
if (tailles.size) {
	echec = true;
	console.error(`\n✗ ${tailles.size} taille(s) propre(s) sur la ligne de méta d’une carte :\n`);
	for (const t of tailles) console.error(`  ${t}`);
	console.error(
		`\n  La ligne se lit à UNE taille, ${REFERENCE}, posée sur \`.ec-tags\` (#1308).\n` +
			'  → retirer la taille (elle s’hérite), ou déclarer l’écart dans `TAILLE_LIBRE`.\n' +
			'  ⚠️ `font: inherit` réinitialise la taille d’un `.badge` : écrire\n' +
			'    `font-family: inherit`.\n',
	);
}
const libresPerimees = Object.keys(TAILLE_LIBRE).filter((c) => !libresVues.has(c));
if (libresPerimees.length) {
	echec = true;
	console.error(`\n✗ Tailles libres qui ne servent plus : ${libresPerimees.join(', ')}\n`);
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : si le parcours n'a trouvé AUCUNE carte,
//  le contrôle n'a pas mesuré — il ne rend pas OK. C'est l'erreur qui rendrait
//  ce garde-fou silencieux le jour où l'arborescence change.
if (cartes === 0) {
	console.error(
		'\n✗ INCONNU : aucune carte de liste trouvée sous `src/`.\n\n' +
			'  Le contrôle ne peut pas mesurer — arborescence déplacée, ou classe\n' +
			'  renommée. Un relevé vide n’est pas un dépôt conforme.\n',
	);
	process.exit(2);
}

if (fautifs.length) {
	echec = true;
	console.error(`\n✗ ${fautifs.length} carte(s) de liste réécrivent leur en-tête :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  `EnteteCarte` porte le titre sur sa propre ligne (R1 — sinon il disparaît\n' +
			'  sur téléphone), le geste asymétrique et l’ordre tags / date / actions /\n' +
			'  chevron. Réécrit à la main, chacun de ces trois points se reprend.\n' +
			'  → employer `EnteteCarte`, ou inscrire le fichier dans `EXCEPTIONS` avec\n' +
			'    son motif.\n',
	);
}

if (chevrons.length) {
	echec = true;
	console.error(`\n✗ ${chevrons.length} carte(s) rendent leur propre chevron :\n`);
	for (const f of chevrons) console.error(`  ${f}`);
	console.error(
		'\n  `EnteteCarte` le rend depuis le 18/09/2026, et sa rotation se lit sur\n' +
			'  `.carte-liste.expanded` — l’état que la carte porte déjà. Le transmettre\n' +
			'  une seconde fois, c’est écrire deux fois le même fait : c’est ainsi que\n' +
			'  quatre cartes en sont venues à dire `expanded` et deux\n' +
			'  `expanded || enEdition`, pour la même classe.\n' +
			'  → retirer le chevron de la carte.\n',
	);
}

if (sansCorps.length) {
	echec = true;
	console.error(`\n✗ ${sansCorps.length} carte(s) de liste sans \`carte-corps\` :\n`);
	for (const f of sansCorps) console.error(`  ${f}`);
	console.error(
		'\n  `.carte-liste .carte-corps` (composants.css) fait ENTRER le corps déplié :\n' +
			'  fondu de 200 ms, coupé sous `prefers-reduced-motion`. Sans la classe il\n' +
			'  apparaît sec, sans un mot (#1579).\n' +
			'  → ajouter `carte-corps` à la classe du corps (`class="carte-corps …"`),\n' +
			'    ou inscrire le fichier dans `EXCEPTIONS` avec son motif.\n',
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
	`✓ En-tête de carte : ${cartes} carte(s) de liste, toutes rendues par ` +
		`EnteteCarte — ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s) ; ` +
		`${lignesMeta} ligne(s) de méta à ${REFERENCE}.`,
);
