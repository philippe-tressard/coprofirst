<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { auth as authApi } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import EnteteAuthentification from '#lib/components/EnteteAuthentification.svelte';
	import { getSiteNom } from '#lib/stores/pageConfig.ts';

	const _siteNom = getSiteNom();

	let status: 'loading' | 'success' | 'error' | 'expired' = 'loading';
	/** Le lien confirmait une NOUVELLE adresse (#1549), pas une inscription. */
	let changementAdresse = false;
	let errorMessage = '';
	let resendEmail = '';
	let resendDone = false;
	let resendLoading = false;

	onMount(async () => {
		const token = page.url.searchParams.get('token');
		if (!token) {
			status = 'error';
			errorMessage = 'Lien de vérification invalide.';
			return;
		}
		try {
			const reponse = await authApi.verifierEmail(token);
			changementAdresse = !!reponse?.changement_adresse;
			status = 'success';
		} catch (e) {
			status = 'expired';
			errorMessage = messageErreur(e, 'Lien de vérification invalide ou expiré.');
		}
	});

	async function resend() {
		if (!resendEmail.trim()) return;
		resendLoading = true;
		try {
			await authApi.renvoyerVerification(resendEmail.trim());
			resendDone = true;
		} catch {
			resendDone = true;
		} finally {
			resendLoading = false;
		}
	}
</script>

<svelte:head><title>Vérification e-mail — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<EnteteAuthentification sousTitre="Vérification de l’adresse e-mail" />

		{#if status === 'loading'}
			<p class="attente">Vérification en cours…</p>
		{:else if status === 'success'}
			<div class="alert alert-success">
				{#if changementAdresse}
					<strong>Nouvelle adresse confirmée !</strong><br />
					C’est désormais avec elle que vous vous connectez, et elle qui reçoit les courriels du site.
				{:else}
					<strong>Adresse e-mail vérifiée !</strong><br />
					Votre adresse a été confirmée. Votre compte est maintenant en attente de validation par le conseil
					syndical.<br />
					Vous recevrez un e-mail dès qu'il sera activé.
				{/if}
			</div>
			<div class="lien-retour">
				<a href="/auth/connexion" class="btn btn-primary">Retour à la connexion</a>
			</div>
		{:else if status === 'expired'}
			<div class="alert alert-error">
				{errorMessage}
			</div>
			<div class="bloc-renvoi">
				<p class="explication">Vous pouvez demander un nouveau lien de vérification :</p>
				{#if resendDone}
					<div class="alert alert-success alerte-renvoi">
						Si un compte non vérifié existe pour cette adresse, un nouveau lien vous a été envoyé.
					</div>
				{:else}
					<form on:submit|preventDefault={resend} class="form-renvoi">
						<div class="field champ-en-ligne champ-renvoi">
							<input type="email" bind:value={resendEmail} placeholder="Votre e-mail" required />
						</div>
						<button type="submit" class="btn btn-primary" disabled={resendLoading}>
							{resendLoading ? 'Envoi…' : 'Renvoyer'}
						</button>
					</form>
				{/if}
			</div>
			<div class="lien-retour">
				<a href="/auth/connexion" class="text-muted-md">Retour à la connexion</a>
			</div>
		{:else}
			<div class="alert alert-error">{errorMessage}</div>
			<div class="lien-retour">
				<a href="/auth/connexion" class="btn btn-outline">Retour à la connexion</a>
			</div>
		{/if}
	</div>
</div>

<style>
	.attente {
		text-align: center;
		color: var(--color-text-muted);
	}
	.lien-retour {
		text-align: center;
		margin-top: 1rem;
	}
	.bloc-renvoi {
		margin-top: 1.5rem;
	}
	.explication {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
		margin-bottom: 0.75rem;
	}
	.alerte-renvoi {
		font-size: var(--fs-base);
	}
	.form-renvoi {
		display: flex;
		gap: 0.5rem;
	}
	.champ-renvoi {
		flex: 1;
	}
</style>
