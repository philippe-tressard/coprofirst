<!--
  Le SQUELETTE d'une page légale — écrit une fois (18/09/2026, #779).

  Les mentions légales et la politique de confidentialité portaient trente-deux
  lignes identiques : le même bloc de script, le même chargement du texte
  personnalisé, le même en-tête, le même repli « Contenu en cours de rédaction »,
  le même pied de page. Seuls le titre et la clé de configuration changeaient.

  ⚠️ Et elles avaient commencé à diverger, sur ce qui se voit le moins : le
  commentaire du `catch`. L'une expliquait pourquoi l'échec est silencieux,
  l'autre renvoyait à la première. C'est le signe qu'on lit — la raison n'a plus
  qu'un exemplaire, ici.

  Ce qui reste PROPRE à chaque page passe par les deux emplacements :
    - le contenu par défaut, après le texte personnalisé (slot par défaut) ;
    - un complément de pied de page (slot « pied »).

  🔴 Les styles d'un complément restent chez la page qui l'écrit, et ne peuvent
  pas s'accrocher à `.legal-page` : cette classe appartient à CE composant, donc
  un sélecteur `.legal-page … ` écrit dans la page ne correspondrait à rien —
  Svelte ne pose sa marque de portée que sur les éléments du fichier où ils sont
  écrits. Viser directement l'élément du complément.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { onMount } from 'svelte';
	import { config as configApi } from '#lib/api/index.ts';
	import { loadSiteConfig, getSiteNom, siteNomStore, configStore } from '#lib/stores/pageConfig.ts';
	import { safeHtml } from '#lib/sanitize.ts';

	/** Le titre affiché, et repris dans l'onglet du navigateur. */
	export let titre: string;
	/** La clé de `config.legal()` qui porte le texte personnalisé. */
	export let cle: string;

	const _siteNom = getSiteNom();
	$: siteNom = $siteNomStore;
	$: siteUrl = $configStore['site_url'] ?? '/';
	const year = new Date().getFullYear();

	let customHtml = '';
	onMount(async () => {
		loadSiteConfig();
		try {
			customHtml = (await configApi.legal())[cle] ?? '';
		} catch {
			//  Silencieux, et c'est voulu : la page a son texte par défaut, et
			//  afficher une erreur sur une page légale serait pire que le texte
			//  générique — un visiteur y cherche une information, pas un incident.
		}
	});
</script>

<svelte:head><title>{titre} — {_siteNom}</title></svelte:head>

<main class="legal-page">
	<a href="/" class="back-link">← Retour</a>
	<h1>{titre}</h1>

	{#if customHtml}
		<div class="custom-content">{@html safeHtml(customHtml)}</div>
	{:else}
		<p class="muted">Contenu en cours de rédaction.</p>
	{/if}

	<slot />
</main>

<footer class="legal-footer">
	© {year}{SEPARATEUR.point}<a href={siteUrl} target="_blank" rel="noopener noreferrer">{siteNom}</a
	>
	<slot name="pied" />
</footer>
