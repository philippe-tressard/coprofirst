<!--
  Admin › Copropriété › ÉQUIPEMENTS (#2442, 01/11/2026) — ce sur quoi l'on
  intervient : l'ascenseur, le chauffage, la plomberie… et, pour les contrats,
  l'assurance et le syndic.

  Ils étaient une énumération du code ; une autre copropriété (une piscine, un
  portail, une borne de recharge) ne pouvait pas compléter la liste. Arbitré :
  l'onglet vit à côté des Périmètres, réservé à l'administrateur, et la fiche
  suit la maquette C — les champs, l'aperçu en direct, ce qui le cite.

  Les gestes sont ceux des contrats : créer en tête (`FormulaireCreation`),
  corriger dans la carte, 📦 retirer de la saisie, et aux Archives ↩️ rendre ou
  🗑️ supprimer — ce dernier seulement quand plus rien ne le cite.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { equipements as equipementsApi, type UsagesEquipement } from '#lib/api/index.ts';
	import { messageErreur, tenter } from '#lib/erreurs.ts';
	import { archiverPuis, confirmerPuis, SUPPRESSION } from '#lib/confirmation.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { contientTousLesMots } from '#lib/texte.ts';
	import { estPerimetreParDefaut } from '#lib/perimetres/index.ts';
	import { slug } from '#lib/texte.ts';
	import {
		chargeEquipement,
		formulaireDepuis,
		formulaireVierge,
		type Equipement,
		type FormulaireEquipement,
	} from '#lib/equipements.ts';
	import { equipementsStore, rechargerEquipements } from '#lib/stores/equipements.ts';
	import { EQUIPEMENT } from '#lib/entites/equipement.ts';
	import BoutonNouveau from './BoutonNouveau.svelte';
	import CarteEquipement from './CarteEquipement.svelte';
	import ChampsEquipement from './ChampsEquipement.svelte';
	import ChampRecherche from './ChampRecherche.svelte';
	import EtatListe from './EtatListe.svelte';
	import FormulaireCreation from './FormulaireCreation.svelte';
	import ListeEtArchives from './ListeEtArchives.svelte';
	import PiedFormulaire from './PiedFormulaire.svelte';
	import ReglagesListe from './ReglagesListe.svelte';

	let chargement = true;
	let erreur = '';
	let recherche = '';
	let ouvert: number | null = null;

	let creationOuverte = false;
	let nouveau: FormulaireEquipement = formulaireVierge();
	let editId: number | null = null;
	let form: FormulaireEquipement = formulaireVierge();
	let enregistrement = false;
	/** Ce qui cite chaque équipement ouvert — lu à l'ouverture de sa carte. */
	let usages: Record<number, UsagesEquipement> = {};

	const estDefaut = (code: string) => estPerimetreParDefaut([code]);

	onMount(async () => {
		try {
			await rechargerEquipements();
		} catch (e) {
			//  Un écran d'administration qui dirait « aucun équipement » faute de
			//  les avoir lus inviterait à recréer ce qui existe (#816).
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			chargement = false;
		}
	});

	//  `archivee` est ce que `ListeEtArchives` lit : un équipement RETIRÉ de la saisie.
	$: liste = $equipementsStore
		.filter((e) =>
			contientTousLesMots([e.libelle, e.code, e.abreviation, e.description], recherche),
		)
		.map((e) => ({ ...e, archivee: !e.actif }));

	async function lireUsages(id: number) {
		try {
			usages = { ...usages, [id]: await equipementsApi.usages(id) };
		} catch {
			//  Le compteur est un confort : sans lui, 🗑️ ne s'offre pas, et la route
			//  refuserait de toute façon un équipement cité (409).
		}
	}

	function deplier(e: Equipement) {
		ouvert = basculer(ouvert, e.id);
		if (ouvert === e.id) lireUsages(e.id);
	}

	function ouvrirCreation() {
		nouveau = formulaireVierge(($equipementsStore.at(-1)?.ordre ?? 0) + 1);
		creationOuverte = true;
	}

	async function creer() {
		if (!nouveau.libelle.trim()) return;
		enregistrement = true;
		let cree: number | null = null;
		const ok = await tenter(async () => {
			({ id: cree } = await equipementsApi.create({
				code: slug(nouveau.libelle, '_'),
				...chargeEquipement(nouveau, estDefaut),
			}));
			await rechargerEquipements();
		}, 'Équipement ajouté');
		enregistrement = false;
		if (!ok) return;
		creationOuverte = false;
		//  Le nouvel équipement s'OUVRE : on voit ce qu'on vient de créer, au lieu de
		//  le chercher dans la liste.
		if (cree !== null) {
			ouvert = cree;
			lireUsages(cree);
		}
	}

	function modifier(e: Equipement) {
		editId = e.id;
		form = formulaireDepuis(e);
		lireUsages(e.id);
	}

	async function enregistrer() {
		if (editId === null || !form.libelle.trim()) return;
		enregistrement = true;
		const id = editId;
		const ok = await tenter(async () => {
			await equipementsApi.update(id, chargeEquipement(form, estDefaut));
			await rechargerEquipements();
		}, 'Équipement enregistré');
		enregistrement = false;
		if (ok) editId = null;
	}

	async function archiver(e: Equipement, retire: boolean) {
		await archiverPuis(`L’équipement « ${e.libelle} »`, 'les Archives', retire, async () => {
			await equipementsApi.update(e.id, { actif: !retire });
			await rechargerEquipements();
		});
	}

	async function supprimer(e: Equipement) {
		await confirmerPuis(SUPPRESSION(`L’équipement « ${e.libelle} »`), 'Supprimé', async () => {
			await equipementsApi.remove(e.id);
			await rechargerEquipements();
		});
	}
</script>

<!--  L'action primaire sur sa rangée, à gauche (`.actions-onglet`), puis les
      réglages de la liste (`ReglagesListe`) : la forme de toute liste du site,
      la page Affaires en tête (`ux-patterns` §3, §5 bis). -->
<div class="actions-onglet">
	<BoutonNouveau
		ouvert={creationOuverte}
		libelle={EQUIPEMENT.libelleNouveau}
		on:basculer={ouvrirCreation}
	/>
</div>

<ReglagesListe>
	<ChampRecherche
		id="recherche-equipements"
		bind:valeur={recherche}
		placeholder="Ascenseur, chauffage…"
		dans="le libellé, le code, l’abréviation"
	/>
</ReglagesListe>

{#if creationOuverte}
	<FormulaireCreation titre={EQUIPEMENT.libelleNouveau}>
		<form on:submit|preventDefault={creer}>
			<ChampsEquipement bind:form={nouveau} etat="creation" />
			<PiedFormulaire
				enCours={enregistrement}
				desactive={!nouveau.libelle.trim()}
				on:annule={() => (creationOuverte = false)}
			/>
		</form>
	</FormulaireCreation>
{/if}

{#if chargement || erreur || liste.length === 0}
	<EtatListe
		{chargement}
		{erreur}
		vide={liste.length === 0}
		titreErreur="Impossible d’afficher les équipements"
		titreVide={recherche ? 'Aucun équipement ne correspond' : 'Aucun équipement'}
		messageVide="Ajoutez-en un : contrats et affaires le proposeront aussitôt."
	/>
{:else}
	<ListeEtArchives
		{liste}
		titreVideCourant="Aucun équipement proposé à la saisie"
		messageVideCourant="Les équipements retirés sont rangés ci-dessous."
		let:items
	>
		{#each items as e (e.id)}
			<CarteEquipement
				equipement={e}
				expanded={ouvert === e.id}
				enEdition={editId === e.id}
				bind:form
				{enregistrement}
				usages={usages[e.id] ?? null}
				onBasculer={() => deplier(e)}
				onModifier={() => modifier(e)}
				onAnnuler={() => (editId = null)}
				onEnregistrer={enregistrer}
				onArchiver={(retire) => archiver(e, retire)}
				onSupprimer={() => supprimer(e)}
			/>
		{/each}
	</ListeEtArchives>
{/if}
