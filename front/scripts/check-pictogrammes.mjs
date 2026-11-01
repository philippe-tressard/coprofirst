#!/usr/bin/env node
/**
 *  📍 = un LIEU physique, 🔹 = un PÉRIMÈTRE logique — jamais mélangés, et le
 *  badge 🔹 ne s'écrit qu'une fois (#1045, point 2).
 *
 *  ## Pourquoi ce contrôle
 *
 *  La règle est la quatrième des « quatre qui ne se négocient pas » de
 *  `CLAUDE.md`, et `ux-patterns` §1 la porte depuis août. L'audit du 19/09/2026
 *  l'a pourtant trouvée enfreinte, et la mesure du 24/09 aussi :
 *
 *   • « 📍 Concerne votre bâtiment » sur l'urgence de l'accueil — un bâtiment
 *     VISÉ est un périmètre, pas une adresse ;
 *   • « 📍 Dépannage » dans les types de prestataire — ni lieu ni périmètre ;
 *   • un badge `🔹 {perimetre_label}` recopié dans l'historique des annonces de
 *     hall, qui affichait donc le périmètre PAR DÉFAUT que `BadgePerimetre`
 *     tait (règle 4 : « le périmètre par défaut ne s'affiche pas »).
 *
 *  Rien ne relisait ces écrans : la règle était écrite, et aucune machine ne la
 *  tenait.
 *
 *  ## Ce qu'il mesure
 *
 *  Deux listes BLANCHES, et tout le reste est refusé :
 *
 *   • 🔹 ne se rend que dans `BadgePerimetre.svelte` — c'est lui qui sait taire
 *     le défaut et relire l'arbre (#947). Les phrases qui NOMMENT un périmètre
 *     sans en faire un badge sont déclarées dans `LOSANGE`, avec leur motif ;
 *   • 📍 ne se rend que là où il désigne un lieu, déclaré dans `LIEUX`.
 *
 *  Chaque entrée porte le NOMBRE d'occurrences qu'elle couvre : une exception
 *  par fichier couvrirait sinon toute occurrence future du même fichier. Une
 *  entrée qui ne sert plus — ou plus autant — fait échouer.
 *
 *  ⚠️ Il ne JUGE pas le sens : il ne sait pas si une adresse est une adresse.
 *  Il oblige seulement chaque emploi à être déclaré, avec sa raison, là où un
 *  relecteur la lira. Les commentaires sont neutralisés — un fichier qui
 *  explique la règle la cite forcément.
 *
 *  Lancer : node scripts/check-pictogrammes.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';

/**  Le glyphe sous ses trois écritures : littérale, entité HTML, échappement JS. */
export const LOSANGE_BLEU = /🔹|&#x1F539;|\\u\{1F539\}/gi;
export const PUNAISE = /📍|&#x1F4CD;|\\u\{1F4CD\}/gi;
/**  L'URGENCE a un glyphe, ⚡, écrit UNE fois (27/09/2026, arbitré à l'écran) :
 *   la carte disait « ⚡ Urgente » quand la case, le bouton d'options et le
 *   manuel disaient 🚨. La sirène ne s'emploie plus nulle part — ni dans le site,
 *   ni dans le manuel —, et l'éclair ne s'écrit qu'à sa source, la table des
 *   options, d'où tout le reste le LIT. */
export const SIRENE = /🚨|&#x1F6A8;|\\u\{1F6A8\}/gi;
export const ECLAIR = /⚡|&#x26A1;|\\u\{26A1\}/gi;
const SOURCE_ECLAIR = 'lib/options-publication.ts';
/**  ⚡ dans un AUTRE sens, déclaré : il ne paraît jamais sur une affaire.
 *   Vide depuis #2442 : « ⚡ Électricité » est parti avec la liste des équipements
 *   écrite dans le code — ils s'administrent, avec une icône au trait. */
const ECLAIRS_AUTRES = {};
const MANUEL = '../docs/manuel-utilisateur.html';

/**  Le seul composant qui rend le badge de périmètre. */
const SOURCE_BADGE = 'lib/components/BadgePerimetre.svelte';

