<!--
  **L'éditeur de texte riche du site — le seul** (Tiptap).

  ## 🔴 Il y en avait DEUX jusqu'au 02/10/2026 (#1539)

  `LegalEditor` (mentions légales et politique de confidentialité, un écran)
  recopiait l'amorçage de celui-ci au caractère près : `new Editor`, le
  `StarterKit`, `onDestroy(() => editor?.destroy())`, la resynchronisation par
  `setContent(…, { emitUpdate: false })`, et neuf règles `:global(.tiptap …)`
  parallèles aux six d'ici. Cinquante-trois lignes sur cent quatre.

  L'écriture retenue est CELLE-CI, la plus déployée (sept formulaires contre un
  écran), enrichie de ce que l'autre savait faire et qui lui manquait :

  | Ce que `LegalEditor` apportait | Devenu ici |
  |---|---|
  | titres H2/H3 et filet de séparation | `titres` |
  | le mode « source HTML » (`</>`) | `sourceHtml` |
  | l'en-tête `label` / `hint` | **retiré** : son unique appelant ne le passait pas |

  Les deux props DÉCLARENT la divergence : un texte long et structuré, qu'un
  administrateur corrige parfois à la main, n'a pas la barre d'une description
  de trois lignes. Ce n'est pas une seconde écriture, c'est un paramètre.

  ⚠️ Ce que l'éditeur légal a GAGNÉ en passant ici, et qui ne se voit pas :
  `BlocDepliable` (un `<details>` collé n'est plus aplati), le texte indicatif,
  et les `aria-label` d'« Annuler » / « Rétablir » qui lui manquaient. Le
  rendu du contenu suit les valeurs d'ici (marges, interligne) — même arbitrage
  que le cadre et la barre, déjà communs (`styles/champs.css`).

  🔒 `npm run lint:editeur-unique` refuse un second `new Editor(` ou un import
  de `@tiptap/core` / `@tiptap/starter-kit` hors de ce fichier.
-->
<script lang="ts">
	import { onMount, onDestroy, createEventDispatcher } from 'svelte';
	//  🔴 TIPTAP SE CHARGE À LA DEMANDE, jamais par un import statique (04/10/2026).
	//
	//  Tiptap et ProseMirror pèsent 389 Ko de JavaScript (121 Ko compressés) : plus
	//  que tout le reste d'un écran. Importés en tête de ce fichier, ils entraient
	//  dans le chargement initial de CHAQUE écran qui contient un formulaire, même
	//  replié — affaires, fiche d'une affaire, Résidence, Communauté,
	//  administration —, et l'« Ouverture du site » de la télémétrie y passait une
	//  seconde sur un téléphone. Seul le TYPE s'importe ici (effacé à la
	//  compilation) ; le code arrive par `import()` dans `onMount`, quand un
	//  éditeur s'affiche réellement. La barre est rendue d'emblée, et ses boutons
	//  ne font rien tant que l'éditeur n'est pas monté (`editor?.`).
	//
	//  🔒 `npm run lint:poids-ouverture` (après le build) refuse Tiptap dans le
	//  chargement initial d'un écran.
	import type { Editor } from '@tiptap/core';

	export let value: string = '';
	export let placeholder: string = '';
	export let minHeight: string = '120px';
	/**
	 * Id posé sur la zone éditable, pour qu'un `<label for="…">` la désigne.
	 *
	 * Trois pages le passaient déjà (`actualites`, `faq`, `sondages/[id]`) alors que le
	 * composant ne le déclarait pas : Svelte le laissait tomber en silence, et leurs
	 * `<label for="…">` ne pointaient sur rien. Cliquer le libellé ne donnait pas le
	 * focus, et les lecteurs d'écran annonçaient un champ sans nom.
	 */
	export let id: string | undefined = undefined;
	/**  `id` de l'élément qui NOMME cette zone de saisie. Nécessaire parce que la
	 *   zone éditable est un `contenteditable`, pas un contrôle labelable : un
	 *   `<label for>` posé dessus n'associe rien, et le fait en silence. Depuis que
	 *   le titre de section porte le libellé (`SectionFormulaire`), c'est lui
	 *   qu'on désigne ici. */
	export let ariaLabelledby: string | undefined = undefined;
	/**  Les titres H2 / H3 et le filet de séparation dans la barre — pour un
	 *   document long et structuré (mentions légales, confidentialité). Une
	 *   description n'en a pas l'usage. */
	export let titres = false;
	/**  Le bouton `</>` : corriger le HTML à la main. Réservé à l'administration,
	 *   qui colle parfois un texte juridique déjà mis en forme. */
	export let sourceHtml = false;

	const dispatch = createEventDispatcher<{ change: string }>();

	let editorEl: HTMLDivElement;
	let editor: Editor;
	let modeSource = false;

	/**  Vrai une fois le composant démonté : un chargement encore en cours ne
	 *   monte alors plus rien — l'élément n'existe plus. */
	let detruit = false;

	onMount(async () => {
		const [{ Editor }, { default: StarterKit }, { default: Placeholder }, blocs] =
			await Promise.all([
				import('@tiptap/core'),
				import('@tiptap/starter-kit'),
				//  🔴 `Underline` N'EST PLUS IMPORTÉ (Tiptap 3, 03/09/2026) : StarterKit 3
				//  l'inclut. Le garder aurait chargé l'extension DEUX fois — Tiptap
				//  avertit à l'exécution et n'en garde qu'une, mais un avertissement de
				//  console n'est lu par personne. Vérifié en listant les extensions du
				//  StarterKit installé, jamais supposé d'après le guide de migration.
				import('@tiptap/extension-placeholder'),
				//  🔴 Deux nœuds pour que les blocs dépliables SURVIVENT à l'éditeur
				//  (#992) : ProseMirror ne garde que ce que son schéma connaît, et le
				//  texte proposé par l'assistant traverse ce formulaire avant d'être
				//  enregistré. Sans eux, un `<details>` serait aplati sans un mot.
				//  Voir `$lib/blocDepliable` — chargé ici aussi : il importe Tiptap.
				import('$lib/blocDepliable'),
			]);
		if (detruit) return;
		editor = new Editor({
			element: editorEl,
			extensions: [
				StarterKit,
				//  Une FONCTION, et non la valeur : le texte indicatif suit la prop.
				//  Il était lu une fois, à l'ouverture — une affaire devenue
				//  actualité gardait « Décrivez le problème… » (23/09/2026).
				Placeholder.configure({ placeholder: () => placeholder }),
				blocs.BlocDepliable,
				blocs.ResumeDepliable,
			],
			// Tiptap remplace l'élément monté : les attributs doivent être posés sur la
			// zone éditable qu'il génère, sinon ils désignent un nœud disparu.
			editorProps: {
				attributes: {
					...(id ? { id } : {}),
					...(ariaLabelledby ? { 'aria-labelledby': ariaLabelledby } : {}),
				},
			},
			content: value,
			onUpdate: ({ editor }) => {
				const html = editor.getHTML();
				value = html;
				dispatch('change', html);
			},
		});
	});

	//  Une transaction vide redessine les décorations, dont le texte indicatif.
	$: if (editor && placeholder !== undefined) editor.view.dispatch(editor.state.tr);

	onDestroy(() => {
		detruit = true;
		editor?.destroy();
	});

	//  Une valeur changée du dehors (formulaire remis à zéro, chargement par
	//  l'API) — sauf en mode source, où c'est la zone de texte qui la tient.
	$: if (editor && !modeSource && value !== editor.getHTML()) {
		editor.commands.setContent(value ?? '', { emitUpdate: false });
	}

	/**  Retour à l'édition visuelle : la valeur corrigée à la main est rendue par
	 *   la synchronisation ci-dessus, dès que `modeSource` retombe. */
	function basculerSource() {
		modeSource = !modeSource;
	}
</script>

<div class="editeur-cadre">
	<!-- Toolbar -->
	<div class="editeur-barre">
		{#if !modeSource}
			{#if titres}
				<button
					type="button"
					class:active={editor?.isActive('heading', { level: 2 })}
					on:click={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
					aria-label="Titre H2"
					title="Titre H2"
				>
					H2
				</button>
				<button
					type="button"
					class:active={editor?.isActive('heading', { level: 3 })}
					on:click={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
					aria-label="Titre H3"
					title="Titre H3"
				>
					H3
				</button>
				<div class="sep"></div>
			{/if}
			<button
				type="button"
				class:active={editor?.isActive('bold')}
				on:click={() => editor?.chain().focus().toggleBold().run()}
				aria-label="Gras"
				title="Gras"
			>
				<b>B</b>
			</button>
			<button
				type="button"
				class:active={editor?.isActive('italic')}
				on:click={() => editor?.chain().focus().toggleItalic().run()}
				aria-label="Italique"
				title="Italique"
			>
				<i>I</i>
			</button>
			<button
				type="button"
				class:active={editor?.isActive('underline')}
				on:click={() => editor?.chain().focus().toggleUnderline().run()}
				aria-label="Souligné"
				title="Souligné"
			>
				<u>U</u>
			</button>
			<div class="sep"></div>
			<button
				type="button"
				class:active={editor?.isActive('bulletList')}
				on:click={() => editor?.chain().focus().toggleBulletList().run()}
				aria-label="Liste à puces"
				title="Liste à puces"
			>
				≡
			</button>
			<button
				type="button"
				class:active={editor?.isActive('orderedList')}
				on:click={() => editor?.chain().focus().toggleOrderedList().run()}
				aria-label="Liste numérotée"
				title="Liste numérotée"
			>
				1≡
			</button>
			<div class="sep"></div>
			<button
				type="button"
				class:active={editor?.isActive('blockquote')}
				on:click={() => editor?.chain().focus().toggleBlockquote().run()}
				aria-label="Citation"
				title="Citation"
			>
				«»
			</button>
			{#if titres}
				<button
					type="button"
					on:click={() => editor?.chain().focus().setHorizontalRule().run()}
					aria-label="Ligne de séparation"
					title="Ligne de séparation"
				>
					―
				</button>
			{/if}
			<button
				aria-label="Annuler"
				type="button"
				on:click={() => editor?.chain().focus().undo().run()}
				title="Annuler"
			>
				↩
			</button>
			<button
				aria-label="Rétablir"
				type="button"
				on:click={() => editor?.chain().focus().redo().run()}
				title="Rétablir"
			>
				↪
			</button>
		{/if}
		<!--  🔴 Ce qui n'appartient pas à la MISE EN FORME va à droite (22/09/2026).
		      Demandé à l'écran : *« l'icône IA … ne peut pas être dans la boîte
		      description sur la ligne d'icône Gras Italique (cadré à droite) ? »*

		      Un SLOT, et non une prop : l'éditeur ne connaît pas l'assistant, et n'a
		      pas à le connaître. Il offre une place ; ce qui s'y met regarde son
		      appelant. Une prop `avecAssistant` ferait entrer une notion de plus
		      dans un composant qui ne sait que mettre en forme du texte.

		      ⚠️ Le séparateur ne s'affiche QUE si le slot est rempli
		      (`$$slots.outils`) : un filet vertical seul en bout de barre annoncerait
		      un groupe vide. Le bouton `</>` vit dans le même groupe : il ne met pas
		      en forme, il change de mode. -->
		{#if $$slots.outils || sourceHtml}
			<div class="editeur-barre-fin">
				{#if $$slots.outils}
					<div class="sep"></div>
					<slot name="outils" />
				{/if}
				{#if sourceHtml}
					<button
						type="button"
						class="source-btn"
						class:active={modeSource}
						aria-label={modeSource ? 'Mode éditeur' : 'Source HTML'}
						title={modeSource ? 'Mode éditeur' : 'Source HTML'}
						on:click={basculerSource}
					>
						&lt;/&gt;
					</button>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Editor area — masquée, et non démontée, en mode source : Tiptap y reste
	     attaché et reprend la valeur corrigée au retour. -->
	<div
		class="rich-content-editable"
		hidden={modeSource}
		style="min-height:{minHeight}"
		bind:this={editorEl}
	></div>

	{#if modeSource}
		<textarea
			class="rich-source"
			style="min-height:{minHeight}"
			bind:value
			aria-label="Source HTML"
			spellcheck="false"></textarea>
	{/if}
</div>

<style>
	/*  Poussé à droite, et sur la même ligne que les boutons de mise en forme
	    tant que la place le permet. `.editeur-barre` a `flex-wrap: wrap` : sur un
	    téléphone, ce groupe passe à la ligne suivante plutôt que de comprimer les
	    boutons — l'enroulement passe avant la compression (mémoire
	    `flex_enroulement_avant_compression`). */
	.editeur-barre-fin {
		display: flex;
		align-items: center;
		gap: 0.15rem;
		margin-left: auto;
	}

	.source-btn {
		font-family: monospace;
		font-size: var(--fs-sm);
		letter-spacing: -0.02em;
	}

	.rich-content-editable {
		padding: 0.55rem 0.75rem;
		font-size: var(--fs-base);
		line-height: 1.6;
		color: var(--color-text);
		outline: none;
		cursor: text;
	}

	.rich-source {
		display: block;
		width: 100%;
		box-sizing: border-box;
		padding: 0.55rem 0.75rem;
		font-family: monospace;
		font-size: var(--fs-sm);
		line-height: 1.6;
		color: var(--color-text);
		background: var(--color-bg-subtle, #f9fafb);
		border: none;
		outline: none;
		resize: vertical;
	}

	/* Placeholder via TipTap */
	:global(.rich-content-editable .tiptap p.is-editor-empty:first-child::before) {
		content: attr(data-placeholder);
		float: left;
		color: var(--color-text-muted);
		pointer-events: none;
		height: 0;
	}

	/* Inline styles for editor content */
	:global(.rich-content-editable .tiptap) {
		outline: none;
	}
	:global(.rich-content-editable .tiptap p) {
		margin: 0 0 0.4rem;
	}
	:global(.rich-content-editable .tiptap p:last-child) {
		margin-bottom: 0;
	}
	:global(.rich-content-editable .tiptap ul, .rich-content-editable .tiptap ol) {
		padding-left: 1.4rem;
		margin: 0.25rem 0;
	}
	:global(.rich-content-editable .tiptap li) {
		margin-bottom: 0.15rem;
	}
	:global(.rich-content-editable .tiptap blockquote) {
		border-left: 3px solid var(--color-border);
		padding-left: 0.75rem;
		color: var(--color-text-muted);
		margin: 0.4rem 0;
	}
	/*  Titres et filet : la barre ne les propose qu'avec `titres`, mais un texte
	    collé peut en porter partout — ils ont donc leur rendu partout. */
	:global(.rich-content-editable .tiptap h2) {
		font-size: 1.15rem;
		font-weight: 600;
		margin: 1rem 0 0.4rem;
	}
	:global(.rich-content-editable .tiptap h3) {
		font-size: 1rem;
		font-weight: 600;
		margin: 0.8rem 0 0.3rem;
	}
	:global(.rich-content-editable .tiptap hr) {
		border: none;
		border-top: 1px solid var(--color-border);
		margin: 0.75rem 0;
	}
</style>
