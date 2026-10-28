<script lang="ts">
	//  🔴 Découpée le 01/10/2026 (#779) : la page passait 788 lignes. Chaque
	//  onglet possède désormais ce qu'il affiche — `OngletContrats`,
	//  `OngletPrestataires`, `OngletConsommations`. La page ne garde que ce
	//  qu'ils partagent : le chargement des trois listes, l'en-tête et ses
	//  boutons « + Nouveau … », la barre d'onglets.
	//
	//  ⏱ Les archives de l'onglet AFFICHÉ partent avec ces trois listes (#1845).
	//  Demandées par l'onglet, elles attendaient qu'il se monte, donc que les
	//  listes soient arrivées : une seconde vague, +130 ms à chaque ouverture.
	//  La page ne les lit pas ; elle les tient, comme les listes, pour qu'un
	//  onglet quitté puis rouvert les retrouve. `null` = pas encore lues :
	//  l'onglet ouvert ensuite les demande lui-même.
	//
	//  🔴 Le vocabulaire des prestataires vit dans `#lib/prestataires.ts`, pas
	//  dans un écran. La table des équipements écrite ici recopiait
	//  `TypeEquipement` et en OUBLIAIT deux valeurs — `assurance` et `syndic`,
	//  précisément celles que la fiche de copropriété désigne (#553).
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { tenter } from '#lib/erreurs.ts';
	import { essayer } from '#lib/chargement.ts';
	import {
		prestataires as prestApi,
		type ContratEntretien,
		type Notation,
		type Prestataire,
	} from '#lib/api/index.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import {
		getPageConfig,
		configStore,
		siteNomStore,
		defautsDePage,
	} from '#lib/stores/pageConfig.ts';
	import { marquerDonneesAffichees, trackTabView } from '#lib/telemetry.ts';
	import { cibleDuHash } from '#lib/deepLink.ts';
	import { routeOnglet } from '#lib/routes-onglets.ts';
	import EntetePage from '#lib/components/EntetePage.svelte';
	import BoutonNouveau from '#lib/components/BoutonNouveau.svelte';
	import BarreOnglets from '#lib/components/BarreOnglets.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	//  ⏱ Contrats et Consommations attendent un geste — le passage sur leur
	//  onglet : chargés à leur affichage (#1844). Le TYPE seul est importé ici.
	import type OngletContrats from '#lib/components/OngletContrats.svelte';
	import OngletPrestataires from '#lib/components/OngletPrestataires.svelte';
	import ChargementDiffere from '#lib/components/ChargementDiffere.svelte';

	$: _pc = getPageConfig($configStore, 'prestataires', defautsDePage('prestataires'));
	$: _siteNom = $siteNomStore;

	let prestataires: Prestataire[] = [];
	let contrats: ContratEntretien[] = [];
	let notations: Notation[] = [];
	let archivesPrestataires: Prestataire[] | null = null;
	let archivesContrats: ContratEntretien[] | null = null;
	let loading = true;

	// ── Onglets (3) ────────────────────────────────────────────────
	//  La liste, l'ordre ET l'adresse de chaque onglet vivent dans la table
	//  (`#lib/pages.ts`). Elle était écrite ici, et la table n'en connaissait que
	//  DEUX sur trois : « Contrats » n'était donc ni renommable ni descriptible
	//  depuis l'administration, alors que les quatre autres pages du site le sont.
	//
	//  ⚠️ `'prestations'` et `'visites'` ont disparu (#603), comme `?onglet=` lui-même
	//  (05/09/2026). Une ancienne adresse qui les nomme encore est redirigée vers la
	//  page par `resoudreOnglet`, jamais vers un onglet inventé.
	export let data: { onglet: string };
	$: onglet = data.onglet;
	$: trackTabView(onglet);

	//  Chaque onglet possède sa boîte de création ; la page n'en lit que l'état,
	//  pour le bouton de l'en-tête, et lui transmet le geste (R1).
	let ongletContrats: OngletContrats | null = null;
	let ongletPrestataires: OngletPrestataires | null = null;
	let creationContrat = false;
	let creationPrestataire = false;
	let showReleveForm = false;
	let libelleReleve = 'Nouveau relevé';

	onMount(async () => {
		//  Sans message de succès : un chargement réussi n'annonce rien.
		//  Les archives sans message : un échec laisse la section absente.
		const archives = Promise.all([
			onglet === 'prestataires' ? essayer(prestApi.archives(), []) : null,
			onglet === 'contrats' ? essayer(prestApi.contratsArchives(), []) : null,
		]);
		await tenter(async () => {
			[prestataires, contrats, notations] = await Promise.all([
				prestApi.list(),
				prestApi.contrats(),
				prestApi.notations(),
			]);
		});
		const [aPrest, aContrats] = await archives;
		if (aPrest) archivesPrestataires = aPrest[0];
		if (aContrats) archivesContrats = aContrats[0];
		marquerDonneesAffichees();
		loading = false;

		// Lien profond `#presta-<id>` : la page s'ouvre sur « Contrats », et une
		// fiche visée sans onglet restait invisible, l'ancre ne désignant aucun
		// élément rendu (`/prestataires#presta-23`, signalé le 28/07/2026).
		// L'ancre décide de la ROUTE ; l'onglet déplie et montre la fiche.
		//
		// ⚠️ L'ancre `#dv-<id>` d'une prestation ponctuelle est partie avec elle
		// (#603) : la page s'ouvre sur son défaut, sans erreur.
		const idPresta = cibleDuHash('presta');
		if (idPresta !== null && onglet !== 'prestataires')
			goto(`${routeOnglet('prestataires', 'prestataires')}#presta-${idPresta}`);
	});
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<!--  `BoutonNouveau` s'EFFACE pendant la saisie : l'annulation vit à côté
      d'« Enregistrer » (voir son en-tête — ce commentaire décrivait encore la
      bascule « ✕ Annuler » abandonnée le 12/09/2026). `alignerSaisie` cale le
      bouton sur la boîte de 720 px. -->
