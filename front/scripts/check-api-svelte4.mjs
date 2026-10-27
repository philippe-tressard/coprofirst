/**
 * Garde-fou : l'API Svelte 4 des composants ne compile plus, mais elle ne se voit pas.
 *
 * ## Le défaut (30/08/2026)
 *
 * `confirmation.ts` montait sa boîte de dialogue avec `new Confirmation({...})`
 * — l'API Svelte 4. Le projet est en **Svelte 5 depuis son origine**, où cette
 * forme lève à l'exécution :
 *
 *     component_api_invalid_new — Attempted to instantiate Confirmation.svelte
 *     with `new Confirmation`, which is no longer valid in Svelte 5.
 *
 * 🔴 **`confirmer()` n'a donc JAMAIS fonctionné**, et 17 gestes en dépendaient :
 * suppressions, archivages. Chacun levait au lieu de demander — et l'action
 * n'avait pas lieu.
 *
 * ## Pourquoi rien ne l'a vu
 *
 * Le fichier **compile**. `svelte-check` ne dit rien, ESLint ne dit rien, le
 * build passe : `new X()` est du JavaScript valide, et le refus vient du
 * *runtime* de Svelte. Tous les contrôles de ce dépôt sont statiques.
 *
 * ⚠️ Et en production, le message est minifié en « Cannot use 'in' operator to
 * search for 'Symbol($state)' in undefined » — illisible, sans rapport apparent
 * avec une boîte de dialogue. C'est l'utilisateur qui l'a signalé, sur un bouton
 * qui « ne faisait rien ».
 *
 * C'est `standards/04` §16 : un contrôle ne peut pas partager la faiblesse de ce
 * qu'il contrôle. Il fallait un contrôle qui lise la FORME, puisque le
 * comportement n'était visible qu'à l'exécution.
 *
 * ## Ce qui est cherché, et ce qui ne l'est pas
 *
 * Uniquement les identifiants **importés depuis un fichier `.svelte`**. Les
 * autres `new X({...})` sont légitimes et nombreux : `new Editor({...})` de
 * TipTap vit dans `RichEditor` (un seul depuis #1539), et il n'a rien à voir.
 *
 * Un contrôle qui crierait sur eux serait désarmé dans la semaine.
 *
 * Usage : node scripts/check-api-svelte4.mjs
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte') || nom.endsWith('.ts')) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(RACINE);
if (tous.length < 50) {
	console.error(`✗ Cas zéro : ${tous.length} fichier(s) analysé(s) — le parcours a changé.`);
	process.exit(1);
}

/** Les identifiants importés depuis un `.svelte` — les seuls que ce contrôle regarde. */
function composantsSvelteImportes(source) {
	const noms = new Set();
	for (const m of source.matchAll(/import\s+(\w+)\s+from\s+['"][^'"]+\.svelte['"]/g)) {
		noms.add(m[1]);
	}
	return noms;
}

const FORMES = [
	{
		//  `new Composant(` — remplacé par `mount(Composant, { target, props })`.
		motif: (nom) => new RegExp(`\\bnew\\s+${nom}\\s*\\(`),
		quoi: 'instancié avec `new` (API Svelte 4)',
		remede: "mount(Composant, { target, props }) — `import { mount } from 'svelte'`",
	},
	{
		//  `composant.$destroy()` — remplacé par `unmount(composant)`.
		motif: () => /\.\$destroy\s*\(/,
		quoi: '`$destroy()` (API Svelte 4)',
		remede: "unmount(composant) — `import { unmount } from 'svelte'`",
		global: true,
	},
	{
		//  `$app/stores` — les stores de SvelteKit, dépréciés au profit de `$app/state`
		//  (#2205, lot 1) et retirés en kit 3 : la montée casserait chaque import.
		motif: () => /from\s+['"]\$app\/stores['"]/,
		quoi: "`$app/stores` (API SvelteKit 2, retirée en kit 3)",
		remede: "`import { page, navigating, updated } from '$app/state'` — des objets, plus de `$`",
		global: true,
	},
	{
		motif: () => /\.\$set\s*\(/,
		quoi: '`$set()` (API Svelte 4)',
		remede: 'passer les props à `mount`, ou rendre le composant réactif',
		global: true,
	},
];

const fautifs = [];
let fichiersAvecComposant = 0;

for (const chemin of tous) {
	const rel = relative(RACINE, chemin).split(sep).join('/');
	const source = sansCommentaires(readFileSync(chemin, 'utf8'));
	const composants = composantsSvelteImportes(source);
	if (composants.size) fichiersAvecComposant++;

	for (const forme of FORMES) {
		if (forme.global) {
			if (forme.motif().test(source)) fautifs.push({ rel, ...forme });
			continue;
		}
		for (const nom of composants) {
			if (forme.motif(nom).test(source)) fautifs.push({ rel, ...forme, nom });
		}
	}
}

//  Le relevé légitime de ce contrôle est VIDE : il ne peut donc pas distinguer
//  « rien trouvé » de « rien lu » (`standards/04` §27). Le témoin est le nombre
//  de fichiers qui importent réellement un composant.
if (fichiersAvecComposant < 20) {
	console.error(
		`✗ Cas zéro : ${fichiersAvecComposant} fichier(s) importent un composant Svelte, ` +
			'20 attendus au minimum. Le repérage ne mord plus — ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error("✗ API Svelte 4 employée — elle COMPILE, et lève à l'exécution :\n");
	for (const f of fautifs) {
		console.error(`   ${f.rel}${f.nom ? ` — ${f.nom} ` : ' '}${f.quoi}`);
		console.error(`       → ${f.remede}`);
	}
	console.error(
		'\n  Ce projet est en Svelte 5. `new Composant()` et `$destroy()` y lèvent —\n' +
			"  et en production le message est minifié en « Cannot use 'in' operator to\n" +
			"  search for 'Symbol($state)' in undefined », qui ne désigne rien.\n" +
			'  `confirmer()` a vécu ainsi depuis sa création, et 17 gestes avec lui.\n',
	);
	process.exit(1);
}

console.log(
	`✓ API Svelte : aucune forme de Svelte 4 sur ${tous.length} fichier(s) ` +
		`(${fichiersAvecComposant} importent un composant).`,
);
