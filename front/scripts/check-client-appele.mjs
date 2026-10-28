#!/usr/bin/env node
/*
 *  **Une méthode du client d'API sans appelant DOIT se déclarer.**
 *
 *  Le pendant de `check-client-api.mjs`, dans l'autre sens : celui-là refuse
 *  qu'un écran écrive une route ; celui-ci refuse qu'une méthode s'ajoute au
 *  client sans que personne ne l'emploie — et sans le dire.
 *
 *  ## Pourquoi il n'INTERDIT pas, il exige une DÉCLARATION (#801, 06/09/2026)
 *
 *  Le ticket refusait à juste titre un contrôle qui crierait sur 48 cas et une
 *  liste de tolérances qui deviendrait un dépotoir : *« une tolérance qui ne
 *  sert plus finit par en couvrir une qui compte »*. Le tri a ramené le compte à
 *  neuf, et surtout il a montré que **les neuf ne sont pas du code mort** :
 *
 *  | Motif | Ce que c'est |
 *  |---|---|
 *  | `@sans-appelant` | une capacité **inatteignable** — le chemin serveur existe, l'écran manque. Un ticket la suit. |
 *  | `@sans-appelant-direct` | l'appelant existe mais **ne passe pas par un écran** (`auth.refresh` par `tryRefresh`, les tâches par une table de ce module) |
 *  | `@sans-appelant-declare` | le geste a été **retiré sur arbitrage**, le chemin est gardé exprès |
 *
 *  Interdire aurait forcé à supprimer des capacités réelles ; tolérer en silence
 *  aurait laissé revenir les 48. Exiger la déclaration est le troisième terme —
 *  c'est **R4 du cadre d'interface** (`ux-patterns` §0 : *toute divergence se
 *  déclare avec son motif*) appliqué au client d'API.
 *
 *  🔴 **Et `@sans-appelant` exige un numéro de ticket.** Une capacité
 *  inatteignable sans ticket est un oubli qui ressemble à une décision — c'est
 *  la formulation du `CLAUDE.md` sur les exceptions XSS, et elle vaut ici.
 *
 *  ## Ce que « appelée » veut dire
 *
 *  `<alias>.<nom>` apparaît dans un `.svelte` ou un `.ts` **hors de `lib/api/`**,
 *  où `<alias>` est le nom local sous lequel CE fichier a importé l'objet
 *  (`import { acces as accesApi } from '#lib/api/index.ts'`).
 *
 *  ⚠️ **Elle exige `.<nom>` et NON `.<nom>(`**, et c'est ce que le relevé
 *  d'origine avait manqué : seize méthodes passées **par référence**
 *  (`upload: accesApi.uploadImportVigik`, sans parenthèse) étaient comptées
 *  mortes. Un tiers du relevé était faux, alors qu'il se déclarait « incapable
 *  de produire un faux positif » (`standards/04` §36).
 *
 *  ## 🔴 Il cherchait `.<nom>` SANS L'OBJET, jusqu'au 12/09/2026 (#932)
 *
 *  L'heuristique d'origine se voulait « volontairement permissive » : elle
 *  répondait à « un `<nom>` est appelé quelque part », jamais à « CE `<nom>`-ci
 *  est appelé ». Les deux questions coïncident tant que le nom est unique.
 *
 *  Elles ne l'étaient pas : **23 noms** sont portés par deux objets du client ou
 *  plus — `list` par 14, `create` par 12, `update` par 11, `get` par 9. Toute
 *  méthode morte homonyme d'une méthode vivante était donc déclarée appelée, et
 *  le faux vert **grandissait tout seul** à chaque homonyme ajouté.
 *
 *  Ce qu'il masquait, constaté : `lots.mesCommandes` et `lots.creerCommande`
 *  pointaient vers deux endpoints qui créaient le même objet que le chemin
 *  officiel **avec une règle d'autorisation différente**. Ce n'est pas ce
 *  contrôle qui les a trouvés — c'est la disparition fortuite du dernier
 *  appelant de leurs homonymes. Généralisé en `standards/04` §44.
 *
 *  ⚠️ **Ne PAS échouer sur l'ambiguïté** : avec `list`, `create` et `get` dans la
 *  liste, une alarme sur les homonymes crierait sur une centaine de cibles
 *  légitimes, et un contrôle qui crie sur du légitime finit désarmé (leçon de
 *  C16). C'est la résolution qu'il fallait écrire, pas l'alarme.
 *
 *  ⚠️ Ce que la résolution ne suit pas : une indirection (`const c = accesApi`),
 *  un import de namespace, un accès calculé (`client[nom]`). Aucun n'existe
 *  aujourd'hui, et le **plancher d'appels résolus** ci-dessous est ce qui le
 *  constate : si la forme des imports change, le compte s'effondre et le
 *  contrôle le dit — au lieu de déclarer tout le client mort.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const RACINE = 'src';
const API = join(RACINE, 'lib', 'api');
//  ⚠️ Du PLUS SPÉCIFIQUE au plus général : `@sans-appelant` est un préfixe des
//  deux autres, et un `find` naïf l'aurait reconnu partout — les deux variantes
//  auraient alors réclamé un numéro de ticket qu'elles n'ont pas à porter.
const MOTIFS = ['@sans-appelant-direct', '@sans-appelant-declare', '@sans-appelant'];

//  🔴 `client.ts` est le TRANSPORT, pas un client de domaine : `api.get/post/…`
//  n'est pas appelé « par un écran », il l'est par tous les autres modules de
//  `lib/api/`. L'y soumettre reviendrait à demander à la fondation de déclarer
//  qu'elle ne porte rien.
const HORS_PERIMETRE = new Set(['client.ts']);

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (/\.(svelte|ts)$/.test(e)) acc.push(p);
	}
	return acc;
}

/**  Les méthodes de premier niveau d'un `export const <objet> = { … }`, avec la
 *   déclaration qui les précède (le bloc de commentaires qui les surplombe). */
