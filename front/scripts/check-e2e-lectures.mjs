#!/usr/bin/env node
/**
 *  Un test e2e ne juge pas l'instant : une lecture sans attente se déclare (#1830).
 *
 *  ## Le défaut (11/10/2026, rejeu de la v2.135.0)
 *
 *  `telemetrie-legende-jours.spec.ts` échouait à chaque passage sur le poste et
 *  passait en CI : `allTextContents()` lu juste après l'hydratation, alors que
 *  depuis la v2.133.1 les onglets se chargent au geste. Une lecture comme
 *  `allTextContents`, `count()`, `textContent()`, `innerText()` ou
 *  `isVisible()` ne réessaie pas : suivie d'un `expect` sur sa valeur, elle
 *  juge l'INSTANT — vert tant que le rendu va plus vite qu'elle, rouge sous
 *  charge, ou l'inverse.
 *
 *  ## Ce qu'il exige
 *
 *  Une telle lecture vit dans un `expect.poll(…)` (qui réessaie), ou se
 *  DÉCLARE dans `DECLAREES` — par fichier, avec son nombre et sa raison :
 *  presque toujours, une assertion qui attend le même élément la précède.
 *  Le compte doit être EXACT : une lecture ajoutée sans déclaration échoue,
 *  une déclaration qui ne sert plus aussi.
 *
 *  ## La mesure aussi (#2768, 15/11/2026)
 *
 *  `courriel-a-classer.spec.ts` lisait des `getBoundingClientRect()` dans un
 *  `evaluate`, une seule fois, juste après le clic qui déplie la ligne : la mise en
 *  page n'était pas stable sous WebKit, et « champ décalé » tombait au rouge sur une
 *  PR qui ne touchait aucun écran. Un `evaluate(…)` ou `evaluateAll(…)` qui mesure
 *  une boîte vit donc, lui aussi, dans un `expect.poll(…)` (ou après `boiteStable`,
 *  `e2e/aides.ts`), ou se DÉCLARE dans `MESURES_DECLAREES`, avec la même exigence
 *  de compte exact.
 *
 *  Lancer : node scripts/check-e2e-lectures.mjs [--selftest]
 */
import { readdirSync, readFileSync } from 'node:fs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const E2E = 'e2e';
const LECTURE = /\.(allTextContents|allInnerTexts|count|textContent|innerText|isVisible)\(\)/;

/** Fichier → [nombre, raison]. Chaque raison dit ce qui a attendu avant la lecture. */
const DECLAREES = {
	'accordeon.spec.ts': [1, 'après `toBeVisible` sur la deuxième section de la même liste'],
	'affaire-sous-contrat.spec.ts': [1, 'après `toBeVisible` sur la section : son pliage est fixé'],
	'case-montree-charge-envoyee.spec.ts': [
		4,
		'le relevé des cases (`casesRendues`) : formulaire attendu (`toBeVisible`), chaque section attendue ouverte',
	],
	'deconnexion.spec.ts': [1, 'après le titre rendu : le menu dépend du profil, pas du temps'],
	'ligne-pastilles.spec.ts': [
		2,
		'après `toBeVisible` (aide `texte`) ou `toContainText` sur la ligne',
	],
	'manuel-nom-residence.spec.ts': [1, 'après `toHaveText` sur le même pied de page'],
	'pieces-jointes-fiche.spec.ts': [1, 'après `toBeVisible` sur la carte : son dépliage est fixé'],
	'pied-de-page.spec.ts': [1, 'fonction passée à `expect.poll` (`rang`)'],
	'telemetrie-legende-jours.spec.ts': [2, 'après `ouvrir`, qui attend les bâtons du graphe'],
};

/** Fichier → [nombre, raison] : les mesures de boîte hors d'un `poll(`, déclarées. */
const MESURES_DECLAREES = {
	'accueil-frise-consignes.spec.ts': [
		1,
		'après `toHaveText` sur la gouttière : la carte est rendue, rien ne se déplie',
	],
	'avertissement-urgence.spec.ts': [1, 'après `waitFor` du bandeau, replié et immobile'],
	'etoile-requis.spec.ts': [1, 'le témoin est posé et mesuré dans le même `evaluate`'],
	'gouttiere-nature.spec.ts': [3, 'après `ouvrir` ou `goto` : listes statiques, sans dépliage'],
	'onglet-actif-lisere.spec.ts': [1, 'après `toHaveText` sur l’onglet actif, sans animation'],
	'pied-de-page.spec.ts': [2, 'fonctions passées à `expect.poll` (`ecarts`)'],
};

