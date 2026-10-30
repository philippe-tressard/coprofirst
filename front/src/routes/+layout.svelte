<script lang="ts">
	import '../app.css';
	import Toast from '#lib/components/Toast.svelte';
	import MajDisponible from '#lib/components/MajDisponible.svelte';
	import { configStore, modeDemoStore } from '#lib/stores/pageConfig.ts';
	import { config as configApi } from '#lib/api/index.ts';
	import { onMount } from 'svelte';
	import { browser } from '$app/env';
	import { appliquerPalette, CLE_PALETTE } from '#lib/palettes.ts';
	import { surveillerImagesProtegees } from '#lib/imagesProtegees.ts';
	import { unSeulDetailsOuvert } from '#lib/accordeon.ts';
	import { signalerDemarrage } from '#lib/garde-demarrage.ts';
	import { initTelemetry } from '#lib/telemetry.ts';

	export let data;

	// Peuple le store depuis les données SSR → zéro flash au premier rendu
	$: if (data?.siteConfig && Object.keys(data.siteConfig).length > 0) {
		configStore.set(data.siteConfig);
	}

	//  La palette de la copropriété (#2379) : le serveur l'a posée sur `<html>`.
	//  Elle ne se repose ici que si la configuration arrive par le client — rendu
	//  serveur sans réponse de l'API —, jamais sur une configuration encore vide,
	//  qui ramènerait la charte un instant.
	$: if (browser && $configStore[CLE_PALETTE]) appliquerPalette($configStore[CLE_PALETTE]);

	//  🔴 UN SEUL écouteur pour toutes les images protégées (#996).
	//
	//  Une session expirée ne se voyait qu'à des vignettes cassées : `/uploads/*`
	//  passe par le `forward_auth` du Caddyfile, donc le navigateur charge ces
	//  fichiers lui-même et le renouvellement du client n'avait aucune prise sur
	//  eux. Monté ICI et nulle part ailleurs : c'est une mutation d'état global
	//  (`standards/11` §12), et la règle ne se recopie pas dans les composants
	//  qui affichent des photos. `onMount` rend la fonction de retrait.
	onMount(surveillerImagesProtegees);

	//  L'accordéon des `<details>` natifs (30/09/2026) : en ouvrir un referme les
	//  autres, partout. Ici pour la même raison — un écouteur global, posé une
	//  fois ; les composants n'ont rien à écrire (`#lib/accordeon`).
	onMount(unSeulDetailsOuvert);

	//  L'application a démarré (#1993) : le garde de `app.html` cesse de
	//  surveiller. Sans ce marqueur, il dirait « pas fini de se charger » à une
	//  page qui marche — c'est ici, à la racine, que toutes les pages passent.
	onMount(signalerDemarrage);

	//  La télémétrie s'arme ICI, à la racine (#2066) : envoi périodique et au
	//  déchargement, écoute des erreurs non rattrapées. Armée par le seul
	//  squelette `(app)`, elle laissait `/auth/*` muet — la file ne partait
	//  qu'au vingtième événement, jamais, et le journal ne voyait rien des
	//  écrans qu'on ouvre juste après une MEP. Le refus du profil reste
	//  appliqué par le serveur pour un visiteur, par `(app)` dès que le compte
	//  est connu (`setTelemetryOptOut`). Un écouteur global, posé une fois
	//  (`standards/11` §12).
	onMount(initTelemetry);

	//  L'icône de l'onglet (#1728) : le logo de la résidence s'il a été
	//  téléversé, sinon le logo neutre. Elle vivait dans `app.html`, figée au
	//  build — d'où ce `<svelte:head>`, qui lit la configuration servie.
	$: logo = $configStore['site_logo'] ?? '';
</script>

<svelte:head>
	{#if $modeDemoStore}<meta name="robots" content="noindex, nofollow" />{/if}
	{#if logo}
		<link rel="icon" type="image/png" href={configApi.logoUrl(64, logo)} />
	{:else}
		<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
	{/if}
</svelte:head>

<slot />

<!--  🔴 APRÈS le contenu dans le DOM, et pas avant (#778, 06/09/2026).

      Les deux sont en `position: fixed` : leur place à l'écran ne dépend pas de
      leur place ici. Leur place dans le DOM, elle, décide de l'ordre du CLAVIER —
      et `MajDisponible` porte DEUX boutons.

      Montés avant, ils précédaient le lien d'évitement « Aller au contenu », qui
      vit dans le squelette `(app)`. Le premier Tab atteignait alors le bandeau de
      mise à jour au lieu du lien — **seulement quand une version était
      disponible**, donc un défaut intermittent, celui qu'on ne reproduit jamais
      au moment où on le cherche.

      ⚠️ Le lien ne peut PAS remonter ici : son ancre `#contenu` est le `<main>`
      du squelette `(app)`, qui n'existe pas sur les écrans de connexion. Un lien
      d'évitement qui pointe vers une ancre absente est pire qu'aucun lien — il
      apparaît au Tab et ne fait rien. -->
<Toast />
<MajDisponible />
