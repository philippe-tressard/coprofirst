<!--
  Les icônes d'action d'une carte d'actualité — extraites de la page le
  06/09/2026 (#796).

  ## Pourquoi ici, et pourquoi maintenant

  Le garde-fou de modularité a refusé que `actualites/+page.svelte` (571 lignes)
  grossisse de la conversion à `EtatListe`. La règle est « on découpe le fichier
  QUAND on y touche », et le refus dit **où** est le code : pas qu'il est trop
  long, mais qu'il est au mauvais endroit (#453).

  Ce bloc est le premier candidat évident — quarante lignes de balisage et de
  commentaires qui ne parlent que d'une chose : quelles icônes, dans quel ordre,
  pour qui.

  ## L'ORDRE DES ICÔNES

  Celui de la carte de ticket, désigné comme référence le 18/08/2026 :

      🔄 commenter · ✏️ modifier · ⚙️ options · 🗑️ supprimer

  Il était inversé ici, et deux cartes du même site ne se lisaient pas pareil.

  ⚠️ TROIS GESTES ONT ÉTÉ RETIRÉS le 18/08/2026, sur arbitrage :
    • ✉️ renvoyer l'e-mail au syndic/CS ;
    • 💬 renvoyer l'annonce sur le groupe WhatsApp ;
    • 📦 archiver.
  Les deux premiers rejouaient un envoi ; l'archivage devient sans objet, la
  publication n'ayant plus d'état « Résolu » à atteindre. L'archivage
  automatique, lui, reste : une publication bascule dans l'Historique au bout de
  son délai.

  🔴 Depuis le 23/09/2026, l'actualité est une affaire (#1091) : les gestes
  sont ceux de la liste des affaires (`GestesTicket`), branchés par
  `ActualiteEnListe`. Ce composant ne dit que QUELLES icônes, pour qui.

  ⚠️ Le bouton d'options n'existe QUE si la publication en porte au moins une :
  sur une actualité ordinaire il n'y a rien à faire évoluer, et **un bouton
  inerte se lit comme une panne**. Il montre les glyphes des options ACTIVES,
  dans l'ordre de la table — c'est ce qui le rend lisible sans l'ouvrir.
-->
<script lang="ts">
	import type { Ticket } from '#lib/api/index.ts';
	import { SUITE } from '#lib/gestes.ts';
	import { isCS, isAdmin } from '#lib/stores/auth.ts';
	import { ticketUrgent } from '#lib/tickets.ts';
	import BoutonOptions from './BoutonOptions.svelte';
	import IconeAction from './IconeAction.svelte';

	export let pub: Ticket;
	//  Les options d'une actualité — épinglage et urgence (#1096). L'urgence
	//  d'une affaire EST sa priorité : lue par `ticketUrgent`, jamais redérivée.
	$: options = { epingle: pub.epingle, urgente: ticketUrgent(pub) };
	/** La publication dont le formulaire de commentaire est ouvert, ou `null`. */
	export let commentaireOuvertId: number | null = null;
	/** Celle dont le formulaire de correction est ouvert, ou `null`. */
	export let editionOuverteId: number | null = null;
	/** Celle dont le panneau d'options est ouvert, ou `null`. */
	export let optionsOuvertesId: number | null = null;

	export let onCommenter: (pub: Ticket) => void;
	/**
	 * **Cette information demande un suivi** — l'actualité devient une affaire
	 * suivie (#1094). Depuis le 23/09/2026 ce n'est plus une conversion : la
	 * même affaire change de catégorie, et son adresse ne bouge pas.
	 */
	export let onPromouvoir: (pub: Ticket) => void;
	export let onModifier: (pub: Ticket) => void;
	export let onOptions: (pub: Ticket) => void;
	export let onSupprimer: (pub: Ticket) => void;
	/** 📦 Le geste de la liste ; 🗑️ n'est offert qu'aux Archives (24/09/2026). */
	export let onArchiver: (pub: Ticket) => void;
	/** Rendue aux Archives : seule la suppression y reste, à l'administrateur. */
	export let archive = false;
</script>

{#if !archive && $isCS}
	<button
		class="btn-icon"
		aria-pressed={commentaireOuvertId === pub.id}
		aria-label={SUITE.libelle}
		title={SUITE.libelle}
		on:click|stopPropagation={() => onCommenter(pub)}><IconeAction icone="refresh-cw" /></button
	>
	<button
		class="btn-icon-edit"
		aria-pressed={editionOuverteId === pub.id}
		aria-label="Modifier"
		title="Modifier"
		on:click|stopPropagation={() => onModifier(pub)}><IconeAction icone="pencil" /></button
	>
	<!--  🔴 « Transformer en affaire » (#1094) — le geste qui évite de TOUT
	      RETAPER quand une actualité dérape. Titre, description, pièces jointes
	      et périmètre suivent ; on ajoute un statut.

	      🔴 Renommé le 10/10/2026, à l'écran : « Suivre cette actualité » n'était
	      pas clair, et se confondait avec la case « Activer le suivi », qui garde
	      l'actualité. Le libellé dit désormais ce que le geste FAIT. -->
	<button
		class="btn-icon"
		aria-label="Transformer en affaire"
		title="Transformer en affaire"
		on:click|stopPropagation={() => onPromouvoir(pub)}><IconeAction icone="target" /></button
	>
	<!--  Le bouton vit dans `BoutonOptions` depuis le 12/09/2026 : tickets et
	      événements portent les mêmes options, et le recopier chez eux aurait
	      recopié aussi ses règles d'accessibilité et sa cible tactile. -->
	<BoutonOptions
		objet={options}
		ouvert={optionsOuvertesId === pub.id}
		onOuvrir={() => onOptions(pub)}
	/>
	<button
		class="btn-icon"
		aria-label="Archiver"
		title="Archiver — rejoint l'onglet Archives"
		on:click|stopPropagation={() => onArchiver(pub)}><IconeAction icone="archive" /></button
	>
{:else if archive && $isAdmin}
	<button
		class="btn-icon-danger"
		aria-label="Supprimer"
		title="Supprimer définitivement"
		on:click|stopPropagation={() => onSupprimer(pub)}><IconeAction icone="trash-2" /></button
	>
{/if}

<style>
</style>
