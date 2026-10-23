<!--
  FUSIONNER des affaires liées du Suivi des affaires (#2083) — au point comme
  entre deux points, et depuis la correction d'une affaire (#2173, monté tel
  quel par `ModaleFusionAffaires`).

  S'ouvre DANS le tableau, sous l'en-tête du groupe (la correction s'ouvre à la
  place de l'objet, `ux-patterns` §14 ter). À l'ouverture, l'assistant propose
  le titre et la description de l'affaire qui absorbe les autres
  (`POST /suivi-affaires/fusions/proposition`) — ✨ puis ⏳ qui clignote pendant
  l'appel ; sans assistant prêt, le serveur compose la proposition sans lui. Le
  conseil relit, corrige, puis **Fusionner**.

  Arbitré le 20/10/2026 : **la plus ancienne absorbe** — elle garde son numéro et
  reste ouverte ; les autres lui sont rattachées (Suites, pièces jointes,
  courriels). Une fusion ne se défait pas : la boîte le dit.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import SectionDescription from '$lib/components/SectionDescription.svelte';
	import { TICKET } from '$lib/entites/ticket';
	import { pliageDe } from '$lib/pliage';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import IconeIA from '$lib/components/IconeIA.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { messageErreur } from '$lib/erreurs';
	import { suiviAffaires } from '$lib/api';
	import type { AffaireAFusionner, FusionFaite } from '$lib/fusion-affaires';

	/**  Les affaires du groupe, la plus ancienne en tête : elle absorbe. Une
	 *   affaire du Suivi, ou une affaire liée depuis sa correction (#2173). */
	export let affaires: AffaireAFusionner[];
	/**  La fusion est faite : la vue relit le suivi — la correction, elle, lit
	 *   la principale, l'affaire corrigée ayant pu être absorbée. */
	export let onFusionne: (r: FusionFaite) => void;
	export let onAnnule: () => void;

	let titre = '';
	let description = '';
	let assisteIA = false;
	let proposition = true;
	let enCours = false;

	$: ids = affaires.map((a) => a.id);
	$: principale = affaires[0];

	async function proposer() {
		proposition = true;
		try {
			const p = await suiviAffaires.fusions.proposer(ids);
			titre = p.titre;
			description = p.description;
			assisteIA = p.assiste_ia;
		} catch (e) {
			toast('error', messageErreur(e, 'Proposition impossible'));
			titre ||= affaires.map((a) => a.titre).join(' / ');
		} finally {
			proposition = false;
		}
	}

	async function fusionner() {
		if (!titre.trim()) return;
		enCours = true;
		try {
			const r = await suiviAffaires.fusions.fusionner(ids, titre.trim(), description);
			toast('success', `${affaires.length} affaires fusionnées dans ${principale.numero}`);
			onFusionne(r);
		} catch (e) {
			toast('error', messageErreur(e, 'Fusion impossible'));
		} finally {
			enCours = false;
		}
	}

	onMount(proposer);
</script>

<form class="fusion" on:submit|preventDefault={fusionner}>
	<p class="aide">
		Fusionnez seulement les affaires qui portent le <strong>même besoin</strong>.
		<strong>{principale.numero}</strong>, la plus ancienne, absorbe
		{affaires
			.slice(1)
			.map((a) => a.numero)
			.join(', ')} : leurs suites, pièces jointes et courriels la rejoignent, et elle reste ouverte. Une
		fusion ne se défait pas.
	</p>
	{#if proposition}
		<EtatListe chargement messageChargement="L’assistant propose un titre et une description…" />
	{:else}
		<div class="field">
			<label for="fusion-titre-{principale.id}"
				>Titre de l’affaire fusionnée<EtoileRequis vide={!titre.trim()} /></label
			>
			<input id="fusion-titre-{principale.id}" type="text" maxlength="200" bind:value={titre} />
		</div>
		<SectionDescription
			pliable={pliageDe(TICKET, 'description')}
			idPrefixe="fusion-{principale.id}"
			hauteur="14rem"
			bind:valeur={description}
			{assisteIA}
		/>
		<div class="rangee">
			<button
				type="button"
				class="btn btn-sm btn-outline"
				disabled={proposition}
				aria-busy={proposition}
				on:click={proposer}
			>
				<IconeIA enCours={proposition} /> Nouvelle proposition
			</button>
		</div>
	{/if}
	<PiedFormulaire petit {enCours} desactive={proposition || !titre.trim()} on:annule={onAnnule} />
</form>

<style>
	.fusion {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.5rem 0 0.25rem;
	}
	.rangee {
		display: flex;
		justify-content: flex-start;
	}
</style>
