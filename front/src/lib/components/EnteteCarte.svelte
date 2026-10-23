<!--
  EnteteCarte.svelte — LE haut d'une carte de liste, écrit une fois.

  ## La règle, posée le 18/08/2026 et valable pour TOUT le site

  Une carte de liste se lit dans cet ordre, et il ne se discute pas :

      ┌─────────────────────────────────────────────┐
      │ Titre en gras               actions  ›      │
      │ quatre lignes d'aperçu                      │
      │ tags ······························ date    │
      └─────────────────────────────────────────────┘

  • le **titre**, en gras, tient la première ligne avec les **actions et le
    chevron** ancrés à droite ; il occupe tout le reste, sur une ou deux lignes ;
  • puis l'**aperçu**, quatre lignes environ ;
  • **en dernier** : tags à gauche (workflow, périmètre, confidentiel, auteur),
    date à droite.

  🔴 Cet ordre a été **dicté à l'écran le 18/09/2026**, capture à l'appui :
  *« Titre en gras (à gauche) et icônes à droite sur la 1ʳᵉ ligne · Description
  (extrait sur 4 lignes environ) · Pastilles en dernière ligne comme sur le fil
  d'actualité »*. C'est le fil d'activité qui fait référence, comme pour le
  survol et pour le geste de dépliage.

  ⚠️ L'aperçu passe donc PAR CE COMPOSANT (`slot="apercu"`), alors que chaque
  carte le rendait après lui. Sans cela, les tags ne pouvaient pas descendre
  en dessous : l'aperçu est un frère de l'en-tête, pas un enfant, et aucun
  `order` CSS ne fait passer un élément sous le frère d'un autre parent.

  ## Pourquoi (signalé à l'écran, capture à l'appui)

  Le titre partageait sa ligne avec les tags, la date et les icônes d'action.
  Sur un téléphone, **il disparaissait purement et simplement** : la ligne étant
  en `flex` avec `text-overflow: ellipsis`, les badges de largeur fixe gagnaient
  et le titre se réduisait à trois points. On lisait une liste d'actualités sans
  savoir de quoi elles parlaient.

  C'est **R1** au sens propre : la responsivité appartient au squelette, une
  seule fois pour toutes les pages. Chaque carte qui recomposait son en-tête
  avait sa propre façon de mal se replier.

  ## ⚠️ La ligne de méta EST la place du résumé d'une carte repliée

  Signalé à l'écran le 18/09/2026 — *« trop d'espace perdu »* — sur la fiche d'un
  membre d'annuaire : elle posait son résumé SOUS l'en-tête, et la ligne de méta
  ne portait plus que les deux icônes d'action. Trois lignes là où deux
  suffisent : 114 px par fiche au lieu de 79, mesurés au navigateur.

  Ce n'est pas une erreur de style, c'est une méprise sur ce composant : la ligne
  `tags` n'est pas réservée aux badges, elle est la ligne de **méta**. Tout ce qui
  décrit une carte repliée — lieu, état, pastilles — y va, et rien ne s'écrit en
  dessous tant qu'elle n'est pas dépliée.

  ## Les actions sont sur la ligne du TITRE (18/09/2026, demandé à l'écran)

  Elles vivaient sur la ligne de méta, avec la date et le chevron. Demandé :
  *« l'UX standard met les icônes édition/supprimer sur la 1ʳᵉ ligne »*.

  ⚠️ Ce n'est PAS un retour au défaut de R1, et ça se mesure plutôt que ça ne se
  suppose. Le défaut d'origine était un titre sur **une seule ligne**, en
  `text-overflow: ellipsis`, partageant sa place avec les tags ET la date ET les
  actions : les éléments de largeur fixe gagnaient et il ne restait que trois
  points. Ici les **tags restent en dessous**, et le titre est en `clamp-2` — il
  se replie sur deux lignes au lieu de se couper.

  Relevé sur la carte la plus chargée du site (un ticket : quatre icônes, un
  chevron, trois tags et une date), à 375 px :

  | | largeur du titre | tronqué ? |
  |---|---|---|
  | avant | 336 px | non |
  | après | 186 px | **non** |

  Et la ligne de méta, libérée de la date des actions, affiche enfin le nom de
  l'auteur en entier — il était coupé à « Marc FE… ».

  La **date reste en bas** à droite : la remonter aussi aurait pris 70 px de plus
  au titre pour une information qu'on lit rarement en premier.

  ## Le geste est ASYMÉTRIQUE (18/08/2026)

  **Repliée**, toute la carte se clique pour déplier, avec un changement de fond
  au survol — la logique du fil d'activité, désignée comme référence.

  **Dépliée**, seul le TITRE replie : le corps doit pouvoir se lire, se
  sélectionner et se copier sans se refermer. C'est ce composant qui porte cette
  seconde moitié — d'où le `<button>` sur le titre.

  🔴 L'asymétrie **résout** le conflit que j'avais cru insoluble : une grande
  cible pour ouvrir (au doigt), aucune cible parasite une fois ouvert. Les deux
  exigences ne se contredisent pas, elles ne portent pas sur le même état.

  Le titre est un vrai `<button>` : il porte le clavier dans les deux sens. Le
  conteneur n'est donc pas interactif, et rien n'est imbriqué.

  ⚠️ J'ai d'abord fait l'inverse, dans ce fichier même, en lisant « tout le titre
  est sélectable » comme « le titre, et lui seul ». L'argument avancé — la carte
  entière intercepte la sélection de texte — était réel mais hors sujet : le
  CORPS déplié arrête déjà la propagation, et la zone repliée n'a rien à
  sélectionner. Une objection juste dans l'absolu peut être fausse ici.
  ⚠️ Le composant porte son balisage **et** son style. C'est la leçon de
  `Pastille.svelte` (v2.67.11) : un style laissé dans la page hôte n'atteint pas
  le balisage d'un enfant, et le composant part nu en production.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/** Le titre, sur une ou deux lignes. Au-delà, il est coupé — pas la carte. */
	export let titre: string;
	/** La date affichée à droite. Déjà formatée : ce composant ne connaît pas
	    `$lib/date`, et n'a donc aucun moyen d'en réinventer un format. */
	export let date = '';
	/**  Le titre bascule-t-il la carte ? `false` laisse un simple texte — une
	 *   fiche qui n'a rien à replier ne propose pas un bouton inerte.
	 *   Explicite, et non déduit d'un écouteur : Svelte ne sait pas dire si le
	 *   parent écoute `on:toggle`, et la déduction serait muette. */
	export let basculable = false;

	const dispatch = createEventDispatcher<{ toggle: void }>();
