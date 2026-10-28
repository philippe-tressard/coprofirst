<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth as authApi, aiguillage } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { setUser } from '#lib/stores/auth.ts';
	import { destinationApresConnexion } from '#lib/redirection.ts';
	import {
		loadSiteConfig,
		configStore,
		modeDemoStore,
		siteNomStore,
	} from '#lib/stores/pageConfig.ts';
	import BandeauDemo from '#lib/components/BandeauDemo.svelte';
	import LogoResidence from '#lib/components/LogoResidence.svelte';
	import ChampMotDePasse from '#lib/components/ChampMotDePasse.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import AiguillageCopropriete from '#lib/components/AiguillageCopropriete.svelte';
	import { NOM_PLATEFORME } from '#lib/plateforme.ts';

	//  L'hôte COMMUN d'une installation à plusieurs copropriétés (#1894) : l'écran
	//  demande d'abord laquelle, puis y renvoie. Partout ailleurs la route répond
	//  `hote_commun: false`, et le formulaire reste celui de la copropriété — un
	//  échec le laisse aussi.
	let hoteCommun = false;

	onMount(async () => {
		loadSiteConfig();
		try {
			hoteCommun = (await aiguillage.etat()).hote_commun === true;
		} catch {
			hoteCommun = false;
		}
	});

	//  L'hôte commun n'est l'espace d'AUCUNE résidence : il porte le nom de la plateforme.
	$: _siteNom = hoteCommun ? NOM_PLATEFORME : $siteNomStore;
	$: loginSousTitre = hoteCommun
		? ''
		: ($configStore['login_sous_titre'] ?? 'Votre espace numérique de résidence');

	let email = '';
	let password = '';
	let error = '';
	let loading = false;
	let emailNotVerified = false;
	let resendDone = false;
	let resendLoading = false;

	async function submit() {
		error = '';
		emailNotVerified = false;
		resendDone = false;
		loading = true;
		email = email.trim().toLowerCase();
		try {
			const user = await authApi.login(email, password);
			setUser(user);
			goto(destinationApresConnexion());
		} catch (e) {
			const msg = messageErreur(e, 'Erreur de connexion');
			if (msg.includes('rifier votre adresse') || msg.includes('email')) {
				emailNotVerified = true;
			}
			error = msg;
		} finally {
			loading = false;
		}
	}

	async function resendVerification() {
		resendLoading = true;
		try {
			await authApi.renvoyerVerification(email);
			resendDone = true;
		} catch {
			resendDone = true;
		} finally {
			resendLoading = false;
		}
	}
</script>

<svelte:head><title>Connexion — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<div class="auth-header">
			<span class="auth-logo"><LogoResidence taille={48} /></span>
			<h1>{_siteNom}</h1>
			{#if loginSousTitre}<p>{loginSousTitre}</p>{/if}
		</div>

		<!--  La démo publique (#1906, #1932) : le bandeau le dit, et l'on se connecte par
		      le formulaire, avec les identifiants publiés sur la page « Démo » du site
		      vitrine. L'inscription et le mot de passe oublié y sont fermés au serveur. -->
		{#if $modeDemoStore}<BandeauDemo dansCarte />{/if}

		{#if hoteCommun}
			<AiguillageCopropriete />
		{:else}
			{#if error}
				<div class="alert alert-error">
					{error}
					{#if emailNotVerified}
						<div class="renvoi">
							{#if resendDone}
								<span class="text-muted-md"
									>Un nouveau lien a été envoyé si un compte non vérifié existe pour cette adresse.</span
								>
							{:else}
								<button
									type="button"
									class="btn btn-sm btn-outline btn-renvoi"
									disabled={resendLoading}
									on:click={resendVerification}
								>
									{resendLoading ? 'Envoi…' : 'Renvoyer le lien de vérification'}
								</button>
							{/if}
						</div>
					{/if}
				</div>
			{/if}

			<form on:submit|preventDefault={submit}>
				<div class="field">
					<label for="email">Email<EtoileRequis vide={!email} /></label>
					<input id="email" type="email" bind:value={email} required autocomplete="email" />
				</div>

				<ChampMotDePasse
					id="password"
					libelle="Mot de passe"
					bind:valeur={password}
					autocomplete="current-password"
				/>

				<div class="btn-wrapper">
					<button class="btn btn-primary" type="submit" disabled={loading}>
						{loading ? 'Connexion…' : 'Se connecter'}
					</button>
				</div>
			</form>

			{#if !$modeDemoStore}
				<div class="auth-links">
					<a href="/auth/mot-de-passe-oublie">Mot de passe oublié ?</a>
					<span>·</span>
					<a href="/auth/inscription">Créer un compte</a>
				</div>
			{/if}
		{/if}

		<div class="auth-legal">
			<a href="/mentions-legales">Mentions légales</a>
			<span>·</span>
			<a href="/politique-de-confidentialite">Politique de confidentialité</a>
		</div>
	</div>
</div>

<style>
	/*  `.auth-page`, `.auth-card`, `.auth-header`, `.auth-logo` (28/08/2026) puis
	    `.auth-header h1`, `.auth-header p` et `.btn-wrapper` (09/09/2026) : tous
	    dans `styles/composants.css`. Les trois derniers étaient écrits ici, à
	    l'inscription et dans les deux écrans de mot de passe — le squelette avait
	    été consolidé, pas ce qui l'habille. */

	.btn-wrapper .btn {
		padding-left: 2.5rem;
		padding-right: 2.5rem;
	}

	.auth-links {
		display: flex;
		justify-content: center;
		gap: 0.5rem;
		margin-top: 1rem;
		font-size: var(--fs-base);
	}

	.auth-legal {
		display: flex;
		justify-content: center;
		gap: 0.5rem;
		margin-top: 1.25rem;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.renvoi {
		margin-top: 0.5rem;
	}
	.btn-renvoi {
		margin-top: 0.25rem;
	}
</style>
