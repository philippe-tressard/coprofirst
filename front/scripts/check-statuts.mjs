/**
 * Garde-fou : un écran ne réécrit pas « quel statut a cette personne ».
 *
 * ## Ce qui l'a rendu nécessaire (15/09/2026)
 *
 * Le même test était recomposé d'un écran à l'autre :
 *
 * | Notion | Écrite dans |
 * |---|---|
 * | « est locataire » | `OngletAcces`, `AccesConnexes`, `calendrier`, `mon-lot`, `residence`, `tableau-de-bord` — **six** fichiers |
 * | « est bailleur » | `OngletAcces`, `mon-lot` |
 * | « est syndic **ou** mandataire » | `PageCommunaute`, `sondages/[id]` |
 * | « est bailleur **ou** résident » | `mon-lot`, deux fois dans le même fichier |
 *
 * 🔴 `mon-lot` définissait `isLocataire` en ligne 92 **et** recomposait
 * `$currentUser?.statut === 'locataire'` aux lignes 172 et 449 : la dérivée
 * existait, dans le fichier même, et n'était pas employée. Une duplication n'a
 * pas besoin de traverser le dépôt pour diverger.
 *
 * 🔴 Pire : le commentaire de `sondages/[id]` affirmait *« cet écran ne réécrit
 * pas la règle d'accès à la Communauté »* juste au-dessus de la ligne qui la
 * réécrivait. Le seul endroit qui parlait du sujet disait que le problème
 * n'existait pas — le motif déjà rencontré sur les destinataires CS
 * (`CLAUDE.md`).
 *
 * ## Ce qui est cherché
 *
 * Une comparaison de `.statut` à un littéral, dans `src/` hors de `#lib/roles`.
 * Les prédicats (`estLocataire`, `estBailleur`, `estResident`,
 * `estCoproprietaire`, `estGestionnaire`) sont là pour ça.
 *
 * ⚠️ **Seul le statut d'une PERSONNE est visé.** `bail.statut === 'actif'`,
 * `imp.statut === 'resolu'`, `acces.statut === 'perdu'` sont d'autres axes, sur
 * d'autres objets : les viser ferait crier le contrôle sur du légitime, et un
 * contrôle qui crie sur du légitime finit désarmé — la leçon de C16 et de
 * `check-stack`. La cible est donc reconnue à son PORTEUR (`currentUser`,
 * `user`, `utilisateur`, `membre`, `porteur`, `personne`), pas au mot `statut`.
 *
 * ## Cas zéro
 *
 * Si `#lib/roles` cessait d'exporter ces prédicats, ce contrôle n'aurait plus de
 * quoi renvoyer les fautifs : il ÉCHOUE alors, au lieu de passer au vert en ne
 * mesurant rien (`standards/04` §2).
 *
 * ## 🔒 Les chaînes que les prédicats comparent (#1577, 02/10/2026)
 *
 * Un prédicat bâti sur une chaîne fautive — un accent oublié dans
 * « copropriétaire_résident » — serait **toujours faux**, et rien ne le
 * signalerait : l'écran afficherait simplement moins de choses. `STATUTS_TESTES`
 * (`#lib/roles`) nomme ces chaînes et son commentaire disait que ce contrôle la
 * lisait : ce n'était plus vrai, et la liste n'était lue par personne — un export
 * mort qui affirmait un garde-fou. Il est rétabli, dans les deux sens :
 *
 * - chaque clé de `STATUTS_TESTES` est une clé de `LIBELLES_STATUT` ;
 * - `STATUTS_TESTES` est exactement l'ensemble des chaînes que `roles.ts`
 *   compare (`statutDe(p) === '…'`) — sans cela une faute de frappe dans le
 *   PRÉDICAT, avec la liste restée juste, passerait.
 *
 * Auto-test : node scripts/check-statuts.mjs --selftest
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SOURCE = join(RACINE, 'lib', 'roles.ts');

/** Les prédicats que la source DOIT exposer — sinon il n'y a rien à conseiller. */
const PREDICATS = [
	'estLocataire',
	'estBailleur',
	'estResident',
	'estCoproprietaire',
	'estGestionnaire',
	//  Trouvée par ce contrôle lui-même, dans `espace-cs` : « aidant ou
	//  mandataire », que le relevé à la main avait manquée.
	'agitPourAutrui',
];