<EntetePage
	titre={_pc.titre}
	descriptif={_pc.descriptif}
	icone={_pc.icone || 'hard-hat'}
	alignerSaisie={creationPrestataire || creationContrat || showReleveForm}
>
	{#if $isCS}
		{#if onglet === 'prestataires'}
			<BoutonNouveau
				ouvert={creationPrestataire}
				libelle="Nouveau prestataire"
				on:basculer={() => ongletPrestataires?.basculerCreation()}
			/>
		{:else if onglet === 'contrats'}
			<BoutonNouveau
				ouvert={creationContrat}
				libelle="Nouveau contrat"
				on:basculer={() =>
					//  L'onglet se charge au geste (#1844) : pas encore monté, il lira
					//  `creationOuverte` à son montage, formulaire vierge — ce que fait
					//  `basculerCreation`. Sans ce repli, un clic rapide se perdait.
					ongletContrats ? ongletContrats.basculerCreation() : (creationContrat = !creationContrat)}
			/>
		{:else if onglet === 'consommations'}
			<BoutonNouveau
				ouvert={showReleveForm}
				libelle={libelleReleve}
				on:basculer={() => (showReleveForm = !showReleveForm)}
			/>
		{/if}
	{/if}
</EntetePage>

<BarreOnglets pageId="prestataires" actif={onglet} />

{#if loading}
	<EtatListe chargement />
{:else if onglet === 'contrats'}
	<ChargementDiffere charger={() => import('#lib/components/OngletContrats.svelte')}>
		{#snippet contenu(OngletContrats)}
			<OngletContrats
				bind:this={ongletContrats}
				bind:creationOuverte={creationContrat}
				bind:contrats
				bind:notations
				bind:archives={archivesContrats}
				{prestataires}
			/>
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'prestataires'}
	<OngletPrestataires
		bind:this={ongletPrestataires}
		bind:creationOuverte={creationPrestataire}
		bind:prestataires
		bind:notations
		bind:archives={archivesPrestataires}
		{contrats}
	/>
{:else if onglet === 'consommations'}
	<ChargementDiffere charger={() => import('#lib/components/OngletConsommations.svelte')}>
		{#snippet contenu(OngletConsommations)}
			<OngletConsommations bind:showReleveForm bind:libelleBouton={libelleReleve} {prestataires} />
		{/snippet}
	</ChargementDiffere>
{/if}
