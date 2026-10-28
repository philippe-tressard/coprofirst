<script lang="ts">
	/**
	 * Les erreurs vues par les résidents (#1631) — extrait d'`OngletTelemetrie`
	 * le 03/10/2026 : l'onglet atteignait 487 lignes, et deux panneaux de plus
	 * l'auraient fait passer le plafond de modularité.
	 *
	 * La clé (page, code) est unique : le serveur regroupe par ce couple.
	 */
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import { fmtDatetimeShort } from '#lib/date.ts';
	import type { ErreurNavigateur } from '#lib/api/index.ts';

	export let erreurs: ErreurNavigateur[] = [];
	export let periode: string;
	/** Section dépliée ? L'onglet décide, et reçoit `basculer` (`PanneauTelemetrie`). */
	export let ouvert = false;
</script>

<PanneauTelemetrie
	titre="⚠️ Erreurs vues par les résidents"
	{periode}
	{ouvert}
	vide={!erreurs.length}
	videLibelle="✅ aucune erreur signalée"
	on:basculer
>
	{#if erreurs.length}
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr><th>Page et erreur</th><th class="nombre">Onglets</th><th>Dernière</th></tr>
				</thead>
				<tbody>
					{#each erreurs as e (`${e.page}|${e.code}`)}
						<tr>
							<td>
								<code>{e.page}</code>
								<span class="code">{e.code}</span>
							</td>
							<td class="nombre">{e.total}</td>
							<td class="text-muted-sm">{fmtDatetimeShort(e.derniere_le)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
	<svelte:fragment slot="pied">
		<p>
			Chaque onglet ouvert signale une même erreur une seule fois. Les comptes qui ont refusé la
			mesure d’audience n’envoient rien. Conservation : 30 jours.
		</p>
	</svelte:fragment>
</PanneauTelemetrie>

<style>
	/*  Au téléphone, un code long fait défiler le TABLEAU (`.table-wrap`), pas
	    la page : c'est la règle des tableaux (`normes.css`, cellules sans retour
	    à la ligne). */
	.code {
		display: block;
		margin-top: 0.2rem;
		font-size: var(--fs-sm);
		color: var(--color-danger);
	}
</style>
