<!--
  L'APERÇU d'un équipement — ce que la fiche produira, pendant qu'on la remplit
  (maquette C, #2442).

  🔴 Ce sont les VRAIS composants, pas un dessin : la carte d'un contrat
  (`CarteListe` et sa gouttière — l'icône et le mot abrégé) et le badge d'une
  fiche de prestataire. Un aperçu recopié divergerait du rendu au premier
  réglage de la gouttière ; celui-ci le suit.
-->
<script lang="ts">
	import CarteListe from './CarteListe.svelte';
	import EnteteCarte from './EnteteCarte.svelte';
	import { abreviationDe, type FormulaireEquipement } from '#lib/equipements.ts';

	export let form: FormulaireEquipement;

	$: libelle = form.libelle.trim() || 'Nouvel équipement';
	$: classe = {
		icone: form.icone || 'wrench',
		libelle,
		abrege: abreviationDe({ abreviation: form.abreviation, libelle }),
	};
</script>

<section class="apercu-equipement" aria-labelledby="apercu-equipement-titre">
	<h4 id="apercu-equipement-titre" class="apercu-titre">Aperçu</h4>
	<p class="apercu-legende">Sur la carte d’un contrat</p>
	<CarteListe {classe}>
		<EnteteCarte titre="Contrat d’entretien — {libelle}">
			<svelte:fragment slot="tags">
				<span class="badge badge-gray">Prestataire</span>
			</svelte:fragment>
		</EnteteCarte>
	</CarteListe>
	<p class="apercu-legende">Sur la fiche d’un prestataire</p>
	<span class="badge badge-gray">{libelle}</span>
</section>

<style>
	.apercu-equipement {
		display: grid;
		gap: 0.4rem;
		justify-items: start;
	}
	.apercu-equipement :global(.carte-liste) {
		justify-self: stretch;
		margin: 0;
	}
	.apercu-titre {
		margin: 0;
		font-size: var(--fs-sm);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-muted);
	}
	.apercu-legende {
		margin: 0.3rem 0 0;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
</style>
