<!--
  À quel titre agit-on dans cet onglet d'administration : opérateur de l'instance,
  ou administrateur de la copropriété. Ne se montre qu'à un compte opérateur — un
  administrateur seul n'a qu'un titre. La règle : `#lib/portee`.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { isAdmin, isOperateur } from '#lib/stores/auth.ts';
	import { siteNomStore } from '#lib/stores/pageConfig.ts';
	import { phrasePortee, porteeOnglet } from '#lib/portee.ts';

	export let onglet: string;

	$: portee = porteeOnglet(onglet, { administrateur: $isAdmin, operateur: $isOperateur });
</script>

{#if portee}
	<p class="portee-onglet" data-portee={portee}>
		<Icon name={portee === 'operateur' ? 'shield-half' : 'building-2'} size={16} />
		<span>{phrasePortee(portee, $siteNomStore)}</span>
	</p>
{/if}

<style>
	.portee-onglet {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
		margin: 0 0 1rem;
		padding: 0.55rem 0.8rem;
		border: 1px solid var(--color-info-bordure);
		border-radius: var(--radius);
		background: var(--color-info-fond);
		color: var(--color-text);
		font-size: var(--fs-sm);
		line-height: 1.45;
	}
	.portee-onglet[data-portee='administrateur'] {
		border-color: var(--color-border);
		background: var(--color-neutre-fond);
	}
	.portee-onglet :global(svg) {
		flex: none;
		margin-top: 0.1rem;
		color: var(--color-info);
	}
</style>
