<!--
  L'onglet **Avis** de la Communauté (#2075) — l'avis des utilisateurs sur
  l'application, la réponse du gestionnaire du site, et ce qui part sur le
  site vitrine.

  L'état et les appels vivent ICI, comme dans les autres onglets
  (`svelte-patterns`) : la page ne garde que le bouton d'en-tête, lié par
  `showForm` et `peutDeposer` — un compte qui a déjà donné son avis le
  corrige, il n'en donne pas un second.

  Ordre sous le titre (`ux-patterns` §0 ter) : ce qui qualifie la liste — un
  problème s'ouvre en affaire, pas en avis —, les filtres, le formulaire, la liste.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import ChargementDiffere from './ChargementDiffere.svelte';
	import ChoixPastilles from './ChoixPastilles.svelte';
	import EncartAvertissement from './EncartAvertissement.svelte';
	import EtatListe from './EtatListe.svelte';
	import ListeEtArchives from './ListeEtArchives.svelte';
	import ReglagesListe from './ReglagesListe.svelte';
	import CarteAvis from './CarteAvis.svelte';
	import { avis as avisApi, type Avis } from '#lib/api/index.ts';
	import { enCours } from '#lib/archives.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { FILTRES_NOTE, VITRINE } from '#lib/avis.ts';
	import { archiverPuis, confirmerPuis, SUPPRESSION } from '#lib/confirmation.ts';
	import { cibleDuHash, revelerCible } from '#lib/deepLink.ts';
	import { CATEGORIE_BUG, lienNouvelleAffaire } from '#lib/formulaire-affaire.ts';
	import { messageErreur, tenter } from '#lib/erreurs.ts';
	import { isAdmin } from '#lib/stores/auth.ts';

	/** Le formulaire de dépôt est ouvert ? Lié : le bouton vit dans l'en-tête de page. */
	export let showForm = false;
	/** Le lecteur peut-il DÉPOSER un avis (il n'en a pas encore) ? Lié pour l'en-tête. */
	export let peutDeposer = false;

	let liste: Avis[] = [];
	let gestionnaire = false;
	let chargement = true;
	let erreur = '';
	let filtreNote = '';
	let ouvert: number | null = null;
	let enEdition: number | null = null;

	$: affiches = filtreNote ? liste.filter((a) => String(a.note) === filtreNote) : liste;
	$: retenus = liste.filter((a) => a.publication_validee).length;

	async function charger() {
		try {
			const reponse = await avisApi.list();
			liste = reponse.avis;
			gestionnaire = reponse.gestionnaire;
			peutDeposer = reponse.mon_avis_id === null;
			erreur = '';
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	}

	onMount(async () => {
		await charger();
		const cible = cibleDuHash('avis');
		if (cible !== null) {
			ouvert = cible;
			revelerCible(`avis-${cible}`);
		}
	});

	function remplacer(maj: Avis) {
		liste = liste.map((a) => (a.id === maj.id ? maj : a));
		enEdition = null;
	}

	async function avisCree() {
		showForm = false;
		await charger();
	}

	const archiver = (a: Avis, archivee: boolean) =>
		archiverPuis("L'avis", 'les Archives, en bas de la liste', archivee, async () => {
			await avisApi.archiver(a.id, archivee);
			await charger();
		});

	const supprimer = (a: Avis) =>
		confirmerPuis(SUPPRESSION('Cet avis'), 'Supprimé', async () => {
			await avisApi.delete(a.id);
			await charger();
		});

	const retenir = (a: Avis, validee: boolean) =>
		tenter(
			async () => remplacer(await avisApi.retenir(a.id, validee)),
			validee ? `Retenu pour ${VITRINE}` : `Retiré de l'export ${VITRINE}`,
		);
</script>

<div class="avis-encart">
	<EncartAvertissement role="note">
		Un problème, un bogue ? Les avis ne sont pas faits pour ça :
		<a href={lienNouvelleAffaire(CATEGORIE_BUG)}>ouvrez une affaire</a>, elle sera suivie jusqu'à sa
		résolution.
	</EncartAvertissement>
</div>

<ReglagesListe>
	<ChoixPastilles
		options={FILTRES_NOTE}
		bind:valeur={filtreNote}
		tous="Toutes"
		compte={enCours(affiches).length}
		libelle="Note"
		libelleDevant
	/>
</ReglagesListe>

{#if gestionnaire}
	<p class="avis-export">
		<a class="btn btn-outline btn-sm" href={avisApi.exportUrl()} download
			>Exporter les avis retenus pour {VITRINE}</a
		>
		<span class="aide">{retenus} avis retenu{retenus > 1 ? 's' : ''}</span>
	</p>
{/if}

{#if showForm}
	<ChargementDiffere charger={() => import('#lib/components/FormulaireAvis.svelte')}>
		{#snippet contenu(FormulaireAvis)}
			<FormulaireAvis on:cree={avisCree} on:annule={() => (showForm = false)} />
		{/snippet}
	</ChargementDiffere>
{/if}

<EtatListe
	{chargement}
	{erreur}
	vide={affiches.length === 0}
	titreErreur="Impossible d'afficher les avis"
	titreVide="Aucun avis pour l'instant"
	messageVide="Dites-nous ce que l'application vous apporte : votre avis nous aide à l'améliorer."
>
	<ListeEtArchives
		liste={affiches}
		titreVideCourant="Aucun avis en cours"
		messageVideCourant="Les avis retirés sont rangés dans les Archives, ci-dessous."
	>
		<svelte:fragment let:items>
			{#each items as a (a.id)}
				<CarteAvis
					avis={a}
					{gestionnaire}
					estAdmin={$isAdmin}
					expanded={ouvert === a.id}
					enEdition={enEdition === a.id}
					onBasculer={() => (ouvert = basculer(ouvert, a.id))}
					onModifier={() => (enEdition = enEdition === a.id ? null : a.id)}
					onAnnuler={() => (enEdition = null)}
					onArchiver={(archivee) => archiver(a, archivee)}
					onSupprimer={() => supprimer(a)}
					onMisAJour={remplacer}
					onRetenir={(validee) => retenir(a, validee)}
				/>
			{/each}
		</svelte:fragment>
	</ListeEtArchives>
</EtatListe>

<style>
	.avis-encart {
		margin-bottom: 1rem;
	}
	.avis-export {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin: 0 0 1rem;
	}
</style>
