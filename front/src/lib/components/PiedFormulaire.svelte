<!--
  **Le pied d'un formulaire** : « Annuler » puis le bouton d'enregistrement.

  ## 🔴 Pourquoi ce composant (#822, 07/09/2026)

  Il était écrit **dix-neuf fois** — `FormulaireActualite`,
  `FormulaireAnnonce`, `FormulaireBail`, `FormulaireDocument`,
  `FormulaireEvenement` (supprimé avec #1092), `FormulaireFaq`, `FormulaireIdee`,
  `FormulaireSondage`, `FormulaireTicket`. Mêmes classes, même ordre, mêmes
  libellés au caractère près (« Enregistrement… » / « Enregistrer »).

  Neuf copies, et elles avaient **déjà divergé sur quatre points** :

  | | Ce qu'on trouvait |
  |---|---|
  | l'événement d'annulation | `annule`, **`annuler`**, **`cancel`** — trois mots |
  | `type="button"` sur Annuler | présent dans six, **absent** dans trois |
  | `disabled` sur Annuler | **seul `FormulaireFaq`** le posait |
  | le bouton principal | `type="submit"`, rien, ou `on:click` — selon le cas |

  🔴 **La première ligne est celle qui coûte.** Deux orthographes du même
  événement, et rien ne lève : un parent qui écoute `on:annule` sur un
  formulaire qui émet `annuler` ne réagit tout simplement pas. Le bouton semble
  mort, sans erreur, sans trace. Sept écoutes `on:annuler` existaient de ce fait
  dans `mon-lot` et `residence` — elles sont corrigées avec ce lot.

  ⚠️ La deuxième aurait pu coûter : dans un `<form>`, un `<button>` sans `type`
  vaut `submit`. Les trois formulaires concernés n'ont pas de `<form>`, donc rien
  ne se produisait — mais le dixième écrit sur ce modèle, si. `type="button"` est
  désormais posé ici, une fois.

  ## Deux façons d'enregistrer, et il faut choisir la bonne

  * `soumission` (défaut) — le bouton est un `type="submit"` : c'est le `<form>`
    qui capte, via son `on:submit`. À employer dès qu'il y en a un, parce que la
    touche Entrée fonctionne alors aussi.
  * `soumission={false}` — le bouton émet `enregistre`. Pour les formulaires qui
    n'ont pas de `<form>` : `FormulaireBail`, `FormulaireDocument`,
    `FormulaireFaq`.

  ⚠️ `disabled` sur « Annuler » pendant l'enregistrement est **généralisé** :
  seul `FormulaireFaq` le posait. Annuler au milieu d'un envoi laissait la requête
  partir sans plus aucun écran pour en lire la réponse.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/** L'enregistrement est en cours : les DEUX boutons se figent. */
	export let enCours = false;

	/**
	 *  Une condition SUPPLÉMENTAIRE qui empêche d'enregistrer — un formulaire
	 *  incomplet, typiquement. Séparée d'`enCours` parce qu'elles ne disent pas la
	 *  même chose : l'une est un état passager, l'autre un refus de la saisie.
	 */
	export let desactive = false;

	/**
	 *  Le bouton principal soumet-il le `<form>` qui l'entoure ?
	 *
	 *  ⚠️ Vrai par défaut, et c'est le bon défaut : là où il y a un `<form>`, la
	 *  touche Entrée doit valider. Passer `false` uniquement quand il n'y en a
	 *  pas — sinon le clavier cesse de fonctionner sans que rien ne le dise.
	 */
	export let soumission = true;

	/**
	 *  Boutons RÉDUITS (`btn-sm`) — pour un formulaire imbriqué dans une carte,
	 *  où des boutons pleine taille écraseraient le contenu autour. Un seul cas
	 *  aujourd'hui : le formulaire d'évolution d'un ticket.
	 */
	export let petit = false;

	export let libelle = 'Enregistrer';
	export let libelleEnCours = 'Enregistrement…';
	export let libelleAnnuler = 'Annuler';

	/**  Le geste est-il DESTRUCTIF ? Le bouton de soumission passe alors en rouge.
	 *
	 *  🔴 Ajouté le 12/09/2026 plutôt que contourné. Les gestes qui s'ouvrent dans
	 *  la carte de leur objet (#889) portaient des `btn-danger` écrits à la main —
	 *  « Terminer le bail », « Supprimer ». Sans cette prop, chaque appelant aurait
	 *  refait son pied pour changer une couleur, et `lint:pied-formulaire` a montré
	 *  où cela mène : neuf pieds, deux orthographes du même événement, trois
	 *  « Annuler » sans `type="button"`.
	 *
	 *  ⚠️ Elle porte sur le SENS du geste, pas sur l'écran : c'est la seule
	 *  variante admise ici. Une prop par nuance d'apparence rouvrirait la porte
	 *  que ce composant a fermée. */
	export let danger = false;

	const dispatch = createEventDispatcher<{ annule: void; enregistre: void }>();
</script>

<div class="form-actions">
	<!--  🔴 `type="button"` TOUJOURS : dans un `<form>`, un bouton sans type vaut
	      `submit`, et « Annuler » soumettrait. Trois des neuf copies l'omettaient. -->
	<button
		type="button"
		class="btn btn-outline"
		class:btn-sm={petit}
		disabled={enCours}
		on:click={() => dispatch('annule')}
	>
		{libelleAnnuler}
	</button>
	{#if soumission}
		<button
			type="submit"
			class="btn"
			class:btn-primary={!danger}
			class:btn-danger={danger}
			class:btn-sm={petit}
			disabled={enCours || desactive}
		>
			{enCours ? libelleEnCours : libelle}
		</button>
	{:else}
		<button
			type="button"
			class="btn"
			class:btn-primary={!danger}
			class:btn-danger={danger}
			class:btn-sm={petit}
			disabled={enCours || desactive}
			on:click={() => dispatch('enregistre')}
		>
			{enCours ? libelleEnCours : libelle}
		</button>
	{/if}
</div>
