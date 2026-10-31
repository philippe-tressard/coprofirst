<script lang="ts">
	//  La rangée de raccourcis du tableau de bord. Le balisage part avec ses
	//  règles CSS (Svelte les scope au composant), et la page passe de 947 à un
	//  peu moins — le découpage se fait au fil de l'eau, sur ce qu'on touche.
	//
	//  Ce composant ne décide de RIEN : qui voit quoi et d'où vient chaque nombre
	//  sont déclarés dans `#lib/raccourcis.ts`. Il ne fait que rendre la table.
	//
	//  Depuis #2397 (31/10/2026, maquette A2) elle porte aussi ce que deux
	//  bandeaux disaient en pleine largeur : le lien vers les consignes, au bout
	//  de la rangée, et le prochain rendez-vous à la place d'un « Calendrier » nu.
	import Icon from '#lib/components/Icon.svelte';
	import LienConsignes from '#lib/components/LienConsignes.svelte';
	import { currentUser, isLocataire } from '#lib/stores/auth.ts';
	import { raccourcisVisibles } from '#lib/raccourcis.ts';
	import { partiesDate } from '#lib/date.ts';
	import { lienTicket } from '#lib/tickets.ts';
	import type { FluxSante } from '#lib/api/index.ts';

	export let sante: FluxSante;
	/** Anime l'apparition, comme les autres sections de la page. */
	export let ready = false;

	$: visibles = raccourcisVisibles($currentUser);
</script>

