<!--
  **Une clé de charges en bloc** — son libellé, le total et le pourcentage, ce qu'elle
  finance, son libellé sur l'appel de fonds, puis la part de chaque lot (#2251, #2252).

  Écrit ici UNE fois pour les deux endroits de `TableauCharges` qui montrent une clé hors du
  tableau : la vue en blocs du téléphone, et les clés prévues au règlement que le syndic
  n'appelle pas en ce moment.
-->
<script lang="ts">
	import type { ColonneDeLot, LigneDeCle } from '$lib/charges-lots';
	import { fmtNombre, fmtPartEnPourcent } from '$lib/utils';

	export let ligne: LigneDeCle;
	export let colonnes: ColonneDeLot[];
</script>

<div class="bloc-entete">
	<span class="cle">{ligne.libelle}</span>
	<span
		><strong>{fmtNombre(ligne.total)}/{fmtNombre(ligne.denominateur)}</strong> · {fmtPartEnPourcent(
			ligne.total,
			ligne.denominateur,
		)}</span
	>
</div>
{#if ligne.description}<span class="detail">{ligne.description}</span>{/if}
{#if ligne.libelleSyndic}
	<span class="detail">Sur l’appel de fonds : {ligne.libelleSyndic}</span>
{/if}
<span class="detail">
	{colonnes
		.filter((c) => ligne.parts[c.id] !== undefined)
		.map((c) => `${c.nom} : ${fmtNombre(ligne.parts[c.id])}`)
		.join(' · ')}
</span>

<style>
	.bloc-entete {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
	}
	.cle {
		font-weight: 600;
	}
	.detail {
		display: block;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		line-height: 1.4;
		margin-top: 0.15rem;
	}
</style>