</script>

<div class="entete">
	<!--  Un vrai `<button>` : il porte le clavier dans les deux sens, et c'est la
	      SEULE cible quand la carte est dépliée. `stopPropagation` l'isole du
	      conteneur, qui ne déplie que depuis l'état replié. -->
	<div class="ec-ligne-titre">
		{#if basculable}
			<button
				type="button"
				class="ec-titre clamp-2 ec-titre-btn"
				on:click|stopPropagation={() => dispatch('toggle')}
				>{titre}<slot name="titre-suffixe" /></button
			>
		{:else}
			<div class="ec-titre clamp-2">{titre}<slot name="titre-suffixe" /></div>
		{/if}
		<div class="ec-droite ec-droite--titre">
			<slot name="actions" />
			<!--  Le chevron n'est qu'un INDICATEUR : c'est la carte entière qui reçoit
			      le clic. Lui donner son propre bouton ferait un élément interactif
			      imbriqué dans un autre — invalide, et le clavier s'y perdrait.

			      🔴 Il est rendu ICI depuis le 18/09/2026, et non plus par un
			      `slot="chevron"` que SIX cartes remplissaient avec la même ligne.
			      Son état ouvert n'a pas besoin d'être transmis : il se lit sur la
			      carte elle-même (`.carte-liste.expanded`), que l'appelant pose
			      déjà. Deux écritures d'un même fait — « cette carte est dépliée » —
			      avaient d'ailleurs commencé à diverger : quatre cartes disaient
			      `expanded`, deux `expanded || enEdition`, pour la même classe.

			      ⚠️ `chevron-carte` NOMME ce chevron-ci : la règle de charte qui le
			      fait tourner ne doit atteindre que lui, pas un chevron posé dans le
			      corps déplié (voir `composants.css`). -->
			{#if basculable}
				<span class="chevron chevron-carte" aria-hidden="true">›</span>
			{/if}
		</div>
	</div>
	<!--  L'aperçu, entre le titre et les tags. Une carte qui n'en a pas — une fiche
	      de membre, un contrat — ne rend rien ici et les deux lignes se suivent. -->
	<slot name="apercu" />

	<div class="ec-meta">
		<div class="ec-tags"><slot name="tags" /></div>
		<div class="ec-droite">
			{#if date}<span class="ec-date">{date}</span>{/if}
		</div>
	</div>
</div>

<style>
	/*  🔴 DENSITÉ « F1 », validée à l'écran le 18/09/2026 après six essais.
	    Ces quatre chiffres ne sont pas décoratifs — ils ont été mesurés :

	    | | avant | F1 |
	    |---|---|---|
	    | hauteur d'une carte de ticket | 206 px | 112 px |
	    | blanc entre le titre et l'extrait | 13 px | 3 px |

	    `gap: 0` et non `0.3rem` : l'espacement entre le titre, l'extrait et la
	    ligne de méta est décidé PAR CHACUN (`margin-top`), pas par un écart
	    uniforme qui ne convenait à aucun des trois. */
	/*  🗂️ AÉRÉE depuis la maquette B (10/10/2026) : la page Affaires est devenue
	    le standard du site le soir même, et sa variante `ample` la forme de
	    TOUTES les cartes. L'air vient de l'INTERLIGNE et des marges, pas d'une
	    carte plus haute pour rien : le titre monte d'un cran (`--fs-lg`),
	    l'aperçu de deux (`--fs-md`, interligne 1,5) — l'écart entre les deux
	    reste celui qui fait ressortir le titre. Les chiffres de F1 ci-dessus
	    disent pourquoi chaque bloc décide de son espacement. */
	.entete {
		display: flex;
		flex-direction: column;
		gap: 0;
		padding: 0.8rem 1.1rem 0.75rem;
		/*  Repère pour les actions, qui sortent du flux sous 480 px. */
		position: relative;
	}

	/*  La ligne du titre : le titre prend toute la place restante, les actions et
	    le chevron sont ancrés à droite et ne se compriment pas.

	    `min-width: 0` est ce qui permet au titre de se REPLIER plutôt que de
	    pousser la ligne : sans lui, un élément flex refuse de descendre sous la
	    largeur de son contenu, et les actions sortiraient du cadre. */
	.ec-ligne-titre {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
	}
	.ec-ligne-titre .ec-titre {
		flex: 1;
		min-width: 0;
	}
	/*  Les actions s'alignent sur la PREMIÈRE ligne du titre, pas sur son milieu :
	    un titre replié sur deux lignes ferait autrement descendre les icônes.

	    🔴 ET ELLES SONT RAPETISSÉES — c'est LA cause du blanc sous le titre,
	    signalée à l'écran : un bouton d'action fait 30 px de haut, le titre 19.
	    La ligne prenant la hauteur du plus grand, les 11 px de différence
	    tombaient entre le titre et l'extrait. On les cherchait dans les marges ;
	    ils venaient des boutons.

	    ⚠️ 22 px, mais SUR GRAND ÉCRAN SEULEMENT : sous 480 px, la règle
	    d'accessibilité reprend la main plus bas dans ce fichier et les ramène à
	    32 px — une cible tactile ne se négocie pas (`standards/11` §10, et
	    `e2e/cible-tactile.spec.ts` le refuse). */
	.ec-droite--titre {
		align-items: flex-start;
		margin-top: -0.1rem;
	}
	/*  26 px depuis la maquette B : avec un titre plus grand, ils n'ouvrent plus
	    de blanc sous lui. `width: auto` : le bouton d'options porte un
	    pictogramme PAR option active, il s'élargit au lieu de les écraser. */
	.ec-droite--titre :global(button) {
		width: auto;
		height: 26px;
		min-width: 26px;
		min-height: 26px;
		padding: 0 0.2rem;
		font-size: var(--fs-2xs);
		line-height: 1;
	}

	/*  Deux lignes au maximum : un titre long est coupé, il ne déforme pas la
	    carte et ne repousse pas ce qui suit. */
	/*  La troncature à deux lignes vit dans `.clamp-2` (normes.css) : elle était
	    écrite ici ET dans le kanban du tableau de bord (#561). */
	/*  🔴 GRAS, demandé à l'écran le 18/09/2026 — « Titre en gras (à gauche) ».
	    Il était à 500 dans ce fichier depuis le 18/08… et rendait 400, la règle
	    `.ec-titre-btn` juste en dessous l'écrasant (voir son commentaire). Le
	    poids voulu n'a donc jamais été servi sur une carte basculable. */
	.ec-titre {
		font-size: var(--fs-lg);
		font-weight: 600;
		line-height: 1.35;
	}

	/*  Tags à gauche, date + actions à droite — sur UNE seule ligne.

	    ⚠️ `flex-wrap: wrap` a été retiré le 18/08/2026 : signalé à l'écran, « sur
	    smartphone l'état est en 2 lignes ». Le repli protégeait les tags d'un
	    écrasement — un souci hérité de l'époque où le titre partageait cette
	    ligne. Le titre ayant la sienne, il ne reste plus rien à protéger, et deux
	    lignes de méta sous une carte repliée coûtent plus qu'elles ne rapportent.

	    Les tags DÉFILENT horizontalement plutôt que de se replier : rien n'est
	    perdu, la date et les actions restent ancrées à droite, et la carte garde
	    sa hauteur. Même parti que la barre de filtres de /prestataires.

	    🔴 SAUF AU TÉLÉPHONE, quand la ligne déborde (27/09/2026, arbitré à
	    l'écran). « Rien n'est perdu » n'était vrai qu'en théorie : la barre de
	    défilement est masquée, et le dernier élément de la ligne — l'AUTEUR,
	    depuis que `PastillesAffaire` fait la norme — se lisait « ✍️ Jear ». Sur
	    une carte chargée (état, périmètre, lecteurs, ⚡, numéro, auteur, date),
	    aucune largeur de téléphone ne suffit. La ligne y passe donc à la ligne,
	    et seulement quand il le faut ; la date s'aligne sur la dernière.
	    🔒 `e2e/ligne-pastilles.spec.ts` : rien ne sort de la ligne. */
	.ec-meta {
		margin-top: 0.6rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.4rem 0.6rem;
		flex-wrap: nowrap;
	}
	/*  Le titre est un bouton, remis à plat : il hérite de son propre style et ne
	    se déguise pas en contrôle de formulaire. Le survol le souligne — c'est le
	    seul repère qui dise « ceci referme », une fois la carte ouverte. */
	/*  🔴 `font: inherit` A ÉTÉ RETIRÉ (18/09/2026, signalé à l'écran : « le titre
	    ne semble plus en gras »).

	    La forme RACCOURCIE réinitialise TOUT ce qu'elle ne nomme pas — poids,
	    taille, style — et elle est déclarée après `.ec-titre`, donc elle gagnait.
	    Un titre BASCULABLE rendait 400 / 16 px hérités du corps de page, là où
	    `.ec-titre` demande 500 / 0,9 rem. Un titre non basculable, lui, est un
	    `<div>` : il n'a jamais traversé cette règle et rendait bien 500.

	    Deux rendus d'une même notion, décidés par un raccourci CSS — et le seul
	    qui se voyait était le mauvais, les cartes basculables étant la majorité.
	    Mesuré au navigateur avant de le corriger : `font-weight` calculé = 400.

	    Ne garder que la police : la famille est bien à hériter (un `<button>` n'en
	    hérite pas), le poids et la taille appartiennent à `.ec-titre`. */
	.ec-titre-btn {
		appearance: none;
		background: none;
		border: 0;
		padding: 0;
		margin: 0;
		font-family: inherit;
		color: inherit;
		text-align: left;
		width: 100%;
		cursor: pointer;
	}
	/*  ⚠️ NI soulignement NI couleur ici : le survol du titre est décidé par
	    `.carte-liste` dans `app.css`, parce qu'il dépend de l'état — replié, on
	    survole n'importe où ; déplié, le titre seul. Un composant enfant ne peut
	    pas connaître le survol de son parent.
	    Le soulignement est écarté sur demande : le titre n'est pas un lien, c'est
	    une zone cliquable. */
	.ec-titre-btn {
		transition: color var(--duree-geste);
	}
	.ec-titre-btn:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
		border-radius: 3px;
	}

	/*  🔴 UNE taille pour toute la ligne, celle d'un `.badge` (#1308) : état,
	    périmètre, pastille de lecture, numéro, auteur. Ils en avaient quatre.
	    Un élément de la ligne l'HÉRITE — `lint:entete-carte` refuse une autre
	    taille posée sur lui, et le raccourci `font:` qui la réinitialise. */
	.ec-tags {
		font-size: var(--fs-xs);
		display: flex;
		align-items: center;
		gap: 0.35rem;
		flex-wrap: nowrap;
		min-width: 0;
		/*  Barre de défilement masquée : elle apparaîtrait sous chaque carte et
		    ferait du bruit pour trois badges. */
		overflow-x: auto;
		scrollbar-width: none;
	}
	.ec-tags::-webkit-scrollbar {
		display: none;
	}
	/*  Les badges ne se compriment pas : un « Confidentiel » réduit à « Confid… »
	    ne dit plus rien, alors qu'un badge sorti du cadre se ramène d'un geste. */
	.ec-tags :global(> *) {
		flex-shrink: 0;
	}
	.ec-droite {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin-left: auto;
		flex-shrink: 0;
	}
	.ec-date {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		white-space: nowrap;
	}
	/*  Au téléphone, la ligne se replie au lieu de défiler — voir `.ec-meta`. */
	@media (max-width: 767px) {
		.ec-meta {
			align-items: flex-end;
		}
		.ec-tags {
			flex-wrap: wrap;
			row-gap: 0.25rem;
			overflow-x: visible;
		}
	}

	/*  L'aperçu de la carte aérée — sa typographie vit dans `ApercuCarte` ;
	    la carte la surcharge ici, bornée à l'en-tête. */
	.entete :global(.carte-apercu.dans-ligne) {
		margin-top: 0.3rem;
	}
	.entete :global(.carte-preview) {
		font-size: var(--fs-md);
		line-height: 1.5;
	}

	/*  Cible tactile sur les actions (socle 11 §10) : sous 480 px, les icônes
	    d'une carte étaient hautes de 26 px. */
	@media (max-width: 480px) {
		.entete {
			padding: 0.55rem 0.7rem;
		}
		/*  🔴 SOUS 480 px, LE TITRE SE CENTRE SUR SES ACTIONS.
		    La cible tactile impose 32 px de haut ; un titre en fait 19. Laissées
		    alignées en haut, les icônes rouvriraient le blanc qu'on vient de
		    fermer — 17 px mesurés, contre 3 px sur grand écran.

		    ⚠️ La piste des actions SORTIES DU FLUX (position absolue) a été
		    essayée et écartée : elle oblige le titre à leur réserver une largeur
		    fixe, qu'il faut dimensionner pour la carte qui en porte le plus.
		    Une fiche de membre, qui n'a que deux icônes, y perdait 12 rem de
		    titre sur un téléphone. Centrer répartit les 13 px de part et d'autre
		    au lieu de les mettre tous sous le titre, sans rien réserver et sans
		    dépendre du nombre d'icônes. */
		.ec-ligne-titre {
			align-items: center;
		}
		/*  🔴 UN TITRE SE LIT AVANT SES ICÔNES (23/10/2026, 💬 Répondre). Une
		    affaire porte jusqu'à six icônes : à 360 px, le titre tombait à 70 px
		    (« Ascenseur en pann… »). Sa base est donc la largeur de son TEXTE
		    (`auto`) : s'il ne tient pas entier à côté des icônes, la rangée passe
		    sous lui, à droite, et il reprend la ligne. Un titre court les garde à
		    côté — la carte ne grandit que là où le titre se serait coupé.
		    🔒 `e2e/repondre-depuis-la-carte.spec.ts`, `e2e/gouttiere-nature`. */
		.ec-ligne-titre {
			flex-wrap: wrap;
			row-gap: 0.25rem;
		}
		.ec-ligne-titre .ec-titre {
			flex: 1 1 auto;
		}
		.ec-droite--titre {
			margin-left: auto;
		}
		.ec-droite--titre {
			align-items: center;
			margin-top: 0;
		}

		/*  `min-*` l'emporte sur les 22 px posés plus haut : la cible tactile
		    reprend la main, et le glyphe retrouve sa taille avec elle. */
		/*  `height` aussi : la règle du titre fixe 26 px, plus spécifique que
		    celle-ci — sans ce rappel, elle la battrait au téléphone
		    (`e2e/cible-tactile`). */
		.ec-droite :global(button),
		.ec-droite--titre :global(button) {
			height: 32px;
			min-height: 32px;
			min-width: 32px;
			font-size: var(--fs-base);
		}
	}
</style>
