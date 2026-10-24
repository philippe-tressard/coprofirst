<!--
  Le PIED d'une carte — le squelette de sa dernière ligne, le même partout
  (24/10/2026).

  Demandé à l'écran sur le carnet d'entretien : le n° de l'affaire (TK-…) y
  occupait une ligne à lui, sous l'aperçu, alors que la carte d'affaire et le
  fil le disent dans leur dernier rang. Le pied n'avait pas de squelette commun
  — `PastillesAffaire` l'écrivait pour trois cartes, le carnet recomposait le
  sien avec d'autres pastilles : l'écart ne pouvait que revenir.

  L'ORDRE, qui ne se discute pas :
    catégorie (emoji, libellé au survol) · [ce que la carte dit : état, 🔹,
    qui la lit, urgence, marqueurs…] · #numéro · [la fin : ✍️ auteur, ✨ IA]

  Il ne porte QUE ce qui est commun : la catégorie et le numéro, qui sont ceux
  d'une affaire où qu'elle se lise. Le milieu et la fin sont des créneaux — une
  carte y met ce qu'elle a, jamais ce qu'elle n'a pas.

  🔒 `npm run lint:pastilles` : le pied d'une carte d'affaire ou du carnet
  passe ici ; l'emoji de catégorie ne s'écrit nulle part ailleurs.
-->
<script lang="ts">
	import { categorieTicketEmoji, categorieTicketLabel } from '$lib/tickets';

	/** La VALEUR de la catégorie de l'affaire (`panne`) ; rien, pas de pictogramme. */
	export let categorie: string | null | undefined = null;
	/** Le numéro d'affaire, sans le « # » (`TK-109008`). */
	export let numero: string | null | undefined = null;
</script>

<!--  `display: contents` : les pastilles restent les enfants de la ligne qui les
      reçoit (`.ec-tags`, `.flux-badges`) — c'est elle qui les range et les fait
      passer à la ligne. L'enveloppe ne sert qu'à borner l'habillage ci-dessous. -->
<span class="pa">
	{#if categorie}
		<span class="pa-cat" title={categorieTicketLabel(categorie)}
			>{categorieTicketEmoji(categorie)}</span
		>
	{/if}
	<slot />
	{#if numero}<span>#{numero}</span>{/if}
	<slot name="fin" />
</span>

<style>
	.pa {
		display: contents;
	}
	/*  Les pastilles ne se compriment pas — la règle de `.ec-tags`, qui ne les
	    atteint plus à travers l'enveloppe. */
	.pa > :global(*) {
		flex-shrink: 0;
	}
	/*  🔴 UN HABILLAGE, et la couleur seulement où elle DISTINGUE (maquette B,
	    10/10/2026 : « visuellement brouillon ») : des CAPSULES, neutres pour ce
	    qui décrit, teintées pour l'état, « qui la lit » et l'urgence. Devenu le
	    standard du site : la règle vit dans `styles/composants.css` (`.badge`,
	    `:is(.ec-tags, .pa) .badge-gray`), plus ici. */
	.pa-cat {
		flex-shrink: 0;
		font-size: var(--fs-lg);
	}
</style>
