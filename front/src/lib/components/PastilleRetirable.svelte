<!--
  La PASTILLE d'un objet retenu — « PRÉFIXE: nom », et la croix qui le retire.

  Sortie de `PastilleFichier` le 26/09/2026 (#1342) : la section « Affaires
  liées » montre ses affaires sous la même forme — « TK-12: Fuite au 3e ×» —,
  et la recopier aurait fait deux pastilles pour un seul geste. Ce qui varie est
  en props : le préfixe (le type d'un fichier, le numéro d'une affaire), le nom,
  et ce que dit la croix.

  🔴 Les règles de style voyagent AVEC le balisage : les laisser chez l'appelant
  rendrait la pastille nue dans l'autre — la régression des pastilles de la
  v2.67.11, reproduite trois fois le 19/08/2026.
-->
<script lang="ts">
	/**  Ce qui se lit d'un coup d'œil, en tête et en gris : « PDF », « TK-12 ». */
	export let prefixe: string;
	export let nom: string;
	export let readonly = false;
	/**  Le titre de la croix — « Retirer ce document », « Retirer ce lien ». */
	export let aideRetirer = 'Retirer';
</script>

<span class="pastille-retirable">
	<span class="pastille-prefixe">{prefixe}</span>
	<span class="pastille-nom">{nom}</span>
	{#if !readonly}
		<button
			type="button"
			class="pastille-retirer"
			title={aideRetirer}
			aria-label="Retirer {nom}"
			on:click
		>
			×
		</button>
	{/if}
</span>

<style>
	.pastille-retirable {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		max-width: 100%;
		padding: 0.2rem 0.45rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-neutre-fond);
		font-size: var(--fs-sm);
	}
	/*  Le préfixe en tête, gris et compact : il se lit d'un coup d'œil sans voler
	    la place au nom, qui est ce qu'on cherche ensuite. */
	.pastille-prefixe {
		font-size: var(--fs-2xs);
		font-weight: 700;
		letter-spacing: 0.02em;
		color: var(--color-text-muted);
		flex-shrink: 0;
	}
	.pastille-prefixe::after {
		content: ':';
	}
	.pastille-nom {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.pastille-retirer {
		border: none;
		background: none;
		color: var(--color-danger);
		cursor: pointer;
		font-size: var(--fs-xl);
		line-height: 1;
		padding: 0;
		flex-shrink: 0;
	}
</style>