/**
 * Le porteur d'un statut de PERSONNE. Un `bail.statut` ou un `imp.statut`
 * décrivent tout autre chose et ne sont pas concernés.
 */
const PORTEURS = '(?:\\$?currentUser|user|utilisateur|membre|porteur|personne|profil)';
const COMPARAISON = new RegExp(`${PORTEURS}\\s*\\??\\.\\s*statut\\s*[=!]==\\s*['"\`]`, 'g');

function fichiers(dossier) {
	const out = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) out.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(entree)) out.push(chemin);
	}
	return out;
}

//  ── Les chaînes de statut : lues dans `roles.ts`, jamais recopiées ici ───────

/** Les clés de la déclaration `STATUT` (`parAttribut({ … })`) — donc de `LIBELLES_STATUT`. */
function clesDeStatut(source) {
	const debut = source.indexOf('const STATUT = parAttribut({');
	if (debut < 0) return [];
	const fin = source.indexOf('\n});', debut);
	//  Une tabulation puis un identifiant : la clé. Les attributs (`libelle:`,
	//  `badge:`) sont à deux tabulations et ne sont pas des clés.
	return [...source.slice(debut, fin).matchAll(/^\t(\p{L}[\p{L}_]*):/gmu)].map((m) => m[1]);
}

/** Le contenu déclaré de `STATUTS_TESTES`. */
function statutsTestes(source) {
	const m = /export const STATUTS_TESTES = \[([\s\S]*?)\] as const/.exec(source);
	return m ? [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]) : [];
}

