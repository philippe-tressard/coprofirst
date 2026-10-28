<!--
  L'onglet « Prestataires » (l'annuaire) de la page des prestataires — extrait
  le 01/10/2026 (#779), la page passait 788 lignes. Il possède ses filtres, la
  création, la correction dans la carte et le lien profond `#presta-<id>`. La
  page garde le chargement des listes et le bouton « Nouveau prestataire » de
  son en-tête, qui appelle `basculerCreation`.

  📦 Les fiches rangées ont leur écran depuis le 02/10/2026 (#1538) : la section
  Archives sous la liste, par `ListeEtArchives` — le motif des trois onglets de
  la Communauté. La page les lit avec ses listes quand l'onglet est celui
  qu'elle ouvre (#1845) ; sinon l'onglet les demande à son montage (`null`).
  Les contrats et les relevés n'ont pas à les voir.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { archiverPuis } from '#lib/confirmation.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { essayer } from '#lib/chargement.ts';
	import { basculer } from '#lib/accordeon.ts';
	import {
		prestataires as prestApi,
		type ContratEntretien,
		type Notation,
		type Prestataire,
	} from '#lib/api/index.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		EQUIPEMENTS as equipements,
		TYPES_PRESTATAIRE as typesPrestataire,
		filtresVides,
		filtresActifs,
		filtrerPrestataires,
		contactsAEnvoyer,
		contactsDepuis,
		prestataireDepuis,
	} from '#lib/prestataires.ts';
	import { telephonesDe } from '#lib/utils.ts';
	import { cibleDuHash, revelerCible } from '#lib/deepLink.ts';
	import FiltresPrestataires from '#lib/components/FiltresPrestataires.svelte';
	import ChampsPrestataire from '#lib/components/ChampsPrestataire.svelte';
	import CartePrestataire from '#lib/components/CartePrestataire.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import IntertitreGroupe from '#lib/components/IntertitreGroupe.svelte';
	import ListeEtArchives from '#lib/components/ListeEtArchives.svelte';

	export let prestataires: Prestataire[] = [];
	export let contrats: ContratEntretien[] = [];
	export let notations: Notation[] = [];
	/** La boîte de création est ouverte — lue par le bouton de l'en-tête. */
	export let creationOuverte = false;

	//  Une seule fiche dépliée à la fois (`#lib/accordeon`) : c'était un `Set`
	//  remis à un élément, déclaré en exception jusqu'au 01/10/2026 (#779).
	let ouvert: number | null = null;
	let submitting = false;

	let editPrestId: number | null = null;
	let prestForm = prestataireDepuis();
	let prestContacts = contactsDepuis();

	/** Les fiches rangées — `archivee` vient du serveur (`REGLES["prestataire"]`) ;
	 *  `null` tant qu'elles ne sont pas lues. */
	export let archives: Prestataire[] | null = null;

	let filtres = filtresVides();
	$: filteredPrests = filtrerPrestataires(prestataires, contrats, filtres);
	//  Les filtres valent aussi pour les Archives : chercher « ascenseur » doit
	//  retrouver l'ancien ascensoriste rangé.
	$: archivesFiltrees = filtrerPrestataires(archives ?? [], contrats, filtres);
	$: compactPrests = filteredPrests.length > 7;

	//  Tous les contrats du prestataire, assurances et mandats compris : la carte
	//  les montre. `contratsDuPrestataire` (`#lib/prestataires`) répond à une
	//  autre question — sous quel contrat il peut INTERVENIR — et les écarte.
	function contratsForPrest(prestId: number): ContratEntretien[] {
		return contrats.filter((c) => c.prestataire_id === prestId);
	}

	function nextVisitForPrest(prestId: number): string | null {
		const dates = contrats
			.filter((c) => c.prestataire_id === prestId && c.prochaine_visite)
			.map((c) => c.prochaine_visite as string)
			.sort();
		return dates[0] ?? null;
	}

	//  Lien profond `#presta-<id>` : la page a déjà conduit ici l'adresse qui le
	//  portait (elle s'ouvre sur « Contrats » par défaut — signalé le 28/07/2026).
	onMount(() => {
		//  Sans message : un échec laisse simplement la section absente.
		if (archives === null) essayer(prestApi.archives(), []).then(([a]) => (archives = a));
		const idPresta = cibleDuHash('presta');
		if (idPresta === null) return;
		ouvert = idPresta;
		revelerCible(`presta-${idPresta}`);
	});

	function resetPrestForm() {
		prestForm = prestataireDepuis();
		prestContacts = contactsDepuis();
		editPrestId = null;
	}

	/** Le geste du bouton « Nouveau prestataire » de l'en-tête de la page. */
	export function basculerCreation() {
		creationOuverte = !creationOuverte;
		//  Ouvrir la création referme une correction en cours : deux boîtes
		//  ouvertes en même temps, c'est le défaut des contrats du 10/09.
		if (creationOuverte) editPrestId = null;
		else resetPrestForm();
	}

	function fermerCreation() {
		creationOuverte = false;
		resetPrestForm();
	}

	function startEditPrest(p: Prestataire) {
		prestForm = prestataireDepuis(p);
		prestContacts = contactsDepuis(p);
		//  🔴 On n'ouvre PAS le formulaire de tête, et on ne fait PAS défiler : la
		//  correction s'ouvre dans la carte du prestataire, là où est le crayon
		//  (`CartePrestataire`). Un `scrollTo` était la cause exacte du symptôme
		//  signalé le 11/09/2026 — la page remontait, et l'objet corrigé quittait
		//  sa place sous les yeux.
		editPrestId = p.id;
	}

	async function savePrest() {
		if (!prestForm.nom || !prestForm.specialite) {
			toast('error', 'Nom et équipement obligatoires');
			return;
		}
		const { contacts, telephone } = contactsAEnvoyer(prestContacts);
		submitting = true;
		await tenter(
			async () => {
				if (editPrestId) {
					await prestApi.update(editPrestId, { ...prestForm, telephone, contacts });
				} else {
					await prestApi.create({ ...prestForm, telephone, contacts });
				}
				prestataires = await prestApi.list();
				fermerCreation();
			},
			editPrestId ? 'Prestataire modifié' : 'Prestataire ajouté',
		);
		submitting = false;
	}

	/** 📦 Ranger (`true`) ou ressortir (`false`) une fiche — un geste, un mot. */
	async function archiver(id: number, archivee: boolean) {
		const nom = [...prestataires, ...(archives ?? [])].find((p) => p.id === id)?.nom ?? '';
		await archiverPuis(`Le prestataire « ${nom} »`, 'les Archives', archivee, async () => {
			await prestApi.archiver(id, archivee);
			[prestataires, archives] = await Promise.all([prestApi.list(), prestApi.archives()]);
		});
	}
</script>

<FiltresPrestataires bind:filtres affiches={filteredPrests.length} />

<!--  🔴 La CRÉATION seulement. Corriger un prestataire ouvre le formulaire DANS
      sa carte, à la place de son corps — le motif des tickets, appliqué aux
      contrats le 10/09/2026 et signalé ici le 11/09 : le crayon est dans la
      carte, la boîte s'ouvrait en tête de liste.
      Aucune `cle` : rien n'a bougé, il n'y a rien à ramener à l'écran. -->
{#if $isCS && creationOuverte}
	<FormulaireCreation titre="Nouveau prestataire">
		<form on:submit|preventDefault={savePrest}>
			<ChampsPrestataire
				bind:prestForm
				bind:prestContacts
				{typesPrestataire}
				{equipements}
				etat="creation"
			/>
			<PiedFormulaire enCours={submitting} on:annule={fermerCreation} />
		</form>
	</FormulaireCreation>
{/if}

{#if filteredPrests.length === 0 && archivesFiltrees.length === 0}
	<div class="empty-state card">
		<h3>Aucun prestataire{filtresActifs(filtres) ? ' pour ces critères' : ''}</h3>
	</div>
{:else}
	<!--  Le même rendu, deux fois : les fiches courantes, puis les Archives
	      repliées sous la liste — `items` est la seule différence. -->
	<ListeEtArchives
		liste={[...filteredPrests, ...archivesFiltrees]}
		titreVideCourant="Aucun prestataire actif{filtresActifs(filtres) ? ' pour ces critères' : ''}"
		messageVideCourant="Les fiches archivées sont rangées dans les Archives, ci-dessous."
		let:items
	>
		{#each typesPrestataire.filter( (t) => items.some((p) => p.type_prestataire === t.val) ) as typeGroup (typeGroup.val)}
			{#if !filtres.type}
				<IntertitreGroupe libelle={typeGroup.label} descriptif={typeGroup.desc} />
			{/if}
			{#each items.filter((p) => p.type_prestataire === typeGroup.val) as p (p.id)}
				<CartePrestataire
					{p}
					archive={p.archivee}
					cs={contratsForPrest(p.id)}
					nextVisit={nextVisitForPrest(p.id)}
					notations={notations.filter((n) => n.prestataire_id === p.id)}
					expanded={ouvert === p.id}
					{compactPrests}
					peutModifier={$isCS}
					{telephonesDe}
					{editPrestId}
					bind:prestForm
					bind:prestContacts
					{typesPrestataire}
					{equipements}
					{submitting}
					onBasculer={(id) => (ouvert = basculer(ouvert, id))}
					onModifier={startEditPrest}
					onArchiver={archiver}
					onAnnuler={fermerCreation}
					onEnregistrer={savePrest}
					on:supprimee={(e) => (notations = notations.filter((n) => n.id !== e.detail))}
				/>
			{/each}
		{/each}
	</ListeEtArchives>
{/if}