/**  🔹 hors du badge : des PHRASES qui nomment un périmètre, pas des badges. */
const LOSANGE = {
	'lib/components/FicheLecture.svelte': {
		occurrences: 1,
		motif:
			'la section Périmètre de la fiche de lecture : un paragraphe à son rang ' +
			'du cadre, qui applique la même règle du défaut par `relire()`',
	},
	'lib/components/RubriqueHistorique.svelte': {
		occurrences: 1,
		motif: 'la phrase « Périmètre précisé : 🔹 … » d’une entrée d’Historique',
	},
	'lib/components/UrgencesAccueil.svelte': {
		occurrences: 1,
		motif: '« 🔹 Concerne votre bâtiment » : l’urgence VISE ce bâtiment',
	},
};

/**  📍 : un lieu physique, et rien d'autre. */
const LIEUX = {
	'lib/components/FluxCorps.svelte': {
		occurrences: 1,
		motif: 'le lieu d’un événement (`meta.lieu`), saisi comme une adresse',
	},
	'lib/components/AnnuaireConseil.svelte': {
		occurrences: 3,
		motif: 'la localisation d’un membre du conseil — bâtiment et étage de son lot',
	},
};

/**  Compte les occurrences RÉELLES — hors commentaires. PURE. */
export function compter(source, motif) {
	return (neutraliserCommentaires(source).match(motif) ?? []).length;
}

/**  Le verdict d'un relevé, PUR. `releve` : { fichier → nombre }.
 *   @returns {{ fautifs: string[], perimees: string[] }} */
export function verdict(releve, autorises) {
	const fautifs = [];
	for (const [f, n] of Object.entries(releve)) {
		const permis = autorises[f]?.occurrences ?? 0;
		if (n > permis) fautifs.push(`${f} (${n} occurrence(s), ${permis} déclarée(s))`);
	}
	const perimees = Object.entries(autorises)
		.filter(([f, d]) => (releve[f] ?? 0) < d.occurrences)
		.map(([f, d]) => `${f} (${releve[f] ?? 0} trouvée(s), ${d.occurrences} déclarée(s))`);
	return { fautifs, perimees };
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, ok) => {
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle}`);
		if (!ok) ko = 1;
	};
	t('glyphe littéral compté', compter('<p>📍 Rue</p>', PUNAISE) === 1);
	t('entité HTML comptée', compter('<p>&#x1F4CD; Rue</p>', PUNAISE) === 1);
	t('échappement JS compté', compter("const l = '\\u{1F4CD} x';", PUNAISE) === 1);
	t('losange en entité compté', compter('<span>&#x1F539; {x}</span>', LOSANGE_BLEU) === 1);
	//  🔴 Le faux positif que trois contrôles de ce dépôt ont déjà connu : le
	//  fichier qui explique la règle la cite.
	t('commentaire ignoré', compter('<!-- jamais 📍 ici -->\n<p>x</p>', PUNAISE) === 0);
	t('sirène en entité comptée', compter('<p>&#x1F6A8; Urgent</p>', SIRENE) === 1);
	t('éclair en échappement compté', compter("const g = '\\u{26A1}';", ECLAIR) === 1);
	const permis = { 'a.svelte': { occurrences: 1, motif: 'm' } };
	//  🔴 LE cas qui donne sa raison d'être au contrôle : « 📍 Dépannage ».
	t('emploi non déclaré refusé', verdict({ 'b.ts': 1 }, permis).fautifs.length === 1);
	t('emploi déclaré accepté', verdict({ 'a.svelte': 1 }, permis).fautifs.length === 0);
	t('occurrence de plus refusée', verdict({ 'a.svelte': 2 }, permis).fautifs.length === 1);
	t('exception qui ne sert plus refusée', verdict({}, permis).perimees.length === 1);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (/\.(svelte|ts)$/.test(e)) acc.push(p);
	}
	return acc;
}

const losanges = {};
const punaises = {};
const sirenes = {};
const eclairs = {};
for (const f of fichiers(RACINE)) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const source = readFileSync(f, 'utf8');
	const nl = compter(source, LOSANGE_BLEU);
	const np = compter(source, PUNAISE);
	if (nl) losanges[rel] = nl;
	if (np) punaises[rel] = np;
	const ns = compter(source, SIRENE);
	const ne = compter(source, ECLAIR);
	if (ns) sirenes[rel] = ns;
	if (ne) eclairs[rel] = ne;
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : si le badge lui-même ne porte plus 🔹,
//  la détection a perdu son ancre — renommage, autre écriture du glyphe. Un
//  relevé vide n'est pas un dépôt conforme.
if (!losanges[SOURCE_BADGE]) {
	console.error(
		`\n✗ INCONNU : aucun 🔹 trouvé dans \`${SOURCE_BADGE}\`.\n\n` +
			'  Le contrôle ne sait plus reconnaître le glyphe là où il DOIT être :\n' +
			'  composant déplacé, ou nouvelle écriture du caractère. Le mettre à jour.\n',
	);
	process.exit(2);
}
delete losanges[SOURCE_BADGE];

