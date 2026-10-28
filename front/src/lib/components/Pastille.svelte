<!--
  LA pastille de sélection — le bouton arrondi qu'on trouve sur Périmètre,
  Destinataires, les filtres et les profils. Un seul objet, qui porte son
  balisage ET son style.

  POURQUOI CE COMPOSANT EXISTE (16/08/2026, régression livrée en v2.67.11).
  Ces règles ne vivaient que dans `PerimetrePicker.svelte`, donc scopées à lui
  par Svelte. Le jour où un second composant a repris le même balisage (l'ancien
  `SelecteurCiblage`, qui servait au ciblage des sondages avant que celui-ci
  rejoigne le standard le 16/08/2026), il a hérité de la structure SANS le
  style : les pastilles sont parties en production nues, sous forme de
  rectangles collés — « Bâtiment 1Bâtiment 2Bâtiment 3 ».

  ⚠️ RIEN NE L'AVAIT SIGNALÉ, et c'est le vrai enseignement. `svelte-check` sait
  dire qu'un sélecteur défini n'est pas utilisé ; il ne sait PAS dire qu'une
  classe utilisée n'est définie nulle part. Le contrôle qui a sauvé les autres
  extractions (« aucun Unused CSS selector nouveau ») est aveugle dans ce sens-là.

  Et la réparation évidente — monter `.pill` dans `app.css` — a été écartée par
  l'utilisateur : « le CSS doit être associé à l'objet pour ne pas avoir des
  divergences ». Un style séparé de son balisage peut être modifié d'un côté sans
  l'autre ; réunis dans un composant, ils ne peuvent plus diverger, et le style
  ne peut plus manquer à l'appel puisqu'il voyage avec.

  UTILISATION :
    <Pastille active={…} on:click={…}>Bâtiment 1</Pastille>
    <Pastille active icone="building-2" chevron>Bâtiment 2</Pastille>
    <Pastille petite active={…}>Hall</Pastille>
    <Pastille active={…}>
      Plomberie
      <span slot="detail">fuites, sanitaires</span>
    </Pastille>
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import Compte from '$lib/components/Compte.svelte';

	/** Pastille retenue — fond plein. */
	export let active = false;

	/**  Un repère de CATÉGORIE, porté par le bord gauche (22/09/2026, #1146).
	 *
	 *   🔴 Il ne touche ni au libellé ni à l'état retenu : c'est tout l'intérêt
	 *   d'un liseré sur un emoji. Il survit au fond bleu de la pastille active,
	 *   là où l'emoji s'y noyait.
	 *
	 *   ⚠️ Il coexiste avec `privatif`, qui habille DÉJÀ la bordure (pointillés).
	 *   Une catégorie du carnet dans un périmètre privatif est un cas réel : les
	 *   deux règles portent sur des côtés différents et ne se contredisent pas. */
	export let marquee = false;
	/**  Ce qu'un lecteur d'écran annonce du repère — OBLIGATOIRE avec `marquee` :
	 *   un liseré n'a aucun équivalent parlé. */
	export let marqueAide = '';

	/**  Une pastille EN TÊTE de sa grille, qui ouvre un autre CHEMIN que les
	 *   autres (23/09/2026, variante A arbitrée à l'écran) : « Actualité » —
	 *   on informe — avant les catégories de suivi — on fait traiter. Pleine
	 *   ligne, bord « information » de la charte, fond blanc. Retenue, elle reprend l'aplat
	 *   commun : son état se lit comme celui des autres. */
	export let enTete = false;

	/** Variante réduite, pour un second niveau de précision. */
	export let petite = false;

	/**  Cet espace est-il PRIVATIF — un logement, une cave, une place attribuée ?
	 *   Demandé le 31/08/2026 : l'arborescence n'avait pas de mot pour dire que
	 *   « Logement » est chez quelqu'un quand « Hall d'entrée » est à tout le
	 *   monde, alors que c'est la première question devant une demande.
	 *
	 *   Le repère est un **contour discontinu** : il se lit sans couleur — donc
	 *   sans entrer en concurrence avec l'état RETENU, qui est le plein — et sans
	 *   ajouter de symbole, la pastille portant déjà son icône.
	 *
	 *   ⚠️ **L'appelant ne le passe QUE sur une pastille pleine.** Dès qu'une
	 *   rangée se contracte, la pastille résume plusieurs espaces à la fois : un
	 *   contour qui dirait « privatif » y parlerait d'un seul d'entre eux. Le
	 *   repère disparaît donc avec la contraction, ce qui est la règle demandée. */
	export let privatif = false;

	/** Icône Lucide facultative, affichée avant le libellé. */
	export let icone = '';

	/** Chevron « › » : annonce qu'un second niveau existe derrière cette pastille.
	    Sans lui, rien n'indiquait qu'un bâtiment cachait neuf espaces, et personne
	    ne cliquait (signalé le 12/08/2026). */
	export let chevron = false;

	/**
	 * Rendre un **vrai bouton radio** plutôt qu'un `<button>` — `{ nom, valeur }`,
	 * `nom` étant le groupe et `valeur` ce que cette pastille sélectionne.
	 *
	 * ## Pourquoi (30/08/2026, signalé à l'écran)
	 *
	 * > « Dans tickets tu ne peux pas réduire ces pastilles à la même taille que
	 * >   nouveau prestataire »
	 *
	 * Les cinq catégories de ticket étaient des cartes maison (`.cat-option`,
	 * grille à deux colonnes, bordure 2 px, padding double) — deux fois plus
	 * hautes que les pastilles du même site, pour la même question posée à
	 * l'utilisateur.
	 *
	 * 🔴 **Elles ne pouvaient PAS être converties jusqu'ici**, et `ux-patterns` le
	 * disait : *« un vrai `radiogroup` avec des `<input type="radio">` ne se
	 * convertit pas — `Pastille` rend un `<button>`, la navigation par flèches et
	 * l'annonce du lecteur d'écran y seraient perdues. L'uniformité ne se paie pas
	 * en accessibilité. »*
	 *
	 * L'argument reste juste. Ce qui change, c'est la réponse : **on enrichit
	 * l'objet au lieu de le contourner.** Avec `radio`, la pastille rend un
	 * `<label>` portant un `<input type="radio">` visuellement masqué — apparence
	 * de pastille, sémantique de radiogroup, flèches et lecteur d'écran intacts.
	 *
	 * ⚠️ Le `<input>` est masqué par `clip`, **jamais par `display:none`** : ce
	 * dernier le retire de l'ordre de tabulation et de l'arbre d'accessibilité,
	 * c'est-à-dire qu'il annule très exactement ce que ce mode existe pour
	 * préserver. C'est ce que faisait `.cat-option input[type='radio']`.
	 */
	export let radio: { nom: string; valeur: string } | null = null;

	/**  Une pastille qui s'ACTIVE ou se DÉSACTIVE, indépendamment des autres
	 *   (08/10/2026, éléments du pied de page) : `aria-pressed` dit son état au
	 *   lecteur d'écran, que le fond plein ne lui dit pas. Laissé à `undefined`,
	 *   l'attribut n'est pas rendu : un choix exclusif n'est pas un interrupteur. */
	export let bascule = false;

	/**  Combien d'éléments la liste filtrée montre — en vignette `Compte`
	 *   après le libellé (10/10/2026). `null` : rien, la pastille reste telle
	 *   qu'elle était chez tous les autres appelants.
	 *
	 *   🔴 Montré sur la pastille RETENUE seulement (maquette J arbitrée à
	 *   l'écran) : un nombre dans chaque pastille chargeait la rangée — dix
	 *   vignettes Bleu Seine pour deux filtres. La règle vit ICI, pas chez
	 *   l'appelant : une rangée donne le même compte à toutes ses pastilles
	 *   (`ChoixPastilles.compte`), la pastille décide s'il se voit. */
	export let compte: number | null = null;
