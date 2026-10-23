/**
 * Garde-fou : les options d'une publication ne s'écrivent qu'une fois.
 *
 * ## Ce qui a rendu ce contrôle nécessaire (29/08/2026)
 *
 * Épinglage, urgence, brouillon et confidentialité étaient écrits à **trois**
 * endroits — les cases de `OptionsPublication`, les badges de `CarteActualite`,
 * et le bord rouge de la carte —, et ils avaient **déjà divergé** :
 *
 *   • l'épinglage portait la punaise sur la carte et **rien** sur la case, qui
 *     disait « Épingler » tout court : deux écrans, deux vocabulaires ;
 *   • le brouillon portait le CRAYON — celui qui EST l'icône « Modifier » de
 *     toutes les barres d'actions du site. Deux notions pour un glyphe, et elles
 *     se sont retrouvées côte à côte le jour où le bouton d'options est né.
 *
 * Rien ne l'empêchait, et rien ne l'aurait signalé : chaque écran était correct
 * pris isolément. C'est la signature de la duplication d'affichage — elle ne
 * casse pas, elle fait seulement dire deux choses au même produit.
 *
 * ## Ce qui est vérifié — le fait, pas la forme
 *
 *   1. la table est lisible et porte les options attendues (cas zéro : si
 *      elle a bougé, ce contrôle ÉCHOUE au lieu de conclure au vert) ;
 *   2. les glyphes de la table sont **distincts entre eux** — deux options qui
 *      partageraient un glyphe rendraient le bouton d'options illisible ;
 *   3. aucun glyphe d'option n'est écrit en dur dans les fichiers qui rendent les
 *      options d'une publication : ils importent la table ;
 *   4. le crayon n'est jamais employé pour « Brouillon », nulle part dans le
 *      front. C'est la régression précise que ce lot a corrigée, et la seule que
 *      la règle générale ne suffirait pas à empêcher — le crayon reste légitime
 *      partout ailleurs, c'est « Modifier ».
 *
 * ⚠️ Le contrôle ne cherche PAS les glyphes dans tout le front. La punaise
 * qualifie aussi l'épinglage d'un ÉVÉNEMENT (`FormulaireEvenement`), qui est une
 * autre entité avec sa propre déclaration : crier dessus ferait un contrôle qui
 * hurle sur du légitime, et un tel contrôle finit désarmé — la leçon de C16,
 * corrigée le 06/08/2026.
 *
 * ⚠️ Et il ne lit **que ce qui est rendu** : les commentaires sont retirés avant
 * la recherche. Sa première version signalait les deux composants parce que
 * leurs commentaires CITENT les glyphes pour expliquer la divergence qu'il
 * empêche. Un garde-fou qui interdit d'écrire son propre motif se fait contourner
 * en effaçant l'explication — l'inverse exact du but.
 */
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SOURCE = join(RACINE, 'lib', 'options-publication.ts');

/**
 * Les fichiers qui rendent les options D'UNE PUBLICATION. Ils doivent importer
 * la table ; ils sont trop peu nombreux pour être devinés, et une détection
 * approximative laisserait passer le prochain.
 */
const CONSOMMATEURS = [
	join('lib', 'components', 'OptionsPublication.svelte'),
	join('lib', 'components', 'CarteActualite.svelte'),
	//  `ActualiteEnListe` a quitté la liste le 01/10/2026 (#1520) : sa Suite passe
	//  par `SuiteAffaire` et sa Mise en avant par `OptionsEvolutionTicket`, comme
	//  une affaire ; il ne rend plus d'option lui-même, il passe `OPTIONS_TICKET`
	//  au panneau — comme `CarteTicket`, que la liste ne nomme pas non plus.
	//  `CaseReservePerimetre` a quitté la liste le 23/10/2026 (#2144) : l'option
	//  `'confidentiel'` est retirée de la table, et la case ne lit plus rien
	//  d'elle — elle porte son icône du catalogue et sa propre aide.
];

//  `'confidentiel'` retirée le 23/10/2026 (#2144) : la retrouver dans la table
//  ferait échouer le contrôle ci-dessous (« clé inattendue »).
const CLES_ATTENDUES = ['epingle', 'urgente', 'brouillon'];

/** Le crayon, sans son sélecteur de variante — c'est « Modifier », et rien d'autre. */
const CRAYON = '✏';

/** Le préfixe des échappements de la table : la barre oblique inverse, puis `u{`. */
const PREFIXE_ECHAPPE = String.fromCharCode(92) + 'u{';

function echec(...lignes) {
	for (const l of lignes) console.error(l);
	process.exit(1);
}

/**
 * Le texte SANS ses commentaires — par le module commun.
 *
 * ⚠️ La copie qui vivait ici avait DEUX défauts de plus que les cinq autres :
 * elle coupait sur `//` sans exclure les URL (`https://…` tronquait la ligne),
 * et son décapage de bloc s'appliquait au balisage, où ces caractères sont du
 * texte ordinaire. Le module partagé traite les deux, et son `--selftest` le
 * montre — c'est tout l'intérêt de n'avoir qu'une écriture.
 */

// ── 1. Cas zéro : la source existe et dit ce qu'elle doit dire ───────────────
if (!existsSync(SOURCE)) {
	echec(
		'✗ `lib/options-publication.ts` est introuvable.',
		"  Ce contrôle ne peut pas s'exécuter : il rend INCONNU, pas OK (standards/04 §1).",
	);
}
const source = readFileSync(SOURCE, 'utf8');

