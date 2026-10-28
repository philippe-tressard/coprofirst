<!--
  UNE installation du registre, vue de la référence (onglet « Installations »,
  R4 #1880).

  La carte suit le standard du site (`ux-patterns` §3) : la gouttière dit QUAND
  l'installation a donné signe de vie et ce qu'elle EST (référence ou réplique) ;
  la dernière ligne, son état — teinté, c'est le seul qui appelle un geste —,
  sa version et ce qu'elle a accepté — et ses ALERTES (R4b #1960) : un badge
  teinté de la plus sérieuse, et leurs noms sous l'aperçu, lisibles au doigt
  sans survol. Repliée, toute la carte ouvre ; dépliée,
  seul le titre referme. Le corps — contact, décisions, services, rapport,
  contrat, journal — est `FicheRegistreInstallation`, chargé au premier dépliage.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import FicheRegistreInstallation from '#lib/components/FicheRegistreInstallation.svelte';
	import type {
		FicheInstallation,
		ResumeInstallation,
		ServiceAccordable,
		VagueLue,
		VersionsPubliees,
	} from '#lib/api/index.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import {
		classeInstallation,
		LIBELLE_ETAT_REGISTRE,
		libelleVersionCible,
		resumeAlertes,
		servicesAccordes,
	} from '#lib/registre-installations.ts';

	export let installation: ResumeInstallation;
	export let ouvert = false;
	/** La fiche, quand elle est chargée ; l'erreur, quand elle n'a pas pu l'être. */
	export let fiche: FicheInstallation | null = null;
	export let erreurFiche = '';
	export let accordables: ServiceAccordable[] = [];
	export let versions: VersionsPubliees = { proposees: [], lues_le: null };
	export let vagues: VagueLue[] = [];
	/** Un geste est en cours sur cette installation : ses boutons attendent. */
	export let enCours = false;

	const dispatch = createEventDispatcher<{ basculer: void }>();

	$: i = installation;
	$: vagueDe = vagues.find((v) => v.code === i.vague);
	$: titre = i.administrateur ? `${i.identifiant} · ${i.administrateur}` : i.identifiant;
	$: alertes = resumeAlertes(i.alertes);
</script>

<CarteListe
	id="installation-{i.identifiant}"
	quand={i.vue_le ?? i.cree_le}
	classe={classeInstallation(i.canal)}
	expanded={ouvert}
	onDeplier={() => dispatch('basculer')}
>
	<EnteteCarte {titre} basculable on:toggle={() => dispatch('basculer')}>
		<svelte:fragment slot="apercu">
			{#if !ouvert}
				<p class="apercu">
					{#if i.vue_le}Dernier contact le {fmtDatetime(i.vue_le)}{:else}Jamais revenue depuis son
						inscription{/if}{#if i.dernier_rapport_le}&nbsp;· dernier rapport le {fmtDatetime(
							i.dernier_rapport_le,
						)}{/if}.
				</p>
				{#if i.alertes.length}
					<p class="apercu-alertes" class:grave={alertes.grave}>
						{i.alertes.map((a) => a.libelle).join(' · ')}
					</p>
				{/if}
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="tags">
			<span
				class="badge"
				class:badge-orange={i.etat === 'en_attente'}
				class:badge-green={i.etat === 'active'}
				class:badge-red={i.etat === 'suspendue'}
				class:badge-gray={i.etat === 'resiliee'}>{LIBELLE_ETAT_REGISTRE[i.etat]}</span
			>
			{#if i.alertes.length}
				<span class="badge" class:badge-red={alertes.grave} class:badge-orange={!alertes.grave}
					>{alertes.texte}</span
				>
			{/if}
			{#if i.version_logicielle}<span class="badge badge-gray">v{i.version_logicielle}</span>{/if}
			{#if i.canal !== 'main'}<span title="Version cible du prochain bail"
					>→ {libelleVersionCible(i.version_cible)}{#if vagueDe}&nbsp;({vagueDe.libelle}){/if}</span
				>{/if}
			{#if i.conditions_acceptees}<span>Contrat v{i.conditions_acceptees}</span>{/if}
			<span>{servicesAccordes(i.services_autorises.length)}</span>
		</svelte:fragment>
	</EnteteCarte>

	{#if ouvert}
		<!--  Le corps ne referme pas la carte : on lit, on sélectionne, on copie. -->
		<div class="carte-corps corps" role="presentation" on:click|stopPropagation>
			{#if fiche}
				<FicheRegistreInstallation
					{fiche}
					{accordables}
					{versions}
					{vagues}
					{enCours}
					on:geste
					on:services
					on:distribution
				/>
			{:else}
				<EtatListe
					chargement={!erreurFiche}
					erreur={erreurFiche}
					titreErreur="Impossible d’afficher cette fiche"
					compact
				/>
			{/if}
		</div>
	{/if}
</CarteListe>

<style>
	/*  Le retrait de l'en-tête (`EnteteCarte`, 0,7 rem) : le corps s'aligne sur le titre. */
	.corps {
		padding: 0 0.7rem 0.75rem;
	}
	.apercu {
		margin: 0;
		color: var(--color-text-muted);
	}
	.apercu-alertes {
		margin: 0.15rem 0 0;
		font-weight: 600;
		color: var(--color-warning-texte);
	}
	.apercu-alertes.grave {
		color: var(--color-danger);
	}
</style>
