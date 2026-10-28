#!/usr/bin/env node
/**
 * Garde-fou : la table des pages ne se recopie pas.
 *
 * Le 17/08/2026 (#401), l'identité des pages — identifiant de configuration, route,
 * libellé de menu, icône, descriptif — vivait dans DEUX tables qui ne se
 * connaissaient pas : `NAV_DEFAULTS` + `DEFAULT_HREFS` dans `Nav.svelte`, et
 * `pagesDefaults` dans l'écran `admin`. Elles avaient déjà divergé de trois façons,
 * et **aucune n'était visible** :
 *
 *   1. les deux ordres par défaut n'étaient pas le même ;
 *   2. `profil` et `notifications` étaient réordonnables sans être dans le menu — le
 *      geste était enregistré, puis écarté en silence ;
 *   3. `delegations` était dans le menu sans être dans l'écran : ni positionnable,
 *      ni renommable.
 *
 * C'est le même motif que les périmètres (#316), les canaux de notification et les
 * libellés de tâches : une table recopiée finit toujours par diverger de celle
 * qu'elle copie, et deux listes d'accord entre elles ne prouvent rien.
 *
 * ## Ce qui est cherché
 *
 * Un fichier qui **déclare** au moins trois identifiants de pages est une TABLE, pas
 * un usage. Deux choses sont donc nécessaires, et c'est la seconde qui fait le tri :
 *
 *   - au moins trois identifiants distincts ;
 *   - écrits sous une forme de DÉCLARATION — `id: 'x'`, `configId: 'x'`, `'x': {` —
 *     et non de simple mention.
 *
 * Sans cette seconde condition, le premier essai accusait `admin/+page.svelte` sur
 * `prestataires`, `espace-cs` et `admin` : les deux premiers venaient de migrations
 * de données historiques (`defaults.id === 'prestataires'`), le troisième est un
 * homonyme — `'admin'` est aussi un RÔLE. Un contrôle qui crie sur du légitime finit
 * désarmé, et l'exception qu'on lui aurait ajoutée aurait rendu aveugle précisément
 * le fichier qui portait la table.
 *
 * Les ROUTES (`/tickets`, `/annuaire`…) ne sont volontairement pas cherchées : elles
 * apparaissent légitimement dans chaque lien et chaque `goto()`. Même raison.
 *
 * ## Ce qui est cherché, deuxième volet : les VALEURS par défaut (#420)
 *
 * Refuser la recopie des identifiants ne suffisait pas. Chaque page passait encore à
 * `getPageConfig` un troisième argument écrit à la main — titre, descriptif, libellé
 * de menu, icône, onglets — c'est-à-dire la table une seconde fois, sous une autre
 * forme. Rien ne les reliait, et **dix pages sur seize avaient déjà divergé**, dont
 * `espace-cs` des deux côtés à la fois : un onglet « Annonces Hall » affiché à
 * l'écran mais absent de la table (donc invisible dans « Descriptif pages », ni
 * renommable ni descriptible), et un descriptif de page qui taisait la relance
 * syndic que la table annonçait.
 *
 * Sont donc refusés, dans tout appel à `getPageConfig` :
 *
 *   - un `titre`, `descriptif`, `navLabel` ou `icone` dont la valeur est un
 *     LITTÉRAL — `titre: def.titre` reste permis, c'est une dérivation ;
 *   - un `onglets: { … }` écrit sur place ;
 *   - un identifiant de page absent de la table : `defautsDePage()` lèverait à
 *     l'exécution, et une page en erreur ne se découvre pas en production.
 *
 * Le troisième argument s'écrit `defautsDePage('<id>')` (`#lib/pages`).
 *
 * Le contrôle s'auto-contrôle : si la source disparaît ou change de forme, il ÉCHOUE
 * au lieu de conclure au vert (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 * Ce volet-ci compte ses propres prises : zéro appel trouvé = motif de lecture
 * périmé, donc ÉCHEC, et non « aucune violation ».
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { valeursDeclarees } from './lib-lecture-source.mjs';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
/**  🔴 DEUX fichiers depuis le 12/09/2026 (#928) : `pages.ts` a franchi son
 *   plafond de modularité, et les pages réservées à un RÔLE sont parties dans
 *   `pages-roles.ts`. La table reste UNE — `PAGES` les concatène.
 *
 *   ⚠️ Le contrôle ne lisait qu'un fichier, et l'extraction l'a rendu AVEUGLE
 *   sur trois pages : il les a aussitôt déclarées « absentes de la table ». Le
 *   refus était juste, et il dit la règle — **la portée du contrôle fait partie
 *   du contrôle** : un découpage qui ne l'élargit pas le transforme en garde-fou
 *   qui garde la moitié de ce qu'on croit. */
const SOURCES = [join(RACINE, 'lib', 'pages.ts'), join(RACINE, 'lib', 'pages-roles.ts')];
const SOURCE = SOURCES[0];

