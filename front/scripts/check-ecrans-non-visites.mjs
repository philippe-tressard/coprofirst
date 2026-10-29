/**
 * Auto-test de `#lib/ecrans-non-visites.ts` — « écrans non visités » (#1630).
 *
 * Le front n'a pas de lanceur de tests : la décision « cet écran a-t-il été
 * ouvert ? » se prouve ici, par le même motif que `check-init-prestataires` —
 * fonctions PURES, lues par Node directement, donc le module éprouvé est CELUI
 * QUE LE SITE EMBARQUE. Une comparaison qui se trompe de chemin (une requête, une
 * barre finale) afficherait tout écran comme mort, ou aucun, sans que rien ne le dise.
 *
 * Il éprouve aussi la TABLE RÉELLE : `pages.ts` n'est pas lisible par Node (alias
 * `#lib`), le contrôle en relit donc les routes dans le texte — et exige qu'elles
 * soient toutes absolues, sans quoi la comparaison les prendrait pour des écrans
 * introuvables.
 *
 * Usage : node scripts/check-ecrans-non-visites.mjs --selftest
 */
import { readFileSync } from 'node:fs';
import {
	cheminNormalise,
	ecransDeclares,
	ecransNonVisites,
} from '../src/lib/ecrans-non-visites.ts';

const echecs = [];
let cas = 0;
const verifier = (nom, obtenu, attendu) => {
	cas++;
	const a = JSON.stringify(attendu);
	const o = JSON.stringify(obtenu);
	if (o !== a) echecs.push(`${nom}\n      attendu ${a}\n      obtenu  ${o}`);
};

// ── La normalisation ────────────────────────────────────────────────────────────
verifier('la requête s’enlève', cheminNormalise('/admin?onglet=telemetry'), '/admin');
verifier('l’ancre s’enlève', cheminNormalise('/faq#question-3'), '/faq');
verifier('la barre finale s’enlève', cheminNormalise('/tickets/'), '/tickets');
verifier('la racine reste la racine', cheminNormalise('/'), '/');
verifier('une chaîne vide retombe sur la racine', cheminNormalise(''), '/');

// ── La table, aplatie ───────────────────────────────────────────────────────────
const PAGES = [
	{ id: 'accueil', href: '/tableau-de-bord', navLabel: 'Accueil' },
	{
		id: 'tickets',
		href: '/tickets',
		navLabel: 'Affaires',
		onglets: [
			{ label: 'Liste', route: '/tickets' },
			{ label: '🗂️ Kanban', route: '/tickets/kanban' },
		],
	},
	{
		id: 'admin',
		href: '/admin',
		navLabel: 'Admin',
		onglets: [
			{ label: 'À traiter', route: '/admin' },
			{ label: 'Télémétrie', route: '/admin?onglet=telemetry' },
		],
	},
	{
		id: 'mon-lot',
		href: '/mon-lot',
		navLabel: 'Mes lots',
		onglets: [
			{
				label: 'Location',
				route: '/mon-lot/location',
				sous: [{ route: '/mon-lot/location/archives' }],
			},
			{ label: 'Carnet', route: '/mon-lot/carnet', reserve: 'proprioOuCS' },
		],
	},
	{ id: 'profil', href: null, navLabel: 'Profil' },
];
const declares = ecransDeclares(PAGES, new Set(['admin']));
const routes = declares.map((e) => e.route);

verifier('les routes sont dédoublonnées, la page passe avant son onglet', routes, [
	'/tableau-de-bord',
	'/tickets',
	'/tickets/kanban',
	'/admin',
	'/mon-lot',
	'/mon-lot/location',
	'/mon-lot/location/archives',
	'/mon-lot/carnet',
]);
verifier(
	'un onglet de l’administration se replie sur /admin (la requête n’est pas collectée)',
	routes.filter((r) => r === '/admin').length,
	1,
);
verifier(
	'le libellé d’un onglet est « Page › Onglet », sans pictogramme',
	declares.find((e) => e.route === '/tickets/kanban')?.libelle,
	'Affaires › Kanban',
);
verifier(
	'une page sans route (profil) n’est pas comparable : elle est absente',
	routes.includes('/profil'),
	false,
);
verifier(
	'une page réservée à un rôle est marquée',
	declares.find((e) => e.route === '/admin')?.reserve,
	true,
);
verifier(
	'un onglet `reserve` est marqué, la page qui le porte non',
	[
		declares.find((e) => e.route === '/mon-lot/carnet')?.reserve,
		declares.find((e) => e.route === '/mon-lot')?.reserve,
	],
	[true, false],
);
verifier(
	'un sous-onglet hérite de la réserve de son onglet',
	declares.find((e) => e.route === '/mon-lot/location/archives')?.reserve,
	false,
);

verifier(
	'un sous-onglet est nommé par son onglet et son dernier segment d’adresse',
	declares.find((e) => e.route === '/mon-lot/location/archives')?.libelle,
	'Mes lots › Location › archives',
);

// ── La soustraction ─────────────────────────────────────────────────────────────
const bilan = ecransNonVisites(declares, [
	{ page: '/tableau-de-bord' },
	{ page: '/tickets/' },
	{ page: '/admin?onglet=telemetry' },
	{ page: '/tickets/123' },
]);
verifier(
	'ne reste que ce que personne n’a ouvert',
	bilan.nonVisites.map((e) => e.route),
	[
		'/tickets/kanban',
		'/mon-lot',
		'/mon-lot/location',
		'/mon-lot/location/archives',
		'/mon-lot/carnet',
	],
);
verifier('une visite avec barre finale ou requête compte', [bilan.visites, bilan.total], [3, 8]);
verifier(
	'un écran de détail (/tickets/123) ne rend pas sa liste « visitée » à sa place',
	ecransNonVisites(
		[{ route: '/tickets/kanban', libelle: 'x', reserve: false }],
		[{ page: '/tickets/123' }],
	).visites,
	0,
);
verifier(
	'cas zéro : aucune page vue → tout écran déclaré est non visité',
	ecransNonVisites(declares, []).nonVisites.length,
	declares.length,
);
verifier(
	'cas zéro : tout vu → aucun écran non visité',
	ecransNonVisites(
		declares,
		declares.map((e) => ({ page: e.route })),
	).nonVisites.length,
	0,
);

// ── La table RÉELLE (`pages.ts`, `pages-roles.ts`) ──────────────────────────────
const textes = ['../src/lib/pages.ts', '../src/lib/pages-roles.ts']
	.map((f) => readFileSync(new URL(f, import.meta.url), 'utf8'))
	.join('\n');
const routesDeclarees = [...textes.matchAll(/\b(?:route|href):\s*'([^']*)'/g)].map((m) => m[1]);
verifier(
	'cas zéro : la table réelle déclare des routes (le relevé lit encore la bonne chose)',
	routesDeclarees.length > 20,
	true,
);
verifier(
	'toute route déclarée est absolue (une relative ne se comparerait à aucune page vue)',
	routesDeclarees.filter((r) => !r.startsWith('/')),
	[],
);

if (echecs.length) {
	console.error(`✗ ${echecs.length} cas en échec sur ${cas} :\n  - ${echecs.join('\n  - ')}`);
	process.exit(1);
}
console.log(`✓ Écrans non visités : ${cas} cas passent.`);
