<!--
  L'onglet **Imports** de l'administration : un tableur du syndic, trois sources.

  ## Pourquoi un onglet et non trois (#2062, maquette validée le 21/10/2026)

  « Import Lots », « Import TC » et « Import Vigik » occupaient trois onglets
  pour un seul geste — déposer un tableur, le rapprocher des lots. La source se
  choisit désormais en pastilles, au-dessus de l'écran d'import qui ne change
  pas : `OngletImportLots`, et `OngletImportAcces` selon son modèle.

  ## La source est une ADRESSE

  `?onglet=imports&source=vigik` ouvre l'import Vigik : le choix se copie, le
  bouton Précédent le rejoue, et les anciennes clés (`?onglet=import_tc`,
  `$lib/admin-adresses`) y mènent. Une source inconnue ouvre les lots.
-->
<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import { IMPORT_TELECOMMANDES, IMPORT_VIGIK } from '$lib/imports-acces';

	const SOURCES = [
		{ val: 'lots', label: 'Lots' },
		{ val: 'telecommandes', label: 'Télécommandes' },
		{ val: 'vigik', label: 'Vigik' },
		//  L'état descriptif du RÈGLEMENT (#2213) : ce qu'est chaque lot — nature,
		//  circulation qui le dessert, tantièmes —, rapproché des lots par leur numéro.
		{ val: 'etat-descriptif', label: 'État descriptif' },
	];

	$: demandee = $page.url.searchParams.get('source') ?? '';
	$: courante = SOURCES.some((s) => s.val === demandee) ? demandee : 'lots';
	let choisie = '';
	//  L'adresse fait foi : un Précédent la change, la pastille suit.
	$: choisie = courante;
	//  Une pastille choisie change l'adresse — jamais l'inverse en boucle : la
	//  ligne du dessus ne dépend que de l'adresse.
	$: if (choisie && choisie !== courante) {
		const params = new URLSearchParams($page.url.searchParams);
		params.set('source', choisie);
		goto(`${$page.url.pathname}?${params.toString()}`, { noScroll: true, keepFocus: true });
	}
</script>

<ChoixPastilles
	options={SOURCES}
	bind:valeur={choisie}
	tous={false}
	radio="source-import"
	libelle="Source"
	libelleVisible
	defilante={false}
/>

{#if courante === 'lots'}
	<ChargementDiffere charger={() => import('$lib/components/OngletImportLots.svelte')}>
		{#snippet contenu(OngletImportLots)}
			<OngletImportLots />
		{/snippet}
	</ChargementDiffere>
{:else if courante === 'etat-descriptif'}
	<ChargementDiffere charger={() => import('$lib/components/OngletImportEtatDescriptif.svelte')}>
		{#snippet contenu(OngletImportEtatDescriptif)}
			<OngletImportEtatDescriptif />
		{/snippet}
	</ChargementDiffere>
{:else}
	{#key courante}
		<ChargementDiffere charger={() => import('$lib/components/OngletImportAcces.svelte')}>
			{#snippet contenu(OngletImportAcces)}
				<OngletImportAcces modele={courante === 'vigik' ? IMPORT_VIGIK : IMPORT_TELECOMMANDES} />
			{/snippet}
		</ChargementDiffere>
	{/key}
{/if}
