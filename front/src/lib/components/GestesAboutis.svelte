<script lang="ts">
	/**
	 * **Gestes aboutis** (#1633) — par geste, combien de fois son formulaire a été
	 * ouvert, combien de fois il a été envoyé, et le taux d'aboutissement. Un
	 * formulaire ouvert souvent et rarement envoyé est un écran qui décourage.
	 *
	 * La liste est FERMÉE, et ses libellés viennent de `#lib/aboutissement` : un
	 * geste déclaré s'affiche même à zéro, un identifiant inconnu du serveur ne
	 * s'affiche pas. Le compte est fait sans compte ni page
	 * (`api/app/utils/gestes_formulaire.py`).
	 */
	import { fmtNombre } from '#lib/utils.ts';
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import { GESTES_MESURES, type GesteMesure } from '#lib/aboutissement.ts';
	import type { GesteAbouti } from '#lib/api/index.ts';

	export let gestes: GesteAbouti[] = [];
	export let periode: string;
	/** Section dépliée ? L'onglet décide, et reçoit `basculer` (`PanneauTelemetrie`). */
	export let ouvert = false;

	$: lignes = (Object.keys(GESTES_MESURES) as GesteMesure[]).map((code) => {
		const mesure = gestes.find((g) => g.geste === code);
		return {
			code,
			libelle: GESTES_MESURES[code],
			ouvertures: mesure?.ouvertures ?? 0,
			envois: mesure?.envois ?? 0,
			taux: mesure?.taux ?? null,
		};
	});
	$: vide = lignes.every((l) => l.ouvertures === 0 && l.envois === 0);
</script>

<PanneauTelemetrie
	titre="✅ Gestes aboutis"
	{periode}
	{ouvert}
	{vide}
	videLibelle="aucun formulaire ouvert"
	on:basculer
>
	<div class="table-wrap">
		<table class="table">
			<thead>
				<tr>
					<th>Geste</th><th class="nombre">Ouvertures</th><th class="nombre">Envois</th>
					<th class="nombre">Aboutis</th>
				</tr>
			</thead>
			<tbody>
				{#each lignes as l (l.code)}
					<tr>
						<td>{l.libelle}</td>
						<td class="nombre">{fmtNombre(l.ouvertures)}</td>
						<td class="nombre">{fmtNombre(l.envois)}</td>
						<td class="nombre">{l.taux == null ? '—' : `${fmtNombre(l.taux)} %`}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<svelte:fragment slot="pied">
		<p>
			Une ouverture est comptée quand le formulaire s’affiche, un envoi quand l’enregistrement a
			réussi. Rien de ce qui est saisi n’est transmis. Les comptes qui ont refusé la mesure
			d’audience n’envoient rien. Conservation : 30 jours.
		</p>
	</svelte:fragment>
</PanneauTelemetrie>
