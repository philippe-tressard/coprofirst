/**
 * Les listes rendues par `{#each … (clé)}` n'ont JAMAIS deux fois la même clé.
 *
 * POURQUOI CE CONTRÔLE (16/09/2026) :
 *
 * `pages_order` est une DONNÉE — elle vit en base et s'édite depuis « Descriptif
 * pages ». Quand elle a porté deux fois le même identifiant, `ordonnerPages` a
 * rendu deux fois la même page, et le `{#each … (pg.id)}` qui l'affiche a levé
 * `each_key_duplicate` : une erreur **fatale et non rattrapable** de Svelte.
 *
 * Ce que ça donnait à l'écran : l'onglet basculait, le contenu restait celui
 * d'avant, et plus aucune mise à jour ne passait — sur toutes les pages. Seule
 * la fermeture de la fenêtre en sortait. C'est arrivé deux fois en production et
 * a été pris pour un « figeage du site », alors que le serveur répondait en
 * moins de 200 ms et que Caddy ne voyait pas une seule requête lente.
 *
 * ⚠️ Le défaut se PROPAGEAIT : `movePage` réécrit `pages_order` à partir de la
 * liste rendue, donc le premier déplacement enregistrait le doublon en base.
 *
 * Le MÊME JOUR, le même défaut a frappé une seconde fois, ailleurs : la colonne
 * « Rôles actifs » de l'écran Utilisateurs rend `{#each … (d.label)}`, et
 * `bailleur` est l'alias hérité de `copropriétaire_bailleur` — **deux rôles, un
 * seul libellé**. Un compte portant les deux figeait l'écran entier. C'est
 * pourquoi ce fichier ne garde pas « l'ordre des pages » mais la NOTION :
 * chaque fonction qui alimente une liste à clé doit garantir l'unicité.
 *
 * ⚠️ Toute nouvelle fonction de ce genre s'ajoute ici. Deux contrôles pour une
 * seule règle divergeraient au premier cas limite — c'est précisément ce qui a
 * causé le premier incident (`Nav` et `pages.ts` avaient chacun leur version).
 *
 * Ces contrôles **exécutent** les fonctions plutôt que de relire leur code :
 * c'est le comportement qui compte, et une relecture aurait laissé passer
 * n'importe quelle réécriture qui perd le dédoublonnage. Le bundle esbuild sert
 * seulement à résoudre les alias `#lib` que Node ne connaît pas.
 */
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const SOURCE_PAGES = 'src/lib/pages.ts';
const SOURCE_ROLES = 'src/lib/roles.ts';
const SOURCE_FLUX = 'src/lib/flux.ts';

async function charger(source, nom) {
	const dossier = await mkdtemp(join(tmpdir(), 'cles-listes-'));
	const sortie = join(dossier, `${nom}.mjs`);
	await build({
		entryPoints: [source],
		bundle: true,
		format: 'esm',
		outfile: sortie,
		logLevel: 'error',
	});
	const module = await import(pathToFileURL(sortie).href);
	return { module, nettoyer: () => rm(dossier, { recursive: true, force: true }) };
}

/** Les clés rendues deux fois — ce qu'un `{#each … (clé)}` ne pardonne pas. */
function doublons(cles) {
	const vus = new Set();
	return [...new Set(cles.filter((c) => (vus.has(c) ? true : (vus.add(c), false))))];
}

/** Un jeu de pages minimal : deux ordonnables, une qui ne l'est pas. */
const PAGES = [
	{ id: 'a', href: '/a' },
	{ id: 'b', href: '/b' },
	{ id: 'sans-route', href: null },
];

const CAS = [
	{ nom: 'ordre sain', ordre: ['b', 'a'], attendu: 'b,a,sans-route' },
	{ nom: 'identifiant répété', ordre: ['b', 'b', 'a'], attendu: 'b,a,sans-route' },
	{ nom: 'répété trois fois', ordre: ['a', 'a', 'a'], attendu: 'a,b,sans-route' },
	{ nom: 'identifiant inconnu', ordre: ['b', 'fantome', 'a'], attendu: 'b,a,sans-route' },
	{ nom: 'page sans route citée', ordre: ['sans-route', 'a'], attendu: 'a,b,sans-route' },
	{ nom: 'ordre vide', ordre: [], attendu: 'a,b,sans-route' },
];

//  🔴 Le cas qui a fait rechuter deux fois : le doublon n'est PAS dans l'ordre
//  enregistré, il est dans les pages elles-mêmes. Elles sont reconstruites à
//  partir du JSON stocké en base, dont `{...saved}` rapportait l'`id` — deux
//  configurations homonymes suffisaient. Une fonction qui ne garantit que le
//  traitement de son entrée ne garantit rien : c'est sa SORTIE qui est rendue.
const PAGES_HOMONYMES = [
	{ id: 'a', href: '/a' },
	{ id: 'a', href: '/autre' },
	{ id: 'b', href: '/b' },
];

