<!--
  Ma résidence › Règlement — la section « Texte du règlement ».

  Arbitré à l'écran le 11/10/2026, maquette à l'appui : *« tu t'es écarté de la
  standardisation »*. La section avait son propre chargement de Markdown et sa
  liste d'actes à cocher ; elle n'a plus que ce que le site a déjà.

  | Lecteur | Ce qu'il voit |
  |---|---|
  | administration | la provenance et les fichiers, en lecture ; le crayon ouvre le formulaire standard : **Provenance**, l'objet **Pièces jointes** (`DocumentsRattaches`, dix fichiers, Markdown accepté — l'assistant lit tous les `.md`, bout à bout), puis Annuler et Enregistrer |
  | tous les autres, conseil compris | une phrase, et le lien vers le règlement publié dans la Fiche |

  ## Le crayon, puis Annuler et Enregistrer (arbitré sur maquette le 11/10/2026)

  *« il serait préférable d'avoir l'icône d'édition et les boutons Annuler et
  Enregistrer (standard UX) »* — la forme de la Fiche de la résidence : le
  crayon (`aria-pressed`, le mode se lit sur lui), `FormulaireCreation`, puis
  `PiedFormulaire`.

  ⚠️ **Annuler ne retire pas un fichier joint.** Comme dans les Fiches de Ma
  résidence, une pièce part au serveur dès qu'on la choisit et se retire d'une
  croix (`DocumentsRattaches`) ; Annuler et Enregistrer ne portent que la
  provenance. Différer le dépôt changerait l'objet Pièces jointes de tout le site.

  La provenance complète « d'après … » sous chaque avis
  (`utils/question_reglement/provenance`).

  Le serveur tient la même frontière : la catégorie des fichiers est réservée à
  l'administration (`visibility.CATEGORIES_ADMIN_SEUL`), et seul l'admin reçoit
  `categorie_id` et `provenance` ; le lien, lui, est calculé pour CE lecteur
  (`lien_reglement`).
-->
<script lang="ts">
	import DocumentsRattaches from '#lib/components/DocumentsRattaches.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import ListeDocuments from '#lib/components/ListeDocuments.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		documents as docsApi,
		reglement as reglementApi,
		type Document,
		type EtatReglement,
	} from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { supprimerDocument } from '#lib/gestes-document.ts';
	import { ACCEPT_FICHIERS_REGLEMENT, TYPES_FICHIERS_REGLEMENT } from '#lib/reglement.ts';
	import { isAdmin } from '#lib/stores/auth.ts';

	export let etat: EtatReglement;
	/** Relit l'état de l'onglet — un fichier joint ou retiré change le texte lu. */
	export let onRecharger: () => Promise<void>;

	let fichiers: Document[] = [];
	let chargement = false;
	let erreur = '';
	let categorieLue: number | null = null;

	let edition = false;
	let provenance = '';
	let enregistrement = false;

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

	function basculerEdition() {
		provenance = etat.provenance ?? '';
		edition = !edition;
	}

	async function enregistrer() {
		if (!provenance.trim()) {
			toast('error', 'La provenance du texte est obligatoire.');
			return;
		}
		enregistrement = true;
		try {
			etat = await reglementApi.modifierProvenance(provenance.trim());
			edition = false;
			toast('success', 'Texte du règlement enregistré.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enregistrement = false;
		}
	}
</script>

<section class="card config-section">
	<div class="entete">
		<h3 class="config-section-title">Texte du règlement</h3>
		{#if $isAdmin && etat.categorie_id !== null}
			<!--  Le mode se lit sur l'icône qui a ouvert le formulaire (`ux-patterns` §13 bis). -->
			<button
				class="btn-icon-edit"
				aria-label={edition ? 'Annuler la modification' : 'Modifier le texte du règlement'}
				title={edition ? 'Annuler la modification' : 'Modifier'}
				aria-pressed={edition}
				on:click={basculerEdition}><IconeAction icone="pencil" /></button
			>
		{/if}
	</div>
	{#if $isAdmin && etat.categorie_id !== null}
		<EtatListe {chargement} {erreur}>
			{#if edition}
				<!--  `encadre={false}` : la section EST le cadre (#425). -->
				<FormulaireCreation titre="Modifier le texte du règlement" encadre={false}>
					<form on:submit|preventDefault={enregistrer}>
						<label class="field">
							<span>Provenance <EtoileRequis vide={!provenance.trim()} /></span>
							<input
								type="text"
								bind:value={provenance}
								maxlength="300"
								placeholder="la numérisation du règlement et de ses modificatifs"
							/>
							<span class="aide">Complète « d'après … » sous chaque réponse de l'assistant.</span>
						</label>
						<div class="field">
							<span class="libelle-groupe" id="reglement-pieces">Pièces jointes</span>
							<div role="group" aria-labelledby="reglement-pieces">
								<DocumentsRattaches
									cible="categorie"
									objetId={etat.categorie_id}
									documents={fichiers}
									idChamp="reglement-fichiers"
									accept={ACCEPT_FICHIERS_REGLEMENT}
									types={TYPES_FICHIERS_REGLEMENT}
									onAjoute={apresChangement}
									onSupprimer={(categorieId, docId) =>
										supprimerDocument(docId, 'ce fichier du règlement', () =>
											apresChangement(categorieId),
										)}
								/>
							</div>
						</div>
						<p class="aide">
							L'assistant lit tous les fichiers Markdown joints, mis bout à bout dans l'ordre
							d'ajout. Un fichier part dès qu'on le choisit, et se retire d'une croix.
						</p>
						<PiedFormulaire enCours={enregistrement} on:annule={() => (edition = false)} />
					</form>
				</FormulaireCreation>
			{:else}
				<dl class="lecture">
					<dt>Provenance</dt>
					<dd>{etat.provenance ?? 'Non renseignée — à saisir par le crayon.'}</dd>
					<dt>Fichiers lus par l'assistant</dt>
					<dd><ListeDocuments documents={fichiers} /></dd>
				</dl>
				<p class="aide">Section visible de l'administration seule.</p>
			{/if}
		</EtatListe>
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
	.entete {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.phrase {
		margin: 0;
	}
	.lecture {
		margin: 0;
	}
	.lecture dt {
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-top: 0.6rem;
	}
	.lecture dt:first-child {
		margin-top: 0;
	}
	.lecture dd {
		margin: 0.2rem 0 0;
	}
</style>
