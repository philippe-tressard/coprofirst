<!--
  Gouttiere.svelte — la colonne de gauche d'une carte de liste : QUAND, puis
  CE QUI LA CLASSE.

  ## Pourquoi (10/10/2026, maquette B « Gouttière », choisie parmi cinq)

  Demandé pour les affaires : une liste « plus premium et aérée, sans perdre
  aucune information ». La liste se parcourt par le temps : la date, rangée en
  bout de dernière ligne, obligeait l'œil à zigzaguer d'une carte à l'autre.
  Elle monte en tête d'une colonne, le jour en grand ; ce qui classe l'objet se
  lit dessous. Tout ce qui SITUE un objet est à gauche, tout ce qui se LIT est à
  droite.

  🔴 Le soir même, la page Affaires est devenue le STANDARD du site (« applique-le
  à toutes les pages ») : ce composant s'appelait `GouttiereAffaire` et ne savait
  lire qu'une affaire. Il prend désormais une date et un classement — la NATURE
  d'une affaire (`gouttiereAffaire`, `#lib/tickets`), le type d'un prestataire,
  la rubrique d'une question… Ce que l'objet n'a pas ne s'invente pas : sans
  date, la colonne ne porte que le classement.

  🔒 Il n'est rendu QUE par `CarteListe` (`lint:carte-liste`), qui pose la
  colonne dès qu'il y a de quoi la remplir : une carte ne l'appelle plus
  elle-même, et ne peut donc plus oublier `.a-gouttiere` ni le rendre ailleurs
  qu'en premier enfant.

  La TEINTE du classement est portée par la carte (`--nature-fort`, posé par
  `[data-nature]` dans `styles/normes.css`) : ce composant la lit, il ne la
  décide pas. Sans teinte, le classement prend le Bleu Seine de la charte.

  🔴 Une carte qui a une gouttière NE PASSE PLUS sa date à `EnteteCarte` : deux
  dates sur une carte en feraient deux faits. `CarteListe` pose la classe
  `a-gouttiere`, qui lui réserve la colonne (`normes.css`).

  Au téléphone (≤ 480 px) la colonne prendrait la place du titre : elle devient
  une LIGNE d'en-tête — « 5 oct. 2026 · CAL. » —, posée au-dessus du titre.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { fmtTime, partiesDate } from '#lib/date.ts';
	import type { ClasseGouttiere } from '#lib/gouttiere.ts';

	/** L'instant qui situe l'objet (ISO), ou rien. */
	export let quand: string | null | undefined = null;
	/** Ce qui classe l'objet — nature, type, rubrique —, ou rien. */
	export let classe: ClasseGouttiere | null = null;
	/**  L'HEURE de l'instant, et non son jour : quand le jour est déjà dit par
	 *   l'intitulé du groupe (le fil d'activité, groupé sous « Aujourd'hui »,
	 *   « Hier »…), le répéter sur chaque carte ne dirait rien (10/10/2026). */
	export let heure = false;

	$: date = heure ? null : partiesDate(quand);
</script>

<div class="gouttiere">
	{#if heure && quand}
		<time class="g-date" datetime={quand}><span class="g-jour">{fmtTime(quand)}</span></time>
	{:else if date && quand}
		<time class="g-date" datetime={quand}>
			<span class="g-jour">{date.jour}</span>
			<span class="g-mois">{date.mois} <span class="g-annee">{date.annee}</span></span>
		</time>
	{/if}
	{#if classe}
		<span class="g-nature" title={classe.libelle}>
			<Icon name={classe.icone} size={18} />
			<abbr title={classe.libelle}>{classe.abrege}</abbr>
		</span>
	{/if}
	<!--  Ce qui tient lieu de classement quand l'objet en a un autre — le vote
	      d'une idée, par exemple. Posé sous le reste, dans la même colonne. -->
	<slot />
</div>

<style>
	/*  La PREMIÈRE COLONNE de la grille que la carte pose (`.a-gouttiere`,
	    `normes.css`) : elle traverse toutes les rangées, s'étire sur une carte
	    haute et fait grandir une carte courte — posée en absolu, elle débordait
	    sous elle (#1819). Son fond est un pierre ADOUCI — la charte, mêlée au
	    blanc de la carte : le repère existe sans crier. */
	.gouttiere {
		grid-column: 1;
		grid-row: 1 / -1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 0.85rem 0.25rem;
		background: color-mix(in srgb, var(--color-bg) 45%, var(--color-surface));
		border-right: 1px solid color-mix(in srgb, var(--color-border) 60%, transparent);
		border-radius: var(--radius) 0 0 var(--radius);
		text-align: center;
	}
	.g-date {
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	.g-jour {
		font-family: var(--police-titres);
		font-size: var(--fs-chiffre);
		line-height: 1;
		color: var(--color-text);
		font-variant-numeric: lining-nums tabular-nums;
	}
	.g-mois {
		margin-top: 0.25rem;
		font-size: var(--fs-xs);
		line-height: 1.25;
		color: var(--color-text-muted);
	}
	.g-annee {
		display: block;
	}
	/*  Le classement prend la teinte de la carte. Petites capitales espacées,
	    abrégées : écrit en entier, « CALENDRIER » élargissait la colonne
	    (#1220). `e2e/gouttiere-nature` mesure que le mot y tient. */
	.g-nature {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
		color: var(--nature-fort, var(--color-primary));
	}
	.g-nature abbr {
		text-decoration: none;
		font-size: var(--fs-2xs);
		font-weight: 700;
		letter-spacing: 0.06em;
	}

	/*  Au pouce, une LIGNE au-dessus du titre : la date à gauche, le classement
	    au bout. Le jour reprend la taille du texte — en vedette, il mangerait la
	    hauteur que la colonne vient de rendre. */
	@media (max-width: 480px) {
		.gouttiere {
			grid-row: auto;
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
			padding: 0.4rem 0.7rem;
			border-right: 0;
			border-bottom: 1px solid color-mix(in srgb, var(--color-border) 60%, transparent);
			border-radius: var(--radius) var(--radius) 0 0;
		}
		.g-date {
			flex-direction: row;
			align-items: baseline;
			gap: 0.3em;
			font-size: var(--fs-sm);
			font-weight: 600;
			color: var(--color-text);
		}
		.g-jour {
			font-family: inherit;
			font-size: inherit;
			line-height: inherit;
		}
		.g-mois {
			margin: 0;
			font-size: inherit;
			color: inherit;
		}
		.g-annee {
			display: inline;
		}
		.g-nature {
			flex-direction: row;
			gap: 0.35rem;
			margin-left: auto;
		}
	}
</style>