const echecs = [];

const { module, nettoyer } = await charger(SOURCE_PAGES, 'pages');
try {
	const { ordonnerPages, identifiantsRepetes } = module;
	if (typeof ordonnerPages !== 'function' || typeof identifiantsRepetes !== 'function') {
		console.error(`✗ ${SOURCE_PAGES} n'exporte plus ordonnerPages / identifiantsRepetes.`);
		process.exit(1);
	}

	for (const cas of CAS) {
		const ids = ordonnerPages(PAGES, cas.ordre).map((p) => p.id);
		const repetees = doublons(ids);
		if (repetees.length) {
			echecs.push(
				`pages : « ${cas.nom} » rend ${repetees.length} page(s) en double (${repetees.join(', ')}) ` +
					`— un {#each … (pg.id)} lèverait each_key_duplicate et figerait l'écran`,
			);
		} else if (ids.join(',') !== cas.attendu) {
			echecs.push(`pages : « ${cas.nom} » rend « ${ids.join(',')} », attendu « ${cas.attendu} »`);
		}
	}

	for (const ordre of [[], ['a'], ['a', 'b'], ['b', 'a']]) {
		const repetees = doublons(ordonnerPages(PAGES_HOMONYMES, ordre).map((p) => p.id));
		if (repetees.length) {
			echecs.push(
				`pages : deux pages HOMONYMES en entrée (ordre ${JSON.stringify(ordre)}) ressortent ` +
					`toutes les deux (${repetees.join(', ')}) — la sortie n'est pas garantie`,
			);
		}
	}

	//  Le cas zéro : sans lui, les assertions ci-dessus pourraient toutes porter
	//  sur des listes déjà saines et ne rien refuser (standards/04 §2).
	const repetes = identifiantsRepetes(['b', 'b', 'a', 'a', 'c']);
	if (repetes.sort().join(',') !== 'a,b') {
		echecs.push(
			`identifiantsRepetes(['b','b','a','a','c']) rend « ${repetes.join(', ')} », attendu « a, b » — ` +
				"le signalement d'une donnée incohérente ne fonctionne plus",
		);
	}
	if (identifiantsRepetes(['a', 'b']).length !== 0) {
		echecs.push('identifiantsRepetes signale une répétition sur un ordre sain');
	}
} finally {
	await nettoyer();
}

// ── Les badges de rôles : deux rôles peuvent rendre UN SEUL libellé ──────────
const CAS_ROLES = [
	{ nom: 'rôles distincts', roles: ['admin', 'résident'] },
	//  Le cas RÉEL qui a figé l'écran Utilisateurs : alias hérité + rôle courant.
	{ nom: 'alias hérité et rôle courant', roles: ['bailleur', 'copropriétaire_bailleur'] },
	{ nom: 'même rôle deux fois', roles: ['résident', 'résident'] },
	{ nom: 'rôle inconnu répété', roles: ['zzz_inconnu', 'zzz_inconnu'] },
	{ nom: 'liste vide', roles: [] },
];

const roles = await charger(SOURCE_ROLES, 'roles');
try {
	const { badgesDeRoles, libelleRole } = roles.module;
	if (typeof badgesDeRoles !== 'function') {
		console.error(`✗ ${SOURCE_ROLES} n'exporte plus badgesDeRoles.`);
		process.exit(1);
	}

	//  Le cas zéro : si plus aucun couple de rôles ne partageait un libellé, les
	//  assertions ci-dessous porteraient sur des listes déjà distinctes et ne
	//  refuseraient plus rien (standards/04 §2).
	if (libelleRole('bailleur') !== libelleRole('copropriétaire_bailleur')) {
		echecs.push(
			'rôles : « bailleur » et « copropriétaire_bailleur » ne rendent plus le même libellé — ' +
				'ce contrôle exerçait ce couple précis ; en trouver un autre, ou le retirer en le disant',
		);
	}

	for (const cas of CAS_ROLES) {
		const repetes = doublons(badgesDeRoles(cas.roles).map((b) => b.label));
		if (repetes.length) {
			echecs.push(
				`rôles : « ${cas.nom} » rend ${repetes.length} badge(s) au même libellé (${repetes.join(', ')}) ` +
					"— un {#each … (d.label)} lèverait each_key_duplicate et figerait l'écran Utilisateurs",
			);
		}
	}
} finally {
	await roles.nettoyer();
}

