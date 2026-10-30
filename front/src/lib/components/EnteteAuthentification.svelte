<!--
  L'EN-TÊTE des écrans sans session — connexion, inscription, mot de passe,
  vérification d'adresse, page d'erreur, aiguillage, lien d'un compte rendu (#2357).

  Le modèle est celui de la connexion, validé à l'écran le 30/10/2026 : la marque
  de la résidence (`LogoResidence`), son NOM en titre, et dessous une phrase que
  la page choisit — la présentation à la connexion, le geste ailleurs (« Créer un
  compte », « Mot de passe oublié »…).

  🔴 Chaque page l'écrivait à la main, et elles avaient divergé : 🏢, 🔑 ou 📧
  en émoji (qui dépend de la police du système), le nom de la résidence en titre
  ici, en sous-titre là. 🔒 `npm run lint:entete-auth` refuse `auth-header` ou
  `auth-logo` écrit hors de ce composant.

  `titre` ne se passe que lorsque l'écran n'est l'espace d'aucune résidence
  (l'hôte commun, l'aiguillage : le nom de la plateforme) ou annonce une erreur.
-->
<script lang="ts">
	import LogoResidence from '#lib/components/LogoResidence.svelte';
	import { siteNomStore } from '#lib/stores/pageConfig.ts';

	/** Le titre : le nom de la résidence, par défaut. */
	export let titre: string | undefined = undefined;
	/** La phrase sous le titre ; vide, elle ne se rend pas. */
	export let sousTitre = '';
</script>

<div class="auth-header">
	<span class="auth-logo"><LogoResidence taille={48} /></span>
	<h1>{titre ?? $siteNomStore}</h1>
	{#if sousTitre}<p>{sousTitre}</p>{/if}
</div>

<style>
	.auth-header {
		text-align: center;
		margin-bottom: 1.5rem;
	}
	/*  Centré par le conteneur, pas par `text-align` : le logo téléversé est un
	    bloc, qui ne suit pas l'alignement du texte (#2305). 🔒 `e2e/logo-menu.spec.ts` */
	.auth-logo {
		display: flex;
		justify-content: center;
		margin-bottom: 0.5rem;
	}
	.auth-header h1 {
		font-size: var(--fs-titre-page);
		font-weight: 700;
		color: var(--color-primary);
		margin-bottom: 0.3rem;
	}
	.auth-header p {
		color: var(--color-text-muted);
		font-size: var(--fs-base);
	}
</style>
