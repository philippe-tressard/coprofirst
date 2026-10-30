<!--
  **La note d'un prestataire**, avec sa teinte — écriture unique.

  ## Pourquoi ce composant (08/09/2026)

  Le rendu d'une note était écrit **quatre fois**, et les quatre ne disaient pas
  la même chose :

  | Où | Teinte | Nombre d'avis |
  |---|---|---|
  | `VueRenouvellementsContrats` ×1 | les trois seuils | en infobulle |
  | `VueRenouvellementsContrats` ×2 | les trois seuils | absent |
  | `VuePrestataires` (tableau) | **orange, toujours** | absent |

  🔴 La dernière ligne est un défaut visible : un prestataire noté **1/5 y
  apparaît en orange**, exactement comme un 3,5. La teinte est censée dire d'un
  coup d'œil si l'on est content de quelqu'un — là, elle ment.

  ⚠️ `starsDisplay` était DÉJÀ dans `#lib/utils` : la règle était factorisée,
  son **emploi** non. C'est le même motif que la validation des téléversements
  (#825) — et c'est l'emploi qui porte les seuils, donc la décision.

  ## Les seuils sont une règle, pas une présentation

  `< 3` mécontent · `< 4` correct · `>= 4` satisfait. Recopiés, ils se
  déplaceraient à trois endroits sur quatre le jour où l'on décide qu'un 3,5
  n'est plus « correct ».
-->
<script lang="ts">
	import { starsDisplay } from '#lib/utils.ts';

	/** La note sur 5. `null` : rien n'est rendu — l'appelant n'a pas à le tester. */
	export let note: number | null | undefined = null;
	/** Le nombre d'avis, quand on le connaît : il devient l'infobulle. */
	export let nbAvis: number | null | undefined = null;
	/**  Affiche « /5 » après la note.
	 *
	 *   ⚠️ Divergence conservée et déclarée : la frise des contrats montre
	 *   « ★★★★ 4.2 » (la colonne est déjà titrée « Note »), le tableau des
	 *   notations « ★★★★ 4.2/5 » au milieu d'autres chiffres. Les aligner
	 *   retirerait une information à l'un ou du bruit à l'autre. */
	export let surCinq = false;

	/**  Mode SAISIE : cinq étoiles cliquables au lieu d'un texte.
	 *
	 *  🔴 Ajouté le 12/09/2026 plutôt que d'écrire un second composant. La saisie
	 *  vivait dans `prestataires/+page.svelte`, en cinq `<button>` portant leurs
	 *  couleurs EN LIGNE (`#f59e0b`, `#d1d5db`) — c'est-à-dire une sixième
	 *  écriture de la note, celle-là même que ce composant a supprimée pour
	 *  l'affichage. Saisir et lire une note sont deux rendus du MÊME objet
	 *  (`ux-patterns` R3) : ils appartiennent au même fichier.
	 *
	 *  ⚠️ En saisie, `note` est LIÉE (`bind:note`) : c'est ce que l'utilisateur
	 *  choisit, pas ce qu'on lui montre. Et la teinte ne s'applique pas — elle
	 *  juge un prestataire, elle ne commente pas un clic en cours. */
	export let saisie = false;
	/** Ce que le survol laisse prévoir, sans encore rien choisir. */
	let survol = 0;

	//  🔴 LES SEUILS, à UN endroit. Ils décident d'une teinte que le lecteur
	//  interprète comme un jugement : les recopier, c'est accepter que le même
	//  prestataire paraisse « correct » sur un écran et « mécontent » sur l'autre.
	$: teinte = note == null ? '' : note < 3 ? 'bad' : note < 4 ? 'ok' : 'good';
</script>

{#if saisie}
	<!--  Les cinq étoiles : littérales et distinctes, chacune sa propre clé. -->
	<div class="note-saisie" role="group" aria-label="Note sur 5">
		{#each [1, 2, 3, 4, 5] as valeur (valeur)}
			<button
				type="button"
				class="note-etoile"
				class:note-etoile-pleine={(survol || note || 0) >= valeur}
				aria-label="{valeur} sur 5"
				aria-pressed={(note ?? 0) >= valeur}
				on:click={() => (note = valeur)}
				on:mouseenter={() => (survol = valeur)}
				on:mouseleave={() => (survol = 0)}
			>
				{(survol || note || 0) >= valeur ? '★' : '☆'}
			</button>
		{/each}
	</div>
	{#if note}
		<p class="note-choisie">{note}/5</p>
	{/if}
{:else if note != null}
	<!--  ⚠️ `class:` et non `class="note-etoiles {teinte}"` (#810) : devant un
	      ternaire INTERPOLÉ, Svelte cesse de déclarer les sélecteurs inutilisés
	      pour TOUT le fichier, et `lint:css-orphelin` y devient aveugle sans le
	      dire. Le plafond décroissant l'a refusé tout de suite.

	      ⚠️ Les SEUILS restent au-dessus, dans `teinte` : ce sont eux la règle.
	      Les remettre ici, dans trois `class:`, les recopierait — c'est
	      exactement ce que ce composant retire. -->
	<!--  🔴 Proposition B, arbitrée sur maquette le 27/09/2026 (#1055) parmi cinq :
	      les ÉTOILES portent le jugement — un graphisme, où le jeton d'état tient
	      le contraste de 3:1 —, le CHIFFRE reste dans la couleur du texte. Teinter
	      le tout mettait l'orange en texte (3,62, sous 4,5) ; l'or de la charte
	      (2,61) ne tenait même pas le 3:1 d'un graphisme. -->
	<span class="note-etoiles" title={nbAvis != null ? `${note}/5 (${nbAvis} avis)` : undefined}
		><span
			class="note-glyphes"
			class:note-bad={teinte === 'bad'}
			class:note-ok={teinte === 'ok'}
			class:note-good={teinte === 'good'}
			aria-hidden="true">{starsDisplay(note)}</span
		>
		<span class="note-chiffre">{note}{surCinq ? '/5' : ''}</span></span
	>
{/if}

<style>
	/*  La saisie : des étoiles assez grandes pour être visées au doigt — 44 px de
	    cible tactile, la norme du produit (`standards/11` §10). */
	.note-saisie {
		display: inline-flex;
		gap: 0.25rem;
	}
	.note-etoile {
		background: none;
		border: none;
		cursor: pointer;
		font-size: var(--fs-picto-lg);
		line-height: 1;
		min-width: 44px;
		min-height: 44px;
		color: var(--color-border);
		transition: color var(--duree-geste);
	}
	/*  ⚠️ La MÊME teinte que `note-ok` : les couleurs de la note vivent dans ce
	    fichier, et une étoile choisie ne peut pas être d'un autre orange que
	    celui qu'on relira ensuite. */
	.note-etoile-pleine {
		color: var(--color-warning);
	}
	.note-choisie {
		margin: 0.25rem 0 0;
		font-size: var(--fs-base);
		color: var(--color-text-muted);
	}
	/*  Taille et césure reprises de `.frise-stars`, d'où ce composant est né. */
	.note-etoiles {
		font-size: var(--fs-sm);
		white-space: nowrap;
	}
	.note-glyphes {
		font-size: 1.1em;
		letter-spacing: -0.02em;
	}
	.note-chiffre {
		color: var(--color-text);
		font-variant-numeric: tabular-nums;
	}
	/*  Les trois teintes viennent de `VueRenouvellementsContrats`, seul des trois
	    rendus à les porter — les deux autres l'ont donc GAGNÉE, et c'est le but. */
	.note-bad {
		color: var(--color-danger);
	}
	.note-ok {
		color: var(--color-warning);
	}
	.note-good {
		color: var(--color-success);
	}
</style>
