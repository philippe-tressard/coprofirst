/**
 * Garde-fou : **le cadre se pose là où le geste est connu**.
 *
 * ## La règle, et pourquoi elle n'était surveillée qu'à moitié
 *
 * `ux-patterns` §14 bis — dans sa forme du 06/09/2026 :
 *
 * > créer et corriger → **la même boîte dans la page**
 *
 * 🔴 Ce fichier a énoncé la règle INVERSE (« éditer → la fenêtre », 30/08/2026)
 * pendant sept jours. Le renversement ne retire rien à ce contrôle : il ne
 * vérifie pas QUEL cadre est rendu, mais que le formulaire qui connaît son geste
 * le laisse choisir à `CadreFormulaire`. C'est cette indirection qui a rendu le
 * revirement possible en une ligne, au lieu de huit.
 *
 * `lint:formulaires` en garde une moitié : *une modale portant un formulaire doit
 * se déclarer `edition`* — autrement dit, **pas de création en modale**. L'autre
 * moitié — *pas d'édition hors modale* — n'avait AUCUN contrôle.
 *
 * 🔴 C'est ce qui a laissé **Communauté → Petites annonces** passer sous les radars
 * pendant six conversions de #640, jusqu'au 02/09/2026. Son `OngletAnnonces.modifier()`
 * ouvre le formulaire DANS la carte — le dépliement sur la même fenêtre que
 * l'arbitrage remplace — et le « Reste » du ticket ne le listait même pas. Il
 * listait deux écrans qui, eux, étaient déjà conformes.
 *
 * ## L'invariant retenu, et pourquoi celui-là
 *
 * DEUX doctrines coexistent dans ce dépôt, chacune écrite noir sur blanc dans un
 * fichier qui affirme avoir raison :
 *
 * | Qui pose le cadre | Écrit dans |
 * |---|---|
 * | l'**appelant** — « le composant n'a pas à connaître le geste » | `FormulaireContrat` |
 * | le **formulaire** — « il le connaît déjà, il le lit trois lignes plus haut » | `FormulaireEvenement` |
 *
 * Elles ne se contredisent pas, et `FormulaireEvenement` a déjà tranché en énonçant
 * la règle plus générale qui les contient : **le cadre se pose là où le geste est
 * connu**. `FormulaireContrat` ne reçoit pas le geste — son appelant met le cadre,
 * et c'est juste. `FormulaireEvenement` le reçoit — il met le cadre, et c'est juste
 * aussi.
 *
 * Ce contrôle vérifie donc exactement cela, et rien de plus :
 *
 * > un formulaire qui CONNAÎT le geste (`modeEdition`, ou `export let edition`)
 * > pose son cadre par `<CadreFormulaire>` — jamais par `<FormulaireCreation>`
 * > seul, qui ne sait rendre que la boîte.
 *
 * ⚠️ Il ne dit RIEN des formulaires qui ne connaissent pas le geste : les
 * condamner reviendrait à trancher entre les deux doctrines sans que personne
 * l'ait décidé — et un contrôle qui crie sur du légitime finit désarmé (leçon de
 * C16, rappelée dans quatre fichiers de ce répertoire).
 *
 * ## Ce qu'il ne peut pas voir
 *
 * Une page qui déplierait un formulaire d'édition **à la main**, sans passer par
 * un composant `Formulaire*`. Rien dans le balisage ne distingue ce dépliement
 * d'un panneau de lecture ; c'est la même raison qui a fait écarter le motif sur
 * `<h2 style="font-size…">` de `check-formulaire-creation`.
 */
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const COMPOSANTS = join(RACINE, 'lib', 'components');
const CADRE = join(COMPOSANTS, 'CadreFormulaire.svelte');

/**
 * Écarts connus, chacun avec son ticket. Ce ne sont PAS des tolérances de
 * confort : ce sont deux conversions qui restent à faire, et qui demandent un
 * changement visible à l'écran — donc à faire constater avant de généraliser
 * (règle R5 du cadre #430).
 *
 * 🔴 Une exception sans ticket serait un dépotoir. Le dernier test de ce fichier
 * échoue si l'une d'elles cesse de servir : le jour où la conversion est faite,
 * il FAUT venir retirer la ligne — sinon le contrôle laisserait passer une
 * régression au même endroit.
 */
