<!--
  Avertissement de plafond souple affiché sous la case « Épingler ».

  Un seul composant pour toutes les rubriques qui savent épingler (actualités,
  calendrier) : c'est aussi la seule façon d'avoir un compte JUSTE. Chaque page
  ne connaît que sa propre rubrique et afficherait donc un total partiel — la
  page des actualités ignore les événements épinglés, et réciproquement. Le
  compte vient de `GET /flux/epingles`, qui les additionne.

  Le plafond est SOUPLE : on informe, on ne bloque jamais. Rien n'est masqué non
  plus dans le fil — cacher un élément épinglé trahirait le marqueur. Le seul
  risque est que le bandeau cesse d'attirer l'œil, et c'est exactement ce que
  dit le message.
-->
<script lang="ts">
	import { flux } from '#lib/api/index.ts';
	import { avertissementEpinglage } from '#lib/flux.ts';

	/** État courant de la case dans le formulaire. */
	export let coche = false;
	/** L'élément en cours d'édition était-il DÉJÀ épinglé avant ouverture ?
	 *  Sans cela, rouvrir un élément épinglé le compterait deux fois. */
	export let dejaEpingle = false;

	let total: number | null = null;
	let enCours = false;

	async function rafraichir() {
		if (enCours) return;
		enCours = true;
		try {
			total = (await flux.epingles()).total;
		} catch {
			// Silencieux, et surtout non bloquant : un avertissement de confort ne
			// doit jamais empêcher d'enregistrer.
			total = null;
		} finally {
			enCours = false;
		}
	}

	// Rechargé à chaque fois que la case passe à cochée : un CS qui épingle
	// plusieurs éléments d'affilée verrait sinon un compte figé à l'ouverture.
	$: if (coche) rafraichir();

	$: message =
		total === null || !coche ? null : avertissementEpinglage(total - (dejaEpingle ? 1 : 0) + 1);
</script>

{#if message}
	<p class="alerte-epinglage" role="status">⚠️ {message}</p>
{/if}

<style>
	.alerte-epinglage {
		margin: 0.3rem 0 0 1.6rem;
		font-size: var(--fs-sm);
		line-height: 1.4;
		color: var(--color-warning-texte);
	}
</style>
