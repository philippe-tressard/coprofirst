<!--
  La marque de la résidence en tête du menu : son logo et son nom, lien vers l'Accueil.

  Elle se rend à deux endroits de `Nav` — la barre latérale et l'en-tête mobile —,
  qui l'écrivaient chacun de leur côté, et dont le second empruntait au premier
  une règle qui ne lui convenait pas (son logo sortait de la barre).

  Le logo était de 22 px, la taille d'une icône du menu : un logo téléversé est
  une vignette pleine, et son dessin s'y réduisait à une tache. « Doublé ou
  triplé » sur la barre latérale, centré au-dessus du nom et le bloc calé à
  gauche (arbitré à l'écran, 08/10/2026) — côte à côte, ils ne tiennent pas
  dans ses 185 px. L'en-tête
  mobile ne fait que 3,25 rem, 39 px au téléphone : le logo y reste en ligne,
  à une taille qui y laisse une marge. 🔒 `e2e/logo-menu.spec.ts`
-->
<script lang="ts">
	import LogoResidence from '#lib/components/LogoResidence.svelte';
	import { siteNomStore } from '#lib/stores/pageConfig.ts';

	/** `barre` : la barre latérale, logo au-dessus du nom ; `entete` : l'en-tête mobile, en ligne. */
	export let variante: 'barre' | 'entete';

	/** Côté du logo, en pixels, pour chaque variante. */
	const TAILLE_LOGO = { barre: 64, entete: 30 };
</script>

<a
	href="/tableau-de-bord"
	class="marque"
	class:barre={variante === 'barre'}
	class:entete={variante === 'entete'}
>
	<LogoResidence taille={TAILLE_LOGO[variante]} />
	<span class="nom">{$siteNomStore}</span>
</a>

<style>
	.marque {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		text-decoration: none;
		color: var(--color-primary);
	}
	@media (hover: hover) and (pointer: fine) {
		.marque:hover {
			opacity: 0.8;
		}
	}
	/*  Une grille d'UNE colonne, à la largeur du plus large des deux : le bloc se
	    cale à gauche de la barre (arbitré à l'écran, 08/10/2026), le logo centré
	    au-dessus du nom. Le lien garde toute la largeur, donc son filet aussi. */
	.barre {
		display: grid;
		justify-content: start;
		justify-items: center;
		padding: 0 1.25rem 1.25rem;
		border-bottom: 1px solid var(--color-border);
		margin-bottom: 0.5rem;
	}
	.nom {
		font-weight: 700;
		font-size: var(--fs-2xl);
	}
	.entete .nom {
		font-size: 1.05rem;
	}
</style>
