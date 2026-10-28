<!--
  BoutonOptions.svelte — l'icône qui montre les options ACTIVES d'un objet et
  ouvre le panneau qui les change, sans passer par l'édition complète.

  ## Pourquoi il est sorti d'`ActionsActualite` (12/09/2026)

  Demandé à l'écran :

  > « Si une publication a une option de publication cochée, alors une icône
  >   spécifique permet juste de changer cet état (et non l'édition de toutes les
  >   sections) ? Si oui, applique cette fonctionnalité à tous les types de page
  >   qui ont la section Options de publication. »

  Réponse : oui, et ça n'existait que sur **Actualités**. Les tickets et les
  événements portent les mêmes options — ils ont la même section dans leur
  formulaire — et n'avaient que le crayon ✏️, qui ouvre TOUT : périmètre,
  destinataires, description, pièces jointes. Dépingler demandait donc d'ouvrir
  huit sections pour en toucher une.

  ## Ce que ce bouton dit, et pourquoi il disparaît

  Il rend les **glyphes des options actives**, pris dans la table
  (`#lib/options-publication`) : 📌 ⚡ 📝 🔒. Il n'apparaît pas quand aucune n'est
  active — un bouton « Options » vide n'annonce rien, et la création d'une option
  se fait dans le formulaire, où la section est complète.

  ⚠️ C'est aussi pourquoi l'`aria-label` ÉNONCE l'état (« Options : épinglée,
  urgente ») et non le geste : un lecteur d'écran doit entendre ce que les
  glyphes montrent, pas « bouton options ».
-->
<script lang="ts">
	import { optionsActives, libelleOptionsActives } from '#lib/options-publication.ts';
	import type { CleOptionPublication } from '#lib/options-publication.ts';
	import IconeAction from '#lib/components/IconeAction.svelte';

	/** L'objet dont on lit les options — n'importe quel porteur des quatre clés. */
	export let objet: Partial<Record<CleOptionPublication, boolean | undefined>>;
	/** Le panneau est-il ouvert sur CET objet ? (pour `aria-pressed`) */
	export let ouvert = false;
	export let onOuvrir: () => void;

	$: actives = optionsActives(objet);
	$: libelle = libelleOptionsActives(objet);
</script>

{#if actives.length > 0}
	<button
		class="btn-icon btn-icon-options"
		aria-pressed={ouvert}
		aria-label={libelle}
		title="{libelle} — cliquer pour les modifier"
		on:click|stopPropagation={onOuvrir}
		>{#each actives as o (o.cle)}<span class="opt-glyphe"><IconeAction icone={o.icone} /></span
			>{/each}</button
	>
{/if}

<style>
	/*  🔴 Ces règles VOYAGENT avec le balisage qu'elles habillent : Svelte scope
	    les styles au FICHIER, et les laisser chez l'appelant livrerait le bouton
	    nu (panne des pastilles, v2.67.11, refaite deux fois depuis). Elles
	    viennent d'`ActionsActualite`, où elles étaient arrivées pour la même
	    raison (#796) — et n'y restent pas : une copie de plus, une divergence de
	    plus.

	    ⚠️ `min-width`/`min-height` à 44 px : c'est la cible tactile minimale, et
	    un bouton qui porte plusieurs glyphes doit s'élargir sans jamais passer
	    sous ce seuil. */
	.btn-icon-options {
		display: inline-flex;
		align-items: center;
		gap: 0.1rem;
		width: auto;
		min-width: 44px;
		min-height: 44px;
		padding: 0 0.35rem;
	}
	/*  Les glyphes se serrent quand ils sont quatre : à taille pleine, le bouton
	    dépasserait la rangée d'actions sur téléphone. */
	.btn-icon-options .opt-glyphe {
		font-size: 0.8em;
		line-height: 1;
	}
</style>
