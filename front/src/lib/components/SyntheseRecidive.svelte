<!--
  SyntheseRecidive.svelte — la récidive d'un équipement (#1647).

  « La énième réparation » : quand au moins deux AUTRES affaires résolues ont
  porté sur le même équipement et le même périmètre dans les 24 mois qui
  précèdent la clôture, le conseil le lit ici, avec les liens — c'est la
  question du remplacement qui se pose. Le relevé est calculé et figé par le
  serveur à la production de la synthèse ; ce composant le dessine.

  Il ne rend rien quand le serveur n'envoie pas la clé : le serveur la RETIRE
  pour qui n'est pas du conseil (les copropriétaires lisent la synthèse validée,
  et ce bloc nomme d'autres affaires).
-->
<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import type { MetriquesSynthese } from '#lib/api/index.ts';
	import { fmtDate } from '#lib/date.ts';
	import { libelleEquipement } from '#lib/stores/equipements.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let metriques: MetriquesSynthese;

	$: recidive = metriques.recidive ?? null;
	$: total = recidive ? recidive.autres.length + 1 : 0;
</script>

{#if recidive}
	<p class="constat">
		<strong
			>{$libelleEquipement(recidive.equipement)} : {total}ᵉ affaire résolue en {fmtNombre(
				recidive.mois,
			)} mois</strong
		>
		sur le même périmètre. La question du remplacement se pose, plutôt qu’une réparation de plus.
	</p>
	<ul class="autres">
		{#each recidive.autres as a (a.id)}
			<li>
				<a href="/tickets/{a.id}">{a.numero}</a>{SEPARATEUR.tiret}{a.titre}
				<span class="date">close le {fmtDate(a.ferme_le)}</span>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.constat {
		margin: 0;
		color: var(--color-text);
		font-size: var(--fs-md);
		line-height: 1.5;
	}
	.autres {
		margin: 0;
		padding-left: 1.2rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: var(--fs-md);
	}
	.date {
		color: var(--color-text-muted);
		white-space: nowrap;
	}
</style>
