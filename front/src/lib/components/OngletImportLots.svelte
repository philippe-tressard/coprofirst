<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { nombreOuNull } from '#lib/utils.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { nomAffiche } from '#lib/noms.ts';
	import { onMount } from 'svelte';
	import { lots as lotsApi, admin as adminApi } from '#lib/api/index.ts';
	import type {
		LigneImportLot,
		MonLot,
		StatsImportLots,
		UtilisateurAdmin,
	} from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { siteNomStore } from '#lib/stores/pageConfig.ts';
	import BarreImport from '#lib/components/BarreImport.svelte';
	import CorrectionImportLot from '#lib/components/CorrectionImportLot.svelte';
	import { parAttribut } from '#lib/table-statuts.ts';
	import { contientTousLesMots } from '#lib/texte.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	$: _siteNom = $siteNomStore;
	// ── Données ─────────────────────────────────────────────────────────────
	let imports: LigneImportLot[] = [];
	let stats: StatsImportLots | null = null;
	let utilisateurs: UtilisateurAdmin[] = [];
	let lots: MonLot[] = [];
	let loading = true;
	let filtre = '';
	let tri = 'copro'; // copro | batiment | numero
	//  La recherche du tableau (#2173) : locale, la liste est chargée en entière.
	let recherche = '';

	// ── Upload ───────────────────────────────────────────────────────────────
	//  Le FORMULAIRE de téléversement vit dans `BarreImport`, comme sur l'écran
	//  d'import d'accès : il ne reste ici que le compte rendu, qui est propre aux
	//  lots (erreurs de ligne, imports écartés, parkings sans lot).
	let uploading = false;

	//  Ce que la résolution a laissé de côté (`resolution_lots.resoudre_imports`) ;
	//  le téléversement en rend le compte préfixé par `auto_` (#1685).
	function signalerEcartes(sansOccupant: number, horsPerimetre: number) {
		if (sansOccupant) toast('info', `${sansOccupant} import(s) sans occupant — à compléter via ✏️`);
		if (horsPerimetre)
			toast('info', `${horsPerimetre} import(s) hors périmètre laissé(s) en attente`);
	}

	async function uploadExcel(fichier: File, remplacer: boolean) {
		uploading = true;
		try {
			const result = await lotsApi.uploadImport(fichier, remplacer);
			toast(
				'success',
				`Import : ${result.importes} ajoutés, ${result.doublons} doublons, ${result.ignores} ignorés${result.auto_resolus ? ` — ${result.auto_resolus} copropriétaire(s) résolu(s) automatiquement` : ''}`,
			);
			if (result.erreurs?.length) toast('error', result.erreurs.slice(0, 3).join('\n'));
			signalerEcartes(result.auto_sans_occupant, result.auto_hors_perimetre);
			await reload();
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur import'));
		} finally {
			uploading = false;
		}
	}

	// ── Auto-match ───────────────────────────────────────────────────────────
	let autoMatching = false;

	async function autoMatch() {
		autoMatching = true;
		try {
			const r = await lotsApi.autoMatchImports();
			toast('success', `${r.matches} liaison(s) automatique(s) trouvée(s)`);
			await reload();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			autoMatching = false;
		}
	}

	// ── Auto-résoudre copropriétaires ────────────────────────────────────────
	let autoResolving = false;

	async function autoResoudre() {
		autoResolving = true;
		try {
			const r = await lotsApi.autoResoudreImports();
			toast('success', `${r.resolus} copropriétaire(s) résolu(s) automatiquement`);
			signalerEcartes(r.sans_occupant, r.hors_perimetre);
			await reload();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			autoResolving = false;
		}
	}

	// ── Édition inline ───────────────────────────────────────────────────────
	let editId: number | null = null;
	let editLot = '';
	let editOccupants: { user_id: string; type_lien: string }[] = [];
	let editNotes = '';
	let saving = false;

	//  ⚠️ La teinte est ici un CODE COULEUR, pas une classe de badge : ces liens
	//  se rendent en pastille pleine, et la charte ne porte pas ces quatre-là.
	const { libelle: TYPE_LIEN_LABEL, couleur: TYPE_LIEN_BADGE } = parAttribut({
		propriétaire: { libelle: 'Propriétaire', couleur: 'var(--color-success)' },
		bailleur: { libelle: 'Bailleur', couleur: 'var(--color-import-lie)' },
		locataire: { libelle: 'Locataire', couleur: 'var(--color-warning-texte)' },
		mandataire: { libelle: 'Mandataire', couleur: 'var(--color-violet)' },
	});

	function openEdit(imp: LigneImportLot) {
		editId = imp.id;
		editLot = String(imp.lot_id ?? '');
		editNotes = imp.notes_admin ?? '';
		if (imp.utilisateurs?.length) {
			editOccupants = imp.utilisateurs.map((u) => ({
				user_id: String(u.user_id ?? ''),
				type_lien: u.type_lien ?? 'propriétaire',
			}));
		} else {
			editOccupants = [{ user_id: '', type_lien: 'propriétaire' }];
		}
	}

	function cancelEdit() {
		editId = null;
	}

	async function saveEdit() {
		if (editId === null) return;
		saving = true;
		try {
			const utilisateurs = editOccupants
				.filter((o) => o.user_id)
				.map((o) => ({ user_id: Number(o.user_id), type_lien: o.type_lien }));
			await lotsApi.patchImport(editId, {
				lot_id: nombreOuNull(editLot),
				utilisateurs,
				notes_admin: editNotes || null,
			});
			toast('success', 'Liaisons mises à jour');
			editId = null;
			await reload();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			saving = false;
		}
	}

	// ── Résolution / Ignorer ─────────────────────────────────────────────────
	async function resoudre(id: number) {
		if (!(await confirmer('Créer/confirmer le lot et créer le lien copropriétaire ?'))) return;
		try {
			await lotsApi.resoudreImport(id);
			toast('success', 'Lot confirmé et lien copropriétaire créé');
			await reload();
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur résolution'));
		}
	}

	async function ignorer(id: number) {
		if (!(await confirmer('Ignorer cet import ?'))) return;
		try {
			await lotsApi.ignorerimport(id);
			toast('info', 'Import ignoré');
			await reload();
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	// ── Chargement ───────────────────────────────────────────────────────────
	async function reload() {
		[imports, stats] = await Promise.all([
			lotsApi.listImports(filtre || undefined, tri),
			lotsApi.statsImports(),
		]);
	}

	onMount(async () => {
		loading = true;
		try {
			//  ⚠️ `/copropriete/batiments` était appelé ici et son résultat JETÉ :
			//  `batiments` n'était lu nulle part. Une requête à chaque ouverture de
			//  l'onglet, pour rien — invisible, puisqu'elle réussissait.
			[utilisateurs, lots] = await Promise.all([adminApi.utilisateurs(), lotsApi.tous()]);
			await reload();
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	// ── Helpers ──────────────────────────────────────────────────────────────
	const { libelle: statutLabel, badge: statutBadge } = parAttribut({
		en_attente: { libelle: 'En attente', badge: 'badge-orange' },
		utilisateur_lie: { libelle: 'Occupant lié', badge: 'badge-purple' },
		lot_lie: { libelle: 'Lot lié', badge: 'badge-blue' },
		resolu: { libelle: 'Résolu', badge: 'badge-green' },
		ignore: { libelle: 'Ignoré', badge: 'badge-gray' },
	});

	//  Ce que la ligne MONTRE, et rien d'autre : chercher dans une colonne
	//  cachée ferait garder une ligne sans qu'on voie pourquoi.
	$: affiches = imports.filter((imp) =>
		contientTousLesMots(
			[
				imp.nom_coproprietaire,
				imp.no_coproprietaire,
				imp.batiment_nom ?? imp.batiment_id,
				imp.numero,
				imp.type_raw,
				imp.etage_raw,
				imp.lot_label,
				statutLabel[imp.statut] ?? imp.statut,
				...(imp.utilisateurs ?? []).flatMap((o) => [
					TYPE_LIEN_LABEL[o.type_lien] ?? o.type_lien,
					o.utilisateur ? nomAffiche(o.utilisateur) : '',
				]),
			],
			recherche,
		),
	);
</script>

<svelte:head><title>Import Lots — {_siteNom}</title></svelte:head>

<!--  ⚠️ Le libellé dit CE QUI EST EFFACÉ, et diverge exprès des deux autres
      imports — motif dans `utils/import_xlsx.purger_staging` (#824). -->
<BarreImport
	tuiles={stats
		? [
				{ valeur: stats.total, libelle: 'Total' },
				{ valeur: stats.en_attente, libelle: 'En attente', couleur: 'var(--color-warning-texte)' },
				{
					valeur: stats.utilisateur_lie ?? 0,
					libelle: 'Occupant lié',
					couleur: 'var(--color-violet)',
				},
				{ valeur: stats.lot_lie, libelle: 'Lot lié', couleur: 'var(--color-import-lie)' },
				{ valeur: stats.resolu, libelle: 'Résolus', couleur: 'var(--color-success)' },
				{ valeur: stats.ignore, libelle: 'Ignorés', couleur: 'var(--color-text-muted)' },
				{ valeur: stats.avec_user, libelle: 'Copro lié' },
			]
		: []}
	colonnesAttendues="ID_BATIMENT | N° LOT | TYPE | ÉTAGE | N° PORTE | N° COPROPRIÉTAIRE | NOM COPROPRIÉTAIRE"
	libelleRemplacer="Remplacer les imports non résolus — les lignes écartées sont conservées"
	enCours={uploading}
	statuts={['', 'en_attente', 'utilisateur_lie', 'lot_lie', 'resolu', 'ignore']}
	libellesStatuts={statutLabel}
	bind:filtre
	bind:recherche
	idRecherche="imp-lots-recherche"
	exempleRecherche="Nom, n° de copropriétaire, bâtiment, lot…"
	compte={affiches.length}
	on:importer={(e) => uploadExcel(e.detail.fichier, e.detail.remplacer)}
	on:filtrer={reload}
>
	<svelte:fragment slot="actions">
		<button class="btn btn-outline btn-sm" on:click={autoMatch} disabled={autoMatching}>
			{autoMatching ? 'Recherche…' : '\u{1F517} Auto-match'}
		</button>
		<button class="btn btn-outline btn-sm" on:click={autoResoudre} disabled={autoResolving}>
			{autoResolving ? 'Résolution…' : '✅ Auto-résoudre copropriétaires'}
		</button>
	</svelte:fragment>
</BarreImport>

<!-- ── Table ─────────────────────────────────────────────────────────────── -->
{#if loading}
	<EtatListe chargement />
{:else if imports.length === 0}
	<div class="empty-state card">
		<h3>Aucun import</h3>
		<p>Importez un fichier .xlsx pour démarrer.</p>
	</div>
{:else if affiches.length > 0}
	<div class="card carte-imports">
		<table class="table imp-table-dense">
			<thead>
				<tr>
					<th>Nom copropriétaire</th><th>N° Copro</th>
					<th>Bât.</th><th>N° Lot</th><th>Type</th><th>Étage</th>
					<th>Lot lié</th><th>Occupants liés</th>
					<th>Statut</th><th>Actions</th>
				</tr>
			</thead>
			<tbody>
				{#each affiches as imp (imp.id)}
					<tr
						class:imp-row-resolu={imp.statut === 'resolu'}
						class:imp-row-ignore={imp.statut === 'ignore'}
					>
						<td class="nom-copro">{imp.nom_coproprietaire ?? '—'}</td>
						<td class="text-muted-sm">{imp.no_coproprietaire ?? '—'}</td>
						<td class="batiment-import">{imp.batiment_nom ?? imp.batiment_id}</td>
						<td class="numero-lot">{imp.numero}</td>
						<td><span class="badge badge-type">{imp.type_raw}</span></td>
						<td class="text-muted-sm">{imp.etage_raw ?? '—'}</td>
						<td class="text-muted-sm">{imp.lot_label ?? '—'}</td>
						<td class="occupants-cellule">
							{#if imp.utilisateurs?.length}
								<div class="occupants-list">
									{#each imp.utilisateurs as occ (occ.user_id ?? occ.type_lien)}
										<div class="occupant-tag">
											<span
												class="occ-role"
												style="color:{TYPE_LIEN_BADGE[occ.type_lien] ?? 'var(--color-text-muted)'}"
												>{TYPE_LIEN_LABEL[occ.type_lien] ?? occ.type_lien}</span
											>
											{#if occ.utilisateur}
												<span class="occupant-lie">{nomAffiche(occ.utilisateur)}</span>
											{:else}
												<span class="non-lie">Non lié</span>
											{/if}
										</div>
									{/each}
								</div>
							{:else if imp.nom_coproprietaire}
								<span class="non-lie">Non lié</span>
							{:else}—{/if}
						</td>
						<td
							><Badge teinte={statutBadge[imp.statut] ?? 'badge-gray'}
								>{statutLabel[imp.statut] ?? imp.statut}</Badge
							></td
						>
						<td>
							{#if imp.statut !== 'resolu' && imp.statut !== 'ignore'}
								<div class="action-row">
									<button
										class="btn-icon-edit"
										aria-label="Modifier"
										title="Modifier"
										on:click={() => openEdit(imp)}><IconeAction icone="pencil" /></button
									>
									{#if imp.utilisateurs?.length > 0}
										<button class="btn btn-sm btn-primary" on:click={() => resoudre(imp.id)}
											>✓ Valider</button
										>
									{/if}
									<button
										class="btn-icon-warn"
										aria-label="Ignorer cet import"
										title="Ignorer"
										on:click={() => ignorer(imp.id)}><IconeAction icone="ban" /></button
									>
								</div>
							{:else if imp.statut === 'resolu'}
								<div class="action-row">
									<span class="badge badge-green lot-valide">✓ Lot #{imp.lot_id}</span>
									<button
										class="btn-icon-edit"
										aria-label="Lier un occupant"
										title="Lier un occupant"
										on:click={() => openEdit(imp)}><IconeAction icone="pencil" /></button
									>
								</div>
							{/if}
						</td>
					</tr>

					<!-- Formulaire d'édition inline -->
					{#if editId === imp.id}
						<tr class="imp-edit-row">
							<td colspan="10">
								<CorrectionImportLot
									{imp}
									{lots}
									{utilisateurs}
									enCours={saving}
									bind:lot={editLot}
									bind:occupants={editOccupants}
									bind:notes={editNotes}
									on:annule={cancelEdit}
									on:enregistre={saveEdit}
								/>
							</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	.badge-type {
		background: var(--color-info-fond);
		color: var(--color-info);
		font-size: var(--fs-xs);
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
		font-weight: 600;
	}

	.occupants-list {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}
	.occupant-tag {
		display: flex;
		gap: 0.35rem;
		align-items: baseline;
		font-size: var(--fs-sm);
	}
	.occ-role {
		font-weight: 600;
		font-size: var(--fs-2xs);
	}
	.carte-imports {
		overflow: auto;
	}
	.nom-copro {
		font-weight: 600;
	}
	.batiment-import {
		font-size: var(--fs-sm);
		font-weight: 600;
	}
	.numero-lot {
		font-weight: 500;
	}
	.occupants-cellule {
		font-size: var(--fs-sm);
	}
	.occupant-lie {
		color: var(--color-success);
	}
	.non-lie {
		color: var(--color-warning-texte);
	}
	.lot-valide {
		font-size: var(--fs-xs);
	}
</style>
