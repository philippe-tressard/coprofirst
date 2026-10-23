<!--
  Une PASTILLE DÉROULANTE — le choix d'une liste LONGUE, à l'allure d'une
  pastille (24/09/2026, arbitré avec l'utilisateur sur les Petites annonces).

  ## Pourquoi

  Le seuil des listes courtes (`ux-patterns` §0, #491) laisse une liste de plus
  de six entrées en `<select>` : neuf catégories d'annonce en pastilles
  rempliraient l'écran. Mais le `<select>` restait NATIF — coins carrés, fond
  gris, police plus grande, hauteur différente — posé à côté d'une rangée de
  pastilles arrondies. Signalé à l'écran : *« son UX dénote à côté du filtre »*.

  R3 dit « toute sélection en pastilles arrondies, jamais un `<select>` nu ».
  Ce composant réconcilie les deux règles : au-delà du seuil, UNE pastille qui
  ouvre la liste.

  ## Ce qui est gardé du `<select>` natif, et pourquoi

  Le `<select>` est toujours là, rendu transparent sur toute la pastille : c'est
  lui qu'on touche. On garde ainsi la roue de sélection du téléphone, la
  navigation au clavier et l'annonce par le lecteur d'écran — une liste
  déroulante réécrite à la main les perd toutes, et c'est la partie qu'on
  oublie (`standards/11-interface-et-ux.md` §2).

  ## Deux usages, qui ne se lisent pas pareil

  - un **filtre** : il offre l'entrée « Toutes… » (`tous`) et se REMPLIT en
    bleu dès qu'il filtre — comme une pastille retenue. Un filtre actif doit se
    voir sans lire son libellé ;
  - un **tri** (`tri`) : un ORDRE, jamais vide, donc jamais « retenu » ; il
    porte l'icône ⇅ et se cale à droite de la barre. Il est la seule exception
    au seuil (`lint:seuil-listes`) : trier n'est pas filtrer, et trois pastilles
    de tri à côté de quatre pastilles de type se liraient comme un seul filtre.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';

	export let options: readonly { val: string; label: string }[] = [];

	/** La valeur retenue. Chaîne vide = pas de filtre (jamais pour un tri). */
	export let valeur = '';

	/** Le libellé de l'entrée qui ne filtre pas — ignoré pour un tri. */
	export let tous = 'Tous';

	/** Ce que la liste choisit — son nom accessible (la pastille n'a pas de libellé visible). */
	export let libelle: string;

	/** Un ORDRE plutôt qu'un filtre : pas d'entrée vide, jamais remplie, calée à droite. */
	export let tri = false;

	$: active = !tri && valeur !== '';
</script>

<span class="pastille-deroulante" class:active class:tri>
	{#if tri}
		<span class="icone icone-tete" aria-hidden="true"><Icon name="arrow-up-down" size={13} /></span>
	{/if}
	<select bind:value={valeur} aria-label={libelle}>
		{#if !tri}<option value="">{tous}</option>{/if}
		{#each options as o (o.val)}<option value={o.val}>{o.label}</option>{/each}
	</select>
	<span class="icone icone-chevron" aria-hidden="true"><Icon name="chevron-down" size={14} /></span>
</span>

<style>
	/*  Les mesures sont celles de `Pastille.svelte` — bordure, rayon, police,
	    couleurs, durée — et c'est tout l'objet : posée dans une rangée de
	    pastilles, elle doit en être une. */
	.pastille-deroulante {
		position: relative;
		display: inline-flex;
		align-items: center;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: var(--color-surface);
		color: var(--color-text-muted);
		font-size: var(--fs-md);
		transition:
			color var(--duree-geste),
			background-color var(--duree-geste),
			border-color var(--duree-geste),
			transform var(--duree-geste) var(--ease-out);
	}
	/*  Le `<select>` occupe TOUTE la pastille : la cible est la pastille entière,
	    pas le seul texte. Les icônes sont posées par-dessus, sans capter le clic. */
	.pastille-deroulante select {
		appearance: none;
		-webkit-appearance: none;
		border: 0;
		margin: 0;
		background: transparent;
		color: inherit;
		font: inherit;
		/*  La hauteur d'une `Pastille` voisine, dont la ligne est haussée par
		    l'emoji de son libellé : mesurée au navigateur, 30 px au bureau et
		    23 px sur téléphone. */
		line-height: 1.3;
		/*  🔴 Les icônes sont en PIXELS (prop `size`), les marges en `rem` : sous
		    768 px la racine passe à 14 px (`normes.css`, 12 jusqu'à #2165), et une marge de 1,7 rem
		    ne couvrait plus le chevron — le texte passait dessous. La réserve se
		    calcule donc à partir de l'icône, pas à côté d'elle. */
		padding: 0.35rem calc(0.6rem + 14px + 0.3rem) 0.35rem 0.75rem;
		border-radius: inherit;
		cursor: pointer;
		/*  La largeur suit l'entrée RETENUE, pas la plus longue : sans cela la
		    pastille garde la place de « Parking / Cave » quand elle dit « Divers ».
		    Là où `field-sizing` n'existe pas, le navigateur garde son calcul
		    habituel — rendu plus large, jamais faux. */
		field-sizing: content;
		width: auto;
		max-width: 100%;
		text-overflow: ellipsis;
	}
	.pastille-deroulante.tri select {
		padding-left: calc(0.7rem + 13px + 0.35rem);
	}
	/*  Le focus se voit sur la pastille, puisque c'est elle qu'on regarde — même
	    contour que `Pastille`. */
	.pastille-deroulante select:focus {
		outline: none;
	}
	.pastille-deroulante:has(select:focus-visible) {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	/*  🔴 Les ENTRÉES reprennent les couleurs du texte : sous Windows, une
	    `<option>` hérite de la couleur du `<select>` — blanche quand la pastille
	    est remplie, donc un texte blanc sur une liste blanche. */
	.pastille-deroulante option {
		color: var(--color-text);
		background: var(--color-surface);
	}
	.icone {
		position: absolute;
		top: 50%;
		transform: translateY(-50%);
		display: inline-flex;
		pointer-events: none;
	}
	.icone-tete {
		left: 0.7rem;
	}
	.icone-chevron {
		right: 0.6rem;
		opacity: 0.7;
	}
	/*  Le tri se cale à DROITE de la barre : un ordre ne se lit pas comme un
	    filtre, et le séparer d'eux le dit sans un mot de plus. */
	.pastille-deroulante.tri {
		margin-left: auto;
	}
	.pastille-deroulante.active {
		background: var(--color-primary);
		border-color: var(--color-primary);
		color: var(--color-surface);
	}
	.pastille-deroulante.active .icone-chevron {
		opacity: 0.9;
	}
	/*  L'appui, comme `Pastille` : 97 %, `transform` seul. Pas coupé sous
	    `prefers-reduced-motion` — c'est un retour d'état, pas un mouvement
	    (`composants.css`, les boutons). */
	.pastille-deroulante:active {
		transform: scale(0.97);
	}
	/*  Le survol ne sert qu'à la souris : au doigt, `:hover` reste collé après le
	    toucher (`ux-patterns` §17). */
	@media (hover: hover) and (pointer: fine) {
		.pastille-deroulante:not(.active):hover {
			border-color: var(--color-primary);
			color: var(--color-text);
		}
	}
</style>
