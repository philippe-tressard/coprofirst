<!--
  L'onglet « Contrats » de la page des prestataires — extrait le 01/10/2026
  (#779), la page passait 788 lignes. Il possède tout ce qu'il affiche : la
  création, la correction dans la carte, les documents, la synthèse ✨ et la
  notation d'un contrat. La page garde le chargement des listes et le bouton
  « Nouveau contrat » de son en-tête, qui appelle `basculerCreation`.

  📦 Les contrats rangés ont leur écran depuis le 02/10/2026 (#1538) : la section
  Archives sous la liste, par `ListeEtArchives`. L'onglet les charge lui-même
  (`contratsArchives()`) ; les décomptes d'échéance ne portent que sur les
  contrats courants — un contrat rangé n'a plus de visite à faire.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { perimetreDefautListe } from '#lib/perimetres/index.ts';
	import { archiverPuis } from '#lib/confirmation.ts';
	import { supprimerDocument } from '#lib/gestes-document.ts';
	import { attacherApres } from '#lib/fichiers.ts';
	import { messageErreur, tenter } from '#lib/erreurs.ts';
	import { essayer } from '#lib/chargement.ts';
	import { basculer } from '#lib/accordeon.ts';
	import {
		prestataires as prestApi,
		documents as docsApi,
		type ContratEntretien,
		type Document,
		type Notation,
		type Prestataire,
	} from '#lib/api/index.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { EQUIPEMENTS as equipements, contratDepuis, contratVierge } from '#lib/prestataires.ts';
	import { minuitDuJour, typeEquipementDuContrat } from '#lib/reporting.ts';
	import { relire, nombreOuNull } from '#lib/utils.ts';
	import CarteContrat from '#lib/components/CarteContrat.svelte';
	import FormulaireContrat from '#lib/components/FormulaireContrat.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import IntertitreGroupe from '#lib/components/IntertitreGroupe.svelte';
	import ListeEtArchives from '#lib/components/ListeEtArchives.svelte';

	export let prestataires: Prestataire[] = [];
	export let contrats: ContratEntretien[] = [];
	export let notations: Notation[] = [];
	/** La boîte de création est ouverte — lue par le bouton de l'en-tête. */
	export let creationOuverte = false;

	//  Un seul contrat déplié à la fois (`#lib/accordeon`) : c'était un `Set`
	//  remis à un élément, déclaré en exception jusqu'au 01/10/2026 (#779).
	let ouvert: number | null = null;
	let submitting = false;

	// ── Notation ──────────────────────────────────────────────────
	//  ⚠️ La notation SURVIT au retrait des prestations ponctuelles (#603) : elle
	//  se saisit depuis la fiche du prestataire, et son seul rattachement restant
	//  est le CONTRAT. Le rattachement à un devis part avec l'objet qui le portait.
	let showNotationForm: { prestataireId: number; contratId?: number } | null = null;
	let notationNote: number | null = null;
	let notationCommentaire = '';
	let notationSaving = false;

	function openNotationForm(prestataireId: number, contratId?: number) {
		showNotationForm = { prestataireId, contratId };
		notationNote = null;
		notationCommentaire = '';
	}

	async function saveNotation() {
		if (!showNotationForm || !notationNote || notationNote < 1 || notationNote > 5) {
			toast('error', 'Sélectionnez une note entre 1 et 5');
			return;
		}
		//  Capturés AVANT le rappel : à l'intérieur, rien ne garantit qu'ils n'ont
		//  pas changé.
		const cible = showNotationForm;
		const note = notationNote;
		notationSaving = true;
		await tenter(async () => {
			const n = await prestApi.createNotation({
				prestataire_id: cible.prestataireId,
				note,
				commentaire: notationCommentaire.trim() || undefined,
				contrat_id: cible.contratId,
			});
			notations = [n, ...notations];
			showNotationForm = null;
		}, 'Notation enregistrée');
		notationSaving = false;
	}

	// ── Formulaire ────────────────────────────────────────────────
	/**  Documents choisis avant que le contrat existe (#921) — vidés à chaque
	 *   fermeture, sinon ils s'attacheraient au contrat SUIVANT. */
	let contratFichiersEnAttente: File[] = [];
	let editContratId: number | null = null;

	//  La forme du formulaire vit dans `#lib/prestataires` : elle était énumérée
	//  TROIS fois ici — déclaration, remise à zéro, édition —, si bien qu'ajouter
	//  un champ demandait de le poser aux trois endroits.
	let contratForm = contratVierge(perimetreDefautListe());

	// ── Documents ─────────────────────────────────────────────────
	//  Chaque `DocumentsRattaches` porte son propre envoi (#370) ; il ne reste ici
	//  que la liste, qui appartient à l'onglet puisque c'est lui qui l'affiche.
	let contratDocsMap: Record<number, Document[]> = {};

	/** Les contrats rangés — `archivee` vient du serveur (`REGLES["contrat"]`) ;
	 *  `null` tant qu'ils ne sont pas lus. La page les lit avec ses listes quand
	 *  elle s'ouvre sur cet onglet (#1845) ; sinon l'onglet les demande. */
	export let archives: ContratEntretien[] | null = null;
	$: rangees = archives ?? [];

	// ── Échéances des contrats ────────────────────────────────────
	//  🔴 L'onglet « Visites » lisait ces mêmes contrats dans un écran à part
	//  (#603). Une visite n'est pas un objet : c'est la PROCHAINE ÉCHÉANCE d'un
	//  contrat, et elle avait deux définitions qui ne donnaient pas la même
	//  réponse — ici `prochaine_visite`, une date posée à la main ; dans le
	//  calendrier, `frequence_type` réparti sur les mois de l'exercice. Le
	//  décompte reste, l'écran séparé part.
	//
	//  ⚠️ Minuit, pas l'instant ; `contrats` cité pour relire (`utils.relire`).
	$: minuit = relire(contrats, minuitDuJour);
	$: contratEnRetard = (c: ContratEntretien) =>
		!!c.prochaine_visite && new Date(c.prochaine_visite) < minuit;
	$: echeancesEnRetard = contrats.filter(contratEnRetard);
	$: echeancesAVenir = contrats.filter((c) => c.prochaine_visite && !contratEnRetard(c));
	$: contratsSansEcheance = contrats.filter((c) => !c.prochaine_visite);

	/**  Les contrats d'un groupe, la prochaine échéance d'abord.
	 *
	 *   ⚠️ Sans échéance = en FIN de liste, jamais en tête : `null` se compare mal
	 *   et un tri naïf les aurait remontés devant les retards. */
	function parEcheance(liste: ContratEntretien[]): ContratEntretien[] {
		return [...liste].sort((a, b) => {
			if (!a.prochaine_visite && !b.prochaine_visite) return 0;
			if (!a.prochaine_visite) return 1;
			if (!b.prochaine_visite) return -1;
			return a.prochaine_visite < b.prochaine_visite ? -1 : 1;
		});
	}

	/**  Les documents de ces contrats, ajoutés à la table — la carte d'un contrat
	 *   rangé montre les siens comme une autre. */
	async function chargerDocs(liste: ContratEntretien[]) {
		const results = await Promise.allSettled(
			liste.map((c) => docsApi.list(undefined, c.id).then((docs) => ({ id: c.id, docs }))),
		);
		const map: Record<number, Document[]> = { ...contratDocsMap };
		for (const r of results) {
			if (r.status === 'fulfilled') map[r.value.id] = r.value.docs;
		}
		contratDocsMap = map;
	}

	onMount(async () => {
		//  Sans message : un échec laisse simplement la section absente.
		if (archives === null) [archives] = await essayer(prestApi.contratsArchives(), []);
		await chargerDocs([...contrats, ...(archives ?? [])]);
	});

	function resetContratForm() {
		contratForm = contratVierge(perimetreDefautListe());
		editContratId = null;
	}

	//  Ferme les deux enveloppes — une seule est ouverte à la fois.
	function closeContratForm() {
		creationOuverte = false;
		editContratId = null;
		contratFichiersEnAttente = []; //  sinon ils iraient au contrat suivant
		resetContratForm();
	}

	/** Le geste du bouton « Nouveau contrat » de l'en-tête de la page. */
	export function basculerCreation() {
		if (creationOuverte) {
			closeContratForm();
			return;
		}
		resetContratForm();
		creationOuverte = true;
	}

	/**  🔴 Le geste ✨ ouvre la CORRECTION, il n'en invente pas une seconde.
	 *
	 *   La proposition remplit le champ « Synthèse » du formulaire d'édition —
	 *   celui du crayon, le même composant, le même bouton Enregistrer. Écrire un
	 *   cadre à part aurait donné deux formulaires pour un seul objet, et deux
	 *   endroits où la règle d'enregistrement aurait divergé.
	 *
	 *   ⚠️ RIEN n'est enregistré : « Annuler » referme, et le contrat garde sa
	 *   synthèse d'origine. C'est la décision 03 du 11/09/2026 — le risque devient
	 *   nul, et améliorer une synthèse bâclée reste possible. */
	let syntheseEnCoursId: number | null = null;

	async function synthetiserContrat(c: ContratEntretien) {
		syntheseEnCoursId = c.id;
		try {
			const { synthese } = await prestApi.synthetiserContrat(c.id);
			startEditContrat({ ...c, notes: synthese });
			toast('info', 'Synthèse proposée — relisez-la avant d’enregistrer');
		} catch (e) {
			//  ⚠️ Le message vient du serveur : il dit POURQUOI (clé refusée, délai
			//  dépassé, quota). Un « Erreur » générique laisserait chercher.
			toast('error', messageErreur(e, 'La rédaction n’a pas abouti'));
		} finally {
			syntheseEnCoursId = null;
		}
	}

	function startEditContrat(c: ContratEntretien) {
		contratForm = contratDepuis(
			c,
			perimetreDefautListe(),
			typeEquipementDuContrat(c, prestataires),
		);
		editContratId = c.id;
		creationOuverte = false;
	}

	async function saveContrat() {
		if (!contratForm.libelle || !contratForm.prestataire_id) {
			toast('error', 'Libellé et prestataire obligatoires');
			return;
		}
		submitting = true;
		//  La règle vit dans `reporting.ts` — elle était écrite ici, dans le
		//  groupement des cartes et dans le chargement du formulaire, avec trois
		//  résultats différents sur le même contrat (29/08/2026).
		const resolvedType = typeEquipementDuContrat(
			{ ...contratForm, prestataire_id: Number(contratForm.prestataire_id) },
			prestataires,
		);
		const payload = {
			...contratForm,
			type_equipement: resolvedType,
			prestataire_id: Number(contratForm.prestataire_id),
			duree_initiale_valeur: nombreOuNull(contratForm.duree_initiale_valeur),
			duree_initiale_unite: contratForm.duree_initiale_valeur
				? contratForm.duree_initiale_unite
				: null,
			frequence_type: contratForm.frequence_type || null,
			frequence_valeur: nombreOuNull(contratForm.frequence_valeur),
			prochaine_visite: contratForm.prochaine_visite || null,
		};
		//  🔴 Lu AVANT la fermeture, qui remet `editContratId` à `null`. Le message
		//  le lisait après : une modification annonçait donc « Contrat créé ».
		const etaitUneModification = editContratId !== null;
		await tenter(
			async () => {
				if (editContratId) {
					await prestApi.updateContrat(editContratId, payload);
				} else {
					const cree = await prestApi.createContrat(payload);
					await attacherApres('contrat', cree?.id, contratFichiersEnAttente, 'Contrat créé');
				}
				contrats = await prestApi.contrats();
				closeContratForm();
			},
			etaitUneModification ? 'Contrat modifié' : 'Contrat créé',
		);
		submitting = false;
	}

	async function rechargerDocs(contratId: number) {
		contratDocsMap = { ...contratDocsMap, [contratId]: await docsApi.list(undefined, contratId) };
	}

	//  Le geste est partagé (`#lib/gestes-document`) ; la liste se recharge.
	const deleteDoc = (contratId: number, docId: number) =>
		supprimerDocument(docId, 'Ce document', () => rechargerDocs(contratId));

	/** 📦 Ranger (`true`) ou ressortir (`false`) un contrat — un geste, un mot. */
	async function archiver(id: number, archivee: boolean) {
		const libelle = [...contrats, ...rangees].find((c) => c.id === id)?.libelle ?? '';
		await archiverPuis(`Le contrat « ${libelle} »`, 'les Archives', archivee, async () => {
			await prestApi.archiverContrat(id, archivee);
			[contrats, archives] = await Promise.all([prestApi.contrats(), prestApi.contratsArchives()]);
		});
	}
</script>

<!--  🔴 CE BLOC NE SERT QU'À LA CRÉATION (corrigé le 10/09/2026).

      Il gouvernait les deux gestes (`contratFormOuvert || editContratId`) tant
      que la correction se rendait ici. Elle a déménagé DANS la carte le matin
      même — et ce bloc-ci est resté ouvert sur la même condition : deux boîtes
      « Modifier le contrat » apparaissaient à l'écran en même temps, celle-ci
      en tête de liste et celle de la carte plus bas, et sa `cle` ramenait la
      page en haut.

      ⚠️ C'est la régression de #356 dans sa forme la plus banale : on DÉPLACE
      un rendu et on oublie de retirer l'ancien. `lint:geste-edition` ne
      pouvait pas la voir — sa règle B compte les rendus d'un formulaire
      FICHIER PAR FICHIER, et l'extraction venait justement d'en mettre un dans
      un second fichier. Un contrôle dont la portée est le fichier devient
      aveugle le jour où l'on découpe.

      La création reste ici, en tête de liste : elle ne corrige aucun objet,
      elle n'a donc pas de place à prendre — et pas de `cle` non plus, le geste
      qui l'ouvre étant juste au-dessus. -->
{#if creationOuverte}
	<FormulaireCreation titre="Nouveau contrat">
		<FormulaireContrat
			bind:contratForm
			{prestataires}
			{equipements}
			contratId={null}
			documents={[]}
			bind:fichiersEnAttente={contratFichiersEnAttente}
			onSupprimer={deleteDoc}
			onAjoute={rechargerDocs}
			{submitting}
			onAnnuler={closeContratForm}
			onEnregistrer={saveContrat}
		/>
	</FormulaireCreation>
{/if}

<!--  Synthèse — les trois décomptes viennent de l'onglet « Visites » retiré
      (#603). Ils portent sur les MÊMES contrats qu'il lisait ; ils sont
      seulement rendus là où vivent les contrats. -->
<div class="contrats-summary">
	<span class="contrats-summary-count"
		>{contrats.length} contrat{contrats.length !== 1 ? 's' : ''} actif{contrats.length !== 1
			? 's'
			: ''}</span
	>
	{#if echeancesEnRetard.length > 0}
		<span class="badge echeance-badge echeance-badge--retard"
			>⚠️ {echeancesEnRetard.length} visite{echeancesEnRetard.length > 1 ? 's' : ''} en retard</span
		>
	{/if}
	{#if echeancesAVenir.length > 0}
		<span class="badge echeance-badge echeance-badge--ok">🗓 {echeancesAVenir.length} à venir</span>
	{/if}
	{#if contratsSansEcheance.length > 0}
		<span class="badge echeance-badge">{contratsSansEcheance.length} sans échéance</span>
	{/if}
</div>

<!-- Groupé par spécialité du prestataire -->
{#if contrats.length === 0 && rangees.length === 0}
	<div class="empty-state card">
		<h3>Aucun contrat</h3>
		<p>Ajoutez le premier contrat via le bouton ci-dessus.</p>
	</div>
{:else}
	<!--  Le même rendu, deux fois : les contrats courants, puis les Archives
	      repliées sous la liste — `items` est la seule différence. -->
	<ListeEtArchives
		liste={[...contrats, ...rangees]}
		titreVideCourant="Aucun contrat actif"
		messageVideCourant="Les contrats archivés sont rangés dans les Archives, ci-dessous."
		let:items
	>
		{#each equipements.filter( (e) => items.some((c) => typeEquipementDuContrat(c, prestataires) === e.val) ) as specGroup (specGroup.val)}
			<IntertitreGroupe libelle={specGroup.label} />
			{#each parEcheance(items.filter((c) => typeEquipementDuContrat(c, prestataires) === specGroup.val)) as c (c.id)}
				{@const contrat = c}
				{@const prest = prestataires.find((p) => p.id === c.prestataire_id)}
				<CarteContrat
					{contrat}
					archive={c.archivee}
					{prest}
					expanded={ouvert === c.id}
					enRetard={!c.archivee && contratEnRetard(c)}
					documents={contratDocsMap[contrat.id] ?? []}
					peutModifier={$isCS}
					{editContratId}
					bind:contratForm
					{prestataires}
					{equipements}
					{submitting}
					onBasculer={(id) => (ouvert = basculer(ouvert, id))}
					onModifier={startEditContrat}
					onSynthetiser={synthetiserContrat}
					{syntheseEnCoursId}
					onArchiver={archiver}
					onSupprimerDoc={deleteDoc}
					onAjouteDoc={rechargerDocs}
					onAnnuler={closeContratForm}
					onEnregistrer={saveContrat}
					onNoter={openNotationForm}
					noteEnCours={showNotationForm?.contratId === c.id}
					bind:noteValeur={notationNote}
					bind:noteCommentaire={notationCommentaire}
					noteSaving={notationSaving}
					onAnnulerNote={() => (showNotationForm = null)}
					onEnregistrerNote={saveNotation}
				/>
			{/each}
		{/each}
	</ListeEtArchives>
{/if}

<style>
	.contrats-summary {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.contrats-summary-count {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}

	/*  Les trois décomptes d'échéance, repris de l'onglet « Visites » retiré. */
	.echeance-badge {
		font-size: var(--fs-sm);
	}
	.echeance-badge--retard {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
	.echeance-badge--ok {
		color: var(--color-primary);
		border-color: var(--color-primary);
	}
</style>
