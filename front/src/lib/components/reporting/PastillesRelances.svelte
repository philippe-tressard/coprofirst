<!--
  Les relances déjà envoyées au syndic pour une affaire : un point plein par
  relance, puis leur nombre et leurs dates — un rond vide quand il n'y en a
  aucune (#2035, maquette 3c retenue pour ce visuel).

  Le nombre de relances était l'information qui manquait à la relance du syndic :
  la liste disait « 1ère relance » ou « Relance n°3 », jamais quand les
  précédentes étaient parties. Le tableau et l'aperçu du courriel le lisent ici.
-->
<script lang="ts">
	import { fmtDayMonth } from '#lib/date.ts';

	/** Les jours (AAAA-MM-JJ) des relances envoyées, la plus ancienne en tête. */
	export let relances: string[];

	$: nombre = relances.length;
	$: libelle = nombre ? `${nombre} relance${nombre > 1 ? 's' : ''}` : 'aucune relance';
</script>

<span
	class="relances"
	role="img"
	aria-label="{libelle}{nombre ? ' : ' : ''}{relances.map(fmtDayMonth).join(', ')}"
>
	<span class="points" aria-hidden="true">
		{#if nombre}
			{#each relances as r, i (i)}<span class="point" title={fmtDayMonth(r)}></span>{/each}
		{:else}
			<span class="point vide"></span>
		{/if}
	</span>
	<span aria-hidden="true">{libelle}</span>
	{#if nombre}<span class="dates" aria-hidden="true">{relances.map(fmtDayMonth).join(' · ')}</span
		>{/if}
</span>

<style>
	.relances {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.points {
		display: flex;
		gap: 0.2rem;
		margin-bottom: 0.1rem;
	}
	.point {
		width: 0.65rem;
		height: 0.65rem;
		border-radius: 50%;
		background: var(--color-danger);
	}
	.point.vide {
		background: transparent;
		border: 1.5px solid var(--color-border);
	}
	.dates {
		white-space: nowrap;
	}
</style>
