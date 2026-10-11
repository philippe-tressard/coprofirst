<!--
  Ma résidence › Règlement — la section « Texte du règlement ».

  Arbitré à l'écran le 11/10/2026, maquette à l'appui : *« tu t'es écarté de la
  standardisation »*. La section avait son propre chargement de Markdown et sa
  liste d'actes à cocher ; elle n'a plus que ce que le site a déjà.

  | Lecteur | Ce qu'il voit |
  |---|---|
  | administration | l'objet **Pièces jointes** standard (`DocumentsRattaches`) : jusqu'à dix fichiers, ajoutés dès qu'on les choisit, retirés d'une croix, Markdown accepté — l'assistant lit tous les `.md`, bout à bout |
  | tous les autres, conseil compris | une phrase, et le lien vers le règlement publié dans la Fiche |

  Le serveur tient la même frontière : la catégorie des fichiers est réservée à
  l'administration (`visibility.CATEGORIES_ADMIN_SEUL`), et seul l'admin reçoit
  `categorie_id` ; le lien, lui, est calculé pour CE lecteur (`lien_reglement`).
-->
<script lang="ts">
	import DocumentsRattaches from '$lib/components/DocumentsRattaches.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { documents as docsApi, type Document, type EtatReglement } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { supprimerDocument } from '$lib/gestes-document';
	import { ACCEPT_FICHIERS_REGLEMENT, TYPES_FICHIERS_REGLEMENT } from '$lib/reglement';
	import { isAdmin } from '$lib/stores/auth';

	export let etat: EtatReglement;
	/** Relit l'état de l'onglet — un fichier joint ou retiré change le texte lu. */
	export let onRecharger: () => Promise<void>;

	let fichiers: Document[] = [];
	let chargement = false;
	let erreur = '';
	let categorieLue: number | null = null;

	$: if ($isAdmin && etat.categorie_id !== null && etat.categorie_id !== categorieLue) {
		categorieLue = etat.categorie_id;
		lire(etat.categorie_id);
	}

	async function lire(categorieId: number) {
		chargement = true;
		try {
			fichiers = await docsApi.list(categorieId);
			erreur = '';
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	}

	async function apresChangement(categorieId: number) {
		await lire(categorieId);
		await onRecharger();
	}
</script>

<section class="card config-section">
	<h3 class="config-section-title">Texte du règlement</h3>
	{#if $isAdmin && etat.categorie_id !== null}
		<EtatListe {chargement} {erreur}>
			<DocumentsRattaches
				cible="categorie"
				objetId={etat.categorie_id}
				documents={fichiers}
				idChamp="reglement-fichiers"
				accept={ACCEPT_FICHIERS_REGLEMENT}
				types={TYPES_FICHIERS_REGLEMENT}
				onAjoute={apresChangement}
				onSupprimer={(categorieId, docId) =>
					supprimerDocument(docId, 'ce fichier du règlement', () => apresChangement(categorieId))}
			/>
		</EtatListe>
		<p class="aide">
			L'assistant lit tous les fichiers Markdown joints, mis bout à bout dans l'ordre d'ajout.
			Section visible de l'administration seule.
		</p>
	{:else if etat.lien_reglement}
		<p class="phrase">
			Le règlement de copropriété est disponible sur le site :
			<a href={etat.lien_reglement}>consulter le règlement de copropriété</a>.
		</p>
	{:else}
		<p class="phrase">Le règlement de copropriété est disponible sur le site, dans la Fiche.</p>
	{/if}
</section>

<style>
	.phrase {
		margin: 0;
	}
</style>
