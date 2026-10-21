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

  ⚠️ Les deux menus ne portent PAS les mêmes tailles d'icône : c'est ce qui
  empêchait de les rapprocher naïvement. Elle devient une prop — la différence
  est déclarée, au lieu d'être recopiée.

  🔴 Le lien se HABILLE LUI-MÊME (21/10/2026, #1571). Il recevait la classe de
  son menu (`class="{classe} nav-guide"`, puis `nav-item` / `overlay-item`) et
  comptait sur deux règles `:global` de `Nav.svelte` pour la rendre : trois
  fichiers à tenir d'accord, un fichier aveugle à `lint:css-orphelin`, et une
  classe « sans définition » pour `lint:classes-nues`. Les deux menus lui
  donnent le MÊME rendu (mesuré avant/après, bureau et mobile) : il le porte.

  ⚠️ `.nav-label` a disparu au passage : elle ne portait AUCUN style, et
  l'employer ici la rendait « nue » au sens de `lint:classes-nues` sans rien
  apporter. Une classe qui ne style rien n'est pas une classe, c'est un vestige.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { manuel } from '$lib/api';

	/** 18 px sur le côté, 20 px en plein écran. */
	export let taille = 18;
	/** Le menu principal ne montre que le guide en ligne (04/09/2026) : deux
	    entrées côte à côte l'encombraient pour un document qu'on télécharge une
	    fois. Le menu mobile, plus court, les garde toutes deux. */
	export let avecPdf = true;
</script>

<a href="/manuel-utilisateur.html" target="_blank" rel="noopener" class="nav-guide">
	<span class="nav-icon"><Icon name="book-open" size={taille} /></span>
	<span>Guide</span>
</a>
{#if avecPdf}
	<!--  Le guide en PDF : il était enterré au bas du manuel (03/09/2026) — un
	      document qu'on ne trouve pas n'existe pas. -->
	<a href={manuel.pdfUrl()} target="_blank" rel="noopener" class="nav-guide">
		<span class="nav-icon"><Icon name="file-text" size={taille} /></span>
		<span>Guide PDF</span>
	</a>
{/if}

<style>
	/*  Le style suit le BALISAGE : `.nav-guide` vivait dans `Nav.svelte`, elle
	    part avec les liens qu'elle habille. Une règle laissée dans la page que le
	    balisage vient de quitter ne s'applique plus à rien (#344).
	    Il porte aussi ce que les deux menus lui prêtaient : la mise en ligne, le
	    même habillage qu'une entrée du menu (`.nav-item`) — d'où `--color-text`
	    et non le gris du lien, que cette règle recouvrait déjà. */
	.nav-guide {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.55rem 0.7rem;
		border-radius: var(--radius);
		color: var(--color-text);
		font-size: var(--fs-md);
		text-decoration: none;
	}
</style>