/** Un `poll(` ouvert sur la ligne ou l'une des `PORTEE_POLL` précédentes l'entoure. */
const PORTEE_POLL = 3;
/** Pour une mesure, l'appel s'écrit souvent sur plusieurs lignes sous le `poll(`. */
const PORTEE_POLL_MESURE = 6;
/** Une mesure : un `evaluate(` dont le corps lit une boîte, sur `CORPS_MESURE` lignes. */
const EVALUE = /\.evaluate(All)?\(/;
const CORPS_MESURE = 15;

/** Les lectures sans attente d'une source — hors d'un `poll(` qui les entoure. PURE. */
export function lecturesALInstant(source) {
	const lignes = neutraliserCommentaires(source).split('\n');
	return lignes.filter(
		(ligne, i) =>
			LECTURE.test(ligne) &&
			!lignes.slice(Math.max(0, i - PORTEE_POLL), i + 1).some((l) => /poll\(/.test(l)),
	).length;
}

/** Les mesures de boîte sans attente d'une source — hors d'un `poll(`. PURE. */
export function mesuresALInstant(source) {
	const lignes = neutraliserCommentaires(source).split('\n');
	let n = 0;
	lignes.forEach((ligne, i) => {
		if (!EVALUE.test(ligne)) return;
		let fin = i + 1;
		while (fin < lignes.length && fin < i + CORPS_MESURE && !EVALUE.test(lignes[fin])) fin++;
		if (!lignes.slice(i, fin).some((l) => l.includes('getBoundingClientRect'))) return;
		const avant = lignes.slice(Math.max(0, i - PORTEE_POLL_MESURE), i + 1);
		if (!avant.some((l) => /poll\(/.test(l))) n++;
	});
	return n;
}

/** Le relevé confronté aux déclarations : la liste des fautes. PURE. */
export function fautes(releve, declarees) {
	const sortie = [];
	for (const [fichier, n] of Object.entries(releve)) {
		const attendu = declarees[fichier]?.[0] ?? 0;
		if (n > attendu)
			sortie.push(`${fichier} : ${n} lecture(s) à l'instant, ${attendu} déclarée(s)`);
	}
	for (const [fichier, [n]] of Object.entries(declarees)) {
		const vu = releve[fichier] ?? 0;
		if (vu < n) sortie.push(`${fichier} : ${n} déclarée(s), ${vu} trouvée(s) — retirer l'excédent`);
	}
	return sortie;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, obtenu) => {
		const ok = JSON.stringify(attendu) === JSON.stringify(obtenu);
		if (!ok) ko++;
		console.log(`${ok ? '✓' : '✗'} ${libelle}`);
	};
	t('une lecture nue est comptée', 1, lecturesALInstant('const n = await cartes.count();'));
	t('dans un poll, elle réessaie', 0, lecturesALInstant('await expect.poll(() => c.count())'));
	t(
		'poll ouvert deux lignes plus haut',
		0,
		lecturesALInstant('.poll(async () => {\n\tx();\n\treturn c.count();'),
	);
	t('en commentaire, ignorée', 0, lecturesALInstant('// await c.isVisible()'));
	t(
		'une assertion web-first n’est pas une lecture',
		0,
		lecturesALInstant('await expect(c).toHaveCount(2);'),
	);
	t('non déclarée → faute', 1, fautes({ 'a.spec.ts': 1 }, {}).length);
	t('déclaration périmée → faute', 1, fautes({}, { 'a.spec.ts': [1, 'x'] }).length);
	t('compte exact → rien', 0, fautes({ 'a.spec.ts': 2 }, { 'a.spec.ts': [2, 'x'] }).length);
	const mesure =
		'const m = await bloc.evaluate((el) => {\n\treturn el.getBoundingClientRect().right;\n});';
	t('une mesure nue est comptée (#2768)', 1, mesuresALInstant(mesure));
	t(
		'une mesure dans un poll réessaie',
		0,
		mesuresALInstant(`await expect\n\t.poll(() =>\n\t\t${mesure.replace('const m = await ', '')}`),
	);
	t(
		'un evaluate qui ne mesure pas n’est pas compté',
		0,
		mesuresALInstant('await b.evaluate((e) => e.id);'),
	);
	t(
		'deux evaluate : seule la mesure compte',
		1,
		mesuresALInstant(`await b.evaluate((e) => (e.id = 'x'));\n${mesure}`),
	);
	process.exit(ko ? 1 : 0);
}

const specs = readdirSync(E2E).filter((f) => f.endsWith('.spec.ts'));
//  Cas zéro : un répertoire mal lu rendrait un contrôle vert sans rien regarder.
if (specs.length < 20) {
	console.error(`✗ ${E2E}/ : ${specs.length} spec(s) lu(s) — la lecture est cassée.`);
	process.exit(1);
}
const releve = {};
const releveMesures = {};
for (const f of specs) {
	const source = readFileSync(`${E2E}/${f}`, 'utf8');
	const n = lecturesALInstant(source);
	if (n) releve[f] = n;
	const m = mesuresALInstant(source);
	if (m) releveMesures[f] = m;
}
const liste = [
	...fautes(releve, DECLAREES),
	...fautes(releveMesures, MESURES_DECLAREES).map((f) => `${f} (mesure de boîte, #2768)`),
];
if (liste.length) {
	console.error(
		'✗ Lectures e2e qui jugent l’instant (#1830) — un `expect` qui attend, ou une déclaration :',
	);
	for (const f of liste) console.error(`  - ${f}`);
	process.exit(1);
}
console.log(`✓ ${specs.length} specs : chaque lecture à l'instant est déclarée.`);
