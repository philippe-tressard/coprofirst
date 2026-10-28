#!/usr/bin/env node
/**
 *  L'éditeur de texte riche est **un seul composant**, `RichEditor` (#1539,
 *  02/10/2026).
 *
 *  🔴 Il y en avait deux : `LegalEditor` (mentions légales, confidentialité)
 *  recopiait l'amorçage de `RichEditor` — `new Editor`, le `StarterKit`, la
 *  destruction au démontage, la resynchronisation par `setContent` et neuf
 *  règles `:global(.tiptap …)` parallèles. Cinquante-trois lignes sur cent
 *  quatre, et déjà des écarts : deux interlignes, deux jeux de marges, des
 *  boutons « Annuler » / « Rétablir » sans nom accessible d'un seul côté.
 *
 *  `lint:editeur` les COMPTAIT (« 2 composant(s) accordé(s) ») sans refuser le
 *  second : il vérifie l'accord avec la version de Tiptap installée, pas
 *  l'unicité. Ce contrôle-ci refuse le deuxième éditeur — un `new Editor(`, ou
 *  tout import d'un paquet `@tiptap/…`, hors de `RichEditor.svelte`. Ce qui
 *  manque à un écran (des titres, le source HTML) s'ajoute là-bas, en prop.
 *
 *  Lancer : node scripts/check-editeur-unique.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  Instancier un éditeur, ou importer de quoi en monter un. */
const COPIE = /\bnew\s+Editor(View)?\s*\(|from\s+['"]@tiptap\/|import\(\s*['"]@tiptap\//;

process.exit(
	controler({
		extensions: ['.svelte', '.ts', '.js'],
		temoin: 'src/lib/components/RichEditor.svelte',
		exceptions: {
			'src/lib/blocDepliable.ts':
				'déclare deux NŒUDS du schéma (`Node.create`) que `RichEditor` charge — aucun éditeur',
		},
		fautes: lignesPortant(COPIE),
		cas: [
			["\timport { Editor } from '@tiptap/core';", 1],
			['\t\teditor = new Editor({ element, extensions: [StarterKit] });', 1],
			["\timport StarterKit from '@tiptap/starter-kit';", 1],
			["\timport Placeholder from '@tiptap/extension-placeholder';", 1],
			["\tconst { Editor } = await import('@tiptap/core');", 1],
			['\tconst vue = new EditorView(el, { state });', 1],
			//  La forme voulue, jamais signalée.
			["\timport RichEditor from '#lib/components/RichEditor.svelte';", 0],
			['\t<RichEditor bind:value minHeight="380px" titres sourceHtml />', 0],
			["\timport { BlocDepliable } from '#lib/blocDepliable.ts';", 0],
			//  Un nom qui CONTIENT « Editor » n'en instancie pas un.
			['\tconst editeur = new EditorState();', 0],
		],
		ok: 'Éditeur riche : monté par RichEditor seul',
		ko: 'éditeur(s) Tiptap monté(s) hors de RichEditor',
		conseil:
			'Employer `<RichEditor />` ; ce qui lui manque (une barre, un mode) s’y ajoute en prop.',
	}),
);
