<!--
  SyntheseChronologie.svelte — la chronologie d'une affaire close (#1643).

  Un FIL vertical, d'après la maquette arbitrée le 03/10/2026 : une puce par
  jalon reliée à la suivante par un trait, sa date, son libellé, et l'écart
  « +N j » en jours ouvrés depuis le jalon précédent. La puce dit le jalon :

    · un état du kanban — cercle gris (À l'AG : cercle bleu) ;
    · résolue — cercle coché, vert · annulée — cercle barré, rouge ;
    · une relance au syndic — cloche, numérotée « Relance 2 au syndic » ;
    · une réouverture — flèches, « Rouvert — <état> ».

  Le serveur compose la liste ; l'écran la date en heure de Paris.
-->
<script lang="ts">
	import type { JalonSynthese, MetriquesSynthese } from '#lib/api/index.ts';
	import { fmtDate, fmtDayMonth } from '#lib/date.ts';
	import { fmtJours, libelleEtape } from '#lib/synthese.ts';
	import Icon from './Icon.svelte';

	export let metriques: MetriquesSynthese;

	/** L'année de la clôture : un jalon d'une autre année porte la sienne. */
	$: anneeCloture = metriques.close_le.slice(0, 4);

	function puce(j: JalonSynthese): { icone: string; ton: string } {
		if (j.type === 'relance') return { icone: 'bell', ton: 'alerte' };
		if (j.type === 'reouverture') return { icone: 'refresh-cw', ton: 'alerte' };
		if (j.statut === 'résolu') return { icone: 'circle-check', ton: 'succes' };
		if (j.statut === 'annulé') return { icone: 'circle-x', ton: 'danger' };
		if (j.statut === 'en_ag') return { icone: 'circle', ton: 'info' };
		return { icone: 'circle', ton: 'neutre' };
	}

	$: lignes = (() => {
		let relances = 0;
		return metriques.chronologie.map((j) => {
			let libelle = libelleEtape(j.statut);
			if (j.type === 'relance') libelle = `Relance ${++relances} au syndic`;
			if (j.type === 'reouverture') libelle = `Rouvert — ${libelleEtape(j.statut)}`;
			const quand = j.quand.slice(0, 4) === anneeCloture ? fmtDayMonth(j.quand) : fmtDate(j.quand);
			return { ...j, ...puce(j), libelle, quand };
		});
	})();
</script>

<ol class="fil">
	{#each lignes as l, i (i)}
		<li class="jalon">
			<span
				class="puce"
				class:info={l.ton === 'info'}
				class:succes={l.ton === 'succes'}
				class:danger={l.ton === 'danger'}
				class:alerte={l.ton === 'alerte'}
				aria-hidden="true"><Icon name={l.icone} size={18} /></span
			>
			<span class="quand">{l.quand}</span>
			<span class="quoi">
				{l.libelle}
				{#if l.ecart != null && i > 0}<span class="ecart">+{fmtJours(l.ecart)}</span>{/if}
			</span>
		</li>
	{/each}
</ol>
<!--  Relevé à l'écran le 03/10/2026 : « +6 j » à côté de « Chez le prestataire »
      se lisait « 6 jours chez le prestataire ». C'est l'écart DEPUIS le jalon
      précédent — la frise, elle, dit le temps passé à chaque étape. -->
<p class="aide">« +N j » : jours ouvrés écoulés depuis le jalon précédent.</p>

<style>
	/*  Le trait passe DERRIÈRE les puces : il court sur toute la hauteur du fil,
	    et chaque puce le masque par son fond. Une seule règle, quel que soit le
	    nombre de jalons. */
	.fil {
		position: relative;
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.fil::before {
		content: '';
		position: absolute;
		left: calc(0.75rem - 1px);
		top: 0.75rem;
		bottom: 0.75rem;
		width: 2px;
		background: var(--color-border);
	}
	.jalon {
		position: relative;
		display: grid;
		grid-template-columns: 1.5rem 5.5rem minmax(0, 1fr);
		align-items: center;
		gap: 0.75rem;
		font-size: var(--fs-md);
	}
	.puce {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.5rem;
		height: 1.5rem;
		background: var(--color-surface);
		color: var(--color-text-muted);
	}
	.puce.info {
		color: var(--color-info);
	}
	.puce.succes {
		color: var(--color-success);
	}
	.puce.danger {
		color: var(--color-danger);
	}
	.puce.alerte {
		color: var(--color-warning);
	}
	.quand {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.quoi {
		color: var(--color-text);
		min-width: 0;
	}
	.ecart {
		margin-left: 0.35rem;
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
		white-space: nowrap;
	}
	/*  Téléphone : la date se resserre, le libellé garde la largeur. */
	@media (max-width: 480px) {
		.jalon {
			grid-template-columns: 1.5rem 4.25rem minmax(0, 1fr);
			gap: 0.5rem;
		}
	}
</style>
