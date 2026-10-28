<!--
  La RÉPONSE du gestionnaire du site à un avis (#2075) — lue de tous, écrite
  par lui seul (`PUT /avis/{id}/reponse` ; vide, elle se retire).

  ⚠️ Pas la fabrique `Reponses` de la Communauté : un avis n'a pas de fil entre
  voisins, une seule réponse, celle de qui gère le site.
-->
<script lang="ts">
	import PiedFormulaire from './PiedFormulaire.svelte';
	import { avis as avisApi, type Avis } from '#lib/api/index.ts';
	import { fmtDate } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from './Toast.svelte';

	export let avis: Avis;
	export let gestionnaire = false;
	export let onMisAJour: (avis: Avis) => void = () => {};

	let ouvert = false;
	let texte = '';
	let envoi = false;

	function ouvrir() {
		texte = avis.reponse ?? '';
		ouvert = true;
	}

	async function enregistrer() {
		envoi = true;
		try {
			const maj = await avisApi.repondre(avis.id, texte);
			toast('success', maj.reponse ? 'Réponse enregistrée' : 'Réponse retirée');
			ouvert = false;
			onMisAJour(maj);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			envoi = false;
		}
	}
</script>

{#if ouvert}
	<form class="avis-reponse" on:submit|preventDefault={enregistrer}>
		<div class="field">
			<label for="avis-{avis.id}-reponse">Réponse de l'équipe</label>
			<textarea
				id="avis-{avis.id}-reponse"
				rows="3"
				bind:value={texte}
				placeholder="Merci pour ce retour… (vide : la réponse est retirée)"></textarea>
		</div>
		<PiedFormulaire petit enCours={envoi} on:annule={() => (ouvert = false)} />
	</form>
{:else if avis.reponse}
	<div class="avis-reponse">
		<p class="avis-reponse-titre">
			Réponse de l'équipe{#if avis.reponse_le}<span class="avis-reponse-date"
					>&nbsp;· {fmtDate(avis.reponse_le)}</span
				>{/if}
		</p>
		<p class="avis-reponse-texte">{avis.reponse}</p>
		{#if gestionnaire}
			<button type="button" class="btn btn-outline btn-sm" on:click={ouvrir}
				>Modifier la réponse</button
			>
		{/if}
	</div>
{:else if gestionnaire}
	<button type="button" class="btn btn-outline btn-sm avis-repondre" on:click={ouvrir}
		>Répondre</button
	>
{/if}

<style>
	.avis-reponse {
		margin-top: 0.75rem;
		padding: 0.6rem 0.8rem;
		border-left: 3px solid var(--color-primary);
		background: var(--color-primary-light);
		border-radius: var(--radius);
	}
	.avis-reponse-titre {
		margin: 0;
		font-weight: 600;
		font-size: var(--fs-sm);
		color: var(--color-primary);
	}
	.avis-reponse-date {
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.avis-reponse-texte {
		margin: 0.25rem 0 0.5rem;
		font-size: var(--fs-md);
		line-height: 1.5;
		white-space: pre-line;
	}
	.avis-repondre {
		margin-top: 0.75rem;
	}
</style>
