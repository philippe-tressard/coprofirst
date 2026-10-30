<!--
  La palette de la résidence, dans Copropriété › Identité, sous le logo (#2379).

  Un GESTE immédiat, comme le logo (`ChampLogo`) : le choix part au serveur dès
  qu'il est fait, et la page le prend aussitôt (`appliquerPalette`) — on juge
  l'effet sur l'écran même. Le serveur vérifie le code contre son registre
  (`PUT /config/palette`) ; refusé, la page revient à la palette enregistrée.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import { config as configApi } from '#lib/api/index.ts';
	import type { PaletteCopropriete } from '#lib/api/index.ts';
	import { configStore } from '#lib/stores/pageConfig.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { appliquerPalette, CLE_PALETTE, lirePalette } from '#lib/palettes.ts';

	let palettes: PaletteCopropriete[] = [];
	let valeur = '';
	let enregistree = '';

	onMount(async () => {
		valeur = enregistree = lirePalette($configStore[CLE_PALETTE]);
		await tenter(
			async () => (palettes = await configApi.palettes()),
			undefined,
			'Palettes indisponibles',
		);
	});

	$: options = palettes.map((p) => ({ val: p.code, label: p.nom }));
	$: choisie = palettes.find((p) => p.code === valeur);
	//  Les pastilles sont de vrais boutons radio (`Pastille`) : leur `change`
	//  remonte ici, une fois `valeur` liée — un geste, pas un effet réactif.
	async function enregistrer() {
		const code = valeur;
		if (!code || code === enregistree) return;
		const avant = enregistree;
		enregistree = code;
		appliquerPalette(code);
		const ok = await tenter(async () => {
			await configApi.choisirPalette(code);
			configStore.update((c) => ({ ...c, [CLE_PALETTE]: code }));
		}, 'Palette enregistrée');
		if (!ok) {
			valeur = enregistree = avant;
			appliquerPalette(avant);
		}
	}
</script>

<div class="field champ-large" on:change={enregistrer}>
	<ChoixPastilles
		{options}
		bind:valeur
		tous={false}
		radio="palette"
		libelle="Palette de couleurs"
		libelleVisible
		defilante={false}
	/>
	{#if choisie}
		<div class="nuancier" aria-hidden="true">
			<span class="pastille-couleur" style:--nuance={choisie.primaire}></span>
			<span class="pastille-couleur" style:--nuance={choisie.accent}></span>
			<span class="pastille-couleur" style:--nuance={choisie.fond}></span>
		</div>
	{/if}
	<span class="aide"
		>Les couleurs du site, des courriels et des affiches de hall. Le style ne change pas&nbsp;; le
		choix s’applique aussitôt, et chaque résident garde son thème clair ou sombre.</span
	>
</div>

<style>
	.nuancier {
		display: flex;
		gap: 0.4rem;
	}
	.pastille-couleur {
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--nuance);
	}
</style>
