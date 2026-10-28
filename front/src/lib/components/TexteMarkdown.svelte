<!--
  TexteMarkdown.svelte — un texte de référence écrit en Markdown, LU mis en forme (#1930).

  Les conditions d'inscription s'affichaient brutes, et de DEUX façons : une zone
  de texte bordée dans le formulaire d'inscription (`CarteInstallation`), un `<pre>`
  sur fond gris dans la fiche du registre (`FicheRegistreInstallation`). Un même
  texte, une même boîte : celle-ci.

  Le texte s'affiche tel quel le temps que le moteur arrive (`#lib/markdown`, chargé
  au premier rendu), puis mis en forme — jamais une boîte vide. Si le moteur ne
  peut pas se charger, le texte reste lisible tel quel.

  🔒 Le HTML passe par `safeHtml` : un texte archivé vient d'une autre installation.
-->
<script lang="ts">
	import { markdownEnHtml } from '#lib/markdown.ts';
	import { safeHtml } from '#lib/sanitize.ts';

	/** Le texte source, en Markdown — jamais modifié ici. */
	export let texte: string;
	/** Ce que la boîte contient, pour un lecteur d'écran (« Conditions d'inscription, version 1 »). */
	export let libelle: string;

	let html = '';
	$: rendre(texte);

	async function rendre(source: string) {
		html = '';
		try {
			const rendu = await markdownEnHtml(source);
			//  Un rendu arrivé après un changement de texte ne remplace pas le suivant.
			if (source === texte) html = rendu;
		} catch {
			//  Le texte brut reste affiché : il se lit, il n'est que moins beau.
		}
	}
</script>

<!--  Une boîte qui défile se parcourt au clavier : elle prend le focus, et dit ce
      qu'elle contient (WCAG 2.1.1). Svelte avertit d'un `tabindex` sur une région :
      l'exception est DÉCLARÉE dans `scripts/check-a11y.mjs`, pas tue. -->
<div class="texte-markdown rich-content" role="region" aria-label={libelle} tabindex="0">
	{#if html}
		{@html safeHtml(html)}
	{:else}
		<p class="brut">{texte}</p>
	{/if}
</div>

<style>
	.texte-markdown {
		max-height: 24rem;
		overflow: auto;
		margin: 0.75rem 0;
		padding: 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		font-size: var(--fs-sm);
		overflow-wrap: anywhere;
	}
	.texte-markdown:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	.brut {
		white-space: pre-wrap;
		margin: 0;
	}
	.texte-markdown :global(:is(h4, h5, h6)) {
		font-size: var(--fs-base);
		margin: 0.9rem 0 0.35rem;
	}
	.texte-markdown :global(h4:first-child) {
		margin-top: 0;
	}
	/*  Dans un texte courant, un lien ne se reconnaît pas à la seule couleur — le bleu
	    du site est presque celui du texte (WCAG 1.4.1). */
	.texte-markdown :global(a) {
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.texte-markdown :global(code) {
		font-size: var(--fs-xs);
	}
</style>
