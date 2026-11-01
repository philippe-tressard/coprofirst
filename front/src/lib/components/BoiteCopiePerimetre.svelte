<!--
  **Copier un périmètre sous d'autres périmètres** (01/11/2026).

  Demandé à l'écran : *« dupliquer un périmètre sur plusieurs autres catégories,
  avec les mêmes paramètres »*. « Local vélos » posé sous le bâtiment 1, on le
  coche sous les bâtiments 2, 3 et 4 : trois copies, même nom, mêmes
  caractéristiques et accès fixes, et ses sous-périmètres avec lui. Seul le code
  change, dérivé de chaque parent — il est immuable, le serveur le compose.

  À ne pas confondre avec la duplication (`BoiteDuplicationPerimetre`), qui pose
  UNE copie à côté de la source, sous un nouveau nom — un bâtiment de plus.

  La liste reprend l'arborescence de l'écran, en retrait par profondeur. Elle
  tait ce que le serveur refuserait toujours : la source, sa branche et son
  parent actuel (`copier_perimetre`). Un code déjà pris, lui, se dit au refus :
  tout ou rien, rien n'est posé.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import LibelleGroupe from '#lib/components/LibelleGroupe.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { perimetres as perimetresApi } from '#lib/api/index.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { estDansLaBranche, type Perimetre } from '#lib/perimetres/index.ts';
	import { perimetresStore, rechargerPerimetres } from '#lib/stores/perimetres.ts';

	/** Le nœud dont on pose des copies. */
	export let source: Perimetre;

	const dispatch = createEventDispatcher<{ annule: void; fini: void }>();

	let choisis: string[] = [];
	let enregistrement = false;

	$: candidats = $perimetresStore.filter(
		(n) => n.code !== source.parent && !estDansLaBranche($perimetresStore, n.code, source.code),
	);
	$: titre = source.nb_descendants
		? `Copier ${source.libelle} et ses ${source.nb_descendants} sous-périmètre(s)`
		: `Copier ${source.libelle}`;

	async function enregistrer() {
		enregistrement = true;
		await tenter(
			async () => {
				await perimetresApi.copier(source.id, choisis);
				await rechargerPerimetres();
				dispatch('fini');
			},
			choisis.length > 1 ? `${choisis.length} copies posées` : 'Copie posée',
			'Copie impossible',
		);
		enregistrement = false;
	}
</script>

<FormulaireCreation {titre} encadre={false}>
	<LibelleGroupe
		titre="Sous les périmètres"
		requis
		vide={!choisis.length}
		id="copie-perimetre-{source.id}"
	>
		<div class="cibles">
			{#each candidats as n (n.code)}
				<label class="case" style="padding-left:{n.profondeur * 1.1}rem">
					<input type="checkbox" value={n.code} bind:group={choisis} />
					{n.libelle}
				</label>
			{/each}
		</div>
	</LibelleGroupe>
	<p class="aide">
		Chaque copie garde le nom « {source.libelle} », ses caractéristiques et ses accès fixes ; son code
		est dérivé du périmètre choisi, et elle se range à la même place qu’ici, après le même voisin. Sous
		un bâtiment, elle en hérite : ses résidents liront ce qui la cible.
	</p>
	<PiedFormulaire
		enCours={enregistrement}
		desactive={!choisis.length}
		soumission={false}
		on:annule={() => dispatch('annule')}
		on:enregistre={enregistrer}
	/>
</FormulaireCreation>

<style>
	.cibles {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		max-height: 20rem;
		overflow-y: auto;
		padding: 0.3rem 0;
	}
</style>