/** Un fichier qui cite au moins ce nombre d'identifiants distincts est un inventaire. */
const SEUIL = 3;

/**
 * Appels à `getPageConfig` attendus dans l'arborescence. En dessous, le motif de
 * lecture ne correspond plus à ce qu'écrivent les pages : le volet « valeurs par
 * défaut » ne mesure alors plus rien, et se taire reviendrait à conclure au vert.
 */
const APPELS_MINIMUM = 10;

/** Une valeur d'identité écrite en dur — `titre: 'Annuaire'` — au lieu d'être dérivée. */
const LITTERAL = /\b(titre|descriptif|navLabel|icone)\s*:\s*['"`]/;
/** Une table d'onglets écrite sur place. */
const ONGLETS_SUR_PLACE = /\bonglets\s*:\s*\{/;

/**
 * Fichiers qui citent plusieurs identifiants pour une AUTRE notion, avec la raison.
 * Une tolérance sans raison se transforme en dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une devient inutile.
 */
//  Vide depuis le 23/09/2026 : `raccourcis.ts` ne cite plus trois pages depuis
//  que Calendrier et Actualités n'en sont plus (#1091, #1092) — ses tuiles ne
//  se confondent plus avec la table.
const EXCEPTIONS = {};

/**
 * L'identifiant est-il DÉCLARÉ (inventaire) plutôt que simplement mentionné (usage) ?
 *
 *   déclaration : `id: 'faq'`, `configId: 'mes-demandes'`, `'faq': { … }`
 *   mention     : `getPageConfig(raw, 'faq', …)`, `defaults.id === 'faq'`, `'admin'` (rôle)
 */
function declare(texte, id) {
	return (
		new RegExp(`\\b(?:id|configId):\\s*['"\`]${id}['"\`]`).test(texte) ||
		new RegExp(`['"\`]${id}['"\`]\\s*:\\s*\\{`).test(texte)
	);
}

/** Retire commentaires et docstrings : expliquer la règle ne doit pas la violer. */

/**
 * Découpe chaque appel `getPageConfig(…)` en ses arguments de premier niveau.
 *
 * Écrit à la main plutôt qu'en expression régulière : un descriptif contient des
 * parenthèses — « Espace Conseil Syndical (CS) », « (appartement, cave & parkings) » —
 * et un motif qui compterait les parenthèses sans savoir ce qu'est une chaîne se
 * tromperait de fin d'appel, donc d'arguments, donc de verdict.
 */
function appelsGetPageConfig(texte) {
	const appels = [];
	const motif = /getPageConfig\(/g;
	let m;
	while ((m = motif.exec(texte)) !== null) {
		// La DÉCLARATION de la fonction n'est pas un appel.
		if (/\bfunction\s+$/.test(texte.slice(Math.max(0, m.index - 20), m.index))) continue;
		let i = m.index + m[0].length;
		let depart = i;
		let profondeur = 1;
		let citation = null;
		const args = [];
		for (; i < texte.length && profondeur > 0; i++) {
			const c = texte[i];
			if (citation) {
				if (c === '\\') i++;
				else if (c === citation) citation = null;
			} else if (c === "'" || c === '"' || c === '`') {
				citation = c;
			} else if (c === '(' || c === '[' || c === '{') {
				profondeur++;
			} else if (c === ')' || c === ']' || c === '}') {
				profondeur--;
				if (profondeur === 0) args.push(texte.slice(depart, i));
			} else if (c === ',' && profondeur === 1) {
				args.push(texte.slice(depart, i));
				depart = i + 1;
			}
		}
		if (profondeur === 0) appels.push(args.map((a) => a.trim()));
	}
	return appels;
}

/** Valeur d'un argument littéral (`'espace-cs'`), ou `null` si c'est une expression. */
function litteral(arg) {
	const m = /^['"`]([a-z0-9-]+)['"`]$/.exec(arg ?? '');
	return m ? m[1] : null;
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

// ── Auto-contrôle (cas zéro) ──────────────────────────────────────────────────
if (!existsSync(SOURCE)) {
	console.error(`✗ Cas zéro : ${SOURCE} est introuvable — contrôle inopérant.`);
	process.exit(1);
}
const source = SOURCES.map((f) => readFileSync(f, 'utf8')).join('\n');
for (const attendu of [
	'export const PAGES',
	'export const HREFS_DEFAUT',
	'export const ID_VERS_HREF',
	'export function defautsDePage',
]) {
	if (!source.includes(attendu)) {
		console.error(
			`✗ Cas zéro : lib/pages.ts n'expose plus \`${attendu}\`. La source a changé de ` +
				'forme — mettre ce contrôle à jour, sinon il laisse repasser toutes les recopies.',
		);
		process.exit(1);
	}
}
//  ⚠️ La lecture ne suppose plus une DISPOSITION. Le motif d'avant exigeait
//  une tabulation puis tout sur une ligne : Prettier passé sur le dépôt, la
//  table devenait illisible et ce contrôle annonçait « 0 identifiant » —
//  son cas zéro a bien parlé, mais il ne mesurait plus rien (#419).
const IDS = valeursDeclarees(source, 'id', { valeur: '[a-z0-9-]+', suivi: 'href' });
if (IDS.length < 10) {
	console.error(
		`✗ Cas zéro : ${IDS.length} identifiant(s) extrait(s) de lib/pages.ts, au moins 10 attendus. ` +
			'Le motif de lecture ne correspond plus à la table — le contrôle ne mesure plus rien.',
	);
	process.exit(1);
}

const tous = fichiers(RACINE);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

// ── Recherche ─────────────────────────────────────────────────────────────────
const violations = [];
const defautsRecopies = [];
const exceptionsUtiles = new Set();
let appelsVus = 0;

for (const chemin of tous) {
	//  ⚠️ TOUS les fichiers de la source, pas seulement le premier : depuis que la
	//  table vit en deux morceaux (#928), le second était compté comme une
	//  RECOPIE — le contrôle lui reprochait de porter les identifiants qu'il est
	//  chargé de porter.
	if (SOURCES.includes(chemin)) continue;
	const rel = relative(RACINE, chemin).split(sep).join('/');
	const texte = sansCommentaires(readFileSync(chemin, 'utf8'));

	// Volet 2 : les valeurs par défaut passées à `getPageConfig`.
	for (const args of appelsGetPageConfig(texte)) {
		appelsVus++;
		const id = litteral(args[1]);
		const defauts = args[2] ?? '';
		if (id && !IDS.includes(id)) {
			defautsRecopies.push({
				rel,
				motif: `page « ${id} » absente de la table`,
				remede:
					'lui ajouter une entrée dans `lib/pages.ts` — sinon elle est ni ordonnable ni renommable',
			});
		}
		if (LITTERAL.test(defauts) || ONGLETS_SUR_PLACE.test(defauts)) {
			defautsRecopies.push({
				rel,
				motif: `valeurs par défaut écrites en dur${id ? ` pour « ${id} »` : ''}`,
				remede: `passer \`defautsDePage(${id ? `'${id}'` : "'<id>'"})\` — la table est la seule source`,
			});
		}
		const derive = /^defautsDePage\(\s*['"`]([a-z0-9-]+)['"`]\s*\)$/.exec(defauts);
		if (id && derive && derive[1] !== id) {
			defautsRecopies.push({
				rel,
				motif: `la page « ${id} » prend les défauts de « ${derive[1]} »`,
				remede: `écrire \`defautsDePage('${id}')\``,
			});
		}
	}

	// Volet 1 : la table d'identifiants elle-même.
	const cites = IDS.filter((id) => declare(texte, id));
	if (cites.length < SEUIL) continue;
	if (rel in EXCEPTIONS) {
		exceptionsUtiles.add(rel);
		continue;
	}
	violations.push({ rel, cites });
}

// Cas zéro du second volet : plus aucun appel reconnu = motif de lecture périmé.
if (appelsVus < APPELS_MINIMUM) {
	console.error(
		`✗ Cas zéro : ${appelsVus} appel(s) à getPageConfig reconnu(s), au moins ${APPELS_MINIMUM} attendus.\n` +
			"  Les pages ne l'appellent plus sous cette forme — mettre ce contrôle à jour, sinon il\n" +
			'  laisse repasser toutes les valeurs par défaut recopiées.',
	);
	process.exit(1);
}

// Une exception qui ne sert plus est une tolérance qui dort : elle laisserait
// repasser une vraie recopie dans ce fichier sans que personne ne l'ait décidé.
const inutiles = Object.keys(EXCEPTIONS).filter((rel) => !exceptionsUtiles.has(rel));

if (violations.length || inutiles.length || defautsRecopies.length) {
	console.error('\n❌ Table des pages recopiée :\n');
	for (const { rel, motif, remede } of defautsRecopies) {
		console.error(`   ${rel} — ${motif}`);
		console.error(`      → ${remede}\n`);
	}
	for (const { rel, cites } of violations) {
		console.error(`   ${rel} — ${cites.length} identifiants de pages : ${cites.join(', ')}`);
		console.error('      → importer PAGES / PAGES_MENU / ID_VERS_HREF depuis `#lib/pages`\n');
	}
	for (const rel of inutiles) {
		console.error(`   ${rel} : exception INUTILE — ce fichier ne cite plus ${SEUIL} identifiants`);
		console.error('      → la retirer de EXCEPTIONS dans ce script\n');
	}
	console.error(
		"Rappel : deux listes d'accord entre elles ne prouvent rien. Les trois divergences\n" +
			"de #401 étaient chacune cohérente de son côté, et aucune n'était juste.\n",
	);
	process.exit(1);
}

console.log(
	`✓ ${tous.length} fichiers analysés — ${IDS.length} pages définies une seule fois, ` +
		`${appelsVus} appels à getPageConfig sans valeur recopiée ` +
		`(${Object.keys(EXCEPTIONS).length} exceptions nommées).`,
);