function methodes(source, fichier) {
	const trouvees = [];
	const re = /export const (\w+)\s*=\s*\{/g;
	let m;
	while ((m = re.exec(source))) {
		const objet = m[1];
		let i = re.lastIndex - 1,
			niveau = 0,
			fin = i;
		for (; i < source.length; i++) {
			if (source[i] === '{') niveau++;
			else if (source[i] === '}') {
				niveau--;
				if (niveau === 0) {
					fin = i;
					break;
				}
			}
		}
		const corps = source.slice(re.lastIndex, fin);
		const lignes = corps.split('\n');
		//  🔴 UNE DÉCLARATION VAUT POUR UNE SEULE MÉTHODE — celle qui la suit
		//  immédiatement — plus le commentaire posé en FIN de sa propre ligne.
		//
		//  La première version laissait un bloc couvrir « les méthodes qui
		//  s'enchaînent sans commentaire entre elles », pour déclarer les cinq
		//  routes de badges en une fois. Le contrôle a alors annoncé 47, puis 18
		//  déclarations « devenues inutiles » sur des méthodes parfaitement
		//  appelées : la portée débordait à chaque objet dont les méthodes se
		//  suivent sans blanc, c'est-à-dire presque tous.
		//
		//  ⚠️ La leçon est celle de `standards/05` §9 — **la portée fait partie du
		//  contrôle**. Une portée « jusqu'à ce que quelque chose l'arrête » dépend
		//  de la mise en forme du fichier, donc de rien. Un groupe se déclare en
		//  répétant le marqueur court en fin de ligne ; l'explication, elle, reste
		//  écrite une fois au-dessus.
		let declaration = '';
		for (const ligne of lignes) {
			const nue = ligne.trim();
			if (nue.startsWith('//') || nue.startsWith('*') || nue.startsWith('/*')) {
				declaration += ' ' + nue;
				continue;
			}
			const nom = /^\t(\w+)\s*[:(]/.exec(ligne);
			if (nom) {
				//  Le commentaire de FIN de ligne appartient à cette méthode-là.
				const enFin = ligne.slice(ligne.indexOf(nom[1]));
				trouvees.push({ fichier, objet, nom: nom[1], declaration: declaration + ' ' + enFin });
				declaration = '';
				continue;
			}
			if (nue === '') declaration = '';
		}
	}
	return trouvees;
}

/**  Les objets du client importés par CE fichier, sous leur nom LOCAL.
 *
 *   `import { acces as accesApi, ApiError } from '#lib/api/index.ts'` rend
 *   `accesApi → acces`. Un `import type` est ignoré : il n'appelle rien.
 *
 *   ⚠️ `objets` borne la lecture aux objets réellement exportés par `lib/api/` :
 *   sans lui, `ApiError` ou un type importé au passage deviendraient des alias,
 *   et n'importe quel `ApiError.<mot>` compterait comme un appel. */
export function aliasDuFichier(source, objets) {
	const map = new Map();
	const re = /import\s+(type\s+)?\{([^}]*)\}\s*from\s*'#lib\/api[^']*'/g;
	let m;
	while ((m = re.exec(source))) {
		if (m[1]) continue;
		for (const brut of m[2].split(',')) {
			const part = brut.trim().replace(/^type\s+/, '');
			if (!part) continue;
			const [nom, alias] = part.split(/\s+as\s+/).map((s) => s.trim());
			if (objets.has(nom)) map.set(alias || nom, nom);
		}
	}
	return map;
}

