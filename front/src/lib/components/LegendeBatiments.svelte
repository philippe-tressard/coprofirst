<!--
  La **légende des bâtiments** — rappel discret de la couleur de chacun, sous le
  kanban d'accueil (16/11/2026, demandé : « Bât. 1 (D) » à « Bât. 4 (A) »).

  Rien n'y est écrit en dur, et c'est ce qui la garde juste :
  - les bâtiments sont les nœuds de PREMIER NIVEAU de l'arbre qui représentent un
    bâtiment (`batiment_id`), dans l'ordre de l'arbre — une copropriété de six
    bâtiments en montre six ;
  - la couleur est celle des pastilles des briques, par la même porte
    (`couleurPerimetre`, `#lib/perimetres-pastilles`) ;
  - le libellé « Bât. 1 (D) » est SERVI (`batiment_libelle`) : la lettre de l'acte vit
    sur le bâtiment, et `utils/batiments.libelle_batiment` est sa seule écriture. Le
    libellé court du nœud sert de repli, le temps que l'API réponde.

  La forme est la légende partagée des graphiques (`styles/graphiques.css`), posée
  DANS l'en-tête du kanban, entre le titre et le lien (variante B, arbitrée le
  16/11/2026 parmi cinq) : pastilles rondes, comme un point de couleur. Au
  téléphone, l'en-tête n'a pas la place : elle passe sous le titre et le lien.
-->
<script lang="ts">
	import { couleurPerimetre } from '#lib/perimetres-pastilles.ts';
	import { codesPremierNiveau, tousLesPerimetres } from '#lib/perimetres/index.ts';
	import { perimetresStore } from '#lib/stores/perimetres.ts';
	import { relire } from '#lib/utils.ts';

	//  ⚠️ `$perimetresStore` n'est pas lu : il dit à Svelte que ce calcul dépend de
	//  l'arbre, que les fonctions lisent dans un état de MODULE (#947, même ligne que
	//  `ItemKanban`).
	$: batiments = relire($perimetresStore, () => {
		const tetes = new Set(codesPremierNiveau());
		return tousLesPerimetres()
			.filter((n) => n.batiment_id !== null && n.actif && tetes.has(n.code))
			.map((n) => ({
				code: n.code,
				libelle: n.batiment_libelle ?? n.libelle_court,
				couleur: couleurPerimetre(n.code),
			}));
	});
</script>

{#if batiments.length > 0}
	<p class="graphique-legende legende-batiments" aria-label="Couleur de chaque bâtiment">
		{#each batiments as b (b.code)}
			<span class="graphique-cle">
				<span class="graphique-pastille" style="background:{b.couleur}" aria-hidden="true"></span>
				{b.libelle}
			</span>
		{/each}
	</p>
{/if}

<style>
	.legende-batiments {
		flex: 1 1 auto;
		justify-content: center;
		margin: 0;
	}
	.legende-batiments .graphique-pastille {
		border-radius: 50%;
	}
	@media (max-width: 767px) {
		.legende-batiments {
			order: 3;
			flex-basis: 100%;
			justify-content: flex-start;
		}
	}
</style>
