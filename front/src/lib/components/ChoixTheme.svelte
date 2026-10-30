<!--
  ChoixTheme.svelte — Automatique, Clair ou Sombre, dans le Profil (mode sombre,
  #2174, lot S5, 30/10/2026).

  Arbitré le 29/10/2026 : le sélecteur vit dans le Profil SEULEMENT, et le choix
  vaut pour l'APPAREIL (un cookie, pas une colonne) — la règle et ses raisons
  sont dans `#lib/theme.ts`.

  Le choix s'applique sur-le-champ : l'attribut de `<html>`, les balises de la
  barre du navigateur et le cookie, sans rechargement. Aucune animation : la
  bascule est rare, et un fondu de toutes les couleurs de la page ferait
  hésiter l'écran au lieu de répondre.

  ⚠️ La valeur se lit sur l'attribut que le SERVEUR a posé, au montage — et non
  dans le cookie : c'est ce que la page affiche réellement. Rien n'est écrit
  avant un vrai choix : ouvrir le Profil ne pose aucun cookie.

  La carte « Apparence » porte aussi, sous le thème, le décor des jours de fête
  (`ChoixDecorFete`, #2312) — retenu, lui, sur le COMPTE.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import ChoixDecorFete from '#lib/components/ChoixDecorFete.svelte';
	import { appliquerTheme, choixDeLAttribut, lireChoix, OPTIONS_THEME } from '#lib/theme.ts';

	let valeur = '';
	let applique = '';

	onMount(() => {
		valeur = applique = choixDeLAttribut(document.documentElement.dataset.theme);
	});

	$: if (valeur && valeur !== applique) {
		applique = valeur;
		appliquerTheme(lireChoix(valeur));
	}
</script>

<section class="card carte-theme">
	<h2 class="section-title">Apparence</h2>
	<ChoixPastilles
		options={OPTIONS_THEME}
		bind:valeur
		tous={false}
		radio="theme"
		libelle="Thème"
		libelleVisible
		defilante={false}
		avecDetail
	/>
	<p class="aide">
		Ce choix vaut pour cet appareil : il est retenu par votre navigateur, pas par votre compte.
	</p>
	<ChoixDecorFete />
</section>

<style>
	/*  `.section-title` : la charte porte tout (composants.css). */
	.carte-theme {
		margin-bottom: 1.5rem;
	}
</style>
