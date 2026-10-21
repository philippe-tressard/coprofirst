<script lang="ts">
	import BandeauDemo from '$lib/components/BandeauDemo.svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { afterNavigate, beforeNavigate } from '$app/navigation';
	import Nav from '$lib/components/Nav.svelte';
	import { auth as authApi } from '$lib/api';
	import { setUser, currentUser, marquerAuthResolue } from '$lib/stores/auth';
	import { urlDeConnexion } from '$lib/redirection';
	import { loadSiteConfig, configStore } from '$lib/stores/pageConfig';
	import { chargerPerimetres } from '$lib/stores/perimetres';
	import {
		commencerNavigation,
		mesurerNavigation,
		trackPageView,
		setTelemetryOptOut,
	} from '$lib/telemetry';
	import { lireSourceArrivee } from '$lib/arrivees';
	import PiedDePage from '$lib/components/PiedDePage.svelte';
	import { lireReglagePied } from '$lib/piedDePage';

	onMount(async () => {
		const [, meResult] = await Promise.allSettled([
			loadSiteConfig(),
			!$currentUser ? authApi.me() : Promise.resolve(null),
		]);
		if (!$currentUser) {
			if (meResult.status === 'fulfilled' && meResult.value) {
				setUser(meResult.value);
			} else {
				// Emporte la page demandée (fragment compris) pour y revenir après
				// la connexion — un lien partagé ne doit pas être perdu au login.
				marquerAuthResolue();
				goto(urlDeConnexion());
			}
		} else {
			//  Utilisateur déjà en mémoire (navigation interne) : l'état est résolu
			//  d'emblée. Sans cette branche, un garde d'accès attendrait indéfiniment.
			marquerAuthResolue();
		}
		//  L'arborescence des périmètres alimente `perimetreLabel()`. Chargée APRÈS
		//  l'authentification — l'endpoint exige une session — et sans `await` : les
		//  listes de contenus arrivent elles aussi en asynchrone, et un libellé
		//  manquant retombe sur son rendu calculé plutôt que de retarder la page.
		if ($currentUser) chargerPerimetres();

		//  Le refus de la mesure d'audience, AVANT le premier envoi (le serveur
		//  l'honore aussi). Dans les deux sens — sinon le refus d'un compte
		//  survivrait à sa déconnexion, sur le même onglet, pour le compte suivant.
		setTelemetryOptOut($currentUser?.opt_out_telemetrie ?? false);
		trackPageView(window.location.pathname);
	});

	//  La durée d'affichage de chaque écran (#1632) : la première page à
	//  l'hydratation (`enter`), les suivantes de `beforeNavigate` à ici.
	beforeNavigate(commencerNavigation);

	afterNavigate((navigation) => {
		mesurerNavigation(navigation.type);
		//  Arrivée par une notification (#1634) : l'étiquette part avec la vue, puis quitte l'adresse.
		trackPageView(window.location.pathname, lireSourceArrivee());
	});

	$: reglagePied = lireReglagePied($configStore);
</script>

<!--  🔴 LE LIEN D'ÉVITEMENT — premier élément focalisable de la page (#778).
      Le menu compte treize entrées : sans lui, un utilisateur au clavier ou au
      lecteur d'écran les retraverse À CHAQUE navigation avant d'atteindre le
      contenu. WCAG 2.4.1, niveau A — le premier critère de navigation, et le
      moins coûteux.

      ⚠️ Il vit dans le SQUELETTE et nulle part ailleurs : c'est R1 (le squelette
      porte ce qui vaut pour toutes les pages), et un lien posé dans un écran
      n'aurait servi que celui-là. -->
<a class="lien-evitement" href="#contenu">Aller au contenu</a>

<div class="app-shell">
	<Nav />
	<div class="app-content">
		<!--  La démo publique (#1906) : en tête de la colonne de contenu, sous la barre
		      mobile fixe — dans le layout racine, elle l'aurait recouverte. -->
		<BandeauDemo />
		<main class="app-main" id="contenu" tabindex="-1">
			<div class="container page">
				<slot />
			</div>
		</main>
		<PiedDePage reglage={reglagePied} />
	</div>
</div>

<style>
	.app-shell {
		display: flex;
		min-height: 100vh;
		min-height: 100svh;
		overflow-x: hidden;
	}

	.app-content {
		flex: 1;
		margin-left: 185px;
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		min-height: 100svh;
		max-width: calc(100vw - 185px);
	}

	.app-main {
		flex: 1;
	}

	@media (max-width: 767px) {
		.app-content {
			margin-left: 0;
			padding-top: 3.25rem;
			max-width: 100vw;
		}
		.app-main {
			overflow-x: clip; /* clip sans créer de scroll-context → position:sticky fonctionne */
		}
	}
</style>
