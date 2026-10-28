<script lang="ts">
	/**
	 * Combien de temps les résidents attendent un écran (#1632) : médiane et 75ᵉ
	 * centile, par indicateur, puis les pages les plus lentes.
	 *
	 * Le 75ᵉ centile se lit « trois écrans sur quatre s'affichent en moins de… » :
	 * c'est lui qui trie les pages, parce qu'une médiane correcte cache la lenteur
	 * que subit un résident sur quatre.
	 */
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import { fmtDuree, fmtNombre } from '#lib/utils.ts';
	import type { SyntheseDurees } from '#lib/api/index.ts';

	export let durees: SyntheseDurees;
	export let periode: string;
	/** Section dépliée ? L'onglet décide, et reçoit `basculer` (`PanneauTelemetrie`). */
	export let ouvert = false;

	const LIBELLES = {
		chargement: 'Ouverture du site',
		navigation: 'Passage d’un écran à l’autre',
		donnees: 'Données affichées',
	} as const;
</script>

<PanneauTelemetrie
	titre="⏱️ Durées d’affichage"
	{periode}
	{ouvert}
	vide={!durees.indicateurs.length}
	videLibelle="aucune mesure"
	on:basculer
>
	{#if durees.indicateurs.length}
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr>
						<th>Mesure</th><th class="nombre">Médiane</th><th class="nombre">3 sur 4 en moins de</th
						><th class="nombre">Mesures</th>
					</tr>
				</thead>
				<tbody>
					{#each durees.indicateurs as i (i.indicateur)}
						<tr>
							<td>{LIBELLES[i.indicateur]}</td>
							<td class="nombre">{fmtDuree(i.mediane)}</td>
							<td class="nombre">{fmtDuree(i.p75)}</td>
							<td class="nombre text-muted-sm">{fmtNombre(i.mesures)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<h4 class="sous-titre">Les écrans les plus lents</h4>
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr
						><th>Page</th><th class="nombre">3 sur 4 en moins de</th><th class="nombre">Mesures</th
						></tr
					>
				</thead>
				<tbody>
					{#each durees.pages as p (`${p.page}|${p.indicateur}`)}
						<tr>
							<td>
								<code>{p.page}</code>
								<span class="text-muted-sm indicateur">{LIBELLES[p.indicateur]}</span>
							</td>
							<td class="nombre">{fmtDuree(p.p75)}</td>
							<td class="nombre text-muted-sm">{fmtNombre(p.mesures)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
	<svelte:fragment slot="pied">
		<p>
			Mesuré dans le navigateur de chacun. « Ouverture » et « passage » s’arrêtent à l’écran prêt ;
			« Données affichées » part du même instant et va jusqu’à ses données principales posées, sur
			les écrans de premier niveau. Les comptes qui ont refusé la mesure d’audience n’envoient rien.
			Conservation : 30 jours.
		</p>
	</svelte:fragment>
</PanneauTelemetrie>

<style>
	.sous-titre {
		font-size: var(--fs-md);
		font-weight: 600;
		margin: 1rem 1rem 0.5rem;
	}
	.indicateur {
		display: block;
		margin-top: 0.2rem;
	}
</style>
