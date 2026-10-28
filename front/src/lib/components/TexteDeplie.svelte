<!--
  TexteDeplie.svelte — le TEXTE ENTIER d'une carte dépliée, quand l'aperçu en a
  montré trois lignes (`ApercuCarte`).

  ## Pourquoi (10/10/2026, la page Affaires devenue le standard du site)

  Passés en cartes, les documents et les règles de la résidence ont la même
  forme : un titre, un texte en aperçu, et ce texte en entier quand on déplie.
  Le corps déplié s'écrivait donc deux fois — retrait, typographie, assainisseur
  —, et deux copies divergent au premier réglage.

  Il reprend la typographie de l'aperçu de la carte aérée (`EnteteCarte` :
  `--fs-md`, interligne 1,5) et le retrait de son en-tête : déplier ne fait que
  libérer les lignes cachées, le texte ne change ni de taille ni de place.

  Ce composant ne porte pas `carte-corps` : c'est la carte qui le pose sur son
  corps (`lint:entete-carte`), et qui décide qu'un clic dedans ne la replie pas.
-->
<script lang="ts">
	import { safeDescription } from '#lib/sanitize.ts';

	/** Le texte, simple ou riche — `safeDescription`, comme l'aperçu. */
	export let contenu: string;
</script>

<div class="texte-deplie rich-content">{@html safeDescription(contenu)}</div>

<style>
	.texte-deplie {
		padding: 0 1.1rem 0.9rem;
		font-size: var(--fs-md);
		line-height: 1.5;
		color: var(--color-text-muted);
	}
	@media (max-width: 480px) {
		.texte-deplie {
			padding: 0 0.7rem 0.75rem;
		}
	}
</style>
