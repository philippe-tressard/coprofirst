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
  | `pastille` | au bout de la rangée de raccourcis de l'accueil | se lit une fois, sert tout le temps : un lien stable, pas un bandeau |
  | `bouton` | au pied d'un annuaire | un renvoi parmi d'autres contacts |

  🔴 La `carte` pleine largeur en tête de l'accueil est devenue une `pastille`
  le 31/10/2026 (#2397, maquette A2 arbitrée à l'écran) : elle prenait la
  hauteur d'un bandeau pour un lien qu'on ouvre rarement. Son sous-titre — ce que
  la fiche contient — passe dans le nom accessible et la bulle de survol.

  `misEnAvant` habille la pastille en avertissement — l'appelant la pose pour un
  locataire, qui n'a pas d'autre accès aux règles de l'immeuble.

  🔒 `npm run lint:lien-consignes` refuse l'adresse de la fiche écrite ailleurs.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { admin as adminApi } from '#lib/api/index.ts';

	export let forme: 'pastille' | 'bouton' = 'bouton';
	/** Pastille seulement : habillée en avertissement. */
	export let misEnAvant = false;

	//  L'adresse vient du client d'API : elle s'écrivait ici en dur (#1578).
	const ADRESSE = adminApi.ficheArrivantUrl();
	const LIBELLE = 'Consignes de la copropriété';
	const CONTENU = 'Règlement intérieur, tri sélectif, accès, stationnement et contacts utiles';
</script>

{#if forme === 'pastille'}
	<a
		href={ADRESSE}
		target="_blank"
		rel="noopener"
		class="consignes-pastille"
		class:mis-en-avant={misEnAvant}
		aria-label="{LIBELLE} — {CONTENU} (nouvel onglet)"
		title={CONTENU}
	>
		<Icon name="file-text" size={14} />
		Consignes
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
	/* ═══ Pastille ═══════════════════════════════════════════════════════
	   La forme d'une pastille de raccourci, en plus discret : sans fond tant
	   qu'elle n'est pas mise en avant — un renvoi, pas un lieu de travail. Sa
	   place (au bout de la rangée) est décidée par la rangée, pas ici. */
	.consignes-pastille {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.4rem 0.8rem;
		border-radius: 2rem;
		border: 1px dashed var(--color-border-champ);
		font-size: var(--fs-sm);
		font-weight: 500;
		color: var(--color-text-muted);
		text-decoration: none;
		white-space: nowrap;
		transition:
			border-color var(--duree-geste),
			color var(--duree-geste),
			transform var(--duree-geste) var(--ease-out);
	}
	@media (hover: hover) and (pointer: fine) {
		.consignes-pastille:hover {
			border-color: var(--color-primary);
			color: var(--color-primary);
		}
	}
	.consignes-pastille:active {
		transform: scale(0.97);
	}
	.consignes-pastille:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}
	.consignes-pastille.mis-en-avant {
		border-style: solid;
		border-color: var(--color-warning);
		background: var(--color-warning-fond);
		color: var(--color-warning-texte);
	}
	@media (max-width: 767px) {
		.consignes-pastille {
			font-size: var(--fs-2xs);
			padding: 0.35rem 0.65rem;
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
