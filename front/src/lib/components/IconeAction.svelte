<!--
  IconeAction.svelte — ce qu'un bouton d'action AFFICHE : son pictogramme AU
  TRAIT.

  ## Pourquoi (10/10/2026, maquette B « Gouttière »)

  Sur une carte d'affaire, six émojis d'action de six couleurs : la couleur ne
  hiérarchisait plus rien. La maquette retenue les dessine au trait, en gris,
  Bleu Seine au survol. Arbitré d'abord pour les affaires seules — la liste
  posait un contexte (`#lib/actions-au-trait`) que ce composant lisait —, puis
  étendu à TOUT le site le soir même : la page Affaires est le standard. Le
  contexte n'avait plus rien à décider ; il est retiré, et l'émoji avec lui.

  Le bouton reste celui de son composant — libellé, `aria-pressed`, geste — :
  seul le dessin est ici. Gris au repos (`--color-text-muted`, 6,3:1 sur le
  blanc : la discrétion ne passe pas sous le seuil de contraste), Bleu Seine au
  survol, et la couleur du bouton quand celui-ci est ACTIF (blanc sur l'aplat
  bleu) ou de DANGER (la corbeille).
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';

	/** Le pictogramme au trait, nommé dans `#lib/icones-svg.json`. */
	export let icone: string;
</script>

<span class="icone-action"><Icon name={icone} size={16} /></span>

<style>
	.icone-action {
		display: inline-flex;
		color: var(--color-text-muted);
		transition: color var(--duree-geste);
	}
	:global(.btn-icon-danger) .icone-action,
	:global(.btn-icon-warn) .icone-action,
	:global(.btn-icon-success) .icone-action,
	:global([aria-pressed='true']) .icone-action {
		color: inherit;
	}
	@media (hover: hover) and (pointer: fine) {
		:global(button:hover) .icone-action {
			color: var(--color-primary);
		}
		:global(.btn-icon-danger:hover) .icone-action,
		:global(.btn-icon-warn:hover) .icone-action,
		:global(.btn-icon-success:hover) .icone-action,
		:global([aria-pressed='true']:hover) .icone-action {
			color: inherit;
		}
	}
</style>
