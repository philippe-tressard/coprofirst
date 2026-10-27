<!--
  EtapeConciliationFusion.svelte — le deuxième temps de `FusionAffaires` : décider,
  pour chaque affaire que la fusion ferait lire à qui ne la lisait pas, comment
  concilier (inverser, restreindre, élargir — confirmé par les noms) ou la laisser
  hors de la fusion (27/10/2026).

  Ce n'est PAS un formulaire : rien n'est enregistré ici, on ne fait que choisir
  avant la fusion elle-même. Il vit donc hors de `FusionAffaires`, dont le `<form>`
  garde son verbe de soumission commun (`lint:soumission`, ux-patterns §9 quinquies bis).
-->
<script lang="ts">
	import ConciliationFusion from '$lib/components/ConciliationFusion.svelte';
	import type { CandidateFusion } from '$lib/api';
	import { verrous, type Decisions } from '$lib/fusion-conciliation';

	/** Le numéro de l'affaire qui absorberait (la plus ancienne). */
	export let numeroPrincipale: string;
	/** Les refusées que le conseil peut concilier. */
	export let refusees: CandidateFusion[];
	/** Les refusées sans aucune option : nommées, avec leur motif. */
	export let horsFusion: CandidateFusion[] = [];
	export let decisions: Decisions;
	/** Une option est choisie sans que ses noms soient confirmés. */
	export let incomplet: boolean;
	/** Reste-t-il au moins deux affaires à fusionner ? */
	export let assez: boolean;
	export let onContinuer: () => void;
	export let onAnnule: () => void;
</script>

<div class="etape">
	<p class="aide">
		Fusionner verse les suites des autres affaires dans <strong>{numeroPrincipale}</strong> : toute personne
		qui la lit les lirait. Pour chaque affaire que cela ferait lire à quelqu'un qui ne la lisait pas,
		décidez comment concilier — ou laissez-la hors de la fusion.
	</p>
	{#each horsFusion as h (h.id)}
		<p class="aide">Hors fusion : {h.numero} — {h.titre}{h.motif ? ` (${h.motif})` : ''}.</p>
	{/each}
	{#each refusees as v (v.id)}
		{@const verrou = verrous(refusees, decisions, v.id)}
		<p class="intitule">{v.numero} — {v.titre}</p>
		<ConciliationFusion
			candidate={v}
			{numeroPrincipale}
			bind:decision={decisions[v.id]}
			bloque={verrou.bloque}
			inversionInterdite={verrou.inversionInterdite}
		/>
	{/each}
	<div class="form-actions">
		<button type="button" class="btn btn-outline" on:click={onAnnule}>Annuler</button>
		<button
			type="button"
			class="btn btn-primary"
			disabled={incomplet || !assez}
			on:click={onContinuer}
		>
			Continuer
		</button>
	</div>
	{#if !assez}
		<p class="aide">
			Aucune autre affaire à fusionner pour l'instant : choisissez une conciliation.
		</p>
	{/if}
</div>

<style>
	.etape {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.5rem 0 0.25rem;
	}
	.intitule {
		margin: 0.5rem 0 0;
		font-weight: 600;
	}
</style>
