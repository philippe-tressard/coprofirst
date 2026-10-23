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

/** Un `poll(` ouvert sur la ligne ou l'une des `PORTEE_POLL` précédentes l'entoure. */
const PORTEE_POLL = 3;

/** Les lectures sans attente d'une source — hors d'un `poll(` qui les entoure. PURE. */
export function lecturesALInstant(source) {
	const lignes = neutraliserCommentaires(source).split('\n');
	return lignes.filter(
		(ligne, i) =>
			LECTURE.test(ligne) &&
			!lignes.slice(Math.max(0, i - PORTEE_POLL), i + 1).some((l) => /poll\(/.test(l)),
	).length;
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
	process.exit(ko ? 1 : 0);
}

const specs = readdirSync(E2E).filter((f) => f.endsWith('.spec.ts'));
//  Cas zéro : un répertoire mal lu rendrait un contrôle vert sans rien regarder.
if (specs.length < 20) {
	console.error(`✗ ${E2E}/ : ${specs.length} spec(s) lu(s) — la lecture est cassée.`);
	process.exit(1);
}
const releve = {};
for (const f of specs) {
	const n = lecturesALInstant(readFileSync(`${E2E}/${f}`, 'utf8'));
	if (n) releve[f] = n;
}
const liste = fautes(releve, DECLAREES);
if (liste.length) {
	console.error(
		'✗ Lectures e2e qui jugent l’instant (#1830) — un `expect` qui attend, ou une déclaration :',
	);
	for (const f of liste) console.error(`  - ${f}`);
	process.exit(1);
}
console.log(`✓ ${specs.length} specs : chaque lecture à l'instant est déclarée.`);
