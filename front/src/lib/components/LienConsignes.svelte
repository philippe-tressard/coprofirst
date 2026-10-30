<!--
  **Le lien vers les consignes de la copropriété** — la fiche que reçoit un
  arrivant (règlement intérieur, tri, accès, stationnement, contacts).

  ## Pourquoi ce composant (#779, 01/10/2026)

  Il était écrit trois fois : l'accueil, l'annuaire et l'onglet Annuaire de
  l'Espace CS. Les copies avaient divergé — « Consignes **de la** copropriété »
  📋 sur l'accueil, « Consignes **de** copropriété » 📄 ailleurs, avec leurs
  styles en ligne. Le libellé retenu est celui du manuel et du courriel
  d'arrivée : c'est le nom sous lequel l'arrivant reçoit la fiche.

  ## Deux formes, une notion

  | `forme` | Où | Pourquoi |
  |---|---|---|
  | `carte` | en tête de l'accueil | se lit une fois, sert tout le temps : elle mérite la place |
  | `bouton` | au pied d'un annuaire | un renvoi parmi d'autres contacts |

  `misEnAvant` habille la carte en avertissement — l'appelant la pose pour un
  locataire, qui n'a pas d'autre accès aux règles de l'immeuble.

  🔒 `npm run lint:lien-consignes` refuse l'adresse de la fiche écrite ailleurs.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { admin as adminApi } from '#lib/api/index.ts';

	export let forme: 'carte' | 'bouton' = 'bouton';
	/** Carte seulement : habillée en avertissement. */
	export let misEnAvant = false;

	//  L'adresse vient du client d'API : elle s'écrivait ici en dur (#1578).
	const ADRESSE = adminApi.ficheArrivantUrl();
	const LIBELLE = 'Consignes de la copropriété';
</script>

{#if forme === 'carte'}
	<a
		href={ADRESSE}
		target="_blank"
		rel="noopener"
		class="consignes-carte"
		class:mis-en-avant={misEnAvant}
	>
		<span class="consignes-icone" aria-hidden="true">📄</span>
		<span class="consignes-texte">
			<strong class="consignes-titre">{LIBELLE}</strong>
			<span class="consignes-sous-titre"
				>Règlement intérieur, tri sélectif, accès, stationnement et contacts utiles</span
			>
		</span>
		<span class="consignes-fleche" aria-hidden="true"><Icon name="chevron-right" size={18} /></span>
	</a>
{:else}
	<div class="form-actions">
		<a href={ADRESSE} target="_blank" rel="noopener" class="btn btn-outline consignes-bouton">
			<span aria-hidden="true">📄</span>
			{LIBELLE}
		</a>
	</div>
{/if}

<style>
	/* ═══ Carte ═══════════════════════════════════════════════════════════
	   L'apparition (fondu, 8 px) est celle de la section qui l'enveloppe
	   (`.section-reveal`, socle.css) : la carte la recopiait. Elle ne garde que
	   ce qui lui appartient — le survol et l'appui. */
	.consignes-carte {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin: 0.75rem 0;
		padding: 0.75rem 1rem;
		border-radius: var(--radius);
		background: var(--color-primary-light);
		border: 1px solid var(--color-primary);
		border-left: 4px solid var(--color-primary);
		text-decoration: none;
		color: inherit;
		transition:
			box-shadow var(--duree-geste),
			transform var(--duree-geste) var(--ease-out);
	}
	@media (hover: hover) and (pointer: fine) {
		.consignes-carte:hover {
			box-shadow: var(--shadow);
		}
	}
	/*  Le soulèvement au survol : seulement pour qui accepte le mouvement. */
	@media (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference) {
		.consignes-carte:hover {
			transform: translateY(-1px);
		}
	}
	/*  L'appui se voit, au doigt comme à la souris. Un cran plus discret qu'un
	    bouton (0,97) : la carte occupe toute la largeur. */
	.consignes-carte:active {
		transform: scale(0.99);
	}
	.consignes-carte:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}
	.consignes-carte.mis-en-avant {
		background: var(--color-warning-fond);
		border-color: var(--color-warning);
		border-left-color: var(--color-warning);
		/*  Mise en avant FIXE (26/09/2026) : elle pulsait à chaque visite, sans fin. */
	}
	.consignes-icone {
		font-size: var(--fs-picto);
		flex-shrink: 0;
	}
	.consignes-texte {
		flex: 1;
		min-width: 0;
	}
	.consignes-titre {
		font-size: var(--fs-base);
		font-weight: 600;
		color: var(--color-primary);
		display: block;
	}
	.consignes-sous-titre {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		line-height: 1.3;
	}
	.consignes-fleche {
		flex-shrink: 0;
		color: var(--color-primary);
		opacity: 0.6;
	}
	@media (prefers-reduced-motion: reduce) {
		.consignes-carte,
		.consignes-carte:active {
			transform: none;
		}
	}
	@media (max-width: 767px) {
		.consignes-carte {
			gap: 0.5rem;
			padding: 0.6rem 0.75rem;
		}
		.consignes-icone {
			font-size: var(--fs-picto-sm);
		}
	}

	/* ═══ Bouton ══════════════════════════════════════════════════════════
	   Rangé à droite par `.form-actions` (normes.css), qui lui donne aussi sa
	   cible de 44 px au doigt et toute la largeur sur un petit téléphone. */
	.consignes-bouton {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--fs-md);
	}
</style>