/**  Les `<objet>.<methode>` appelés dans cette source, alias résolus. */
export function appelsResolus(source, objets) {
	const trouves = new Set();
	for (const [alias, objet] of aliasDuFichier(source, objets)) {
		//  `(?<![\w$])` : `monAccesApi.foo` ne doit pas compter pour `accesApi`.
		const re = new RegExp(String.raw`(?<![\w$])${alias}\s*\.\s*(\w+)`, 'g');
		let m;
		while ((m = re.exec(source))) trouves.add(`${objet}.${m[1]}`);
	}
	return trouves;
}

//  ── Cas zéro ────────────────────────────────────────────────────────────────
function selftest() {
	const src = [
		'export const truc = {',
		"\tappelee: () => api.get('/a'),",
		"\torpheline: () => api.get('/b'),",
		'',
		'\t//  @sans-appelant Rien ne l’appelle, et c’est suivi. (#123)',
		"\tdeclaree: () => api.get('/c'),",
		"\tsuivante: () => api.get('/c2'),",
		"\tenFinDeLigne: () => api.get('/e'), //  @sans-appelant idem (#123)",
		'};',
	].join('\n');
	const m = methodes(src, 'test.ts');
	const par = Object.fromEntries(m.map((x) => [x.nom, x]));
	let ko = 0;
	if (m.length !== 5) {
		console.error(`  ✗ 5 méthodes attendues, ${m.length} lues`);
		ko++;
	}
	if (par.declaree && !par.declaree.declaration.includes('@sans-appelant')) {
		console.error('  ✗ la déclaration n’est pas rattachée à la méthode qu’elle précède');
		ko++;
	}
	//  🔴 LE CAS QUI A PRODUIT 47 PUIS 18 FAUX POSITIFS : la déclaration ne doit
	//  couvrir QUE la méthode suivante, jamais celle d'après.
	if (par.suivante && par.suivante.declaration.includes('@sans-appelant')) {
		console.error('  ✗ la déclaration a débordé sur la méthode d’APRÈS');
		ko++;
	}
	if (par.orpheline && par.orpheline.declaration.includes('@sans-appelant')) {
		console.error('  ✗ une déclaration a débordé sur la méthode PRÉCÉDENTE');
		ko++;
	}
	//  Le marqueur court en fin de ligne — la façon de déclarer un groupe sans
	//  répéter l'explication.
	if (par.enFinDeLigne && !par.enFinDeLigne.declaration.includes('@sans-appelant')) {
		console.error('  ✗ le marqueur en fin de ligne n’est pas lu');
		ko++;
	}
	//  Un motif sans ticket doit être refusé — sinon `@sans-appelant` devient une
	//  case à cocher.
	const sansTicket = '  //  @sans-appelant parce que voilà';
	if (/#\d+/.test(sansTicket)) {
		console.error('  ✗ le contrôle du numéro de ticket ne mesure rien');
		ko++;
	}
	//  🔴 LE CAS QUI A MOTIVÉ #932 : deux objets portant le même nom de méthode.
	//  Sur la version d'avant, `truc.commun` passait pour appelée parce que
	//  `machin.commun` l'était — vérifié échouant.
	const objets = new Set(['truc', 'machin']);
	const consommateur = [
		"import { truc as trucApi, machin, ApiError } from '#lib/api/index.ts';",
		'await machin.commun();',
		'const f = machin.parReference;',
		'await monTrucApi.commun();',
	].join('\n');
	const resolus = appelsResolus(consommateur, objets);
	const attendu = [
		['machin.commun', true],
		['machin.parReference', true],
		['truc.commun', false],
		['truc.parReference', false],
	];
	for (const [cle, doitEtre] of attendu) {
		if (resolus.has(cle) !== doitEtre) {
			console.error(
				`  ✗ résolution d’alias : ${cle} ${resolus.has(cle) ? 'compté' : 'manquant'}` +
					` alors qu’on attend ${doitEtre ? 'compté' : 'non compté'}`,
			);
			ko++;
		}
	}
	//  Un `import type` n'appelle rien, et `ApiError` n'est pas un objet du client.
	if (
		aliasDuFichier("import type { Ticket } from '#lib/api/index.ts';", new Set(['Ticket'])).size
	) {
		console.error('  ✗ un `import type` a été lu comme un appelant');
		ko++;
	}
	if (aliasDuFichier(consommateur, objets).has('ApiError')) {
		console.error('  ✗ `ApiError` a été pris pour un objet du client');
		ko++;
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : déclarations rattachées, alias d’import résolus.');
}

selftest();

const toutes = [];
for (const f of readdirSync(API).filter((f) => f.endsWith('.ts') && !HORS_PERIMETRE.has(f))) {
	toutes.push(...methodes(readFileSync(join(API, f), 'utf8'), f));
}

const objets = new Set(toutes.map((m) => m.objet));
const appelees = new Set();
for (const p of fichiers(RACINE).filter((p) => !p.split('\\').join('/').includes('src/lib/api/'))) {
	for (const cle of appelsResolus(readFileSync(p, 'utf8'), objets)) appelees.add(cle);
}

//  🔴 PLANCHER — le cas zéro de la résolution (`standards/04` §2).
//
//  Si la forme des imports change (namespace, ré-export, alias calculé), la
//  résolution ne trouve plus rien et le contrôle déclarerait TOUT le client
//  mort : deux cent quatre-vingts « méthodes sans appelant », un mur que
//  personne ne lit, et la tentation de désarmer. Sous ce plancher, il dit qu'il
//  ne mesure plus — il ne conclut pas.
//
//  ⬆️ Il SUIT le relevé, il ne le précède pas : 269 appels résolus au
//  12/09/2026, plancher à 240.
const PLANCHER_APPELS = 240;
if (appelees.size < PLANCHER_APPELS) {
	console.error(
		`\n✗ INCONNU : ${appelees.size} appel(s) résolu(s), au moins ${PLANCHER_APPELS} attendus.\n\n` +
			"  La résolution d'alias ne reconnaît plus la forme des imports du front.\n" +
			'  Le contrôle ne peut PAS conclure : tout le client paraîtrait mort.\n',
	);
	process.exit(1);
}

const nonDeclarees = [];
const sansTicket = [];
const declareesInutilement = [];

for (const m of toutes) {
	const appelee = appelees.has(`${m.objet}.${m.nom}`);
	const motif = MOTIFS.find((mo) => m.declaration.includes(mo));
	if (!appelee && !motif) nonDeclarees.push(m);
	//  ⚠️ `@sans-appelant` seul (pas les variantes) exige un ticket : les deux
	//  autres motifs décrivent un état stable, pas un travail à faire.
	if (!appelee && motif === '@sans-appelant' && !/#\d+/.test(m.declaration)) sansTicket.push(m);
	//  🔴 La déclaration ne survit pas à son objet : si la méthode a fini par
	//  trouver un appelant, le motif doit partir — sinon on garde une tolérance
	//  pour un cas qui n'existe plus.
	if (appelee && motif) declareesInutilement.push({ ...m, motif });
}

let echec = false;

if (nonDeclarees.length) {
	echec = true;
	console.error(
		`\n✗ ${nonDeclarees.length} méthode(s) du client que personne n'appelle, sans déclaration :\n`,
	);
	for (const m of nonDeclarees) console.error(`  ${m.fichier} — ${m.objet}.${m.nom}`);
	console.error(
		`\n  Trois issues, jamais une quatrième :\n` +
			`    • un écran devrait l'appeler → l'y brancher ;\n` +
			`    • c'est un doublon ou un reliquat → la SUPPRIMER (client et endpoint) ;\n` +
			`    • la capacité manque côté écran → ouvrir un ticket et poser\n` +
			`      « @sans-appelant <pourquoi> (#<ticket>) » juste au-dessus.\n`,
	);
}

if (sansTicket.length) {
	echec = true;
	console.error(`\n✗ ${sansTicket.length} déclaration(s) @sans-appelant sans numéro de ticket :\n`);
	for (const m of sansTicket) console.error(`  ${m.fichier} — ${m.objet}.${m.nom}`);
	console.error(
		`\n  Une capacité inatteignable sans ticket est un oubli qui ressemble à une\n` +
			`  décision. Ouvrir le ticket, puis le citer : « (#<numéro>) ».\n`,
	);
}

if (declareesInutilement.length) {
	echec = true;
	console.error(`\n✗ ${declareesInutilement.length} déclaration(s) devenue(s) inutile(s) :\n`);
	for (const m of declareesInutilement)
		console.error(`  ${m.fichier} — ${m.objet}.${m.nom} porte ${m.motif} et EST appelée`);
	console.error(
		`\n  Retirer le motif (et fermer le ticket) : une tolérance qui ne sert plus\n` +
			`  finit par en couvrir une qui compte.\n`,
	);
}

if (echec) process.exit(1);

const declarees = toutes.filter((m) => MOTIFS.some((mo) => m.declaration.includes(mo)));
console.log(
	`✓ ${toutes.length} méthodes du client — toutes appelées, ou déclarées avec leur motif (${declarees.length}).`,
);
