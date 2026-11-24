<!--
  Le mot de passe TEMPORAIRE se change avant d'entrer (#3019).

  Les deux comptes initiaux d'une installation neuve naissent avec un mot de passe
  écrit au journal du conteneur : l'API ne leur ouvre que leur profil et le
  changement (`api/app/auth/mot_de_passe_a_changer.py`). La connexion et le
  squelette `(app)` mènent ici (`#lib/mot-de-passe-temporaire`).

  Hors du squelette `(app)` : son menu et ses chargements appelleraient ce que l'API
  refuse. Après le changement, le jeton d'accès est tombé avec l'ancien mot de passe
  (#1063) : `me()` renouvelle la session, puis l'on va où l'on allait.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import EnteteAuthentification from '#lib/components/EnteteAuthentification.svelte';
	import ChangementMotDePasse from '#lib/components/ChangementMotDePasse.svelte';
	import { auth as authApi } from '#lib/api/index.ts';
	import { setUser } from '#lib/stores/auth.ts';
	import { loadSiteConfig, getSiteNom } from '#lib/stores/pageConfig.ts';
	import { CHEMIN_CONNEXION, destinationApresConnexion, urlDeConnexion } from '#lib/redirection.ts';

	const _siteNom = getSiteNom();
	let pret = false;
	let deconnexionEnCours = false;

	onMount(async () => {
		loadSiteConfig();
		try {
			const moi = await authApi.me();
			setUser(moi);
			//  Plus rien à changer : la page n'a pas lieu d'être.
			if (!moi.mot_de_passe_a_changer) {
				goto(destinationApresConnexion());
				return;
			}
			pret = true;
		} catch {
			window.location.assign(urlDeConnexion(destinationApresConnexion()));
		}
	});

	async function entrer() {
		setUser(await authApi.me());
		goto(destinationApresConnexion());
	}

	async function seDeconnecter() {
		if (deconnexionEnCours) return;
		deconnexionEnCours = true;
		await authApi.logout().catch(() => {});
		window.location.assign(CHEMIN_CONNEXION);
	}
</script>

<svelte:head><title>Choisir votre mot de passe — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<EnteteAuthentification sousTitre="Choisir votre mot de passe" />

		{#if pret}
			<p class="auth-consigne">
				Le mot de passe avec lequel vous venez de vous connecter est temporaire. Saisissez-le, puis
				choisissez le vôtre pour accéder à votre espace.
			</p>
			<ChangementMotDePasse integre apresChangement={entrer} />
			<div class="btn-wrapper">
				<button
					type="button"
					class="btn btn-outline"
					disabled={deconnexionEnCours}
					on:click={seDeconnecter}
				>
					Se déconnecter
				</button>
			</div>
		{/if}
	</div>
</div>