<!--  🔴 La pastille est un CONTENEUR depuis le 21/09/2026, et non plus un lien
      unique : un compteur peut porter sa propre adresse (« 1 relance » mène à la
      vue Relance syndic, pas à la porte de l'Espace CS), et un `<a>` ne
      s'imbrique pas dans un `<a>`.

      Le lien principal reste cliquable sur TOUTE la pastille grâce à son
      `::after` étendu — le motif dit « lien étiré » —, et un compteur qui porte
      une adresse passe au-dessus (`z-index`). Rien ne bouge à l'œil ; ce qui
      change est la cible sous le doigt. -->
<nav class="quick-nav section-reveal" class:section-visible={ready} aria-label="Raccourcis">
	{#each visibles as r (r.id)}
		{@const rdv = r.agenda?.(sante)}
		{@const jour = partiesDate(rdv?.debut)}
		{#if r.agenda}
			{#if rdv && jour}
				<!--  La date en médaillon, puis le titre : la pastille dit QUAND et
				      QUOI, et mène à l'affaire. Le nom accessible dit la date en
				      entier — le médaillon abrège. -->
				<a
					href={lienTicket(rdv.id)}
					class="quick-pill quick-pill-agenda"
					aria-label="Prochain rendez-vous : {rdv.titre}, le {jour.jour} {jour.mois} {jour.annee}"
				>
					<span class="quick-date" aria-hidden="true"
						><span class="quick-date-jour">{jour.jour}</span><span class="quick-date-mois"
							>{jour.mois}</span
						></span
					>
					<span class="quick-agenda-titre">{rdv.titre}</span>
				</a>
			{/if}
		{:else}
			<div
				class="quick-pill"
				class:quick-pill-cs={r.variante === 'cs'}
				class:quick-pill-admin={r.variante === 'admin'}
			>
				<a href={r.href} class="quick-pill-cible">
					<Icon name={r.icone} size={14} />
					{r.libelle}
				</a>
				{#each r.compteurs(sante) as c (c)}
					{#if c.valeur > 0}
						{#if c.href}
							<a
								href={c.href}
								class="quick-count quick-count-lien"
								class:quick-count-urgent={c.ton === 'urgent'}
								class:quick-count-orange={c.ton === 'orange'}
								>{c.libelle ? c.libelle(c.valeur) : c.valeur}</a
							>
						{:else}
							<span
								class="quick-count"
								class:quick-count-urgent={c.ton === 'urgent'}
								class:quick-count-orange={c.ton === 'orange'}
								>{c.libelle ? c.libelle(c.valeur) : c.valeur}</span
							>
						{/if}
					{/if}
				{/each}
			</div>
		{/if}
	{/each}
	<!--  Au bout de la rangée : un renvoi, pas un lieu de travail. -->
	<span class="quick-fin">
		<LienConsignes forme="pastille" misEnAvant={$isLocataire} />
	</span>
</nav>

<style>
	.quick-nav {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin: 0.75rem 0;
		padding: 0;
	}
	/*  L'apparition (fondu, 8 px, 200 ms) est `.section-reveal`, dans
	    `styles/socle.css` ; le délai vient de la page (`--delay`). */
	.quick-pill {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.4rem 0.8rem;
		border-radius: 2rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		font-size: var(--fs-sm);
		font-weight: 500;
		color: var(--color-text);
		text-decoration: none;
		transition:
			border-color var(--duree-geste),
			box-shadow var(--duree-geste),
			background var(--duree-geste);
		white-space: nowrap;
	}
	@media (hover: hover) and (pointer: fine) {
		.quick-pill:hover {
			border-color: var(--color-primary);
			box-shadow: var(--shadow-sm);
			background: var(--color-primary-light);
		}
	}
	/*  Le lien étiré : toute la pastille reste cliquable pour la destination
	    principale, sans imbriquer d'ancres. */
	.quick-pill-cible {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		color: inherit;
		text-decoration: none;
	}
	.quick-pill-cible::after {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
	}
	/*  Un compteur qui porte son adresse passe AU-DESSUS du lien étiré — sinon
	    il serait recouvert par lui et ne recevrait jamais le clic. */
	.quick-count-lien {
		position: relative;
		z-index: 1;
		text-decoration: none;
	}
	.quick-count {
		background: var(--color-primary-plein);
		color: var(--color-sur-plein);
		font-size: var(--fs-2xs);
		font-weight: 700;
		padding: 0.05rem 0.4rem;
		border-radius: 1rem;
		line-height: 1.3;
		min-width: 1.1rem;
		text-align: center;
	}
	/*  La pastille d'agenda : un médaillon de date à gauche, le titre coupé
	    au-delà de 18 rem — c'est une pastille, pas une carte. */
	.quick-pill-agenda {
		padding-left: 0.25rem;
		max-width: 18rem;
	}
	.quick-date {
		display: inline-flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		background: var(--color-primary-light);
		color: var(--color-primary);
		line-height: 1;
		flex-shrink: 0;
	}
	.quick-date-jour {
		font-size: var(--fs-xs);
		font-weight: 700;
	}
	.quick-date-mois {
		font-size: var(--fs-3xs);
	}
	.quick-agenda-titre {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.quick-fin {
		margin-left: auto;
		display: inline-flex;
	}
	.quick-pill-cs {
		border-color: var(--color-warning);
	}
	@media (hover: hover) and (pointer: fine) {
		.quick-pill-cs:hover {
			border-color: var(--color-warning);
			background: var(--color-warning-fond);
		}
	}
	/*  L'Admin se distingue du CS : deux pastilles orange côte à côte se liraient
	    comme une seule zone, alors que ce sont deux destinations différentes. */
	.quick-pill-admin {
		border-color: var(--color-violet);
	}
	@media (hover: hover) and (pointer: fine) {
		.quick-pill-admin:hover {
			border-color: var(--color-violet);
			background: var(--color-violet-fond);
		}
	}
	.quick-count-urgent {
		background: var(--color-danger);
	}
	.quick-count-orange {
		background: var(--color-warning);
	}

	@media (max-width: 767px) {
		.quick-nav {
			gap: 0.35rem;
		}
		.quick-pill {
			font-size: var(--fs-2xs);
			padding: 0.35rem 0.65rem;
		}
		/*  Au téléphone, le titre se borne plus court : la pastille tient alors
		    sur la ligne d'une voisine au lieu d'en prendre une entière. */
		.quick-pill-agenda {
			max-width: 11rem;
		}
	}
</style>
