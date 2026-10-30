<!--
  **Les diagnostics réglementaires de la copropriété** — leurs rapports, leur
  dépôt, leur synthèse, et les types déclarés non applicables.

  ## Pourquoi ce composant (#852, 08/09/2026)

  Ramener les sept formulaires de Résidence **dans leur section** — demandé à
  l'écran : *« l'édition est en bas de page et non dans la section
  sélectionnée »* — a porté la page de 1 350 à 1 412 lignes, et le garde-fou de
  modularité l'a refusée.

  🔴 **Il avait raison, et pas seulement sur la taille.** C'était la dernière
  section de l'écran à ne passer par aucun composant : Plans, Règlement et
  Comptes-rendus d'AG partagent `SectionDocuments` depuis #522, celle-ci était
  restée à même la page avec ses **onze** variables d'état, ses **six** gestes et
  ses cent quatre-vingts lignes de balisage.

  ⚠️ Trois réponses possibles au refus, une seule mauvaise (`ux-patterns`) :
  découper quand l'ajout est propre à l'écran, remonter la règle d'un cran quand
  il dit quelque chose de global, **raboter — jamais**. Ici c'est la première :
  une section de l'écran Résidence, avec son état et ses appels.

  ## Ce qu'il porte, et ce qu'il laisse à la page

  Il porte **tout** son domaine : la liste, ses formulaires, ses appels d'API et
  ses messages. La page ne lui passe que ce qu'elle a déjà chargé —
  `bind:types` — et le droit d'écrire.

  ⚠️ `bind:types` plutôt qu'un événement : la page charge la liste au démarrage,
  en parallèle des trois autres, et c'est elle qui sait dire « la lecture a
  échoué » (`erreur`). Lui faire recharger depuis le composant dupliquerait cet
  état de chargement, qui est justement ce que #522 avait unifié.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import ChampDateDocument from '#lib/components/ChampDateDocument.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import LigneRapportDiagnostic from '#lib/components/LigneRapportDiagnostic.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import FormulaireDocument from '#lib/components/FormulaireDocument.svelte';
	import {
		diagnostics as diagnosticsApi,
		documents as documentsApi,
		type DiagnosticType,
		type Document,
		type RapportDiagnostic,
	} from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import type { PiecesFiche } from '#lib/components/PiecesJointesFiche.svelte';
	import { tenter } from '#lib/erreurs.ts';
	import { titreOuNomDuFichier } from '#lib/fichiers.ts';
	import { confirmerPuis, SUPPRESSION } from '#lib/confirmation.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { jourIso } from '#lib/date.ts';
	import { classeFlux } from '#lib/flux.ts';

	/** Les types de diagnostic et leurs rapports — chargés par la page. */
	export let types: DiagnosticType[] = [];
	/** Non vide = on n'a PAS pu charger. Distinct de « chargé et vide » (#522). */
	export let erreur = '';
	/** Le lecteur peut-il déposer, corriger et supprimer ? (conseil syndical) */
	export let peutModifier = false;

	//  Dépôt d'un rapport : l'identifiant du TYPE en cours d'ajout, ou `null`.
	let showDiagForm: number | null = null;
	let newDiagTitre = '';
	let newDiagDate = '';
	let newDiagFichiers: File[] = [];
	let savingDiag = false;

	let editingRapportId: number | null = null;
	let editingRapportTitre = '';
	let editingRapportDate = '';
	let editingRapportSynthese = '';
	let savingRapport = false;
	/** La section « Pièces jointes » du rapport en correction (migration 0278). */
	let piecesRapport: PiecesFiche | null = null;

	/**  Les annexes des rapports, rangées sous leur rapport — un appel pour la
	 *   section. Un échec les laisse vides : les rapports restent lisibles. */
	let annexes = new Map<number, Document[]>();
	onMount(async () => {
		[annexes] = await essayer(documentsApi.annexesParFiche('diagnostic'), annexes);
	});

	function remplacerDans(rapport: RapportDiagnostic) {
		types = types.map((t) => ({
			...t,
			rapports: t.rapports.map((r) => (r.id === rapport.id ? rapport : r)),
		}));
	}

	let togglingNonApplicableId: number | null = null;
	//  UN bloc déplié à la fois dans la section (accordéon, 30/09/2026 —
	//  `#lib/accordeon`) : la synthèse d'un rapport (son id) ou le bloc des
	//  diagnostics non applicables (`NON_APPLICABLES`). C'était un `Set` de
	//  synthèses, et le `<details>` vivait à côté sans rien savoir d'elles.
	const NON_APPLICABLES = 'non-applicables';
	let deplie: number | typeof NON_APPLICABLES | null = null;

	/**  La GOUTTIÈRE d'un diagnostic (arbitré le 11/10/2026) : la date de son
	 *   rapport le plus récent — celle du diagnostic, jamais celle du dépôt —,
	 *   puis « DIAG. », le classement du fil (`classeFlux`). Sans rapport daté,
	 *   la gouttière ne porte que le classement. */
	const CLASSE = classeFlux('diagnostic');
	const dernierDiagnostic = (t: DiagnosticType) =>
		t.rapports
			.map((r) => r.date_rapport)
			.filter((d): d is string => !!d)
			.sort()
			.at(-1) ?? null;

	$: actifs = types.filter((t) => !t.non_applicable);
	$: nonApplicables = types.filter((t) => t.non_applicable);

	function startAddRapport(typeId: number) {
		showDiagForm = typeId;
		newDiagTitre = '';
		//  La date est DEMANDÉE et PROPOSÉE — aujourd'hui, modifiable (11/10/2026).
		newDiagDate = jourIso();
		newDiagFichiers = [];
	}

	async function addRapport() {
		if (!showDiagForm || !newDiagFichiers?.length || !newDiagDate) return;
		//  Capturé AVANT le rappel : TypeScript ne conserve pas dans une closure le
		//  fait que la garde ci-dessus a écarté `null`.
		const typeId = showDiagForm;
		savingDiag = true;
		const files = Array.from(newDiagFichiers);
		const newRapports: RapportDiagnostic[] = [];
		await tenter(
			async () => {
				for (const file of files) {
					//  Sans titre saisi, chaque fichier prend le sien — c'est ce que dit
					//  l'aide du champ, et c'est ici que ça se décide.
					const titre = titreOuNomDuFichier(newDiagTitre, file);
					const rapport = await diagnosticsApi.uploadRapport(typeId, titre, newDiagDate, file);
					newRapports.push(rapport);
				}
				types = types.map((t) =>
					t.id === typeId ? { ...t, rapports: [...newRapports, ...t.rapports] } : t,
				);
				showDiagForm = null;
			},
			files.length > 1 ? `${files.length} rapports ajoutés` : 'Rapport ajouté',
		);
		savingDiag = false;
	}

	function startEditRapport(r: RapportDiagnostic) {
		editingRapportId = r.id;
		editingRapportTitre = r.titre;
		//  Un rapport sans date : la correction PROPOSE celle de son dépôt.
		editingRapportDate = r.date_rapport
			? String(r.date_rapport).substring(0, 10)
			: jourIso(r.publie_le);
		editingRapportSynthese = r.synthese ?? '';
		piecesRapport = {
			cible: 'diagnostic',
			objetId: r.id,
			principal: {
				url: diagnosticsApi.downloadUrl(r.id),
				nom: r.fichier_nom,
				retirer: async () => {
					const suivant = await diagnosticsApi.retirerFichier(r.id);
					remplacerDans(suivant);
					return { url: diagnosticsApi.downloadUrl(suivant.id), nom: suivant.fichier_nom };
				},
			},
			onChange: (liste) => (annexes = new Map(annexes).set(r.id, liste)),
		};
	}

	async function saveRapport() {
		if (!editingRapportId) return;
		savingRapport = true;
		//  Capturé AVANT le rappel : TypeScript ne conserve pas dans une closure le
		//  fait que la garde ci-dessus a écarté `null`.
		const rapportId = editingRapportId;
		await tenter(async () => {
			const updated = await diagnosticsApi.updateRapport(rapportId, {
				titre: editingRapportTitre.trim() || undefined,
				date_rapport: editingRapportDate || null,
				synthese: editingRapportSynthese.trim() || null,
			});
			remplacerDans(updated);
			editingRapportId = null;
		}, 'Rapport mis à jour');
		savingRapport = false;
	}

	async function deleteRapport(typeId: number, rapportId: number) {
		await confirmerPuis(SUPPRESSION('Ce rapport'), 'Rapport supprimé', async () => {
			await diagnosticsApi.deleteRapport(rapportId);
			types = types.map((t) =>
				t.id === typeId ? { ...t, rapports: t.rapports.filter((r) => r.id !== rapportId) } : t,
			);
		});
	}

	async function toggleNonApplicable(typeId: number, value: boolean) {
		togglingNonApplicableId = typeId;
		await tenter(
			async () => {
				const updated = await diagnosticsApi.toggleNonApplicable(typeId, value);
				types = types.map((t) =>
					t.id === typeId ? { ...t, non_applicable: updated.non_applicable } : t,
				);
			},
			value ? 'Diagnostic masqué (non applicable)' : 'Diagnostic réactivé',
		);
		togglingNonApplicableId = null;
	}