</script>

<!--  ⚠️ `$$slots.detail` et non une prop : c'est le SEUL moyen pour Svelte de
      savoir si l'appelant a fourni un sous-texte. Sans cette condition, la
      pastille passerait en deux lignes chez tout le monde — y compris là où il
      n'y a rien à mettre dessous. -->
{#if radio}
	<!--  Le mode radio : même apparence, sémantique de `radiogroup`. Le contenu
	      est écrit deux fois dans le balisage parce que Svelte n'a pas d'élément
	      « `<button>` ou `<label>` selon le cas » qui accepte un `<slot>` — mais
	      le STYLE, lui, n'existe qu'une fois, et c'est ce qui compte : c'est sa
	      duplication qui produit les divergences (v2.67.11). -->
	<label
		class="pastille"
		class:active
		class:marquee
		class:en-tete={enTete}
		class:petite
		class:privatif
		class:avec-detail={$$slots.detail}
	>
		<input
			type="radio"
			class="pastille-radio"
			name={radio.nom}
			value={radio.valeur}
			checked={active}
			on:change
		/>
		{#if icone}<Icon name={icone} size={15} />{/if}
		<span class="pastille-corps">
			<span class="pastille-libelle"><slot /></span>
			{#if $$slots.detail}<span class="pastille-detail clamp-3"><slot name="detail" /></span>{/if}
		</span>
		{#if compte !== null && active}<Compte n={compte} surAplat />{/if}
	</label>
{:else}
	<button
		type="button"
		class="pastille"
		class:active
		class:marquee
		class:en-tete={enTete}
		class:petite
		class:privatif
		class:avec-detail={$$slots.detail}
		aria-pressed={bascule ? active : undefined}
		on:click
	>
		{#if icone}<Icon name={icone} size={15} />{/if}
		<span class="pastille-corps">
			<span class="pastille-libelle"><slot /></span>
			{#if $$slots.detail}<span class="pastille-detail clamp-3"><slot name="detail" /></span>{/if}
		</span>
		{#if compte !== null && active}<Compte n={compte} surAplat />{/if}
		{#if chevron}<span class="pastille-chevron" aria-hidden="true">›</span>{/if}
		{#if marquee && marqueAide}<span class="sr-only"> — {marqueAide}</span>{/if}
	</button>
{/if}

<style>
	.pastille {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.35rem 0.7rem;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: var(--color-surface);
		font-size: var(--fs-md);
		cursor: pointer;
		color: var(--color-text-muted);
		/*  Les propriétés NOMMÉES, jamais `all` : `all` anime aussi ce qu'une
		    règle voisine change sans le vouloir (largeur, rembourrage), et la
		    rangée se déforme pendant 120 ms. `transform` y figure pour l'appui. */
		transition:
			color var(--duree-geste),
			background-color var(--duree-geste),
			border-color var(--duree-geste),
			box-shadow var(--duree-geste),
			transform var(--duree-geste) var(--ease-out);
		white-space: nowrap;
	}
	/*  L'appui, comme les boutons de la charte (`composants.css`) : 97 %, et
	    `transform` seul pour que la rangée ne tremble pas. Une pastille RETENUE
	    s'enfonce aussi — contrairement à l'icône active, elle n'est pas
	    grossie, donc rien ne la fait retomber sous sa taille. */
	.pastille:active:not(:disabled) {
		transform: scale(0.97);
	}
	/*  PRIVATIF : un contour discontinu au repos.
	    Pas de couleur — elle est prise par l'état retenu — ni de symbole —
	    l'icône du nœud l'occupe déjà. */
	/*  🔴 LE LISERÉ DU CARNET D'ENTRETIEN (#1146, 22/09/2026).

	    Un bord gauche épais en Or Croissy, et les coins de ce côté redeviennent
	    droits : un liseré de 4 px sur un rayon de 999 px se lirait comme une
	    tache, pas comme un trait (`standards/11` : pas de coin arrondi sur une
	    bordure d'un seul côté).

	    ⚠️ Il tient sur les DEUX états — fond blanc et fond bleu — et c'est
	    tout l'intérêt : l'emoji 📒 qu'il remplace disparaissait sur la pastille
	    retenue, ce qui est le moment où le repère compte le plus.

	    ⚠️ Il coexiste avec `privatif`, qui habille la bordure en pointillés :
	    les deux règles portent sur des côtés différents. Une catégorie du carnet
	    dans un périmètre privatif est un cas réel. */
	.pastille.marquee {
		border-left: 4px solid var(--color-accent);
		border-top-left-radius: 0;
		border-bottom-left-radius: 0;
		padding-left: 0.55rem;
	}

	.pastille.en-tete {
		grid-column: 1 / -1;
		/*  Pleine ligne : la borne des pastilles à sous-texte (11 rem, plus bas)
		    ne la concerne pas — elle la réduisait à une vignette. */
		max-width: none;
		border: 1.5px solid var(--color-info);
	}
	/*  ⚠️ Non retenue, elle garde le fond BLANC des autres (23/09/2026) : un
	    fond bleu clair la faisait paraître cochée — signalé à l'écran, sur une
	    capture où c'était « Panne » qui l'était. Seul le bord reste bleu. */
	.pastille.privatif {
		border-style: dashed;
		border-width: 1.5px;
	}

	/*  🔴 ET UN APLAT HACHURÉ UNE FOIS RETENUE (signalé à l'écran le 01/09/2026 :
	    *« une pastille privative active n'est pas très visible »*).

	    Le contour discontinu disparaissait sous l'aplat plein : la bordure et le
	    fond prenaient la même couleur, et le trait n'avait plus rien à trancher.
	    La distinction ne tenait donc que sur les pastilles NON retenues —
	    c'est-à-dire justement celles qu'on ne regarde pas.

	    Le motif reprend l'idée du trait interrompu, à l'échelle du fond : des
	    hachures dans les deux bleus de la charte. Il reste lisible en noir et
	    blanc et ne dépend d'aucune image. Le texte garde son fond uni derrière
	    lui — sans quoi les hachures passeraient sous les lettres. */
	.pastille.privatif.active {
		background-image: repeating-linear-gradient(
			135deg,
			transparent 0,
			transparent 5px,
			rgba(255, 255, 255, 0.28) 5px,
			rgba(255, 255, 255, 0.28) 10px
		);
		border-style: dashed;
		border-color: var(--color-surface);
	}
	/*  `:not(.active)` (10/10/2026) : sans lui, le survol — plus spécifique
	    que `.active` — rendait le texte SOMBRE sur l'aplat Bleu Seine de la
	    pastille qu'on vient de retenir, tant que la souris restait dessus. */
	@media (hover: hover) and (pointer: fine) {
		.pastille:not(.active):hover {
			border-color: var(--color-primary);
			color: var(--color-text);
		}
	}
	.active {
		background: var(--color-primary-plein);
		color: var(--color-sur-plein);
		border-color: var(--color-primary-plein);
	}
	.petite {
		font-size: var(--fs-sm);
		padding: 0.28rem 0.6rem;
	}
	.pastille-chevron {
		margin-left: 0.3rem;
		opacity: 0.6;
	}

	/*  🔴 Le bouton radio est masqué à l'ŒIL, jamais à l'accessibilité.
	    `display: none` l'aurait retiré de l'ordre de tabulation et de l'arbre
	    d'accessibilité — donc annulé la navigation par flèches et l'annonce du
	    lecteur d'écran, c'est-à-dire tout ce que ce mode existe pour préserver.
	    C'est pourtant ce que faisait `.cat-option input[type='radio']`, qu'il
	    remplace. Le découpage à 1 px est le motif standard : l'élément reste
	    focusable et lu, il n'occupe simplement aucune surface. */
	.pastille-radio {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip: rect(0 0 0 0);
		clip-path: inset(50%);
		white-space: nowrap;
		border: 0;
	}
	/*  Le focus clavier doit se VOIR : sans cela, un utilisateur au clavier
	    déplace une sélection invisible. Le contour est porté par la pastille,
	    puisque c'est elle qu'on regarde. */
	.pastille:has(.pastille-radio:focus-visible) {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}

	/*  ── Le SOUS-TEXTE (29/08/2026, arbitré avec l'utilisateur) ──────────────
	    Deux listes portaient une description par option — type de prestataire,
	    catégorie de ticket — et étaient rendues en cartes maison pour cette
	    seule raison. La pastille les accueille désormais plutôt que d'être
	    contournée : c'est l'objet qui s'enrichit, pas un second motif qui naît.

	    ⚠️ Sans `detail`, RIEN ne change : `.pastille-corps` reste en ligne et la
	    pastille garde sa hauteur. Un enrichissement qui modifierait les appelants
	    existants ne serait pas un enrichissement. */
	/*  Le libellé porte le poids ; le sous-texte s'en distingue par la taille et
	    l'opacité, jamais par une couleur qui deviendrait illisible en actif. */
	.pastille-libelle {
		font-weight: inherit;
	}
	.pastille-corps {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-start;
		line-height: 1.25;
	}
	.avec-detail {
		align-items: flex-start;
		padding: 0.45rem 0.8rem;
		border-radius: var(--radius);
		/*  Le sous-texte est une phrase : elle doit pouvoir se replier. */
		white-space: normal;
		text-align: left;
		/*  🔴 Une BORNE, pas une largeur — arbitré à l'écran le 30/08/2026 :
		    *« mets le libellé sur 2 lignes pour diminuer la largeur »*.

		    Sans elle, la pastille s'étire à la longueur de sa phrase la plus
		    longue : « Équipement défectueux, ascenseur, chauffage… » faisait à
		    elle seule le double des autres, et une rangée de cinq débordait de
		    l'écran. Bornée, chaque pastille se replie sur deux lignes et la
		    rangée redevient lisible d'un coup d'œil.

		    ⚠️ `max-width` et non `width` : une pastille au libellé court —
		    « Gestion / Syndic, gestion locative » — reste étroite. Une largeur
		    fixe alignerait au prix d'un vide à droite de chacune.

		    🔴 Resserrée de 13 à 11 rem le 07/09/2026, sur le même arbitrage
		    poursuivi : *« pour le sous-texte, passe à 3 lignes si nécessaire
		    (même hauteur) pour diminuer la largeur »*. À 13 rem, huit catégories
		    de ticket ne tenaient pas sur deux lignes ; à 11 rem, elles y tiennent
		    à quatre par ligne sur un écran ordinaire.

		    Le sous-texte prend alors parfois une troisième ligne — c'est le prix
		    demandé, et il ne coûte rien : `filters--egalisee` étire déjà toutes
		    les pastilles d'une rangée à la hauteur de la plus haute, donc aucune
		    ne se retrouve plus courte que ses voisines. */
		max-width: 11rem;
	}
	.pastille-detail {
		font-size: var(--fs-2xs);
		opacity: 0.75;
		font-weight: 400;
	}
	/*  Sur fond plein, le sous-texte reste lisible : c'est l'opacité qui le
	    distingue, jamais une couleur fixe qui deviendrait illisible en actif. */
	.active .pastille-detail {
		opacity: 0.85;
	}

	/*  Sous 480 px, une pastille à sous-texte prend toute la largeur : côte à
	    côte, deux phrases de six mots débordent (socle 11 §10). */
	@media (max-width: 480px) {
		.avec-detail {
			width: 100%;
		}
	}
</style>
