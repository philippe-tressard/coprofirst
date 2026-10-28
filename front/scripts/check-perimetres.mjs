/**
 * Garde-fou : le front ne connaît AUCUN code de périmètre.
 *
 * ## Ce que ce contrôle vérifiait avant, et pourquoi il a changé de cible
 *
 * `PERIMETRE_LABELS` vivait dans `lib/utils.ts` et trois copies s'étaient
 * installées autour (#316) : `actualites`, `calendrier` (signature différente —
 * une chaîne au lieu d'un tableau, ce qui l'avait fait diverger), `prestataires`
 * et `PerimetrePicker`. Ce contrôle cherchait donc les **recopies de la table**.
 *
 * La table n'existe plus. L'arborescence vit en base et s'édite depuis
 * `/admin/patrimoine` : le front la reçoit par `GET /perimetres` et n'en écrit
 * aucun élément. L'invariant est donc plus fort qu'avant — non plus « la table
 * n'est pas recopiée », mais « aucun code de périmètre n'est écrit ».
 *
 * C'est ce que la demande exige : le produit doit servir une autre copropriété,
 * qui n'a ni AFUL, ni quatre bâtiments, ni forcément de caves. Un `'résidence'`
 * écrit dans une page casse silencieusement dès que ce nœud est renommé — le
 * badge s'affiche quand il ne devrait pas, le formulaire s'ouvre sur une pastille
 * morte, et rien ne lève d'erreur.
 *
 * ## Ce qui est cherché
 *
 *   - `'résidence'` / `"résidence"` — le code du périmètre par défaut ;
 *   - `'bat:1'`, `` `bat:${…}` `` — la convention de nommage des bâtiments, qui
 *     appartient au seed et non au front.
 *
 * `'parking'` et `'cave'` ne sont **pas** cherchés : ce sont aussi des valeurs de
 * `TypeLot` (`mon-lot/+page.svelte`), et un contrôle qui crie sur du légitime finit
 * désarmé — c'est la leçon de C16, corrigée le 06/08.
 *
 * ## Les deux homonymes, déclarés avec leur raison
 *
 * `Document.perimetre` vaut `résidence` | `bâtiment` | `lot` : ce n'est PAS le même
 * axe. Il ne dit pas *où* se passe une demande mais *qui a le droit de lire* un
 * fichier. Les fichiers qui le portent sont dans EXCEPTIONS.
 *
 * Le contrôle s'auto-contrôle : si la source n'existe plus ou n'expose plus ce
 * qu'elle doit exposer, il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
//  ⚠️ `#lib/perimetres` est un PAQUET depuis le 10/09/2026 (le fichier unique
//  avait franchi les 500 lignes). Le chemin ci-dessous pointe le module qui
//  porte réellement ce que ce contrôle mesure — l'`index.ts` ne fait que
//  réexporter, et transpiler une réexportation ne donne rien à lire.
//  🔴 LES DEUX modules du paquet, pas un fichier : `#lib/perimetres` est un
//  paquet depuis le 10/09/2026, et les quatre exports que ce contrôle exige
//  y sont répartis — `perimetreLabel` dans les libellés, les trois autres
//  dans l'arbre. N'en lire qu'un déclencherait le cas zéro à chaque fois.
const SOURCES = [
	join(RACINE, 'lib', 'perimetres', 'arbre.ts'),
	join(RACINE, 'lib', 'perimetres', 'libelles.ts'),
];
const STORE = join(RACINE, 'lib', 'stores', 'perimetres.ts');

/** Motifs interdits, avec ce qu'il faut écrire à la place. */
const MOTIFS = [
	{
		regex: /['"]résidence['"]/g,
		quoi: 'le code du périmètre par défaut, écrit en dur',
		remede: '`perimetreParDefaut()`, `perimetreDefautListe()` ou `estPerimetreParDefaut()`',
	},
	{
		regex: /['"`]bat:[^'"`]*['"`]|`bat:\$\{/g,
		quoi: 'la convention de nommage des bâtiments, qui appartient au seed',
		remede: '`perimetreDuBatiment(batimentId)`',
	},
];

/**
 * Fichiers qui emploient ces mots pour une AUTRE notion, avec la raison.
 *
 * Une tolérance sans raison se transforme en dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une devient inutile (voir plus bas).
 */
const EXCEPTIONS = {
	//  Le paquet depuis le 10/09/2026 : la convention `bat:` vit dans `arbre.ts`,
	//  qui EST la source unique — l'exception voyage avec le code, comme celles
	//  de `test_regle_acces_source_unique` deux fois cette semaine.
	'lib/perimetres/arbre.ts':
		"la source elle-même : elle porte le repli d'affichage `bat:N` pour les " +
		'contenus qui citent un nœud supprimé depuis, et documente ce qui a été retiré.',
	'lib/api/documents.ts':
		'granularité documentaire — `Document.perimetre` vaut `résidence` | `bâtiment` | ' +
		'`lot`. Autre axe : qui a le droit de LIRE un fichier, pas où se passe une demande.',
	//  🔴 `routes/(app)/residence/+page.svelte` RETIRÉ le 08/09/2026 (#852) : ses
	//  trois `'résidence'` en dur ont disparu quand `documentsApi.upload` est
	//  passé d'une liste de huit paramètres positionnels à un objet nommé — le
	//  défaut de lecture y vit désormais, une fois.
	//
	//  ⚠️ C'est ce contrôle qui l'a signalé, pas la relecture : une exception qui
	//  ne sert plus est une porte qu'on croit fermée.
};

/**
 * Retire commentaires et docstrings avant la recherche.
 *
 * Sans cela, le contrôle interdit d'EXPLIQUER la règle : les commentaires qui
 * racontent pourquoi `bat:4` a disparu contiennent `bat:4`. Un contrôle qui
 * pousse à supprimer les explications plutôt que les défauts se retourne contre
 * ce qu'il protège — c'est la même correction que celle faite côté Python, où
 * l'analyse passe par l'AST pour la même raison.
 */

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
//  Sans la source ni le store, le motif a changé et ce contrôle ne mesure plus
//  rien : il passerait au vert pour la pire des raisons.
for (const [chemin, quoi] of [
	...SOURCES.map((chemin) => [chemin, 'la source du rendu']),
	[STORE, 'le store'],
]) {
	if (!existsSync(chemin)) {
		console.error(`✗ Cas zéro : ${quoi} est introuvable (${chemin}) — contrôle inopérant.`);
		process.exit(1);
	}
}
const source = SOURCES.map((chemin) => readFileSync(chemin, 'utf8')).join('\n');
const store = readFileSync(STORE, 'utf8');
const attendus = [
	'perimetreLabel',
	'definirPerimetres',
	'estPerimetreParDefaut',
	'perimetreDuBatiment',
];
const manquants = attendus.filter((f) => !source.includes(`export function ${f}`));
if (manquants.length > 0) {
	console.error(
		`✗ Cas zéro : le paquet lib/perimetres n'exporte plus ${manquants.join(', ')}. ` +
			'Le rendu a changé de forme — mettre ce contrôle à jour, sinon il laisse ' +
			'passer toutes les écritures en dur.',
	);
	process.exit(1);
}
if (!store.includes('/perimetres') && !store.includes('perimetresApi')) {
	console.error(
		"✗ Cas zéro : le store n'appelle plus l'API des périmètres. L'arborescence ne " +
			"viendrait plus de la base, et ce contrôle n'aurait plus d'objet.",
	);
	process.exit(1);
}

const tous = fichiers(RACINE);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

//  ── Recherche ───────────────────────────────────────────────────────────────
const fautifs = [];
const exceptionsUtiles = new Set();

for (const f of tous) {
	const rel = relative(RACINE, f).split(sep).join('/');
	const contenu = sansCommentaires(readFileSync(f, 'utf8'));
	const trouves = [];
	for (const motif of MOTIFS) {
		const m = contenu.match(motif.regex);
		if (m) trouves.push({ ...motif, exemples: [...new Set(m)].slice(0, 3) });
	}
	if (trouves.length === 0) continue;
	if (rel in EXCEPTIONS) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push({ fichier: rel, trouves });
}

if (fautifs.length > 0) {
	console.error('✗ Code(s) de périmètre écrit(s) en dur dans le front :');
	for (const { fichier, trouves } of fautifs) {
		for (const t of trouves) {
			console.error(`    ${fichier} — ${t.exemples.join(', ')}`);
			console.error(`        ${t.quoi}`);
			console.error(`        → ${t.remede}`);
		}
	}
	console.error(
		"\n  L'arborescence vit en base et s'édite depuis /admin/patrimoine. Un code\n" +
			"  écrit ici cesse d'être vrai dès qu'une copropriété le renomme — sans\n" +
			"  erreur, sans trace, et seulement à l'écran.",
	);
	process.exit(1);
}

//  Une tolérance qui n'a plus lieu d'être fait échouer, comme pour les routes
//  admin : sinon la liste se remplit et ne protège plus rien.
const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s) — plus aucun code en dur dedans :');
	for (const f of inutiles) console.error(`    ${f} — retirer l'entrée de EXCEPTIONS`);
	process.exit(1);
}

console.log(
	`✓ Périmètres : aucun code en dur, ${tous.length} fichier(s) vérifié(s), ` +
		`${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s) et justifiée(s).`,
);
