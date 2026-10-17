<!--
  Les CANAUX de distribution, en tête de l'onglet « Installations » (R5 #1881, D21).

  Un canal est un pointeur vers une version de `main` — jamais une branche de travail :
  - `replica` avance SEUL, chaque nuit, à la lecture de sa branche sur le dépôt
    public (`registre/canaux.relire_replica`) : il n'a pas de geste ici ;
  - un canal spécial (`special-<nom>`) se crée et s'avance par l'opérateur — chaque
    installation qui le suit l'inscrit à son journal.

  Repliée par défaut : ce qui qualifie la liste reste au-dessus d'elle (`ux-patterns`
  §0 ter), sans la repousser sous un formulaire qu'on n'a pas demandé.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import SectionRepliee from '$lib/components/SectionRepliee.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { registre as registreApi, type CanalDistribution } from '$lib/api';
	import { fmtDatetime } from '$lib/date';
	import { messageErreur } from '$lib/erreurs';
	import { PREFIXE_CANAL_SPECIAL } from '$lib/registre-installations';
	import { demander } from '$lib/saisie';

	export let canaux: CanalDistribution[] = [];

	const dispatch = createEventDispatcher<{ change: CanalDistribution[] }>();

	let ouvert = false;
	let nom = PREFIXE_CANAL_SPECIAL;
	let version = '';
	let enCours = false;

	$: saisi = nom.trim() !== PREFIXE_CANAL_SPECIAL && version.trim() !== '';

	function avancer(c: CanalDistribution) {
		nom = c.nom;
		version = c.version ?? '';
	}

	function effacer() {
		nom = PREFIXE_CANAL_SPECIAL;
		version = '';
	}

	async function enregistrer() {
		const cible = nom.trim();
		const motif = await demander({
			titre: `Canal ${cible} en ${version.trim()}`,
			message: 'Ses installations reçoivent cette version à leur prochain bail, selon leur vague.',
			libelle: 'Motif',
			placeholder: 'Ce qui motive le changement — il s’inscrit au journal de chaque installation.',
			libelleValider: 'Enregistrer',
			requis: true,
		});
		if (!motif?.trim()) return;
		enCours = true;
		try {
			dispatch('change', await registreApi.pointerCanal(cible, version.trim(), motif.trim()));
			toast('success', `${cible} pointe vers ${version.trim()}.`);
			effacer();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}
</script>

<SectionRepliee titre="Canaux de distribution" compte={canaux.length} bind:ouvert>
	<ul class="canaux">
		{#each canaux as c (c.nom)}
			<li>
				<strong>{c.nom}</strong>
				<span>{c.version ? `v${c.version}` : 'version pas encore lue'}</span>
				{#if c.avance_le}
					<span class="aide-ligne"
						>avancé le {fmtDatetime(c.avance_le)}{#if c.version_precedente}&nbsp;(depuis v{c.version_precedente}){/if}</span
					>
				{/if}
				{#if c.modifiable}
					<button type="button" class="btn btn-sm" disabled={enCours} on:click={() => avancer(c)}
						>Avancer</button
					>
				{:else}
					<span class="aide-ligne">suit la branche, chaque nuit</span>
				{/if}
			</li>
		{:else}
			<li class="aide">
				Aucun canal lu : replica le sera cette nuit, avant le renouvellement des baux.
			</li>
		{/each}
	</ul>

	<div class="pointer">
		<div class="field">
			<label for="canal-special-nom">Canal spécial</label>
			<input id="canal-special-nom" type="text" bind:value={nom} disabled={enCours} />
		</div>
		<div class="field">
			<label for="canal-special-version">Version</label>
			<input
				id="canal-special-version"
				type="text"
				inputmode="decimal"
				placeholder="2.172.0"
				bind:value={version}
				disabled={enCours}
			/>
		</div>
	</div>
	<p class="aide">
		Un canal spécial épingle un groupe d’installations sur une version promue. Ce qu’un client a de
		spécifique passe par les services accordés, jamais par un canal.
	</p>
	{#if saisi}
		<PiedFormulaire soumission={false} {enCours} on:annule={effacer} on:enregistre={enregistrer} />
	{/if}
</SectionRepliee>

<style>
	.canaux {
		list-style: none;
		margin: 0 0 0.75rem;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: var(--fs-sm);
	}
	.canaux li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem 0.75rem;
	}
	.aide-ligne {
		color: var(--color-text-muted);
	}
	.pointer {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
	}
</style>
