<!--
  Le BILAN DES VISITES de l'année, en tête du mode « Suivi entretiens
  périodiques » (#2043, arbitré le 17/10/2026 : les affaires non closes en
  tableau, ET le bilan des visites de l'année au-dessus).

  Repris de l'ancienne vue « Entretien périodique », retirée : les compteurs de
  chaque état, lus sur `GET /tickets/entretiens-periodiques`, que le serveur
  calcule (`utils/entretien_periodique`).

  Les visites lues remontent au parent (`bind:visites`) : la section « Visites
  réalisées » (`VisitesRealisees`) les liste sans un second appel.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { tickets as ticketsApi, type EtatVisite, type VisitePeriodique } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { COMPTEURS_VISITE } from '#lib/entretien-periodique.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	/** Lu par le parent (`bind:visites`) — ne pas écrire depuis l'extérieur. */
	export let visites: VisitePeriodique[] = [];
	let exercice = new Date().getFullYear();
	let chargement = true;
	let erreur = '';

	$: nombre = (etat: EtatVisite) => visites.filter((v) => v.etat === etat).length;

	onMount(async () => {
		try {
			const r = await ticketsApi.entretiensPeriodiques();
			[exercice, visites] = [r.exercice, r.visites];
		} catch (e) {
			erreur = messageErreur(e, 'Bilan des visites indisponible');
		} finally {
			chargement = false;
		}
	});
</script>

<section class="bilan" aria-labelledby="titre-bilan-visites">
	<h3 id="titre-bilan-visites" class="intitule">Visites {exercice}</h3>
	{#if chargement || erreur}
		<EtatListe compact {chargement} {erreur} titreErreur="Bilan des visites indisponible" />
	{:else}
		<div class="kpi-row">
			{#each COMPTEURS_VISITE as c (c.etat)}
				<div class="kpi-card" class:kpi-alert={c.etat === 'non_realisee' && nombre(c.etat) > 0}>
					<div class="kpi-value">{nombre(c.etat)}</div>
					<div class="kpi-label">{c.libelle}</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

<style>
	.bilan {
		margin-bottom: 0.75rem;
	}
	.intitule {
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin: 0 0 0.4rem;
	}
</style>
