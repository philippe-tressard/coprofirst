<script lang="ts">
	/**
	 * **Comptes dormants et retour des arrivants** (#1629) — les deux signaux qui
	 * disent si le site s'installe dans les habitudes : qui a cessé de venir, et
	 * quel nouvel arrivant n'est jamais revenu après sa validation.
	 *
	 * Seuils fixes (60 et 90 jours, retour sous 7 jours) : la section ne suit pas
	 * la vue. La liste est NOMINATIVE — l'onglet est réservé à l'administrateur
	 * (`require_admin` sur le tableau de bord). Les règles de calcul :
	 * `api/app/utils/retour_comptes.py`.
	 */
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import { fmtDate } from '#lib/date.ts';
	import type { RetourComptes } from '#lib/api/index.ts';

	export let retour: RetourComptes;
	/** Section dépliée ? L'onglet décide, et reçoit `basculer` (`PanneauTelemetrie`). */
	export let ouvert = false;

	$: arrivants = retour.arrivants;
	const pluriel = (n: number) => (n > 1 ? 's' : '');
</script>

<PanneauTelemetrie
	titre="💤 Comptes dormants et arrivants"
	{ouvert}
	vide={retour.comptes_mesures === 0}
	videLibelle="aucun compte mesuré"
	on:basculer
>
	<PanneauTelemetrie titre="Comptes dormants" niveau="bloc">
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr><th>Sans visite depuis</th><th class="nombre">Comptes</th></tr>
				</thead>
				<tbody>
					{#each retour.dormants as d (d.seuil)}
						<tr>
							<td>{d.seuil} jours ou plus</td>
							<td class="nombre">{d.nombre} / {retour.comptes_mesures}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if retour.liste_dormants.length}
			<div class="table-wrap">
				<table class="table">
					<thead>
						<tr>
							<th>Compte</th><th>Type</th><th>Dernière visite</th><th class="nombre">Jours</th>
						</tr>
					</thead>
					<tbody>
						{#each retour.liste_dormants as c (c.user_id)}
							<tr>
								<td>{c.nom}</td>
								<td class="text-muted-sm">{c.type}</td>
								<td class="text-muted-sm">
									{c.derniere_visite ? fmtDate(c.derniere_visite) : 'aucune depuis la validation'}
								</td>
								<td class="nombre">{c.jours}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</PanneauTelemetrie>

	<PanneauTelemetrie titre="Retour des arrivants" periode={arrivants.periode} niveau="bloc">
		<div class="table-wrap">
			<table class="table">
				<tbody>
					<tr>
						<td>Comptes validés</td>
						<td class="nombre">{arrivants.valides}</td>
					</tr>
					<tr>
						<td>Revenus sous {arrivants.fenetre_jours} jours</td>
						<td class="nombre">{arrivants.revenus}</td>
					</tr>
					<tr>
						<td>Jamais revenus</td>
						<td class="nombre">{arrivants.jamais_revenus}</td>
					</tr>
					<tr>
						<td>Délai pas encore écoulé</td>
						<td class="nombre">{arrivants.en_attente}</td>
					</tr>
					<tr class="taux">
						<td>Taux de retour</td>
						<td class="nombre">{arrivants.taux == null ? '—' : `${arrivants.taux} %`}</td>
					</tr>
				</tbody>
			</table>
		</div>
	</PanneauTelemetrie>

	<svelte:fragment slot="pied">
		<p>
			Un compte est dormant quand ni sa dernière visite ni sa validation n’ont moins de 60 (ou 90)
			jours : un arrivant de la semaine ne l’est pas. Un arrivant est revenu s’il a ouvert une page
			dans les {arrivants.fenetre_jours} jours suivant sa validation ; le taux ne compte que ceux dont
			le délai est écoulé ou qui sont déjà revenus.
			{#if retour.refus}
				{retour.refus} compte{pluriel(retour.refus)}
				{retour.refus > 1 ? 'ont' : 'a'} refusé la mesure d’audience : exclu{pluriel(retour.refus)} du
				calcul.
			{/if}
		</p>
	</svelte:fragment>
</PanneauTelemetrie>

<style>
	.taux > td {
		font-weight: 700;
	}
</style>