const EXCEPTIONS = {
	'FormulaireTicket.svelte':
		'#463 (fermé, l’écart subsiste ; suivi : #2315) — le quatrième ' +
		'état (`evolution`) reste à confronter à son rendu. ' +
		'EvolForm sert cinq écrans ; les changer tous avant de les avoir regardés ' +
		'est exactement ce que R5 interdit.',
};

if (!existsSync(CADRE)) {
	console.error(
		'✗ Cas zéro : lib/components/CadreFormulaire.svelte est introuvable. Le cadre ' +
			'n’a plus de source unique — ce contrôle ne mesure plus la règle qu’il énonce.',
	);
	process.exit(1);
}

//  Un formulaire « connaît le geste » s'il porte `modeEdition` ou expose `edition`.
//  Les deux formes sont en service ; en chercher une seule aurait laissé la moitié
//  des composants hors du contrôle.
const CONNAIT_LE_GESTE = /\bmodeEdition\b|export let edition\b/;

const fautifs = [];
const exceptionsUtiles = new Set();
let examines = 0;
let conformes = 0;

for (const nom of readdirSync(COMPOSANTS)) {
	if (!nom.startsWith('Formulaire') || !nom.endsWith('.svelte')) continue;
	if (nom === 'FormulaireCreation.svelte') continue;
	const contenu = sansCommentaires(readFileSync(join(COMPOSANTS, nom), 'utf8'));
	if (!CONNAIT_LE_GESTE.test(contenu)) continue;
	examines++;
	if (/<CadreFormulaire(?=[\s>])/.test(contenu)) {
		conformes++;
		continue;
	}
	if (nom in EXCEPTIONS) {
		exceptionsUtiles.add(nom);
		continue;
	}
	fautifs.push(nom);
}

//  🔴 CAS ZÉRO. Le relevé légitime de ce contrôle est VIDE : sans compter ce qu'il
//  a LU, il ne peut pas distinguer « rien trouvé » de « rien lu » (`standards/04`
//  §27). Un renommage des composants le rendrait muet et vert.
const PLANCHER = 5;
if (examines < PLANCHER) {
	console.error(
		`✗ Cas zéro : ${examines} formulaire(s) connaissant le geste, ${PLANCHER} attendus au ` +
			'minimum. Les composants ont-ils été renommés ? Ce contrôle ne mord plus.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error('✗ Formulaire(s) qui connaissent le geste et ne posent pas leur cadre :');
	for (const f of fautifs) console.error(`    lib/components/${f}`);
	console.error('');
	console.error('  Un formulaire qui lit `modeEdition` connaît le geste : il doit');
	console.error('  poser son cadre par <CadreFormulaire {edition} …>, et non rendre');
	console.error('  <FormulaireCreation> lui-même.');
	console.error('');
	console.error('  ⚠️ Depuis le 06/09/2026 les deux gestes emploient la MÊME boîte');
	console.error('  (`ux-patterns` §14 bis) : passer par le cadre ne change donc plus');
	console.error('  le rendu. Ce qui compte reste que le choix vive à UN endroit — le');
	console.error('  jour où le produit voudra un autre format, la question se posera');
	console.error('  là, une fois, et non dans huit formulaires.');
	console.error('');
	console.error('  Si la conversion demande un changement visible qu’il faut faire');
	console.error('  constater d’abord, ajouter le composant à EXCEPTIONS AVEC SON TICKET.');
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s) :');
	for (const f of inutiles) {
		console.error(
			`    ${f} — la conversion est faite (ou le fichier a disparu) : retirer l’entrée`,
		);
	}
	console.error('');
	console.error('  Une tolérance qui ne sert plus fait croire la règle plus poreuse');
	console.error('  qu’elle ne l’est — et laisserait passer une régression au même endroit.');
	process.exit(1);
}

console.log(
	`✓ Cadre du geste : ${conformes} formulaire(s) sur ${examines} posent leur cadre par ` +
		`CadreFormulaire, ${Object.keys(EXCEPTIONS).length} écart(s) déclaré(s) avec leur ticket.`,
);
