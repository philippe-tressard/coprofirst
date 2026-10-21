<!--
  Les deux entrées « Guide » du menu — le manuel en ligne, et le même en PDF.

  🔴 EXTRAITES PARCE QU'ELLES ÉTAIENT ÉCRITES DEUX FOIS (03/09/2026) : une fois
  dans le menu latéral, une fois dans le menu mobile. Deux liens × deux menus =
  quatre blocs à tenir d'accord, et il a suffi d'ajouter le PDF pour que la
  duplication double.

  C'est le garde-fou de modularité qui l'a imposé — `Nav.svelte` dépasse 500
  lignes et ne peut plus grossir. Il aurait été plus court d'y tasser deux
  lignes ; c'est exactement ce que #453 condamne, et la bonne réponse était sous
  la main.

  ⚠️ Les deux menus ne portent PAS les mêmes classes ni les mêmes tailles
  d'icône : c'est ce qui empêchait de les rapprocher naïvement. Elles deviennent
  des props — la différence est déclarée, au lieu d'être recopiée.

  ⚠️ `.nav-label` a disparu au passage : elle ne portait AUCUN style, et
  l'employer ici la rendait « nue » au sens de `lint:classes-nues` sans rien
  apporter. Une classe qui ne style rien n'est pas une classe, c'est un vestige.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { manuel } from '$lib/api';

	/** `nav-item` dans le menu latéral, `overlay-item` dans le menu mobile. Un
	    booléen et non une classe passée en prop : `class="{classe} …"` rendait ce
	    fichier aveugle à `lint:css-orphelin` (#1571). */
	export let mobile = false;
	/** 18 px sur le côté, 20 px en plein écran. */
	export let taille = 18;
	/** Le menu principal ne montre que le guide en ligne (04/09/2026) : deux
	    entrées côte à côte l'encombraient pour un document qu'on télécharge une
	    fois. Le menu mobile, plus court, les garde toutes deux. */
	export let avecPdf = true;
</script>

<a href="/manuel-utilisateur.html" target="_blank" rel="noopener" class="nav-guide" class:nav-item={!mobile} class:overlay-item={mobile}>
	<span class="nav-icon"><Icon name="book-open" size={taille} /></span>
	<span>Guide</span>
</a>
{#if avecPdf}
	<!--  Le guide en PDF : il était enterré au bas du manuel (03/09/2026) — un
	      document qu'on ne trouve pas n'existe pas. -->
	<a href={manuel.pdfUrl()} target="_blank" rel="noopener" class="nav-guide" class:nav-item={!mobile} class:overlay-item={mobile}>
		<span class="nav-icon"><Icon name="file-text" size={taille} /></span>
		<span>Guide PDF</span>
	</a>
{/if}

<style>
	/*  Le style suit le BALISAGE : `.nav-guide` vivait dans `Nav.svelte`, elle
	    part avec les liens qu'elle habille. Une règle laissée dans la page que le
	    balisage vient de quitter ne s'applique plus à rien (#344). */
	.nav-guide {
		color: var(--color-text-muted);
		font-size: var(--fs-md);
	}
</style>
