<!--
  MetriquesPrestataire.svelte — 📊 les affaires closes d'un prestataire, en chiffres (#1646).

  Celles où il était l'intervenant désigné, du carnet ou non (arbitré le
  04/10/2026) : combien, combien de temps « Chez le prestataire » (jours ouvrés),
  la durée totale, les relances au syndic — l'ensemble, puis chaque exercice
  comptable, le plus récent d'abord.

  🔴 RÉSERVÉ au conseil syndical, comme la notation de l'intervenant : la carte
  le monte sous `$isCS`, le serveur refuse tout autre lecteur
  (`require_cs_or_admin`).

  Monté dans le corps DÉPLIÉ de `CartePrestataire` : il ne demande rien au
  serveur tant qu'on n'a pas ouvert la fiche.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { prestataires as prestApi, type MetriquesPrestataire } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { etapeMoyenne, fmtJours, libelleAffaires, surAffaires } from '#lib/synthese.ts';
	import { fmtNombre } from '#lib/utils.ts';
	import EtatListe from './EtatListe.svelte';
	import MoyennesAffaires from './MoyennesAffaires.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let prestataireId: number;

	/** L'étape qui mesure un intervenant (`agregats.ETAPE_PRESTATAIRE`). */
	const CHEZ_PRESTATAIRE = 'chez_prestataire';

	let donnees: MetriquesPrestataire | null = null;
	let erreur = '';
	let chargement = true;

	onMount(async () => {
		[donnees, erreur] = await essayer<MetriquesPrestataire | null>(
			prestApi.metriques(prestataireId),
			null,
		);
		chargement = false;
	});

	$: ensemble = donnees?.ensemble ?? null;
	$: chez = ensemble ? etapeMoyenne(ensemble, CHEZ_PRESTATAIRE) : null;
</script>

<section class="metriques-presta" aria-labelledby="metriques-presta-{prestataireId}">
	<span class="detail-label" id="metriques-presta-{prestataireId}"
		>📊 Affaires traitées{SEPARATEUR.tiret}conseil syndical</span
	>
	<EtatListe
		{chargement}
		{erreur}
		vide={!ensemble?.nombre}
		compact
		messageVide="Aucune affaire close où ce prestataire était l'intervenant désigné."
	>
		{#if ensemble}
			<p class="metriques-resume">
				{libelleAffaires(ensemble)}.
				{#if chez}
					Étape « Chez le prestataire » : <strong>{fmtJours(chez.jours)}</strong> en moyenne (jours
					ouvrés), {surAffaires(chez.nombre)}.
				{:else}
					Aucune n'est passée par l'étape « Chez le prestataire ».
				{/if}
			</p>
			<MoyennesAffaires resume={ensemble} libelle="Moyennes des affaires du prestataire" />
			<div class="table-wrap">
				<table class="table">
					<caption class="table-legende">Par exercice comptable (jours ouvrés)</caption>
					<thead>
						<tr>
							<th scope="col">Exercice</th>
							<th scope="col" class="nombre">Affaires</th>
							<th scope="col" class="nombre">Chez le prestataire</th>
							<th scope="col" class="nombre">Durée totale</th>
							<th scope="col" class="nombre">Relances</th>
						</tr>
					</thead>
					<tbody>
						{#each donnees?.exercices ?? [] as e (e.annee)}
							<tr>
								<td>{e.libelle}</td>
								<td class="nombre">{fmtNombre(e.nombre)}</td>
								<td class="nombre">{fmtJours(etapeMoyenne(e, CHEZ_PRESTATAIRE)?.jours)}</td>
								<td class="nombre">{fmtJours(e.duree_totale)}</td>
								<td class="nombre">{fmtNombre(e.relances)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</EtatListe>
</section>

<style>
	.metriques-presta {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		margin-top: 0.75rem;
		min-width: 0;
	}
	.metriques-resume {
		margin: 0;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
</style>