</script>

<section class="section-diagnostics">
	<div class="section-header">
		<h2 class="section-title">&#x1F50D; Diagnostics et Contrôles Réglementaires</h2>
	</div>

	<!--  🔴 LES FORMULAIRES SONT DANS LEUR SECTION (#852). Ils étaient rendus à la
	      FIN du fichier de la page, après toutes les sections : déposer un rapport
	      ouvrait une boîte quatre cents pixels plus bas, hors de l'écran. -->
	{#if showDiagForm !== null}
		<FormulaireDocument
			intitule="Ajouter un rapport"
			bind:titre={newDiagTitre}
			titreRequis={false}
			placeholderTitre="Rapport DPE 2024…"
			aideTitre="Sans titre, chaque fichier prend le sien."
			multiple
			libelleFichier="Fichier(s)"
			bind:fichiers={newDiagFichiers}
			enregistrement={savingDiag}
			complet={!!newDiagFichiers?.length && !!newDiagDate}
			on:annuler={() => (showDiagForm = null)}
			on:enregistrer={addRapport}
		>
			<svelte:fragment slot="specifiques">
				<ChampDateDocument
					idPrefixe="diag"
					libelle="Date du diagnostic"
					bind:valeur={newDiagDate}
				/>
			</svelte:fragment>
		</FormulaireDocument>
	{/if}

	{#if editingRapportId !== null}
		<FormulaireDocument
			edition
			intitule="Modifier le rapport"
			bind:titre={editingRapportTitre}
			avecFichier={false}
			piecesJointes={piecesRapport}
			enregistrement={savingRapport}
			complet={!!editingRapportTitre.trim() && !!editingRapportDate}
			on:annuler={() => (editingRapportId = null)}
			on:enregistrer={saveRapport}
		>
			<svelte:fragment slot="specifiques">
				<ChampDateDocument
					idPrefixe="edit-r"
					libelle="Date du diagnostic"
					bind:valeur={editingRapportDate}
				/>
			</svelte:fragment>
			<label class="field" for="edit-r-synthese" slot="description">
				Synthèse
				<textarea
					id="edit-r-synthese"
					bind:value={editingRapportSynthese}
					placeholder="Conclusions clés, points d'attention, recommandations…"
					rows="4"></textarea>
			</label>
		</FormulaireDocument>
	{/if}

	<EtatListe
		compact
		{erreur}
		vide={types.length === 0}
		messageVide="Aucun diagnostic réglementaire disponible."
	>
		<div>
			{#each actifs as dtype (dtype.id)}
				<!--  La carte du site (#1819), sans dépliage : ses rapports sont son
				      contenu, toujours visibles. La date et « DIAG. » dans la
				      gouttière (11/10/2026), la fréquence en capsule neutre. -->
				<CarteListe quand={dernierDiagnostic(dtype)} classe={CLASSE}>
					<EnteteCarte titre={dtype.nom}>
						<svelte:fragment slot="actions">
							{#if peutModifier && dtype.rapports.length === 0}
								<button
									class="btn-icon"
									aria-label="Non applicable à cette copropriété"
									title="Non applicable à cette copropriété"
									disabled={togglingNonApplicableId === dtype.id}
									on:click={() => toggleNonApplicable(dtype.id, true)}
									><IconeAction icone="eye-off" /></button
								>
							{/if}
						</svelte:fragment>
						<p class="diag-texte" slot="apercu">{dtype.texte_legislatif}</p>
						<svelte:fragment slot="tags">
							{#if dtype.frequence}
								<span class="badge badge-gray">{dtype.frequence}</span>
							{/if}
						</svelte:fragment>
					</EnteteCarte>
					<div class="carte-corps corps-diagnostic">
						{#if dtype.rapports.length > 0}
							<div class="diag-rapports">
								{#each dtype.rapports as rapport (rapport.id)}
									<LigneRapportDiagnostic
										{rapport}
										{peutModifier}
										ouvert={deplie === rapport.id}
										annexes={annexes.get(rapport.id) ?? []}
										onBasculer={() => (deplie = basculer(deplie, rapport.id))}
										onModifier={() => startEditRapport(rapport)}
										onSupprimer={() => deleteRapport(dtype.id, rapport.id)}
									/>
								{/each}
							</div>
						{/if}

						{#if peutModifier}
							<div class="diag-add">
								<button class="btn btn-sm" on:click={() => startAddRapport(dtype.id)}
									>+ Ajouter un rapport</button
								>
							</div>
						{/if}
					</div>
				</CarteListe>
			{/each}
		</div>

		{#if peutModifier && nonApplicables.length > 0}
			<details
				class="diag-non-applicable-section"
				open={deplie === NON_APPLICABLES}
				on:toggle={(e) => {
					if (e.currentTarget.open) deplie = NON_APPLICABLES;
					else if (deplie === NON_APPLICABLES) deplie = null;
				}}
			>
				<summary>Diagnostics non applicables ({nonApplicables.length})</summary>
				<div class="diag-list liste-non-applicables">
					{#each nonApplicables as dtype (dtype.id)}
						<div class="diag-card card diag-card-disabled">
							<div class="diag-header">
								<div class="diag-title-row">
									<span class="diag-nom">{dtype.nom}</span>
									{#if dtype.frequence}
										<span class="badge badge-blue">{dtype.frequence}</span>
									{/if}
									<button
										class="btn btn-sm"
										disabled={togglingNonApplicableId === dtype.id}
										on:click={() => toggleNonApplicable(dtype.id, false)}
										><Icon name="undo-2" size={14} /> Réactiver</button
									>
								</div>
								<p class="diag-texte">{dtype.texte_legislatif}</p>
							</div>
						</div>
					{/each}
				</div>
			</details>
		{/if}
	</EtatListe>
</section>

<style>
	.section-diagnostics {
		margin-bottom: 2.5rem;
	}
	/*  Seul `margin: 0` diffère : la charte pose `margin-bottom` (#607). */
	.section-title {
		margin: 0;
	}
	/*  🔴 LES STYLES VOYAGENT AVEC LE BALISAGE. Svelte scope les styles au
	    composant qui rend l'élément : les laisser dans la page qu'ils viennent de
	    quitter aurait livré les cartes NUES en production — c'est la panne des
	    pastilles de la v2.67.11, refaite deux fois depuis (#344, #356).

	    ⚠️ `.doc-row`, `.doc-info`, `.doc-titre` et `.doc-date` ne sont PAS ici :
	    elles vivent dans `styles/composants.css` depuis #491, parce que trois
	    écrans les emploient. Une notion partagée vit dans la charte. */
	.diag-list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	.diag-card {
		padding: 1rem 1.25rem;
	}
	.diag-header {
		margin-bottom: 0.75rem;
	}
	.diag-title-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-wrap: wrap;
		margin-bottom: 0.4rem;
	}
	.diag-nom {
		font-weight: 600;
		font-size: var(--fs-xl);
	}
	.diag-texte {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		line-height: 1.5;
		margin: 0;
	}
	.diag-rapports {
		border-top: 1px solid var(--color-border);
		padding-top: 0.6rem;
		margin-bottom: 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.diag-add {
		padding-top: 0.4rem;
	}
	.diag-card-disabled {
		opacity: 0.65;
	}
	.diag-non-applicable-section {
		margin-top: 1rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.6rem 1rem;
		background: var(--color-surface);
	}
	.diag-non-applicable-section > summary {
		cursor: pointer;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		font-weight: 500;
		user-select: none;
	}
	@media (hover: hover) and (pointer: fine) {
		.diag-non-applicable-section > summary:hover {
			color: var(--color-text);
		}
	}

	/*  Le corps d'une carte de diagnostic s'aligne sur son en-tête (`EnteteCarte`). */
	.corps-diagnostic {
		padding: 0 1.1rem 0.75rem;
	}
	@media (max-width: 480px) {
		.corps-diagnostic {
			padding: 0 0.7rem 0.6rem;
		}
	}
	.liste-non-applicables {
		margin-top: 0.75rem;
	}
</style>
