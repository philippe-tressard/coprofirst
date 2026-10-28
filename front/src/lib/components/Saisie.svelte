<!--
  Saisie.svelte — « dites-nous pourquoi », dans la charte du site.

  ## Le défaut qu'il retire

  Deux gestes du site demandaient un texte avec `prompt()` — la boîte NATIVE du
  navigateur. Elle a exactement les défauts de `confirm()`, que `Confirmation`
  a retirés le 29/08/2026, plus un qui lui est propre :

  1. **elle bloque le fil d'exécution** du navigateur entier ;
  2. **elle ignore la charte** — ni la couleur, ni le libellé des boutons, ni la
     casse du site. Sur mobile elle s'affiche en haut de l'écran, loin du pouce ;
  3. 🔴 **son champ est une ligne**, sans étiquette et sans indication de ce qui
     est attendu. Le motif d'un signalement part au conseil syndical : il mérite
     une zone de texte, un libellé, et un bouton qui dit ce qu'il envoie.

  ## ⚠️ Pas de `<form>`, et ce n'est pas un oubli

  Ce composant a d'abord été écrit avec un `<form on:submit>`. Trois contrôles
  l'ont refusé, et ils avaient raison : dans ce dépôt, un formulaire rendu dans
  une modale est soit une **création** (`FormulaireCreation`, la boîte dans la
  page), soit une **édition** (`<Modale edition>`) — ce sont les deux seules
  formes, et le cadre #430 le tranche. Une saisie impérative n'est ni l'une ni
  l'autre : c'est une question, comme `Confirmation`, dont ce fichier reprend
  exactement la structure — un message, les champs, `.form-actions`.

  ⚠️ Ce composant s'emploie par `demander()` (`#lib/saisie.ts`), jamais
  directement — même raison que `Confirmation` : c'est l'appel impératif qui
  garde les appelants à une ligne, sans état d'ouverture ni gestionnaire.
-->
<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import Modale from './Modale.svelte';

	export let titre: string;
	export let message: string;
	export let libelle: string;
	export let placeholder = '';
	export let libelleValider = 'Envoyer';
	export let libelleAnnuler = 'Annuler';
	/** Refuser une réponse vide — le cas de tous les appels d'aujourd'hui. */
	export let requis = true;
	export let onReponse: (texte: string | null) => void;

	let valeur = '';
	$: vide = requis && !valeur.trim();

	function valider() {
		if (vide) return;
		onReponse(valeur.trim());
	}
</script>

<!--  ⚠️ PAS de `edition` : la prop dirait « on corrige un objet existant », et
      `lint:geste-edition` a raison de la refuser — la correction s'ouvre DANS la
      carte de l'objet, jamais dans une fenêtre (arbitrage du 10/09/2026).
      Ici rien n'est corrigé : on pose une question avant un geste.
      ⚠️ Le clic sur le fond ne ferme pas quand même : `Modale` le déduit de
      `contientSaisie` — la présence d'un champ suffit, la prop est superflue. -->
<Modale {titre} on:fermer={() => onReponse(null)}>
	<!--  `.modal-body` et `.modal-footer` portent la marge intérieure de la fenêtre,
	      comme dans `Confirmation`, sa jumelle : sans eux, le message, le champ et
	      les boutons collaient au bord (signalé à l'écran le 14/10/2026). -->
	<div class="modal-body">
		<p class="saisie-message">{message}</p>
		<div class="field">
			<label for="saisie-texte"
				>{libelle}{#if requis}<EtoileRequis vide={!valeur} />{/if}</label
			>
			<!--  Ctrl/⌘+Entrée valide depuis la zone : Entrée seule y fait un retour à
		      la ligne, et c'est la convention des zones multilignes du site.
		      `autofocus` est VOULU, et déclaré dans `check-a11y.mjs` (#1045). -->
			<textarea
				id="saisie-texte"
				rows="3"
				autofocus
				bind:value={valeur}
				{placeholder}
				required={requis}
				on:keydown={(e) => {
					if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) valider();
				}}></textarea>
		</div>
	</div>
	<!--  « Annuler » AVANT la validation — la norme du 18/08/2026, vérifiée par
	      `lint:soumission`. La même main, le même ordre que `Confirmation`. -->
	<div class="modal-footer form-actions">
		<button type="button" class="btn btn-outline" on:click={() => onReponse(null)}>
			{libelleAnnuler}
		</button>
		<button type="button" class="btn btn-primary" disabled={vide} on:click={valider}>
			{libelleValider}
		</button>
	</div>
</Modale>

<style>
	.saisie-message {
		margin: 0 0 1rem;
		font-size: var(--fs-lg);
		line-height: 1.5;
		white-space: pre-line;
	}
</style>
