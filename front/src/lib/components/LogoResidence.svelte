<!--
  La marque de la résidence — son logo téléversé, sinon l'icône neutre du bâtiment (#1728).

  🔴 L'icône du catalogue (`site_icone`) est RETIRÉE le 17/10/2026 (#2060, arbitré) :
  aucun écran ne la choisissait plus, et un réglage lu sans écran ne se règle que
  par un appel d'API écrit à la main. L'identité visuelle passe par le logo seul.

  Arbitré le 08/10/2026 : un logo téléversé REMPLACE l'icône choisie dans le
  catalogue (`site_icone`) partout où celle-ci s'affichait — la barre de
  navigation et l'écran de connexion. Sans logo, rien ne change.

  L'icône était lue à trois endroits (deux dans `Nav`, un à la connexion), chacun
  avec son repli `'building-2'` recopié : la règle « logo, sinon icône » s'y
  serait recopiée trois fois à son tour.

  `alt` est vide : le nom de la résidence est toujours écrit à côté.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { config as configApi } from '#lib/api/index.ts';
	import { configStore } from '#lib/stores/pageConfig.ts';

	/** Côté affiché, en pixels. */
	export let taille: number;

	$: logo = $configStore['site_logo'] ?? '';
	const ICONE_NEUTRE = 'building-2';
</script>

{#if logo}
	<!--  Demandé en double densité : net sur un écran de téléphone. -->
	<img
		class="logo-residence"
		src={configApi.logoUrl(taille * 2, logo)}
		width={taille}
		height={taille}
		alt=""
	/>
{:else}
	<Icon name={ICONE_NEUTRE} size={taille} />
{/if}

<style>
	/*  Le fond du logo, et son liseré de même teinte : invisibles au clair, où le
	    logo a été composé ; au sombre, la carte claire qu'il attend (#2174, S4d).
	    Un liseré en `box-shadow` ne déplace rien : la mise en page ne bouge pas
	    d'un pixel, et l'image n'est ni recopiée ni filtrée — un filtre
	    inverserait aussi les couleurs d'un logo qui en porte. */
	.logo-residence {
		display: block;
		object-fit: contain;
		background: var(--color-fond-logo);
		box-shadow: 0 0 0 4px var(--color-fond-logo);
	}
</style>