const glyphes = new Map();
for (const cle of CLES_ATTENDUES) {
	//  On lit le littéral tel qu'il est écrit, sans exécuter le module — même
	//  parti pris que `lint:etats` : une déclaration doit rester lisible telle
	//  quelle, et un contrôle qui exécute finit par mesurer autre chose.
	//
	//  Recherche LITTÉRALE et non par expression régulière : le motif est fixe,
	//  et un regex écrit ici a déjà été aplati en un motif inerte lors d'une
	//  copie — il trouvait alors zéro option et criait sur une table saine.
	const debut = source.indexOf(`cle: '${cle}'`);
	const marque = debut === -1 ? -1 : source.indexOf("glyphe: '", debut);
	const fin = marque === -1 ? -1 : source.indexOf("'", marque + 9);
	if (debut === -1 || marque === -1 || fin === -1 || marque - debut > 400) {
		echec(
			`✗ L'option « ${cle} » n'est plus déclarée avec un glyphe dans la table.`,
			'  Soit la table a changé de forme, soit une option a disparu : dans les deux',
			"  cas ce contrôle ne mesure plus ce qu'il croit mesurer.",
		);
	}
	const brut = source.slice(marque + 9, fin);
	//  La table écrit ses glyphes en échappement, pour rester lisibles en diff :
	//  on en déduit le caractère réel.
	const glyphe = brut.startsWith(PREFIXE_ECHAPPE)
		? String.fromCodePoint(parseInt(brut.slice(PREFIXE_ECHAPPE.length, -1), 16))
		: brut;
	glyphes.set(cle, glyphe);
}
//  …et la table n'en déclare PAS d'autre : une option qui y revient sans être
//  attendue ici redeviendrait rendable sans que personne l'ait décidé (#2144).
const declarees = [...source.matchAll(/cle: '([a-z_]+)'/g)].map((m) => m[1]);
const inattendues = declarees.filter((c) => !CLES_ATTENDUES.includes(c));
if (inattendues.length > 0) {
	echec(
		`✗ Clé inattendue dans la table : ${inattendues.join(', ')}.`,
		'  Une option ajoutée se déclare dans CLES_ATTENDUES, avec sa raison.',
	);
}

// ── 2. Les glyphes sont distincts ────────────────────────────────────────────
const vus = new Map();
for (const [cle, g] of glyphes) {
	if (vus.has(g)) {
		echec(
			`✗ Deux options partagent le glyphe ${g} : « ${vus.get(g)} » et « ${cle} ».`,
			"  Le bouton d'options affiche les glyphes des options actives — deux",
			'  identiques y seraient indiscernables, et le libellé seul ne rattrape pas',
			"  ce que l'œil lit en premier.",
		);
	}
	vus.set(g, cle);
}

// ── 3. Les consommateurs importent la table ─────────────────────────────────
const sansImport = [];
const enDur = [];
for (const rel of CONSOMMATEURS) {
	const chemin = join(RACINE, rel);
	if (!existsSync(chemin)) {
		echec(
			`✗ Consommateur déclaré introuvable : ${rel}.`,
			'  Un fichier renommé rendrait ce contrôle aveugle sur son cas le plus utile.',
		);
	}
	const texte = readFileSync(chemin, 'utf8');
	if (!texte.includes("from '$lib/options-publication'")) sansImport.push(rel);
	//  Le glyphe écrit en dur ALORS QUE la table existe : c'est la recopie.
	const rendu = sansCommentaires(texte);
	for (const [cle, g] of glyphes) {
		if (rendu.includes(g)) enDur.push({ rel, cle, g });
	}
}
if (sansImport.length > 0) {
	echec(
		"✗ Fichier(s) rendant les options d'une publication sans importer la table :",
		...sansImport.map((f) => `    ${f}`),
		'  → importer depuis `$lib/options-publication` (glyphe, action, état, aide).',
	);
}
if (enDur.length > 0) {
	echec(
		'✗ Glyphe(s) d’option écrit(s) en dur alors que la table les porte :',
		...enDur.map(({ rel, cle, g }) => `    ${rel} — ${g} (« ${cle} »)`),
		"  → `optionPublication('<clé>')?.glyphe`. Un glyphe recopié diverge : celui",
		"  de l'épinglage l'avait déjà fait entre la carte et le formulaire.",
	);
}

// ── 4. Le crayon n'est plus « Brouillon » nulle part ────────────────────────
const fautifs = [];
function parcourir(dir) {
	for (const nom of readdirSync(dir)) {
		const p = join(dir, nom);
		if (statSync(p).isDirectory()) {
			parcourir(p);
			continue;
		}
		if (!/\.(svelte|ts)$/.test(nom)) continue;
		const texte = sansCommentaires(readFileSync(p, 'utf8'));
		for (const [i, ligne] of texte.split('\n').entries()) {
			if (ligne.includes(CRAYON) && ligne.toLowerCase().includes('brouillon')) {
				fautifs.push(`${relative(RACINE, p).split(sep).join('/')}:${i + 1}`);
			}
		}
	}
}
parcourir(RACINE);
if (fautifs.length > 0) {
	echec(
		'✗ Le crayon est employé pour « Brouillon » :',
		...fautifs.map((f) => `    ${f}`),
		`  → le brouillon porte ${glyphes.get('brouillon')} ; le crayon est « Modifier »,`,
		'  et les deux se retrouvent côte à côte dans la barre d’actions.',
	);
}

console.log(
	`✓ Options de publication : ${glyphes.size} option(s) déclarées une seule fois, ` +
		`glyphes distincts, ${CONSOMMATEURS.length} consommateur(s) sur la table.`,
);