const l = verdict(losanges, LOSANGE);
const p = verdict(punaises, LIEUX);
let echec = false;

if (l.fautifs.length) {
	echec = true;
	console.error('\n✗ 🔹 rendu hors de `BadgePerimetre` :\n');
	for (const f of l.fautifs) console.error(`  ${f}`);
	console.error(
		'\n  Le badge de périmètre s’écrit par `<BadgePerimetre perimetre={…} />` :\n' +
			'  c’est lui qui TAIT le périmètre par défaut et relit l’arbre à son arrivée.\n' +
			'  Une phrase qui nomme un périmètre sans en faire un badge se déclare dans\n' +
			'  `LOSANGE`, avec son motif.\n',
	);
}
if (p.fautifs.length) {
	echec = true;
	console.error('\n✗ 📍 employé hors d’un lieu déclaré :\n');
	for (const f of p.fautifs) console.error(`  ${f}`);
	console.error(
		'\n  📍 désigne un LIEU physique ; un périmètre (un bâtiment visé, un parking)\n' +
			'  se dit 🔹 (CLAUDE.md, règle 4). Un vrai lieu se déclare dans `LIEUX`.\n',
	);
}
const sirenesManuel = compter(readFileSync(MANUEL, 'utf8'), SIRENE);
if (sirenesManuel) sirenes['docs/manuel-utilisateur.html'] = sirenesManuel;
if (Object.keys(sirenes).length) {
	echec = true;
	console.error('\n✗ 🚨 employé — l’urgence se dit ⚡, lu dans la table des options :\n');
	for (const [f, n] of Object.entries(sirenes)) console.error(`  ${f} (${n})`);
}
if (!eclairs[SOURCE_ECLAIR]) {
	console.error(`\n✗ INCONNU : aucun ⚡ dans \`${SOURCE_ECLAIR}\` — la source a bougé.\n`);
	process.exit(2);
}
delete eclairs[SOURCE_ECLAIR];
const e = verdict(eclairs, ECLAIRS_AUTRES);
if (e.fautifs.length) {
	echec = true;
	console.error('\n✗ ⚡ écrit hors de sa source — le lire dans `OPTIONS_PUBLICATION` :\n');
	for (const f of e.fautifs) console.error(`  ${f}`);
}
const perimees = [...l.perimees, ...p.perimees, ...e.perimees];
if (perimees.length) {
	echec = true;
	console.error('\n✗ Ces déclarations ne servent plus (ou plus autant) — les ajuster :\n');
	for (const f of perimees) console.error(`  ${f}`);
	console.error('\n  Une exception reconduite « au cas où » masquerait la suivante.\n');
}

if (echec) process.exit(1);
console.log(
	`✓ Pictogrammes : 🔹 rendu par BadgePerimetre + ${Object.keys(LOSANGE).length} phrase(s) ` +
		`déclarée(s) · 📍 dans ${Object.keys(LIEUX).length} lieu(x) déclaré(s).`,
);