/** Les chaînes que les prédicats comparent réellement. */
function statutsComparesParLesPredicats(source) {
	return [...new Set([...source.matchAll(/statutDe\(p\)\s*===\s*'([^']+)'/g)].map((m) => m[1]))];
}

/** Les écarts d'un source `roles.ts` — liste vide si tout concorde. PURE. */
function ecartsStatuts(source) {
	const code = sansCommentaires(source);
	const cles = new Set(clesDeStatut(code));
	const testes = statutsTestes(code);
	const compares = statutsComparesParLesPredicats(code);
	//  🔴 CAS ZÉRO — ne rien lire n'est pas « tout concorde ».
	if (cles.size < 7 || testes.length === 0 || compares.length === 0) {
		return [
			`relevé vide (${cles.size} clé(s) de STATUT, ${testes.length} dans STATUTS_TESTES, ` +
				`${compares.length} comparée(s)) : le contrôle ne lit plus rien`,
		];
	}
	const ecarts = [];
	for (const t of testes) {
		if (!cles.has(t)) ecarts.push(`STATUTS_TESTES nomme « ${t} », inconnu de LIBELLES_STATUT`);
	}
	for (const c of compares) {
		if (!cles.has(c)) ecarts.push(`un prédicat compare « ${c} », inconnu de LIBELLES_STATUT`);
		else if (!testes.includes(c))
			ecarts.push(`un prédicat compare « ${c} », absent de STATUTS_TESTES`);
	}
	for (const t of testes) {
		if (!compares.includes(t))
			ecarts.push(`STATUTS_TESTES nomme « ${t} » : aucun prédicat ne le compare`);
	}
	return ecarts;
}

if (process.argv.includes('--selftest')) {
	const ROLES = (cles, testes, comparaisons) =>
		`const STATUT = parAttribut({\n${cles
			.map((c) => `\t${c}: { libelle: 'x', abrege: 'x', badge: 'y' },`)
			.join('\n')}\n});\n` +
		`export const STATUTS_TESTES = [${testes.map((t) => `'${t}'`).join(', ')}] as const;\n` +
		comparaisons.map((c) => `const f = (p) => statutDe(p) === '${c}';`).join('\n');
	const SEPT = ['a', 'b', 'c', 'd', 'e', 'f', 'g'];
	let ko = 0;
	const verifier = (nom, obtenu, attendu) => {
		const ok = obtenu === attendu;
		if (!ok) ko++;
		console.log(`${ok ? 'PASS' : 'ÉCHEC'}  ${nom} → ${obtenu} (attendu ${attendu})`);
	};
	verifier('tout concorde', ecartsStatuts(ROLES(SEPT, ['a', 'b'], ['a', 'b'])).length, 0);
	//  🔴 LE CAS FAUTIF : l'accent oublié que le commentaire de roles.ts cite.
	verifier(
		'chaîne fautive dans la liste',
		ecartsStatuts(ROLES(SEPT, ['a', 'zz'], ['a', 'zz'])).length,
		2,
	);
	verifier(
		'chaîne fautive dans le PRÉDICAT, liste restée juste',
		ecartsStatuts(ROLES(SEPT, ['a', 'b'], ['a', 'zz'])).length,
		2, // « zz » inconnu de LIBELLES_STATUT, et « b » que plus aucun prédicat ne compare
	);
	verifier(
		'prédicat juste mais absent de la liste',
		ecartsStatuts(ROLES(SEPT, ['a'], ['a', 'b'])).length,
		1,
	);
	verifier(
		'liste qui nomme un statut que personne ne compare',
		ecartsStatuts(ROLES(SEPT, ['a', 'b'], ['a'])).length,
		1,
	);
	verifier('cas zéro : source vide', ecartsStatuts('').length, 1);
	verifier('cas zéro : aucune clé de STATUT', ecartsStatuts(ROLES([], ['a'], ['a'])).length, 1);
	//  Un commentaire qui cite la forme n'est pas une comparaison.
	verifier(
		'commentaire qui cite un prédicat : ignoré',
		ecartsStatuts(ROLES(SEPT, ['a'], ['a']) + "\n// statutDe(p) === 'zz'\n").length,
		0,
	);
	console.log(ko ? `== ${ko} ÉCHEC(S) ==` : '== TOUS OK ==');
	process.exit(ko ? 1 : 0);
}

//  ── Cas zéro : la source existe et porte bien ce qu'on va conseiller ────────
if (!existsSync(SOURCE)) {
	console.error(`✗ ${relative(RACINE, SOURCE)} est introuvable — contrôle INCONNU, pas OK.`);
	process.exit(1);
}
const source = readFileSync(SOURCE, 'utf8');
const absents = PREDICATS.filter((p) => !new RegExp(`export const ${p}\\b`).test(source));
if (absents.length) {
	console.error(
		`✗ #lib/roles n'exporte plus : ${absents.join(', ')}.\n` +
			"  Ce contrôle n'a plus de quoi renvoyer les écrans fautifs : il échoue " +
			'plutôt que de passer au vert sans rien mesurer.',
	);
	process.exit(1);
}

//  ── Les chaînes que les prédicats comparent ────────────────────────────────
const ecarts = ecartsStatuts(source);
if (ecarts.length) {
	console.error(
		`✗ #lib/roles — ${ecarts.length} écart(s) entre STATUTS_TESTES, les prédicats et LIBELLES_STATUT :\n  ` +
			ecarts.join('\n  ') +
			'\n\n  Un prédicat bâti sur une chaîne fautive est TOUJOURS faux, et rien ne le dit (#1577).',
	);
	process.exit(1);
}

//  ── Le relevé ───────────────────────────────────────────────────────────────
const fautifs = [];
for (const chemin of fichiers(RACINE)) {
	const rel = relative(RACINE, chemin).split(sep).join('/');
	if (rel === 'lib/roles.ts') continue; // la source a le droit, c'est elle la règle
	const code = sansCommentaires(readFileSync(chemin, 'utf8'));
	for (const ligne of code.split('\n')) {
		COMPARAISON.lastIndex = 0;
		if (COMPARAISON.test(ligne)) fautifs.push(`${rel} : ${ligne.trim().slice(0, 110)}`);
	}
}

if (fautifs.length) {
	console.error(
		`✗ ${fautifs.length} écran(s) recomposent un statut de personne :\n  ` +
			fautifs.join('\n  ') +
			`\n\n  Emploie un prédicat de #lib/roles — ${PREDICATS.join(', ')} —\n` +
			'  ou ajoutes-y la notion si elle manque. Une notion écrite deux fois\n' +
			"  diverge : « bailleur ou résident » l'était déjà deux fois dans le\n" +
			'  même fichier (#959).',
	);
	process.exit(1);
}

console.log('✓ Statuts de personne : aucun écran ne recompose la règle de #lib/roles');
