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

  **Un bâtiment neuf, par défaut** (#1945, arbitré le 14/10/2026) : aucun écran
  ne crée de bâtiment, et tous ceux de la copropriété ont déjà leur périmètre —
  « Bâtiment 1 → Bâtiment 5 » n'aboutissait jamais. La boîte demande donc le
  numéro du bâtiment à créer ; le serveur le crée à l'image de celui copié. Les
  bâtiments existants SANS périmètre restent proposés (`noeudDuBatiment`, la
  question que pose aussi le refus serveur) ; s'il n'y en a aucun, le choix
  disparaît et seul le numéro reste.
-->
<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import BoiteNouveauPerimetre from '#lib/components/BoiteNouveauPerimetre.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import { copropriete as coproprieteApi, perimetres as perimetresApi } from '#lib/api/index.ts';
	import type { Batiment } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { codeSousParent, noeudDuBatiment, type Perimetre } from '#lib/perimetres/index.ts';
	import { rechargerPerimetres } from '#lib/stores/perimetres.ts';

	/** Le nœud dont on copie la branche. */
	export let source: Perimetre;

	const dispatch = createEventDispatcher<{ annule: void; fini: void }>();

	let nouveau = { code: '', libelle: '', description: source.description };
	/**  Le bâtiment de la copie : un existant libre, ou `'nouveau'` — le défaut,
	 *   puisque c'est le seul choix qui aboutit sur une copropriété complète. */
	let choix: number | 'nouveau' = 'nouveau';
	let numero = '';
	let batiments: Batiment[] = [];
	let erreurBatiments = '';
	let enregistrement = false;

	$: estBatiment = source.batiment_id !== null;
	$: codePropose = codeSousParent(source.parent, nouveau.libelle);
	$: libres = batiments.filter((b) => !noeudDuBatiment(b.id));
	$: neuf = choix === 'nouveau';

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
					batiment_id: estBatiment && choix !== 'nouveau' ? choix : null,
					nouveau_batiment: estBatiment && neuf ? numero.trim() : null,
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
	incomplet={estBatiment && neuf && !numero.trim()}
	on:annule={() => dispatch('annule')}
	on:enregistre={enregistrer}
>
	{#if estBatiment}
		{#if libres.length}
			<label class="field"
				><span>Bâtiment<EtoileRequis /></span>
				<select bind:value={choix}>
					<option value="nouveau">Nouveau bâtiment</option>
					{#each libres as b (b.id)}
						<option value={b.id}>Bât. {b.numero}</option>
					{/each}
				</select>
				{#if !neuf}
					<span class="aide"
						>Celui que représente la copie : ses résidents liront ce qui la cible.</span
					>
				{/if}
			</label>
		{/if}
		{#if neuf}
			<label class="field"
				><span>Numéro du nouveau bâtiment<EtoileRequis vide={!numero.trim()} /></span>
				<input bind:value={numero} autocomplete="off" />
				<span class="aide">
					{erreurBatiments ||
						`Créé dans la fiche de la copropriété avec les caractéristiques de « ${source.libelle} » (étages, appartements…), sans aucun lot. Ses résidents liront ce qui cible la copie.`}
				</span>
			</label>
		{/if}
	{/if}
</BoiteNouveauPerimetre>
