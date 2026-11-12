<!--
  **Demander la suppression de son compte** (#2699), dans le pavé RGPD du profil.

  Le même geste que l'app iOS (règle 5.1.1 v de l'App Store) : la personne
  DEMANDE, l'administration traite (arbitrage du 12/11/2026). Mot de passe exigé ;
  la demande se retire tant qu'elle n'est pas traitée.

  ⚠️ Ce qui est effacé et ce qui reste (`consequences`) et le délai annoncé sont
  SERVIS par l'API (`utils/demande_suppression`) : le site et l'app lisent le même
  texte, et il dit ce que fait réellement la purge.

  Aucune prop, comme `TelemetrieRGPD` : le composant parle seul à l'API.
-->
<script lang="ts">
	import { suppressionCompte, type EtatDemandeSuppression } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { fmtDate } from '#lib/date.ts';
	import { fmtNombre } from '#lib/utils.ts';
	import { quandAuthResolue } from '#lib/stores/auth.ts';
	import ChampMotDePasse from '#lib/components/ChampMotDePasse.svelte';

	let etat: EtatDemandeSuppression | null = null;
	let erreur = '';
	let formulaire = false;
	let motDePasse = '';
	let motif = '';
	let envoi = false;

	async function charger() {
		try {
			etat = await suppressionCompte.etat();
			erreur = '';
		} catch (e) {
			erreur = messageErreur(e);
		}
	}
	quandAuthResolue(charger);

	async function demander() {
		envoi = true;
		try {
			await suppressionCompte.demander({ mot_de_passe: motDePasse, motif: motif.trim() || null });
			toast('success', 'Demande de suppression envoyée. Un accusé de réception vous est adressé.');
			formulaire = false;
			motDePasse = '';
			motif = '';
			await charger();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			envoi = false;
		}
	}

	async function retirer() {
		envoi = true;
		try {
			await suppressionCompte.retirer();
			toast('info', 'Demande de suppression retirée : votre compte est conservé.');
			await charger();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			envoi = false;
		}
	}
</script>

<div class="bloc-suppression">
	<h3 class="titre-suppression">Supprimer mon compte</h3>
	{#if erreur}
		<p class="texte-suppression">Impossible de lire l’état de votre demande : {erreur}</p>
	{:else if etat?.demande}
		<p class="texte-suppression">
			Demande de suppression envoyée le <strong>{fmtDate(etat.demande.cree_le)}</strong>.
			L’administration de la résidence la traite sous {fmtNombre(etat.demande.delai_annonce_jours)} jours
			au plus.
		</p>
		<button type="button" class="btn btn-sm" disabled={envoi} on:click={retirer}>
			Retirer ma demande
		</button>
	{:else if etat && !formulaire}
		<p class="texte-suppression">
			Vous pouvez demander la suppression de votre compte ; l’administration de la résidence la
			traite sous {fmtNombre(etat.delai_annonce_jours)} jours au plus.
		</p>
		<button type="button" class="btn btn-sm btn-danger" on:click={() => (formulaire = true)}>
			Demander la suppression de mon compte
		</button>
	{:else if etat}
		<form on:submit|preventDefault={demander}>
			<ul class="consequences">
				{#each etat.consequences as phrase, i (i)}
					<li>{phrase}</li>
				{/each}
			</ul>
			<ChampMotDePasse
				id="suppression-mdp"
				libelle="Votre mot de passe, pour confirmer"
				bind:valeur={motDePasse}
				autocomplete="current-password"
			/>
			<div class="field">
				<label for="suppression-motif">Motif (facultatif)</label>
				<textarea id="suppression-motif" rows="2" maxlength="1000" bind:value={motif}></textarea>
			</div>
			<div class="actions-suppression">
				<button type="submit" class="btn btn-sm btn-danger" disabled={envoi || !motDePasse}>
					Confirmer la demande
				</button>
				<button
					type="button"
					class="btn btn-sm"
					on:click={() => {
						formulaire = false;
						motDePasse = '';
					}}
				>
					Annuler
				</button>
			</div>
		</form>
	{/if}
</div>

<style>
	.bloc-suppression {
		margin-top: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-warning-bordure);
	}
	.titre-suppression {
		font-size: var(--fs-md);
		font-weight: 600;
		margin: 0 0 0.4rem;
	}
	.texte-suppression {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0 0 0.6rem;
	}
	.consequences {
		font-size: var(--fs-sm);
		margin: 0 0 0.75rem;
		padding-left: 1.2rem;
	}
	.consequences li + li {
		margin-top: 0.3rem;
	}
	.actions-suppression {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
</style>
