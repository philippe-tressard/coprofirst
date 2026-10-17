<!--
  La rubrique « COMPTES RENDUS » d'une affaire dépliée — maquette B4, arbitrée
  le 17/10/2026 (#2042) : tous les points CS / Syndic où l'affaire a été
  abordée, le plus récent en tête.

  - Elle n'existe qu'une fois un compte rendu VALIDÉ : rien ne paraît ici avant
    (`GET /points-conseil/affaires/{id}`, qui ne rend que ceux-là, et tait au
    lecteur ce qui est « Conseil seul »). Sans compte rendu, pas de rubrique.
  - Elle ne se corrige PAS ici : la correction vit dans le Reporting, tant que
    l'affaire n'est ni close ni annulée. Le conseil peut seulement rendre un
    compte rendu privé (« Conseil seul »), ou le rouvrir.
  - Une étape du rail (`RubriqueEtape`), entre la suite et la synthèse ;
    l'accordéon reste tenu par la carte (`ouverte`, `onBasculer`).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import RubriqueEtape from './RubriqueEtape.svelte';
	import Badge from './Badge.svelte';
	import IconeAction from './IconeAction.svelte';
	import { toast } from './Toast.svelte';
	import { pointsConseil, type CrPublie } from '$lib/api';
	import { fmtDate, fmtDatetime } from '$lib/date';
	import { messageErreur } from '$lib/erreurs';
	import { safeHtml } from '$lib/sanitize';
	import { isCS } from '$lib/stores/auth';

	export let ticketId: number;
	export let ouverte = false;
	export let onBasculer: () => void;

	let crs: CrPublie[] = [];

	async function charger() {
		try {
			crs = await pointsConseil.crsAffaire(ticketId);
		} catch (e) {
			toast('error', messageErreur(e, 'Comptes rendus indisponibles'));
		}
	}

	async function basculerConfidentialite(cr: CrPublie) {
		try {
			await pointsConseil.confidentialite(cr.cr_id, !cr.conseil_seul);
			await charger();
		} catch (e) {
			toast('error', messageErreur(e, 'Modification impossible'));
		}
	}

	onMount(charger);
</script>

{#if crs.length}
	<RubriqueEtape
		titre="Comptes rendus"
		icone="users"
		compte={crs.length}
		resume="Dernier point CS / Syndic le {fmtDate(crs[0].debut)}"
		{ouverte}
		{onBasculer}
	>
		{#each crs as cr (cr.cr_id)}
			<article class="cr">
				<p class="tete">
					<strong>Point CS / Syndic du {fmtDatetime(cr.debut)}</strong>
					<span class="lieu">· {cr.ou}</span>
					{#if cr.conseil_seul}<Badge teinte="badge-purple" compact>Conseil seul</Badge>{/if}
					{#if $isCS}
						<button
							type="button"
							class="btn-icon"
							aria-pressed={cr.conseil_seul}
							aria-label={cr.conseil_seul
								? 'Rendre ce compte rendu lisible de qui lit l’affaire'
								: 'Réserver ce compte rendu au conseil syndical'}
							title={cr.conseil_seul ? 'Rouvrir à qui lit l’affaire' : 'Conseil seul'}
							on:click={() => basculerConfidentialite(cr)}
							><IconeAction icone="shield-check" /></button
						>
					{/if}
				</p>
				<div class="contenu">{@html safeHtml(cr.contenu)}</div>
			</article>
		{/each}
	</RubriqueEtape>
{/if}

<style>
	.cr + .cr {
		margin-top: 0.6rem;
		padding-top: 0.6rem;
		border-top: 1px solid var(--color-border);
	}
	.tete {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		margin: 0 0 0.25rem;
		font-size: var(--fs-sm);
	}
	.lieu {
		color: var(--color-text-muted);
	}
	.tete .btn-icon {
		margin-left: auto;
	}
	.contenu {
		font-size: var(--fs-sm);
	}
</style>
