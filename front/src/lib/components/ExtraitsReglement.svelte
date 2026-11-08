<!--
  Les extraits d'un avis sur le règlement, avec ce que le CODE en a vérifié.

  Sorti de `CarteQuestionReglement` le 29/10/2026 : un avis en sections montre
  deux listes — les extraits du règlement, puis ceux des décisions d'AG —, et la
  même forme ne s'écrit qu'une fois.

  Un extrait retrouvé montre son repère — l'acte, la rubrique (chapitre, section
  ou résolution) et la page ; un extrait NON retrouvé le dit en clair, avec la
  référence que le modèle a donnée : un avis dont une citation est fausse a l'air
  vérifiable.

  Dans un avis à renvois (08/11/2026), chaque extrait porte son renvoi (`R1`,
  `AG2`) et une ancre `{idPrefixe}-{renvoi}` : la ligne « Ce qui fonde l'avis »
  y mène. Sans `titre`, la liste se lit sous le bandeau qui la plie.
-->
<script lang="ts">
	import type { ExtraitReglement } from '#lib/api/index.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let titre = '';
	export let extraits: ExtraitReglement[];
	/** Préfixe des ancres des extraits — avec leur renvoi : `{idPrefixe}-R1`. */
	export let idPrefixe = '';
</script>

{#if extraits.length}
	{#if titre}<h4 class="intertitre">{titre}</h4>{/if}
	<ul class="extraits">
		{#each extraits as e, i (i)}
			<li id={idPrefixe && e.renvoi ? `${idPrefixe}-${e.renvoi}` : undefined}>
				{#if e.renvoi}<span class="renvoi">{e.renvoi}</span>{/if}
				<blockquote>{e.citation}</blockquote>
				{#if e.verifie}
					<p class="repere">
						✓ {[e.acte, e.rubrique, e.page].filter(Boolean).join(SEPARATEUR.tiret) || e.reference}
					</p>
				{:else}
					<p class="repere alerte">
						⚠️ Non retrouvé mot pour mot dans le texte{SEPARATEUR.tiret}à vérifier{e.reference
							? ` (référence donnée : ${e.reference})`
							: ''}
					</p>
				{/if}
				{#if e.apport}<p class="aide">{e.apport}</p>{/if}
			</li>
		{/each}
	</ul>
{/if}

<style>
	.extraits {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}
	.renvoi {
		display: inline-block;
		margin-bottom: 0.2rem;
		font-size: var(--fs-sm);
		font-weight: 600;
		color: var(--color-primary);
	}
	blockquote {
		margin: 0;
		padding: 0.4rem 0.7rem;
		border-left: 3px solid var(--color-primary);
		background: var(--color-bg);
		font-style: italic;
	}
	.repere {
		margin: 0.25rem 0 0;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.alerte {
		color: var(--color-warning-texte);
	}
</style>
