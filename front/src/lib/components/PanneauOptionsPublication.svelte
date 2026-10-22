<!--
  PanneauOptionsPublication.svelte — les options d'une actualité, modifiables
  seules, sans passer par l'édition ni par un commentaire.

  Sorti d'`actualites/+page.svelte` le 05/09/2026, sur refus du contrôle de
  modularité : la page accueillait les mêmes options DANS le formulaire de
  commentaire (demande de l'utilisateur), et dépassait son plafond.

  ⚠️ **Deux chemins mènent désormais aux mêmes options** : ce panneau, et
  la section 2 du formulaire de commentaire. C'est un écart connu au principe
  « un geste, un endroit » (`ux-patterns` §10 bis) — ils ne répondent pas tout à
  fait à la même question (« je corrige une option » contre « je commente, et
  j'en profite pour revalider le ciblage »), mais s'il faut n'en garder qu'un,
  c'est celui-ci qui part : le formulaire de commentaire fait les deux.

  Le composant ne décide de rien : la page tient la copie de travail et appelle
  le serveur. Il montre, et dit ce qu'on a cliqué.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import SectionOptionsPublication from '$lib/components/SectionOptionsPublication.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import type { CleOptionPublication } from '$lib/options-publication';

	/**  Le nom de l'objet décrit — il entre dans les libellés qui le nomment
	 *   (« Visibilité du **ticket** au seul conseil syndical »). */
	export let objet = 'actualité';
	/**  Les options RENDUES : un événement n'a que l'épinglage, un ticket en a
	 *   l'épinglage et l'urgence. C'est l'appelant qui sait. */
	export let optionsRendues: CleOptionPublication[] = ['epingle', 'urgente', 'brouillon'];
	/** L'objet était-il DÉJÀ épinglé ? (évite un double comptage) */
	export let dejaEpingle = false;
	/** 🔒 Motif pour lequel l'épinglage est impossible — relayé tel quel. */
	export let epingleInterdit = '';
	/** La copie de travail, tenue par la page : on n'écrit qu'après le serveur. */
	export let options: {
		epingle: boolean;
		urgente: boolean;
		brouillon: boolean;
	};
	export let enregistrement = false;

	const dispatch = createEventDispatcher<{ enregistrer: void; annuler: void }>();
</script>

<!--  ── Mise en avant ──
      LE MÊME composant qu'à la création et à l'édition
      (`SectionOptionsPublication`, section « Mise en avant » du cadre #430) : ni copie, ni
      variante : un panneau réécrit en aurait recopié les règles.
      `role="presentation"` : ce conteneur n'est qu'un relais, il
      arrête la propagation pour que cocher ne referme pas la carte. -->
<div class="options-form" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
	<!--  🔴 La SECTION « Mise en avant » (#1329), et non un titre écrit ici sous
	      l'ancien nom « Options de publication » : même objet, même intitulé
	      que dans le formulaire. Première section rendue : pas de filet. -->
	<SectionOptionsPublication
		premiere
		{objet}
		options={optionsRendues}
		{dejaEpingle}
		{epingleInterdit}
		bind:epingle={options.epingle}
		bind:urgente={options.urgente}
		bind:brouillon={options.brouillon}
	/>
	<!--  🔴 `PiedFormulaire`, et non deux boutons écrits ici (12/09/2026, signalé
	      à l'écran). Cette rangée était une **dixième copie** du pied que #822 a
	      supprimé neuf fois — et elle avait déjà divergé sur les deux points qui
	      se voient : « Enregistrer » AVANT « Annuler », et un alignement à GAUCHE
	      faute de porter `.form-actions`.

	      ⚠️ C'est précisément parce qu'elle portait sa propre classe
	      (`.options-actions`) qu'aucun contrôle ne l'a vue. `lint:pied-formulaire`
	      cherche désormais la paire quelle que soit la classe de la rangée. -->
	<PiedFormulaire
		enCours={enregistrement}
		soumission={false}
		petit
		on:enregistre={() => dispatch('enregistrer')}
		on:annule={() => dispatch('annuler')}
	/>
</div>

<style>
	.options-form {
		padding: 0.5rem 0;
	}
	/*  ⚠️ `.options-actions` et sa règle mobile sont MONTÉES dans `.form-actions`
	    (`styles/normes.css`, 12/09/2026) : elles ne servaient qu'ici, ce qui
	    faisait de ce panneau la seule rangée d'actions correcte au doigt. La
	    règle la plus utile était la moins déployée. */
</style>