// ── Le fil : plusieurs tables, donc des `id` qui se répètent ────────────────
//  `publication` #12 et `ticket_mis_a_jour` #12 coexistent, et
//  `sondage_ouvert` / `sondage_clos` d'un même sondage portent le même id : une
//  clé `(item.id)` s'y répète forcément.
const CAS_FLUX = [
	{
		nom: 'types différents, même id',
		items: [
			{ type: 'publication', id: 12 },
			{ type: 'ticket_mis_a_jour', id: 12 },
		],
	},
	{
		nom: 'même sondage, ouvert puis clos',
		items: [
			{ type: 'sondage_ouvert', id: 4 },
			{ type: 'sondage_clos', id: 4 },
		],
	},
	{
		nom: 'même type, ids distincts',
		items: [
			{ type: 'annonce', id: 1 },
			{ type: 'annonce', id: 2 },
		],
	},
];

const flux = await charger(SOURCE_FLUX, 'flux');
try {
	const { cleFluxItem } = flux.module;
	if (typeof cleFluxItem !== 'function') {
		console.error(`✗ ${SOURCE_FLUX} n'exporte plus cleFluxItem.`);
		process.exit(1);
	}
	for (const cas of CAS_FLUX) {
		const repetees = doublons(cas.items.map(cleFluxItem));
		if (repetees.length) {
			echecs.push(
				`fil : « ${cas.nom} » rend ${repetees.length} clé(s) répétée(s) (${repetees.join(', ')}) ` +
					"— un {#each … } du fil lèverait each_key_duplicate et figerait l'écran",
			);
		}
	}
} finally {
	await flux.nettoyer();
}

// ── La porte : aucun écran ne doit reprendre `(item.id)` sur une liste du fil ─
const FICHIERS_DU_FIL = [
	'src/routes/(app)/tableau-de-bord/+page.svelte',
	'src/lib/components/ArchivesDuFil.svelte',
	//  Le widget kanban de l'accueil, extrait de la page le 18/09/2026 : ses
	//  listes sont les mêmes, elles ont seulement changé de fichier.
	'src/lib/components/KanbanTableauBord.svelte',
	//  Les urgences de l'accueil, extraites le 30/09/2026 (#779).
	'src/lib/components/UrgencesAccueil.svelte',
	//  La frise du fil, de l'Épinglé et des Archives (#779, 01/10/2026).
	'src/lib/components/FriseDuFil.svelte',
];

/**
 * Les listes de ces fichiers qui ne portent PAS des éléments du fil.
 *
 * ⚠️ Une exception non écrite n'est pas une exception, c'est un oubli qui
 * ressemble à une décision : chacune porte donc sa raison, et le contrôle
 * échoue si l'une d'elles cesse de servir.
 */
