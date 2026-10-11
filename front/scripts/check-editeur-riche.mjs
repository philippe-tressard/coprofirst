/**
 * Garde-fou : l'éditeur riche suit l'API de la version de Tiptap INSTALLÉE.
 *
 * ## 🔴 Pourquoi (#724, 03/09/2026)
 *
 * La montée Tiptap 2 → 3 corrige `GHSA-cp6q-959q-f8rh`. Elle a cassé deux
 * choses, et **aucune des deux ne se voit à la compilation** :
 *
 * 1. `setContent(html, false)` — le second argument est devenu un objet.
 *    TypeScript l'a attrapé ici (trois occurrences), mais seulement parce que
 *    l'ancienne forme était typée. Elle ne l'est pas partout.
 * 2. `Underline` est désormais **inclus dans StarterKit**. L'importer en plus
 *    charge l'extension DEUX fois : Tiptap avertit dans la console et n'en garde
 *    qu'une. Un avertissement de console n'est lu par personne, et le jour où le
 *    comportement changerait, le souligné tomberait sans un mot.
 *
 * Le second n'a été vu qu'en LISTANT les extensions du paquet installé. C'est ce
 * que fait ce contrôle : il ne croit pas un guide de migration, il lit ce qui est
 * là. La prochaine montée déplacera d'autres extensions, et il le dira.
 *
 * ## Ce qu'il ne fait pas
 *
 * Il ne remplace **pas** la vérification à l'écran. Gras, listes, liens, collage
 * depuis Word et le rendu des contenus existants ne se voient qu'en regardant —
 * c'est écrit dans #724, et ce fichier ne le contredit pas. Il empêche seulement
 * les deux régressions qui, elles, sont mécanisables.
 *
 * Usage : npm run lint:editeur
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** Les extensions que le StarterKit INSTALLÉ apporte déjà. */
function extensionsDuStarterKit() {
	//  Le paquet n'expose que son point d'entrée : on passe par lui, jamais par un
	//  chemin interne — un `dist/` déplacé casserait le contrôle sans rien dire.
	const sk = require('@tiptap/starter-kit');
	const liste = sk.StarterKit.config.addExtensions.call({ options: {} });
	return new Set(liste.map((e) => e.name.toLowerCase()));
}

function fichiersSvelte(dossier) {
	const trouves = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) trouves.push(...fichiersSvelte(chemin));
		else if (entree.endsWith('.svelte')) trouves.push(chemin);
	}
	return trouves;
}

const incluses = extensionsDuStarterKit();

//  Cas zéro : un StarterKit qu'on ne saurait pas lire rendrait un ensemble vide,
//  et le contrôle laisserait tout passer en se croyant vert.
if (incluses.size < 10) {
	console.error(
		`\n✗ lint:editeur — ${incluses.size} extension(s) lue(s) dans StarterKit : ` +
			`le paquet n'a pas été lu correctement, le verdict ne vaut rien.\n`,
	);
	process.exit(1);
}

const fautes = [];
let editeursVus = 0;

for (const chemin of fichiersSvelte(RACINE)) {
	const source = readFileSync(chemin, 'utf8');
	if (!source.includes('@tiptap/')) continue;
	editeursVus += 1;
	const court = chemin.slice(RACINE.length + 1).replace(/\\/g, '/');

	//  1. La forme Tiptap 2 de `setContent`.
	for (const m of source.matchAll(/setContent\([^)]*,\s*(true|false)\s*\)/g)) {
		fautes.push(
			`  ${court} — \`${m[0]}\` : forme Tiptap 2. Depuis la 3, le second ` +
				`argument est un objet — \`{ emitUpdate: false }\`.`,
		);
	}

	//  2. Une extension importée alors que StarterKit l'apporte déjà — par
	//  `import … from`, ou par `import(…)` : Tiptap se charge à la demande depuis
	//  le 04/10/2026, et un motif qui ne lisait que la première forme serait
	//  resté vert sans plus rien regarder.
	for (const m of source.matchAll(/(?:from |import\(\s*)'@tiptap\/extension-([\w-]+)'/g)) {
		if (incluses.has(m[1].replace(/-/g, '').toLowerCase())) {
			fautes.push(
				`  ${court} — \`@tiptap/extension-${m[1]}\` est DÉJÀ dans le ` +
					`StarterKit installé : l'importer la charge deux fois.`,
			);
		}
	}
}

//  Cas zéro, second volet : aucun éditeur trouvé = le motif ne mord plus.
//  Le seuil était 2 tant que `LegalEditor` doublait `RichEditor` ; ils n'en font
//  plus qu'un depuis #1539, et `lint:editeur-unique` refuse le second.
if (editeursVus < 1) {
	console.error(
		`\n✗ lint:editeur — ${editeursVus} composant(s) employant Tiptap : le ` +
			`repérage ne trouve plus les éditeurs, il ne mesure rien.\n`,
	);
	process.exit(1);
}

if (fautes.length) {
	console.error(
		`\n✗ lint:editeur — ${fautes.length} appel(s) désaccordé(s) avec la version ` +
			`de Tiptap installée :\n\n${fautes.join('\n')}\n\n` +
			`  Ces défauts NE SE VOIENT PAS à l'exécution : Tiptap avertit dans la\n` +
			`  console, et un avertissement de console n'est lu par personne.\n`,
	);
	process.exit(1);
}

console.log(
	`✓ Éditeur riche : ${editeursVus} composant(s) accordé(s) avec le StarterKit ` +
		`installé (${incluses.size} extensions incluses).`,
);
