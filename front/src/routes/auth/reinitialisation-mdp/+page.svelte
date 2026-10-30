<script lang="ts">
	import ChampMotDePasse from '#lib/components/ChampMotDePasse.svelte';
	import EnteteAuthentification from '#lib/components/EnteteAuthentification.svelte';
	import { auth as authApi, ApiError } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { getSiteNom } from '#lib/stores/pageConfig.ts';

	export let data: { token: string };

	const _siteNom = getSiteNom();

	let token = data.token;
	let nouveauMdp = '';
	let confirmMdp = '';
	let saving = false;
	let done = false;
	let tokenInvalide = !token;

	/* Même défaut qu'au profil (issue #344) : la divergence des deux saisies
	   était connue à la frappe et n'était dite qu'au clic. On ne la signale
	   qu'une fois la confirmation entamée, pour ne pas crier sur un champ vide. */
	$: confirmationDivergente = confirmMdp.length > 0 && nouveauMdp !== confirmMdp;

	async function submit() {
		if (nouveauMdp !== confirmMdp) {
			toast('error', 'Les mots de passe ne correspondent pas.');
			return;
		}
		saving = true;
		try {
			await authApi.resetPassword({ token, nouveau_mot_de_passe: nouveauMdp });
			done = true;
		} catch (e) {
			if (e instanceof ApiError && e.status === 400) {
				toast('error', 'Lien invalide ou expiré. Faites une nouvelle demande.');
				tokenInvalide = true;
			} else {
				toast('error', 'Une erreur est survenue. Réessayez.');
			}
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head><title>Nouveau mot de passe — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card">
		<EnteteAuthentification sousTitre="Nouveau mot de passe" />

		{#if done}
			<div class="alert alert-success">
				<p>Votre mot de passe a été modifié avec succès.</p>
			</div>
			<div class="btn-wrapper">
				<a href="/auth/connexion" class="btn btn-primary">Se connecter</a>
			</div>
		{:else if tokenInvalide}
			<div class="alert alert-error">
				<p>Ce lien est invalide ou a expiré.</p>
			</div>
			<div class="btn-wrapper">
				<a href="/auth/mot-de-passe-oublie" class="btn btn-primary">Nouvelle demande</a>
			</div>
		{:else}
			<p class="auth-consigne">Choisissez un nouveau mot de passe pour votre compte.</p>
			<form on:submit|preventDefault={submit}>
				<ChampMotDePasse
					id="mdp-nouveau"
					libelle="Nouveau mot de passe"
					bind:valeur={nouveauMdp}
					autocomplete="new-password"
					longueurMini={8}
					robustesse
				/>
				<ChampMotDePasse
					id="mdp-confirm"
					libelle="Confirmer le mot de passe"
					bind:valeur={confirmMdp}
					autocomplete="new-password"
					longueurMini={8}
					erreur={confirmationDivergente ? 'Cette saisie diffère du nouveau mot de passe.' : ''}
				/>
				<div class="btn-wrapper">
					<a href="/auth/connexion" class="btn btn-outline">Annuler</a>
					<button type="submit" class="btn btn-primary" disabled={saving}>
						{saving ? 'Enregistrement…' : 'Enregistrer'}
					</button>
				</div>
			</form>
		{/if}
	</div>
</div>

<style>
	/*  🔴 Ce `<style>` portait `.auth-wrapper` — le nom local de ce que la charte
	    appelle `.auth-page` —, une redéfinition de `.auth-card`, un `h1`, une
	    `.success-box` et un `.btn-wrapper`. Tout venait de la charte ou aurait dû
	    y venir : une copie sous un AUTRE NOM échappe à `lint:charte`, qui ne
	    compare que les classes de la charte. Retiré le 09/09/2026. */
</style>
