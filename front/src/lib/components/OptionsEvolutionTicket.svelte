<!--
  OptionsEvolutionTicket.svelte — les options de publication d'un ticket, dans
  la section 2 d'un COMMENTAIRE.

  ## Pourquoi ce fichier (05/09/2026)

  Demandé à l'écran :

  > « tous les autres options de publication doivent être aussi conservé dans
  >   l'objet pour les tickets en édition et commentaire »
  > « pas que Visibilité du ticket »

  L'actualité tient cette section dans son écran (`actualites/+page.svelte`), et
  c'est justifié là-bas : **un** écran la rend. Le ticket en a **deux** — la
  liste, par `CarteTicket`, et la fiche, par `HistoriqueTicket`. Le même bloc
  écrit deux fois aurait divergé au premier ajout d'option, exactement comme les
  destinataires en quatre exemplaires (`api/app/utils/destinataires.py`).

  ## Ce que ce composant N'EST PAS

  Il ne décide pas de la liste des options ni de ce qu'elles écrivent : c'est
  `#lib/tickets` qui porte le pont écran ⇄ objet (`OPTIONS_TICKET`,
  `optionsDuTicket`, `optionsVersTicket`). Ici, il n'y a qu'un rendu et une
  liaison.

  ⚠️ **Réservé au conseil syndical**, comme le serveur : `appliquer_options`
  ignore ces champs pour un non-CS. L'écran ne les propose donc pas — mais c'est
  le serveur qui protège, pas cette condition.
-->
<script lang="ts">
	import SectionOptionsPublication from '#lib/components/SectionOptionsPublication.svelte';
	import { OPTIONS_TICKET } from '#lib/tickets.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import { TICKET } from '#lib/entites/ticket.ts';
	import { pliageDe } from '#lib/pliage.ts';

	/** Vrai pour la première section rendue du formulaire : pas de filet au-dessus. */
	export let premiere = false;
	/**  L'état COURANT des options, lié. L'hôte le remplit avec `optionsDuTicket()`
	 *   à l'ouverture, et le renvoie avec `optionsVersTicket()` à l'envoi : ce
	 *   qu'on enregistre DEVIENT l'état. */
	export let options = { epingle: false, urgente: false, brouillon: false };
</script>

{#if $isCS}
	<SectionOptionsPublication
		{premiere}
		pliable={pliageDe(TICKET, 'mise_en_avant')}
		objet="ticket"
		options={OPTIONS_TICKET}
		bind:epingle={options.epingle}
		bind:urgente={options.urgente}
		bind:brouillon={options.brouillon}
	/>
{/if}
