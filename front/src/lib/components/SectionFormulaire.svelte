<!--
  Une SECTION de formulaire : un intitulé, une séparation, et son contenu.

  POURQUOI CE COMPOSANT (16/08/2026). L'ordre des champs avait été fixé — Titre,
  champs spécifiques, Workflow, Périmètre, Destinataires, Description, Photos,
  Documents, Diffusion — mais **rien ne le montrait à l'écran** : les champs se
  suivaient sans respiration, et l'utilisateur a demandé le sous-titre manquant
  avant de constater qu'aucune section n'était nommée nulle part.

  « Sépare bien chaque section, il y a peut-être l'UX à revoir pour cela. »

  Ordonner ne suffit pas : une suite de dix champs sans repère se lit comme une
  liste, pas comme des groupes de décisions. Le titre dit CE QU'ON DÉCIDE ici
  (à qui ça s'adresse, comment ça se diffuse), le filet le sépare de ce qui suit.

  DEUX NIVEAUX DE MARQUAGE, volontairement discrets :
    • un intitulé en petites capitales — il structure sans concurrencer les
      libellés de champs, qui restent l'information principale ;
    • un filet fin au-dessus, sauf pour la première section : un trait avant le
      premier groupe séparerait la section de son propre titre de formulaire.

  ## Le titre EST le libellé quand la section n'a qu'un champ (16/08/2026)

  Première livraison, l'écran affichait :

      PÉRIMÈTRE
      Périmètre *                      [Copropriété entière]

  Le nom deux fois de suite, en deux typographies. Signalé par l'utilisateur,
  capture à l'appui, dès la mise en production. La redondance venait de ce que le
  champ portait déjà son intitulé (`PerimetrePicker`, `DestinatairePicker`,
  `FichiersUpload` le portent tous) et que la section en ajoutait un second.

  **Règle** : une section qui ne contient qu'UN champ ne répète pas son nom. Le
  titre de section devient le libellé — il porte l'astérisque du requis (`requis`)
  et le badge d'état (`badge`) —, et le champ n'écrit plus rien (`titre=""`).
  Les sections à PLUSIEURS champs (Détails, Clôture, Diffusion) gardent leur
  titre de groupe **et** les libellés de leurs champs : là, il n'y a pas
  redondance mais hiérarchie.

  ## L'accessibilité y gagne, et ce n'est pas un effet de bord

  `Périmètre *` était un `<div>` : décoratif pour un lecteur d'écran, qui
  annonçait donc un groupe de boutons sans nom. Le titre de section est
  désormais :
    • un vrai `<label for>` quand la section porte un contrôle labelable
      (`<select>`, `<input>`) — l'association est alors native ;
    • un `<h4 id>` sinon, l'appelant reliant son groupe par `aria-labelledby`.
      C'est le cas des pastilles et de l'éditeur riche, qui ne sont PAS des
      contrôles labelables : `for` n'y produirait aucune association, en silence.
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import Icon from './Icon.svelte';
	import { membre } from '#lib/accordeon.ts';
	import EtoileRequis from './EtoileRequis.svelte';
	import ContenuBadge from './ContenuBadge.svelte';

	/** Intitulé de la section — ex. « Diffusion ». Vide : aucun titre, mais la
	    séparation reste, ce qui sert aux groupes évidents (le titre d'un objet). */
	export let titre = '';

	/** Icône du catalogue partagé (`#lib/icones-svg.json`), devant l’intitulé.
	    Les titres portaient des ÉMOJI ; l’en-tête de page, lui, prenait déjà ses
	    tracés dans le catalogue. Deux façons de désigner une section, dont une
	    qui dépend de la police du système (19/08/2026). */
	export let icone = '';

	/** Première section du formulaire : pas de filet au-dessus. */
	export let premiere = false;

	/** Ajoute l'astérisque des champs requis au titre. */
	export let requis = false;

	/**
	 *  Le champ de cette section est-il RENSEIGNÉ ? (#1121, 22/09/2026)
	 *
	 *  🔴 L'astérisque est rouge tant que le champ est vide : c'est l'état du
	 *  champ, plus une décoration. La section ne peut pas le deviner — « vide »
	 *  n'a pas le même sens pour un texte, une liste ou une date —, donc
	 *  l'appelant le dit.
	 *
	 *  ⚠️ Non renseigné **par défaut**, et c'est le choix prudent : une section
	 *  obligatoire dont personne ne dit l'état s'affiche comme un travail qui
	 *  reste à faire, jamais comme un travail fait.
	 */
	export let rempli = false;

	/** État résumé, à droite du titre — « Copropriété entière », « Tous les
	    résidents ». On lit ce qui est retenu sans dépiler les pastilles
	    (`ux-patterns` §9 quater). Vide : aucun badge. */
	export let badge = '';
	/** Les icônes du badge, et celle qui le termine — la pastille de lecture
	    des Destinataires (25/09/2026), la même qu'en carte (`ContenuBadge`). */
	export let badgeIcones: string[] = [];
	export let badgeIconeFin = '';

	/** `id` du contrôle labelable unique de la section : le titre devient alors
	    un `<label for>`. Ne l'utiliser QUE pour `<select>`, `<input>`, `<textarea>` —
	    sur un `contenteditable` ou un groupe de boutons, `for` n'associe rien. */
	export let pour = '';

	/** `id` posé sur le titre, pour qu'un groupe s'y relie par `aria-labelledby`. */
	export let idTitre = '';

	/**
	 * **Repliée par défaut** — la section se réduit à son intitulé et à un
	 * résumé d'une ligne, cliquables (#1095).
	 *
	 * 🔴 La valeur vient de la DÉCLARATION (`section(ENTITE, id).pliee`), jamais
	 * d'un choix d'écran : la règle est *obligatoire → déplié · facultatif →
	 * plié*, et `lint:etats` la vérifie. Un écran qui plierait de son côté
	 * rouvrirait la divergence que le cadre existe pour fermer.
	 */
	export let pliable = false;

	/**
	 * Ce qu'on lit quand elle est pliée — « sans date », « en mon nom », « rien
	 * ne part à l'extérieur ».
	 *
	 * ⚠️ Il doit dire l'ÉTAT, jamais l'invitation : « sans date » et non
	 * « ajouter une date ». Une section pliée se lit comme une ligne de résumé,
	 * pas comme un bouton de plus.
	 */
	export let resume = '';

	/**
	 * 🔴 **La valeur diffère-t-elle du défaut ?** Elle gouverne TROIS choses.
	 *
	 * C'est la moitié non déclarative du cadre : elle dépend de ce que l'objet
	 * PORTE, pas de ce que la table dit.
	 *
	 * | | valeur par défaut | valeur modifiée |
	 * |---|---|---|
	 * | la section | peut être pliée | s'ouvre, et **ne se replie plus** |
	 * | sa pastille | verte | bleue |
	 *
	 * ⚠️ Elle s'appelait `valeurModifiee` — un nom qui décrivait son
	 * EFFET d'alors, quand elle n'en avait qu'un. Renommée le 22/09/2026 : un
	 * nom qui dit le geste n'est appelé que par ce geste, et les deux autres
	 * usages auraient été réécrits à côté (c'est ce qui est arrivé à
	 * `peut_commander`, #1028, vingt-six fois).
	 *
	 * 🔴 **Pliée ⟺ valeur par défaut**, et c'est un invariant, pas un effet :
	 * une section pliée qui cacherait une valeur saisie serait pire que pas de
	 * pliage du tout — on corrigerait un objet sans voir ce qu'il contient.
	 * C'est ce qui rend la vignette de droite TOUJOURS verte.
	 */
	export let valeurModifiee = false;

	/**
	 * 🔒 **Inactive** — le motif pour lequel la section ne s'applique pas ici, ou
	 * vide (23/09/2026, arbitré à l'écran avec maquette).
	 *
	 * Demandé : un seul formulaire pour les affaires et les actualités, *« toutes
	 * les sections, grisées, pliées et inactives pour celles inappropriées pour
	 * la catégorie, qui doivent être sans données »*. La section reste à son rang
	 * — on voit ce qui s'éteint en changeant de catégorie —, mais :
	 *
	 *   - elle est pliée, atténuée, marquée « sans objet », et ne se déplie pas ;
	 *   - son CONTENU n'est pas rendu : aucun champ, donc aucune donnée à envoyer ;
	 *   - son motif est ÉCRIT sur la ligne — au doigt il n'y a pas de survol.
	 *
	 * La valeur vient de la déclaration (`motifInactif`), jamais d'un écran.
	 */
	export let inactive = '';

	let ouverteParLUtilisateur = false;

	//  🔴 L'ACCORDÉON (30/09/2026, arbitré : « partout, formulaires compris »).
	//  Déplier une section replie celles que l'utilisateur avait dépliées. Celles
	//  dont la valeur a changé restent ouvertes quoi qu'il arrive — `ouverte`
	//  ci-dessous l'impose, et c'est l'exception arbitrée : on ne cache jamais une
	//  saisie. Les sections non pliables n'entrent pas dans le groupe.
	const accordeon = membre('sections-formulaire', () => (ouverteParLUtilisateur = false));
	onDestroy(accordeon.liberer);
	let section: HTMLElement;
	function deplier() {
		ouverteParLUtilisateur = true;
		accordeon.prendre(section);
	}
	/**  Se replier est possible — tant que la valeur est celle du défaut.
	 *
	 *   ⚠️ Arbitré à l'écran le 22/09/2026 : *« pour une section pliée qui est
	 *   dépliée, si on reclique sur le titre on la replie uniquement si on n'a
	 *   pas changé la valeur par défaut »*. En création comme en édition. */
	$: ouverte = !pliable || valeurModifiee || ouverteParLUtilisateur;
	$: replialbe = pliable && ouverte && !valeurModifiee;
	const idContenu = `sect-${Math.random().toString(36).slice(2, 9)}`;
</script>

<section
	bind:this={section}
	class="section-formulaire"
	class:premiere
	class:repliee={(pliable && !ouverte) || !!inactive}
>
	{#if inactive}
		<div class="section-pliee section-inactive" aria-disabled="true">
			<span class="section-titre section-titre-plie">
				<span aria-hidden="true">&#x1F512;</span><span
					class="section-titre-texte"
					id={idTitre || undefined}>{titre}</span
				>
			</span>
			<!--  La pastille de résumé, en GRIS : même place et même forme que
			      « sans date », pour dire qu'il n'y a rien à ouvrir ici. -->
			<span class="badge badge-gray section-resume">sans objet</span>
			<span class="section-motif">{inactive}</span>
		</div>
	{:else if pliable && !ouverte}
		<!--  🔴 Un vrai `<button>`, et non un `<div role="button">` : il faut le
		      clavier, le focus et l'annonce d'état sans rien réécrire. La cible
		      fait 44 px de haut (`standards/11` §10). -->
		<button
			type="button"
			class="section-pliee"
			aria-expanded="false"
			aria-controls={idContenu}
			on:click={deplier}
		>
			<!--  `idTitre` AUSSI sur le titre plié (#1329) : le contenu reste dans la
			      page, et ce qui s'y rattache (`aria-labelledby`) pointait sur un
			      identifiant absent tant que la section était pliée. -->
			<span class="section-titre section-titre-plie">
				{#if icone}<Icon name={icone} size={15} />{/if}<span
					class="section-titre-texte"
					id={idTitre || undefined}
					>{titre}{#if requis}<EtoileRequis vide={!rempli} />{/if}</span
				>
			</span>
			<span class="badge badge-green section-resume"
				>{#if resume}{resume}{:else}<ContenuBadge
						icones={badgeIcones}
						texte={badge}
						icone={badgeIconeFin}
					/>{/if}</span
			>
			<svg
				class="section-chev"
				width="12"
				height="8"
				viewBox="0 0 12 8"
				fill="none"
				stroke="currentColor"
				stroke-width="1.6"
				aria-hidden="true"><path d="M1 1l5 5 5-5" /></svg
			>
		</button>
	{/if}
	{#if titre && ouverte && !inactive}
		{#if pour}
			<label class="section-titre" for={pour} id={idTitre || undefined}>
				{#if icone}<Icon name={icone} size={15} />{/if}<span class="section-titre-texte"
					>{titre}{#if requis}<EtoileRequis vide={!rempli} />{/if}</span
				>
				{#if badge}<span
						class="badge section-badge"
						class:badge-green={!valeurModifiee}
						class:badge-bleu={valeurModifiee}
						><ContenuBadge icones={badgeIcones} texte={badge} icone={badgeIconeFin} /></span
					>{/if}
			</label>
		{:else}
			<h4 class="section-titre" id={idTitre || undefined}>
				{#if icone}<Icon name={icone} size={15} />{/if}<span class="section-titre-texte"
					>{titre}{#if requis}<EtoileRequis vide={!rempli} />{/if}</span
				>
				{#if badge}<span
						class="badge section-badge"
						class:badge-green={!valeurModifiee}
						class:badge-bleu={valeurModifiee}
						><ContenuBadge icones={badgeIcones} texte={badge} icone={badgeIconeFin} /></span
					>{/if}
				<!--  🔴 Replier est un GESTE, donc un `<button>` — et il n'existe que
				      quand il est permis. Une commande visible qui ne ferait rien dit
				      au doigt que le geste a échoué, jamais qu'il était interdit.

				      ⚠️ Il est absent d'un `<label for>` : un bouton à l'intérieur
				      d'un label vole le clic destiné au champ. Ces sections-là se
				      replient par leur résumé, comme avant. -->
				{#if replialbe}
					<button
						type="button"
						class="section-replier"
						aria-expanded="true"
						aria-controls={idContenu}
						aria-label="Replier la section {titre}"
						on:click={() => (ouverteParLUtilisateur = false)}
					>
						<svg
							width="12"
							height="8"
							viewBox="0 0 12 8"
							fill="none"
							stroke="currentColor"
							stroke-width="1.6"
							aria-hidden="true"><path d="M11 7L6 2 1 7" /></svg
						>
					</button>
				{/if}
			</h4>
		{/if}
	{/if}
	{#if !inactive}
		<div id={idContenu} hidden={!ouverte}>
			<!--  🔴 CACHÉ, jamais démonté. Un `{#if}` détruirait les champs, et avec
		      eux l'état interne des composants qu'ils portent — un éditeur riche,
		      une liste de pièces jointes en cours de téléversement. `hidden` les
		      retire aussi de l'ordre de tabulation, ce qu'un simple `display:none`
		      appliqué plus loin ne garantirait pas. -->
			<slot />
		</div>
	{/if}
</section>

<style>
	/*  ⚠️ L'écart sous le filet vaut la MOITIÉ de celui du dessus, et c'est
	    voulu : le trait appartient à la section qui commence, pas à celle qui
	    finit. À 0.9rem des deux côtés, le titre flottait au milieu et l'œil ne
	    savait plus à quel groupe il se rattachait — signalé à l'écran le
	    22/09/2026, capture à l'appui. */
	.section-formulaire {
		border-top: 1px solid var(--color-border);
		padding-top: 0.45rem;
		margin-top: 0.9rem;
	}
	/*  🔴 Une section REPLIÉE respire deux fois moins (22/09/2026).

	    Signalé à l'écran, capture à l'appui : *« l'espacement avant et après une
	    section repliée est trop grand, divise-le par 2 »*. Une ligne de résumé
	    n'a pas de contenu à séparer de son titre — elle EST son titre. L'air que
	    mérite un groupe de champs la faisait flotter au milieu de rien.

	    ⚠️ L'écart ne tombe QUE quand elle est fermée. Dépliée, elle redevient
	    un groupe comme les autres et reprend l'espacement commun : sinon
	    l'ouverture déplacerait tout ce qui suit d'un demi-centimètre, et le
	    regard perdrait la ligne qu'il venait de cliquer.

	    ⚠️ La HAUTEUR de la ligne, elle, ne bouge pas : `min-height: 44px` dans
	    la charte. C'est ce que `e2e/cible-tactile` mesure — resserrer l'air
	    autour est gratuit, resserrer la cible ne l'est pas. */
	.repliee {
		padding-top: 0.225rem;
		margin-top: 0.45rem;
	}
	/*  La première section n'est séparée de rien : le titre de la boîte
	    (`FormulaireCreation`) joue déjà ce rôle au-dessus d'elle. */
	.premiere {
		border-top: none;
		padding-top: 0;
		margin-top: 0;
	}
	/*  Petites capitales : l'intitulé de section se lit comme un repère de
	    structure. Il était gris ; il reprend la couleur du texte depuis qu'il
	    porte AUSSI le libellé du champ, l'astérisque du requis et le badge —
	    un intitulé de champ en gris clair se lit moins bien que ce qu'il nomme. */
	.section-titre {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin: 0 0 0.6rem;
		font-size: var(--fs-2xs);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text);
	}
	/*  🔴 L'astérisque appartient au TEXTE, pas à la rangée (22/09/2026).

	    `.section-titre` est un conteneur flex avec `gap: .4rem` — l'écart qui
	    sépare proprement l'icône du libellé. Un nœud de texte nu y est un enfant
	    anonyme : l'astérisque, posée à côté de `{titre}`, recevait donc le même
	    écart et s'affichait « PÉRIMÈTRE * ». Le code l'écrivait collée, et le
	    composant la rendait collée : c'est la MISE EN PAGE qui les séparait.

	    ⚠️ Signalé à l'écran, capture à l'appui, le lendemain de sa livraison.
	    Aucune relecture de code ne pouvait le montrer — il fallait regarder. */
	.section-titre-texte {
		display: inline;
	}

	/*  Un `<label>` de section désigne un contrôle : il doit se cliquer. */
	label.section-titre {
		cursor: pointer;
	}
	/*  ── La section PLIÉE ───────────────────────────────────────
	    🔴 `.section-pliee` vit dans la CHARTE (`composants.css`) depuis le
	    22/09/2026, et pas ici : elle porte une cible tactile de 44 px, qui est une
	    règle de charte (`standards/11` §10) et non une décision de composant.

	    Svelte scope les styles au fichier : enfermée ici, elle était
	    **invisible à tout contrôle extérieur** — un test de navigateur qui pose
	    son propre témoin mesurait 21 px, faute de règle, et aurait conclu à un
	    défaut inexistant. Même cas que `.sr-only` la veille.

	    Ce qui RESTE ici est ce qui appartient vraiment à ce composant : la marge
	    du titre plié, la vignette de résumé, le chevron. */
	/*  Le titre d'une section pliée ne porte pas sa marge du bas : il n'a rien
	    en dessous de lui. */
	.section-titre-plie {
		margin: 0;
		flex-shrink: 0;
	}
	/*  Le résumé pousse le chevron au bout et se coupe avant lui.

	    🔴 VIGNETTE VERTE, et non plus du texte gris (22/09/2026). Une section
	    pliée porte forcément la valeur par défaut — c'est l'invariant du cadre,
	    puisqu'une valeur modifiée l'ouvre et l'empêche de se refermer. Le vert
	    dit donc exactement ce qu'il y a à savoir : *rien n'a été touché ici*.
	    Il n'y a jamais de vignette bleue à droite, pour la même raison.

	    ⚠️ `max-width` plutôt qu'une largeur libre : un résumé long
	    (« rien ne part à l'extérieur ») doit se couper avant le chevron, et un
	    badge ne se coupe pas tout seul. */
	.section-resume {
		margin-left: auto;
		min-width: 0;
		max-width: 60%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--fs-2xs);
		text-transform: none;
		letter-spacing: normal;
		font-weight: 600;
	}
	/*  🔒 La section INACTIVE — style « A » arbitré à l'écran le 23/09/2026,
	    captures à l'appui : les hachures du premier jet étaient « moches ».
	    Titre atténué précédé du cadenas, pastille grise « sans objet » à la
	    place du résumé, et le motif en petite ligne SOUS le titre — écrit, car
	    au doigt il n'y a pas de survol. Pas de curseur de clic : rien ne s'y
	    ouvre. */
	.section-inactive {
		cursor: default;
		flex-wrap: wrap;
		row-gap: 0.15rem;
		color: var(--color-text-muted);
	}
	.section-inactive .section-titre {
		color: var(--color-text-muted);
	}
	.section-motif {
		flex-basis: 100%;
		min-width: 0;
		padding-left: 1.4rem;
		font-size: var(--fs-xs);
		line-height: 1.35;
	}
	.section-chev {
		flex-shrink: 0;
		color: var(--color-text-muted);
	}
	/*  Le badge ne suit PAS les petites capitales du titre : c'est une valeur,
	    pas un intitulé — la lire en majuscules espacées la rendrait illisible. */
	.section-badge {
		font-size: var(--fs-2xs);
		text-transform: none;
		letter-spacing: normal;
		font-weight: 600;
	}
	/*  🔴 Le bleu de la valeur MODIFIÉE (22/09/2026, arbitré à l'écran).

	    `--color-info` de la charte : il dit « ce n'est plus le défaut » sans
	    juger. L'ambre aurait dit « attention », l'or est déjà pris par le
	    repère du carnet d'entretien — deux sens sur le même écran.

	    ⚠️ Il n'existe qu'à côté du TITRE, jamais à droite : une valeur
	    modifiée ouvre la section, donc il n'y a plus de ligne pliée à décorer. */
	.badge-bleu {
		background: var(--color-info-fond);
		color: var(--color-info);
	}
	/*  Le chevron de repli : même poids visuel que celui du dépliage, et une
	    cible tactile qui tient (`standards/11` §10). */
	.section-replier {
		margin-left: auto;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 44px;
		min-height: 44px;
		margin-top: -0.5rem;
		margin-bottom: -0.5rem;
		padding: 0;
		border: none;
		background: none;
		cursor: pointer;
		color: var(--color-text-muted);
	}
	@media (hover: hover) and (pointer: fine) {
		.section-replier:hover {
			color: var(--color-text);
		}
	}
</style>
