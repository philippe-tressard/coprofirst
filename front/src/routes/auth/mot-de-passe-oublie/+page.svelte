<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import EnteteAuthentification from '#lib/components/EnteteAuthentification.svelte';
	import { auth as authApi } from '#lib/api/index.ts';
	import { getSiteNom } from '#lib/stores/pageConfig.ts';

	const _siteNom = getSiteNom();

	let email = '';
	let sending = false;
	let done = false;

	async function submit() {
		email = email.trim().toLowerCase();
		sending = true;
		try {
			await authApi.requestPasswordReset({ email });
			done = true;
		} catch {
			// Ne pas révéler si l'e-mail existe ou non (sécurité)
			done = true;
		} finally {
			sending = false;
		}
	}
</script>

<svelte:head><title>Mot de passe oublié — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card">
		<EnteteAuthentification sousTitre="Mot de passe oublié" />

		{#if done}
			<div class="alert alert-success">
				<p>Si un compte est associé à cet e-mail, un lien de réinitialisation vous a été envoyé.</p>
				<p>Vérifiez votre boîte de réception (et les spams).</p>
			</div>
			<div class="btn-wrapper">
				<a href="/auth/connexion" class="btn btn-primary">Retour à la connexion</a>
			</div>
		{:else}
			<p class="auth-consigne">
				Saisissez votre adresse e-mail et nous vous enverrons un lien pour réinitialiser votre mot
				de passe.
			</p>
			<form on:submit|preventDefault={submit}>
				<div class="field">
					<label for="reset-email">Adresse e-mail<EtoileRequis vide={!email} /></label>
					<input id="reset-email" type="email" bind:value={email} required autocomplete="email" />
				</div>
				<div class="btn-wrapper">
					<button type="submit" class="btn btn-primary" disabled={sending}>
						{sending ? 'Envoi…' : 'Envoyer le lien'}
					</button>
				</div>
			</form>
			<p class="retour">
				<a href="/auth/connexion" class="lien-retour">Retour à la connexion</a>
			</p>
		{/if}
	</div>
</div>

<style>
	/*  🔴 Ce `<style>` portait `.auth-wrapper` — le nom local de ce que la charte
	    appelle `.auth-page` —, une redéfinition de `.auth-card`, un `h1`, une
	    `.success-box` et un `.btn-wrapper`. Tout venait de la charte ou aurait dû
	    y venir : une copie sous un AUTRE NOM échappe à `lint:charte`, qui ne
	    compare que les classes de la charte. Retiré le 09/09/2026. */
	.retour {
		text-align: center;
		font-size: var(--fs-sm);
		margin-top: 1rem;
	}
	.lien-retour {
		color: var(--color-primary);
	}
</style>
