<!--
  Le CADRE d'un geste ouvert dans la carte de son objet — l'encadré, et le pied.

  ## Pourquoi ce composant (12/09/2026, #889)

  L'arbitrage « les gestes courts s'ouvrent dans la carte » a produit **trois**
  encadrés en deux lots, et ils différaient déjà :

  | Écran | Ce qu'il écrivait |
  |---|---|
  | `admin` | une ligne de tableau `background: --color-bg-alt`, `padding: 1rem` |
  | `espace-cs` | une carte aux coins du haut carrés, `border-top: none` |
  | `mon-lot` | un encadré `padding: .75rem`, sa propre bordure |

  Trois fois la même intention — *ceci est un geste, attaché à l'objet au-dessus* —
  et trois apparences. C'est la duplication au moment où elle naît : la corriger
  maintenant coûte un composant, la corriger dans six mois coûtera un audit.

  🔴 Il ne porte PAS le geste, seulement son cadre : l'appelant met ses champs
  dans le slot et reçoit `annule` / `enregistre`. Un composant qui saurait aussi
  *quoi faire* redeviendrait un écran, et il y en aurait un par geste.

  ⚠️ Le pied passe par `PiedFormulaire` — jamais deux boutons écrits à la main
  (#396 : neuf pieds, deux orthographes du même événement, trois « Annuler » sans
  `type="button"`).
-->
<script lang="ts">
	import PiedFormulaire from './PiedFormulaire.svelte';
	import { safeRichContent } from '#lib/sanitize.ts';

	/**  Ce que le geste demande de confirmer, en une phrase.
	 *
	 *  🔴 Elle est ASSAINIE avant rendu (`safeRichContent`), et ce n'est pas une
	 *  précaution de principe : les appelants y glissent un `<strong>` autour d'un
	 *  nom qui vient de la BASE — « Confirmer la fin du bail de X ? ». Ce nom est
	 *  saisi par quelqu'un. `lint:html` l'a refusé immédiatement, et il avait
	 *  raison : c'était un `{@html}` nu sur une donnée d'utilisateur. */
	export let question = '';
	export let enCours = false;
	/**  Le geste est-il destructif ? Le pied le dit alors en rouge — c'est la
	 *   seule variante admise, et elle porte sur le SENS, pas sur l'écran. */
	export let danger = false;

	export let onAnnuler: () => void = () => {};
	export let onValider: () => void = () => {};
</script>

<div class="geste" class:geste--danger={danger}>
	{#if question}
		<p class="geste-question">{@html safeRichContent(question)}</p>
	{/if}
	<slot />
	<!--  `soumission={false}` : ce geste s'ouvre dans une carte, pas dans un
	      `<form>`. Sans cela le bouton serait un `submit` orphelin, donc
	      inerte — c'est le défaut #1132, trouvé ici par la même sonde. -->
	<PiedFormulaire
		{enCours}
		{danger}
		soumission={false}
		on:annule={onAnnuler}
		on:enregistre={onValider}
	/>
</div>

<style>
	/*  Un encadré discret, pas une carte : la carte, c'est l'objet au-dessus.
	    Deux bordures pour un seul objet, c'est le défaut de #425. */
	.geste {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-neutre-fond);
		padding: 0.75rem;
		margin-bottom: 0.75rem;
	}
	/*  Le liseré rouge dit ce que le bouton dira : le geste ne se répare pas. */
	.geste--danger {
		border-left: 3px solid var(--color-danger);
	}
	.geste-question {
		margin: 0 0 0.6rem;
		font-size: var(--fs-base);
	}
</style>