const PAS_DU_FIL = {
	//  ⚠️ Ces trois listes ont DÉMÉNAGÉ le 18/09/2026 : le widget kanban vit dans
	//  `KanbanTableauBord.svelte` (#779). Le contrôle l'a dit tout seul — les
	//  exceptions « ne correspondent plus à rien » dans le fichier du fil —, ce
	//  qui est exactement le service qu'on attend d'une exception qui expire.
	dashKanbanCols: 'colonnes constantes (DASH_KANBAN_COLS) — ids fixes et distincts',
	'col.items': 'événements du calendrier — une seule table, donc des id uniques',
	'mobileKanbanCurrent.items': 'idem, la même liste au format mobile',
};
const MOTIF_EACH_PAR_ID = /\{#each\s+([^}]*?)\s+as\s+(\w+)\s*\(\s*\2\.id\s*\)\s*\}/g;

//  🔴 Les exceptions sont relevées sur l'ENSEMBLE des fichiers du fil, pas
//  fichier par fichier. Elles l'étaient sur le seul tableau de bord, par un test
//  sur son NOM — et le jour où le widget kanban a déménagé dans son composant
//  (18/09/2026, #779), les trois dérogations ont été déclarées périmées alors
//  qu'elles servaient, à dix lignes de là. Une exception appartient à la RÈGLE,
//  pas au fichier où elle se trouvait ce jour-là.
const vuesDuFil = new Set();
for (const fichier of FICHIERS_DU_FIL) {
	const src = await readFile(fichier, 'utf-8');
	for (const m of src.matchAll(MOTIF_EACH_PAR_ID)) {
		const collection = m[1].trim();
		if (collection in PAS_DU_FIL) {
			vuesDuFil.add(collection);
			continue;
		}
		echecs.push(
			`fil : ${fichier} rend « ${m[1].trim()} » par (${m[2]}.id) — le fil agrège ` +
				"plusieurs tables, donc les id s'y répètent. Passer par cleFluxItem().",
		);
	}
}
//  Le cas zéro des exceptions : une dérogation qui ne sert plus se retire.
for (const [collection, raison] of Object.entries(PAS_DU_FIL)) {
	if (!vuesDuFil.has(collection)) {
		echecs.push(
			`fil : l'exception « ${collection} » (${raison}) ne correspond plus à rien ` +
				'dans les fichiers du fil — la retirer de PAS_DU_FIL.',
		);
	}
}

// ── Les listes de SAISIE LIBRE portent une clé COMPOSITE ───────────────────
//
//  Une valeur saisie par un résident peut être écrite deux fois : deux réponses
//  libres « Oui », deux fois la même photo, un numéro de téléphone recopié. Les
//  prendre pour clé, c'est parier que personne ne se répétera — et
//  `each_key_duplicate` fige alors l'écran entier.
//
//  Retirer la clé serait sûr — ces listes sont des affichages sans état — mais
//  `check-each-key.mjs` tient un PLAFOND DÉCROISSANT du nombre de `{#each}` sans
//  clé, et le faire remonter de 1 à 7 aurait défait son travail. Les deux règles
//  se concilient par une clé UNIQUE PAR CONSTRUCTION : l'index d'abord, la
//  valeur ensuite (`${i}|${url}`). L'index garantit l'unicité, la valeur garde
//  la clé lisible dans les outils de développement.
//
//  ⚠️ La porte ci-dessous exige cette forme. Une clé réduite à la seule valeur
//  saisie ramènerait l'écran figé.
const LISTES_A_CLE_COMPOSITE = [
	{
		fichier: 'src/lib/components/ResultatsSondage.svelte',
		collection: 'opt.reponses_libres',
		raison: 'deux résidents peuvent écrire la même réponse libre',
	},
	{
		fichier: 'src/lib/components/PiecesJointes.svelte',
		collection: 'photos',
		raison: 'la même photo peut être jointe deux fois',
	},
	{
		fichier: 'src/lib/components/PiecesJointes.svelte',
		collection: 'documents',
		raison: 'le même document peut être joint deux fois',
	},
	{
		fichier: 'src/lib/components/CartePrestataire.svelte',
		collection: 'telephonesDe(p.telephone)',
		raison: 'un numéro peut être saisi deux fois dans le même champ',
	},
	{
		fichier: 'src/routes/(app)/annuaire/+page.svelte',
		collection: 'telephonesDe(m.telephone)',
		raison: 'idem, côté annuaire',
	},
];

for (const { fichier, collection, raison } of LISTES_A_CLE_COMPOSITE) {
	const src = await readFile(fichier, 'utf-8');
	const sansCle = src.includes(`{#each ${collection} as `);
	if (!sansCle) {
		//  Cas zéro : la liste a disparu ou changé de nom — la déclaration ne garde
		//  plus rien, et se tairait. On le dit.
		echecs.push(
			`saisie libre : « ${collection} » est introuvable dans ${fichier} — ` +
				'la déclaration ne garde plus rien, la mettre à jour ou la retirer.',
		);
		continue;
	}
	//  TOUTES les occurrences, pas la première : `photos` est rendue quatre fois
	//  dans le même composant, et n'en contrôler qu'une laisserait les autres
	//  libres de reprendre une clé — un contrôle partiel qui se dit complet.
	const ouverture = `{#each ${collection} as `;
	for (let i = src.indexOf(ouverture); i !== -1; i = src.indexOf(ouverture, i + 1)) {
		//  ⚠️ La fin du bloc n'est PAS le premier `}` : une clé composite en contient
		//  (`${i}`). On équilibre les accolades — la première version coupait l'en-tête
		//  au milieu de l'interpolation et refusait la forme qu'elle exigeait.
		let profondeur = 0;
		let j = i;
		for (; j < src.length; j++) {
			if (src[j] === '{') profondeur++;
			else if (src[j] === '}' && --profondeur === 0) break;
		}
		const entete = src.slice(i, j + 1);
		if (/\(`\$\{\w+\}\|\$\{[^`]+\}`\)\s*\}$/.test(entete)) continue;
		echecs.push(
			`saisie libre : ${fichier} rend « ${collection} » sans clé composite — ${raison}. ` +
				'Forme attendue : (`${index}|${valeur}`). Vu : ' +
				entete.trim(),
		);
	}
}

if (echecs.length) {
	console.error(`\n✗ ${echecs.length} clé(s) de liste non garantie(s) :\n`);
	for (const e of echecs) console.error(`  ${e}`);
	console.error(
		'\n  Une clé de {#each} doit être unique PAR CONSTRUCTION, jamais par confiance :\n' +
			'  ces listes viennent de la base ou de saisies libres, et le rendu ne doit\n' +
			'  jamais mourir de leur incohérence.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Clés de listes : ${CAS.length + CAS_ROLES.length + CAS_FLUX.length} cas exercés (ordre des pages, badges de rôles, fil), aucune clé répétée.`,
);
