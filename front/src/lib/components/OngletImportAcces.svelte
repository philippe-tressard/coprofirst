<!--
  L'écran d'import d'ACCÈS — un seul, piloté par un modèle (`#lib/imports-acces`).

  ## 🔴 Un badge appartient au LOT (#1194, 23/09/2026)

  Arbitré sur maquettes : une ligne du fichier se RATTACHE à son lot, et ses
  porteurs s'en déduisent — les copropriétaires du lot, conjoint compris. Le
  formulaire demandait jusqu'ici un compte « Propriétaire » obligatoire, que le
  serveur exigeait (422) : la plupart des lots n'en ont pas, et les lignes
  restaient en attente d'une inscription. Puis « Lier » ne suffisait pas, il
  fallait encore « ✓ Créer » — la colonne « Proprio lié » était pourtant verte.

  Il ne reste qu'un champ obligatoire, le **lot**, et un seul geste,
  **Rattacher** — ligne par ligne, ou en masse pour toutes les lignes dont le
  lot est reconnu. Les noms du fichier ne sont plus que des indices.

  ⚠️ Ce composant ne connaît **aucun** nom de type d'import (#453) : ni
  « Vigik », ni « télécommande », ni un chemin d'API.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { champDe, nombreOuNull } from '#lib/utils.ts';
	import { onMount } from 'svelte';
	import {
		acces as accesApi,
		admin as adminApi,
		type LotPourBadge,
		type StatsImportAcces,
		type UtilisateurAdmin,
	} from '#lib/api/index.ts';
	import { nomAffiche } from '#lib/noms.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { siteNomStore } from '#lib/stores/pageConfig.ts';
	import { isAdmin } from '#lib/stores/auth.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import {
		STATUT_BADGE,
		STATUT_LABEL,
		libelleLotPourBadge,
		lotsPourBadge,
		type LigneImport,
		type ModeleImportAcces,
	} from '#lib/imports-acces.ts';
	import BarreImport from '#lib/components/BarreImport.svelte';
	import { contientTousLesMots } from '#lib/texte.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';

	export let modele: ModeleImportAcces;

	$: _siteNom = $siteNomStore;

	let imports: LigneImport[] = [];
	let stats: StatsImportAcces | null = null;
	let lots: LotPourBadge[] = [];
	let chargement = true;
	let erreur = '';
	let filtre = '';
	//  La recherche du tableau (#2173) : locale, la liste est chargée en entière.
	let recherche = '';
	let enCours = false;

	$: lotsTries = lotsPourBadge(lots, modele.natureLot);
	/** Les comptes, pour désigner le locataire qui a le badge en main. */
	let comptes: UtilisateurAdmin[] = [];

	async function geste<T>(appel: () => Promise<T>, succes: (r: T) => string) {
		enCours = true;
		try {
			const r = await appel();
			toast('success', succes(r));
			await recharger();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}

	const televerser = (fichier: File, remplacer: boolean) =>
		geste(
			() => modele.api.upload(fichier, remplacer),
			(r) => `Import : ${r.importes} ajoutés, ${r.doublons} doublons, ${r.ignores} ignorés`,
		);

	//  `reprises` : des lignes « résolues » sans lot, rendues au rapprochement (#1338).
	const rechercher = () =>
		geste(
			modele.api.autoMatch,
			(r) =>
				`${r.matches} ligne(s) complétée(s)` +
				(r.reprises ? ` — dont ${r.reprises} résolue(s) sans lot, reprise(s)` : ''),
		);

	async function rattacherTout() {
		const n = stats?.a_rattacher ?? 0;
		if (
			!(await confirmer(
				`Rattacher ${n} ligne(s) à leur lot ? Les copropriétaires de chaque lot en deviendront porteurs.`,
			))
		)
			return;
		await geste(modele.api.rattacher, (r) => `${r.rattachees} ligne(s) rattachée(s)`);
	}

	const rattacher = (id: number) =>
		geste(
			() => modele.api.resoudre(id),
			() => `Rattaché : ${modele.objet} est sur son lot`,
		);

	async function ignorer(id: number) {
		if (!(await confirmer('Ignorer cette ligne ?'))) return;
		await geste(
			() => modele.api.ignorer(id),
			() => 'Ligne ignorée',
		);
	}

	async function supprimer(id: number) {
		const ok = await confirmer({
			message: 'Supprimer cette ligne du fichier ? Le badge qu’elle aurait créé reste au parc.',
			libelleConfirmer: 'Supprimer',
			danger: true,
		});
		if (ok)
			await geste(
				() => modele.api.supprimer(id),
				() => 'Ligne supprimée',
			);
	}

	const remettreEnAttente = (id: number) =>
		geste(
			() => modele.api.remettreEnAttente(id),
			() => 'Ligne remise en attente',
		);

	// ── Préciser une ligne : le lot, et la possession ───────────────────────────
	let editId: number | null = null;
	let editLot = '';
	let editChezLoc = false;
	let editLocataire = '';
	let editNotes = '';
	//  Les cases propres à un type (« Locataire a refusé ») : le modèle les déclare.
	let editBooleens: Record<string, boolean> = {};

	function ouvrirEdition(imp: LigneImport) {
		editId = imp.id;
		editLot = String(imp.lot_id ?? '');
		editChezLoc = imp.chez_locataire;
		editLocataire = String(imp.user_locataire_id ?? '');
		editNotes = imp.notes_admin ?? '';
		editBooleens = Object.fromEntries(
			modele.champsBooleens.map((c) => [c.cle, champDe(imp, c.cle) === true]),
		);
	}

	async function enregistrer() {
		if (editId === null) return;
		const id = editId;
		await geste(
			//  `lot_id: null` DÉLIE : le serveur distingue un champ absent d'un
			//  champ vidé depuis #1194.
			() =>
				modele.api.patch(id, {
					lot_id: nombreOuNull(editLot),
					chez_locataire: editChezLoc,
					//  Le locataire qui l'a en main : il en devient porteur (#1194).
					user_locataire_id: editChezLoc ? nombreOuNull(editLocataire) : null,
					notes_admin: editNotes || null,
					...editBooleens,
				}),
			() => 'Ligne mise à jour',
		);
		editId = null;
	}

	async function recharger() {
		[imports, stats] = await Promise.all([
			modele.api.list(filtre || undefined),
			modele.api.stats(),
		]);
	}

	onMount(async () => {
		try {
			[lots, comptes] = await Promise.all([
				accesApi.lotsImports(),
				adminApi.utilisateurs(),
				recharger(),
			]);
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});

	/** « 2 porteurs » ou « sans compte » — ce que le rattachement donnera. */
	const porteurs = (n: number | null) =>
		!n ? 'sans compte' : n === 1 ? '1 porteur' : `${n} porteurs`;

	$: nbColonnes = modele.colonnes.length + 5;

	//  Ce que la ligne MONTRE — les colonnes du modèle, les indices du fichier,
	//  la clé, le lot, le statut — et rien d'autre.
	$: affiches = imports.filter((imp) =>
		contientTousLesMots(
			[
				...modele.colonnes.map((c) => String(champDe(imp, c.cle) ?? '')),
				imp.nom_proprietaire,
				imp.nom_locataire,
				String(champDe(imp, modele.colonneCle.cle) ?? ''),
				imp.lot_label,
				STATUT_LABEL[imp.statut] ?? imp.statut,
			],
			recherche,
		),
	);
</script>

<svelte:head><title>{modele.titre} — {_siteNom}</title></svelte:head>

<BarreImport
	tuiles={stats
		? [
				{ valeur: stats.total, libelle: 'Total' },
				{ valeur: stats.a_rattacher, libelle: 'Lot reconnu', couleur: 'var(--color-success)' },
				{
					valeur: stats.lot_a_preciser,
					libelle: 'Lot à préciser',
					couleur: 'var(--color-warning-texte)',
				},
				{ valeur: stats.resolu, libelle: 'Rattachés', couleur: 'var(--color-import-lie)' },
				{ valeur: stats.ignore, libelle: 'Ignorés', couleur: 'var(--color-text-muted)' },
			]
		: []}
	colonnesAttendues={modele.colonnesAttendues}
	{enCours}
	statuts={['', 'en_attente', 'proprietaire_lie', 'resolu', 'ignore']}
	libellesStatuts={STATUT_LABEL}
	bind:filtre
	bind:recherche
	idRecherche="imp-acces-recherche"
	exempleRecherche="{modele.colonneCle.entete}, nom, lot…"
	rechercheDans="toutes les colonnes du tableau, propriétaire, locataire, lot et statut"
	compte={affiches.length}
	on:importer={(e) => televerser(e.detail.fichier, e.detail.remplacer)}
	on:filtrer={recharger}
>
	<svelte:fragment slot="actions">
		<button class="btn btn-outline btn-sm" on:click={rechercher} disabled={enCours}>
			{'\u{1F50E}'} Rechercher les lots
		</button>
		{#if stats?.a_rattacher}
			<button class="btn btn-primary btn-sm" on:click={rattacherTout} disabled={enCours}>
				Rattacher les {stats.a_rattacher} lignes reconnues
			</button>
		{/if}
	</svelte:fragment>
</BarreImport>

<EtatListe
	{chargement}
	{erreur}
	vide={imports.length === 0}
	titreVide="Aucun import"
	messageVide="Importez un fichier .xlsx pour démarrer."
>
	<!--  Une recherche sans résultat : `BilanRecherche` le dit au-dessus. -->
	{#if affiches.length > 0}<div class="card carte-table">
			<table class="table imp-table-dense">
				<thead>
					<tr>
						{#each modele.colonnes as c (c.cle)}<th>{c.entete}</th>{/each}
						<th>Indices du fichier</th>
						<th>{modele.colonneCle.entete}</th>
						<th>Lot</th>
						<th>Statut</th>
						<th>Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each affiches as imp (imp.id)}
						<tr
							class:imp-row-resolu={imp.statut === 'resolu'}
							class:imp-row-ignore={imp.statut === 'ignore'}
						>
							{#each modele.colonnes as c (c.cle)}
								<td class="texte-sm">{champDe(imp, c.cle) ?? '—'}</td>
							{/each}
							<td>
								<span class="proprietaire">{imp.nom_proprietaire}</span>
								{#if imp.nom_locataire}
									<span class="muted texte-sm"> · loc. {imp.nom_locataire}</span>
								{/if}
							</td>
							<td><code class="texte-sm">{champDe(imp, modele.colonneCle.cle) ?? '—'}</code></td>
							<td>
								{#if imp.lot_label}
									<span class="badge badge-green"
										>{imp.lot_label} · {porteurs(imp.lot_porteurs)}</span
									>
								{:else if imp.statut !== 'ignore'}
									<span class="badge badge-orange">à préciser</span>
								{:else}—{/if}
							</td>
							<td>
								<Badge teinte={STATUT_BADGE[imp.statut] ?? 'badge-gray'}
									>{STATUT_LABEL[imp.statut] ?? imp.statut}</Badge
								>
								{#each modele.decorationsStatut(imp) as d (d.titre)}
									<span title={d.titre} class="icone-diff">{d.icone}</span>
								{/each}
							</td>
							<td>
								<div class="action-row">
									{#if imp.statut === 'ignore'}
										<button
											class="btn-icon-success"
											aria-label="Remettre en attente"
											title="Remettre en attente"
											on:click={() => remettreEnAttente(imp.id)}
											><IconeAction icone="undo-2" /></button
										>
									{:else}
										{#if imp.rattachable}
											<button
												class="btn btn-sm btn-primary"
												disabled={enCours}
												on:click={() => rattacher(imp.id)}>Rattacher</button
											>
										{:else if imp.statut !== 'resolu' && !imp.lot_id}
											<button class="btn btn-sm btn-outline" on:click={() => ouvrirEdition(imp)}
												>Choisir le lot</button
											>
										{/if}
										<button
											class="btn-icon-edit"
											aria-label="Préciser la ligne"
											title="Préciser la ligne"
											aria-pressed={editId === imp.id}
											on:click={() => ouvrirEdition(imp)}><IconeAction icone="pencil" /></button
										>
										{#if imp.statut !== 'resolu'}
											<button
												class="btn-icon-warn"
												aria-label="Ignorer cette ligne"
												title="Ignorer"
												on:click={() => ignorer(imp.id)}><IconeAction icone="ban" /></button
											>
										{/if}
									{/if}
									<!--  🔒 Supprimer : l'administrateur seul, comme toute suppression
								      définitive (`ux-patterns` §8) — le 🗑️ vient en dernier. -->
									{#if $isAdmin}
										<button
											class="btn-icon-danger"
											aria-label="Supprimer cette ligne"
											title="Supprimer la ligne"
											on:click={() => supprimer(imp.id)}><IconeAction icone="trash-2" /></button
										>
									{/if}
								</div>
							</td>
						</tr>

						{#if editId === imp.id}
							<tr class="imp-edit-row">
								<td colspan={nbColonnes}>
									<div class="imp-edit-form card form-correction">
										<p class="aide">
											Indices du fichier : <strong>{imp.nom_proprietaire}</strong>{imp.nom_locataire
												? ` · locataire ${imp.nom_locataire}`
												: ''} · {modele.colonneCle.entete.toLowerCase()}
											<code>{champDe(imp, modele.colonneCle.cle) ?? '—'}</code>
										</p>
										<div class="imp-edit-grid">
											<div class="field champ-large">
												<label for="imp-lot">Lot<EtoileRequis vide={!editLot} /></label>
												<select id="imp-lot" bind:value={editLot}>
													<option value="">— Aucun lot (délier) —</option>
													<!--  Le copropriétaire est celui du FICHIER DES LOTS : c'est le
												      seul nom qu'un lot sans compte possède (#1154, #1194). -->
													{#each lotsTries as l (l.id)}
														<option value={String(l.id)}>{libelleLotPourBadge(l)}</option>
													{/each}
												</select>
											</div>
											<div class="field imp-field-checkbox">
												<label>
													<input type="checkbox" bind:checked={editChezLoc} />
													Remis au locataire
												</label>
												<p class="aide sous-case">Sinon, il est chez les copropriétaires du lot.</p>
											</div>
											{#if editChezLoc}
												<!--  Retour du 23/09/2026 : « on ne peut pas rattacher le
											      locataire ». Son compte, s'il en a un, le rend porteur. -->
												<div class="field">
													<label for="imp-locataire">Locataire</label>
													<select id="imp-locataire" bind:value={editLocataire}>
														<option value="">— sans compte —</option>
														{#each comptes as u (u.id)}
															<option value={String(u.id)}>{nomAffiche(u)}</option>
														{/each}
													</select>
												</div>
											{/if}
											{#each modele.champsBooleens as c (c.cle)}
												<div class="field imp-field-checkbox">
													<label>
														<input type="checkbox" bind:checked={editBooleens[c.cle]} />
														{c.libelle}
													</label>
												</div>
											{/each}
											<div class="field champ-large">
												<label for="imp-notes">Notes admin</label>
												<input
													id="imp-notes"
													type="text"
													bind:value={editNotes}
													placeholder="Note interne…"
												/>
											</div>
										</div>
										<PiedFormulaire
											{enCours}
											soumission={false}
											on:annule={() => (editId = null)}
											on:enregistre={enregistrer}
										/>
									</div>
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>{/if}
</EtatListe>

<style>
	.carte-table {
		overflow: auto;
	}
	.texte-sm {
		font-size: var(--fs-sm);
	}
	.proprietaire {
		font-weight: 500;
	}
	.icone-diff {
		margin-left: 0.25rem;
	}
	.form-correction {
		margin: 0.5rem 0;
	}
</style>
