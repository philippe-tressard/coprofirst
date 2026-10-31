<!--
  Les extraits d'un avis sur le règlement, avec ce que le CODE en a vérifié.

  Sorti de `CarteQuestionReglement` le 29/10/2026 : un avis en sections montre
  deux listes — les extraits du règlement, puis ceux des décisions d'AG —, et la
  même forme ne s'écrit qu'une fois.

  Un extrait retrouvé montre son repère — l'acte et la page, ou l'assemblée et
  la page du PV ; un extrait NON retrouvé le dit en clair, avec la référence que
  le modèle a donnée : un avis dont une citation est fausse a l'air vérifiable.
-->
<script lang="ts">
	import type { ExtraitReglement } from '#lib/api/index.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let titre: string;
	export let extraits: ExtraitReglement[];
</script>

{#if extraits.length}
	<h4 class="intertitre">{titre}</h4>
	<ul class="extraits">
		{#each extraits as e, i (i)}
			<li>
				<blockquote>{e.citation}</blockquote>
				{#if e.verifie}
					<p class="repere">
						✓ {[e.acte, e.page].filter(Boolean).join(' — ') || e.reference}
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
