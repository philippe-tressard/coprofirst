<!--
  **Export vérifié de la copropriété** (#1749), dans Administration › Maintenance.

  Deux gestes, une même règle (`api/app/utils/export_copropriete.py`) :
  - « Vérifier la restauration » exporte la base dans un format neutre puis la
    réimporte dans une base jetable, table par table, empreinte par empreinte : on
    SAIT qu'elle se restaure, au lieu de le supposer ;
  - « Exporter » écrit l'archive complète — tables ET fichiers — dans le volume
    des sauvegardes (les trois dernières sont gardées). C'est elle qui servira au
    passage à PostgreSQL (DI-7) et à rendre ses données à une copropriété qui part.

  Les deux s'exécutent dans le processus de l'API : aucune base n'est ouverte à côté.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { instance, type DernierExport, type VerificationRestauration } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { fmtNombre, fmtOctets } from '#lib/utils.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	let verification: VerificationRestauration | null = null;
	let enVerification = false;
	let erreurVerification = '';

	let dernier: DernierExport | null = null;
	let erreurDernier = '';
	let enExport = false;

	async function relireDernier() {
		erreurDernier = '';
		try {
			dernier = await instance.dernierExport();
		} catch (e) {
			erreurDernier = messageErreur(e);
		}
	}

	onMount(relireDernier);

	async function verifier() {
		enVerification = true;
		erreurVerification = '';
		try {
			verification = await instance.verifierRestauration();
			toast(
				verification.restaurable ? 'success' : 'error',
				verification.restaurable
					? 'La base se restaure à l’identique.'
					: 'La base ne se restaure pas.',
			);
		} catch (e) {
			erreurVerification = messageErreur(e);
			verification = null;
		} finally {
			enVerification = false;
		}
	}

	async function exporter() {
		enExport = true;
		try {
			const { archive } = await instance.exporterCopropriete();
			toast('success', `Export lancé : ${archive}. Il s’écrit en arrière-plan.`);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enExport = false;
		}
	}
</script>

<section class="card config-section">
	<div class="config-section-entete">
		<div>
			<SectionFormulaire titre="Export vérifié" icone="layers" />
			<p class="muted">
				Toute la base dans un format qui ne doit rien au moteur, avec le nombre de lignes et une
				empreinte par table. La vérification la réimporte dans une base jetable et compare&nbsp;:
				rien n’est envoyé, rien n’est modifié.
			</p>
		</div>
		<div class="actions">
			<button class="btn btn-primary" type="button" on:click={verifier} disabled={enVerification}>
				{enVerification ? 'Vérification…' : 'Vérifier la restauration'}
			</button>
			<button class="btn" type="button" on:click={exporter} disabled={enExport}>
				{enExport ? 'Lancement…' : 'Exporter'}
			</button>
		</div>
	</div>

	{#if erreurVerification}
		<p class="verdict verdict-ko">
			La vérification n’a pas pu s’exécuter&nbsp;: {erreurVerification}
		</p>
	{:else if verification}
		<p
			class="verdict"
			class:verdict-ok={verification.restaurable}
			class:verdict-ko={!verification.restaurable}
		>
			{#if verification.restaurable}
				Se restaure à l’identique{SEPARATEUR.tiret}{fmtNombre(verification.tables)} tables, {fmtNombre(
					verification.lignes,
				)}
				lignes, en {fmtNombre(verification.duree_secondes)}&nbsp;s.
			{:else}
				Ne se restaure pas&nbsp;: {verification.ecarts.join(' ; ')}
			{/if}
		</p>
		{#if verification.ignorees.length}
			<p class="aide">
				Non exportées (absentes des modèles)&nbsp;: {verification.ignorees.join(', ')}.
			</p>
		{/if}
	{:else}
		<p class="muted verdict">Jamais vérifiée depuis cet écran.</p>
	{/if}

	{#if erreurDernier}
		<p class="aide">Dernier export illisible&nbsp;: {erreurDernier}</p>
	{:else if dernier?.archive}
		<p class="aide">
			Dernier export&nbsp;: <code>{dernier.archive}</code>{SEPARATEUR.tiret}{fmtOctets(
				dernier.octets,
			)},
			{fmtNombre(dernier.lignes)} lignes, {fmtNombre(dernier.fichiers)} fichiers{#if dernier.cree_le},
				le {fmtDatetime(dernier.cree_le)}{/if}.
			<button class="btn btn-sm btn-outline" type="button" on:click={relireDernier}
				>Actualiser</button
			>
		</p>
	{:else if dernier}
		<p class="aide">Aucun export dans le volume des sauvegardes.</p>
	{/if}
</section>

<style>
	.actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	/*  44 px : une cible tactile est une taille PHYSIQUE (#839). */
	.actions .btn {
		min-height: 44px;
	}
	.verdict {
		margin: 0.75rem 0 0.25rem;
	}
	.verdict-ok {
		color: var(--color-success-texte);
	}
	.verdict-ko {
		color: var(--color-danger);
	}
</style>
