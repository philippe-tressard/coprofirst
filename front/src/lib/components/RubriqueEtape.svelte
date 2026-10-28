<!--
  RubriqueEtape.svelte — une RUBRIQUE d'un objet déplié, lue comme une étape :
  un jalon sur le rail à gauche, un encart teinté à droite, pliable.

  ## Pourquoi (maquette G, arbitrée le 16/10/2026)

  La carte d'une affaire dépliée se lisait en trois rubriques — La demande, La
  synthèse, La suite — titrées de deux façons (« LA DEMANDE » en gris, « 🧾 LA
  SYNTHÈSE » en gras), sans limite visible entre elles. Signalé à l'écran :
  *« la limite de chacune d'elle est floue »*. Dix maquettes en deux tours :

  - le RAIL relie les rubriques et dit l'ordre — retenu du tour 1 (D), mais
    seul il laissait la limite floue ;
  - l'ENCART teinté délimite chaque rubrique sans ambiguïté — retenu (B) ;
  - le PLIAGE : une rubrique à la fois, la première ouverte, et chaque rubrique
    pliée tient en UNE LIGNE qui dit l'essentiel (`resume`). Sans ce résumé, le
    pliage cacherait « Résolu le 15 oct. » derrière un clic de plus.

  L'accordéon est tenu par l'APPELANT (`ouverte`, `onBasculer`) : il connaît
  les rubriques voisines, et `basculer` (`#lib/accordeon`) dit laquelle s'ouvre.

  Le rail se trace de jalon en jalon : une étape suivie d'une autre étape porte
  le trait (`:has`). La dernière n'en a pas, quelle que soit celle qui l'est —
  une affaire ouverte n'a pas de synthèse, une affaire neuve pas de suite.

  Le contenu plié est CACHÉ, jamais démonté (`hidden`) : une correction de suite
  en cours ou une synthèse en édition survivent au repli — même règle que
  `SectionFormulaire`.
-->
<script lang="ts">
	import Icon from './Icon.svelte';

	export let titre: string;
	/** Icône du catalogue (`#lib/icones-svg.json`), dans le jalon. */
	export let icone: string;
	/** La teinte de l'encart : neutre, l'information, ou ce qui est conclu. */
	export let ton: 'neutre' | 'info' | 'succes' = 'neutre';
	/** Ce que dit la rubrique PLIÉE, sur une ligne — l'état, jamais l'invitation. */
	export let resume = '';
	/** « 5 entrées » à côté du titre — absent si rien ne se compte. */
	export let compte: number | null = null;
	export let ouverte = false;
	export let onBasculer: () => void;

	const idCorps = `rubrique-${Math.random().toString(36).slice(2, 9)}`;
</script>

<div class="etape">
	<!--  `class:` et non `ton-{ton}` : une classe interpolée rend le fichier
	      aveugle à `lint:css-orphelin`. -->
	<span
		class="jalon"
		class:ton-neutre={ton === 'neutre'}
		class:ton-info={ton === 'info'}
		class:ton-succes={ton === 'succes'}
		aria-hidden="true"><Icon name={icone} size={15} /></span
	>
	<section
		class="encart"
		class:ton-neutre={ton === 'neutre'}
		class:ton-info={ton === 'info'}
		class:ton-succes={ton === 'succes'}
	>
		<h4 class="encart-h">
			<button
				type="button"
				class="encart-tete"
				aria-expanded={ouverte}
				aria-controls={idCorps}
				on:click={onBasculer}
			>
				<span class="encart-titre"
					>{titre}{#if compte !== null}<span class="encart-compte"
							>{compte} {compte > 1 ? 'entrées' : 'entrée'}</span
						>{/if}</span
				>
				{#if !ouverte && resume}<span class="encart-resume">{resume}</span>{/if}
				<span class="encart-chevron" class:ouvert={ouverte}
					><Icon name="chevron-down" size={16} /></span
				>
			</button>
		</h4>
		<div class="encart-corps" id={idCorps} hidden={!ouverte}>
			<slot />
		</div>
	</section>
</div>

<style>
	.etape {
		position: relative;
		display: grid;
		grid-template-columns: 2rem minmax(0, 1fr);
		column-gap: 0.875rem;
		padding-bottom: 0.75rem;
	}
	/*  Le RAIL : du jalon de cette étape à celui de la suivante. Une étape sans
	    suivante n'en porte pas, et ne garde pas d'air en dessous. */
	.etape:has(~ :global(.etape))::before {
		content: '';
		position: absolute;
		left: calc(1rem - 1px);
		top: 2.75rem;
		bottom: 0.1rem;
		width: 2px;
		border-radius: 2px;
		background: var(--color-border);
	}
	.etape:not(:has(~ :global(.etape))) {
		padding-bottom: 0;
	}
	.jalon {
		margin-top: 0.5rem;
		width: 2rem;
		height: 2rem;
		box-sizing: border-box;
		border-radius: 50%;
		border: 1.5px solid var(--color-border);
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.encart {
		min-width: 0;
		border: 1px solid;
		border-radius: var(--radius);
	}
	.ton-neutre {
		background: var(--color-neutre-fond);
		border-color: var(--color-neutre-bordure);
		color: var(--color-text-muted);
	}
	.ton-info {
		background: var(--color-primary-light);
		border-color: var(--color-border);
		color: var(--color-primary);
	}
	.ton-succes {
		background: var(--color-success-fond);
		border-color: var(--color-success-bordure);
		color: var(--color-success-texte);
	}
	/*  L'encart rend la couleur du TEXTE à son contenu : sa teinte ne colore que
	    le jalon. */
	.encart {
		color: var(--color-text);
	}
	.encart-h {
		margin: 0;
	}
	/*  Toute la ligne est la cible : 3 rem de haut, au-delà des 44 px du doigt. */
	.encart-tete {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		width: 100%;
		min-height: 3rem;
		padding: 0 0.875rem 0 1rem;
		border: none;
		background: none;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
		border-radius: var(--radius);
	}
	.encart-titre {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		font-size: var(--fs-lg);
		font-weight: 600;
		white-space: nowrap;
		transition: color var(--duree-geste) var(--ease-out);
	}
	.encart-compte {
		font-size: var(--fs-md);
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.encart-resume {
		flex: 1;
		min-width: 0;
		text-align: right;
		font-size: var(--fs-sm);
		font-weight: 400;
		color: var(--color-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.encart-chevron {
		display: inline-flex;
		margin-left: auto;
		flex-shrink: 0;
		color: var(--color-text-muted);
		transition: transform var(--duree-apparition) var(--ease-out);
	}
	.encart-chevron.ouvert {
		transform: rotate(180deg);
	}
	@media (hover: hover) and (pointer: fine) {
		.encart-tete:hover .encart-titre {
			color: var(--color-primary);
		}
	}
	.encart-corps {
		padding: 0 1rem 1rem;
	}
	/*  Au téléphone, le résumé passe SOUS le titre : à droite, il ne laissait
	    que trois mots avant les points de suspension. */
	@media (max-width: 480px) {
		.encart-tete {
			flex-wrap: wrap;
			row-gap: 0;
			padding-top: 0.5rem;
			padding-bottom: 0.5rem;
		}
		.encart-resume {
			order: 3;
			flex-basis: 100%;
			text-align: left;
		}
	}
</style>
