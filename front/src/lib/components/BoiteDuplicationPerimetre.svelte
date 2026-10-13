<!--
  **Dupliquer un périmètre avec ses sous-périmètres** (13/10/2026).

  Demandé à l'écran : « Bâtiment 1 » porte ses espaces ; un bâtiment de plus,
  c'était les recréer un par un. La copie reçoit un nom, un code et une
  description ; ses descendants gardent les leurs, et leurs caractéristiques.

  La boîte est celle de la création (`BoiteNouveauPerimetre`) : mêmes champs,
  même règle d'activation — le code proposé sous le même parent que la source.
  Elle s'ouvre DANS le nœud, là où est le geste (`ux-patterns` §14 ter).

  🔴 **Le bâtiment se choisit, il ne se recopie pas.** Le lien d'un nœud au
  bâtiment réel décide qui lit un contenu ciblé : la copie de « Bâtiment 1 » qui
  le garderait ferait lire aux résidents du bâtiment 1 ce qui est publié pour le
  nouveau. Le champ n'apparaît que si la source en porte un — le serveur exige
  alors le choix, et le refuse sinon.
-->
<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import BoiteNouveauPerimetre from '$lib/components/BoiteNouveauPerimetre.svelte';
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';
	import { copropriete as coproprieteApi, perimetres as perimetresApi } from '$lib/api';
	import type { Batiment } from '$lib/api';
	import { essayer } from '$lib/chargement';
	import { tenter } from '$lib/erreurs';
	import { codeSousParent, type Perimetre } from '$lib/perimetres';
	import { rechargerPerimetres } from '$lib/stores/perimetres';

	/** Le nœud dont on copie la branche. */
	export let source: Perimetre;

	const dispatch = createEventDispatcher<{ annule: void; fini: void }>();

	let nouveau = { code: '', libelle: '', description: source.description };
	let batimentId: number | null = null;
	let batiments: Batiment[] = [];
	let erreurBatiments = '';
	let enregistrement = false;

	$: estBatiment = source.batiment_id !== null;
	$: codePropose = codeSousParent(source.parent, nouveau.libelle);

	onMount(async () => {
		if (estBatiment) [batiments, erreurBatiments] = await essayer(coproprieteApi.batiments(), []);
	});

	async function enregistrer() {
		enregistrement = true;
		await tenter(
			async () => {
				await perimetresApi.dupliquer(source.id, {
					code: (nouveau.code || codePropose).trim(),
					libelle: nouveau.libelle.trim(),
					description: nouveau.description,
					batiment_id: estBatiment ? batimentId : null,
				});
				await rechargerPerimetres();
				dispatch('fini');
			},
			'Périmètre dupliqué',
			'Duplication impossible',
		);
		enregistrement = false;
	}
</script>

<BoiteNouveauPerimetre
	titre="Copie de {source.libelle} et de ses {source.nb_descendants} sous-périmètre(s)"
	encadre={false}
	bind:nouveau
	{codePropose}
	{enregistrement}
	incomplet={estBatiment && batimentId === null}
	on:annule={() => dispatch('annule')}
	on:enregistre={enregistrer}
>
	{#if estBatiment}
		<label class="field"
			><span>Bâtiment<EtoileRequis vide={batimentId === null} /></span>
			<select bind:value={batimentId}>
				<option value={null}>— Choisir —</option>
				{#each batiments as b (b.id)}
					<option value={b.id}>Bât. {b.numero}</option>
				{/each}
			</select>
			<span class="aide">
				{erreurBatiments ||
					'Celui que représente la copie : ses résidents liront ce qui la cible. Un bâtiment qui a déjà son périmètre est refusé.'}
			</span>
		</label>
	{/if}
</BoiteNouveauPerimetre>
