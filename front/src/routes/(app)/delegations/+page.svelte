<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import { confirmer } from '#lib/confirmation.ts';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import { nomAffiche } from '#lib/noms.ts';
	import Icon from '#lib/components/Icon.svelte';
	import EntetePage from '#lib/components/EntetePage.svelte';
	import { currentUser, isCS, quandAuthResolue } from '#lib/stores/auth.ts';
	import {
		delegations as delegationsApi,
		admin as adminApi,
		type Delegation,
		type UtilisateurAdmin,
	} from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		getPageConfig,
		configStore,
		siteNomStore,
		defautsDePage,
	} from '#lib/stores/pageConfig.ts';
	import { fmtDateShort as fmt } from '#lib/date.ts';
	import ChargementPartiel from '#lib/components/ChargementPartiel.svelte';
	import { essayer } from '#lib/chargement.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import { parAttribut } from '#lib/table-statuts.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	// Cette page importait déjà getPageConfig sans s'en servir : son titre était en
	// dur, elle était donc la seule entrée du menu qu'on ne pouvait ni renommer ni
	// positionner (#401).
	$: _pc = getPageConfig($configStore, 'delegations', defautsDePage('delegations'));
	$: _siteNom = $siteNomStore;

	let delegations: Delegation[] = [];
	let loading = true;
	let users: UtilisateurAdmin[] = []; // pour le formulaire CS
	/** Non vide = la liste des résidents n'a pas pu être chargée (#522). */
	let erreurUtilisateurs = '';

	// Formulaire création
	let showForm = false;
	let formMandantId = 0;
	let formAidantId = 0;
	let formMotif = '';
	let formDateFin = '';
	let saving = false;

	//  Pas `onMount` : il précède le layout qui charge l'utilisateur (#1486).
	quandAuthResolue(async () => {
		try {
			delegations = await delegationsApi.list();
			if ($isCS) {
				//  Donnée de RÉFÉRENCE : elle garnit deux menus déroulants. Un
				//  échec les laissait vides, et l'écran donnait à croire qu'aucun
				//  résident n'était délégable (#522).
				[users, erreurUtilisateurs] = await essayer(adminApi.utilisateurs(), []);
			}
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	//  🔴 `expiree` portait `badge-grey` — à l'anglaise. La charte écrit
	//  `badge-gray`, et cette classe-là n'existait donc nulle part : l'écran la
	//  redéfinissait en bas de fichier, en couleurs EN DUR, hors du thème. Le
	//  commentaire qui l'accompagnait disait « la charte ne la porte pas » —
	//  c'était vrai de `grey`, et faux de la classe qu'il fallait. Une faute
	//  d'orthographe avait fait conclure à l'absence du composant partagé.
	const { libelle, badge } = parAttribut({
		en_attente: { libelle: 'En attente', badge: 'badge-orange' },
		active: { libelle: 'Active', badge: 'badge-green' },
		revoquee: { libelle: 'Révoquée', badge: 'badge-red' },
		expiree: { libelle: 'Expirée', badge: 'badge-gray' },
	});

	function statutLabel(s: string): string {
		return libelle[s] ?? s;
	}

	function statutBadge(s: string): string {
		return badge[s] ?? '';
	}

	async function creer() {
		if (!formMandantId || !formAidantId) return;
		saving = true;
		try {
			const created = await delegationsApi.create({
				mandant_id: formMandantId,
				aidant_id: formAidantId,
				motif: formMotif,
				date_fin: formDateFin || undefined,
			});
			delegations = [created, ...delegations];
			showForm = false;
			formMandantId = 0;
			formAidantId = 0;
			formMotif = '';
			formDateFin = '';
			toast('success', 'Délégation créée');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			saving = false;
		}
	}

	async function accepter(id: number) {
		try {
			const updated = await delegationsApi.accepter(id);
			delegations = delegations.map((d) => (d.id === id ? updated : d));
			toast('success', 'Délégation acceptée');
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function revoquer(id: number) {
		if (!(await confirmer('Révoquer cette délégation ?'))) return;
		try {
			const updated = await delegationsApi.revoquer(id);
			delegations = delegations.map((d) => (d.id === id ? updated : d));
			toast('success', 'Délégation révoquée');
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}
</script>

<svelte:head><title>Délégations aidant — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'heart-handshake'} />

<ChargementPartiel
	erreur={erreurUtilisateurs}
	consequence="Les menus « mandant » et « aidant » du formulaire de délégation sont vides : ce n'est pas qu'aucun résident n'est éligible."
/>

{#if loading}
	<EtatListe chargement />
{:else}
	{#if $isCS}
		<div class="barre-delegation">
			<button class="btn btn-primary" on:click={() => (showForm = true)}
				>+ Nouvelle délégation</button
			>
		</div>
	{/if}

	{#if delegations.length === 0}
		<div class="card vide-delegations">Aucune délégation.</div>
	{:else}
		<div class="deleg-list">
			{#each delegations as d (d.id)}
				<div class="card deleg-card">
					<div class="deleg-main">
						<div class="deleg-people">
							<div class="deleg-person">
								<span class="deleg-label">Personne aidée</span>
								<span class="deleg-name">{d.mandant_nom}</span>
							</div>
							<span class="deleg-arrow"><Icon name="arrow-right" size={16} /></span>
							<div class="deleg-person">
								<span class="deleg-label">Aidant</span>
								<span class="deleg-name">{d.aidant_nom}</span>
							</div>
						</div>
						<div class="deleg-meta">
							<Badge teinte={statutBadge(d.statut)}>{statutLabel(d.statut)}</Badge>
							<span class="deleg-date"
								>Du {fmt(d.date_debut)}{d.date_fin ? ` au ${fmt(d.date_fin)}` : ' — illimité'}</span
							>
						</div>
						{#if d.motif}
							<p class="deleg-motif">{d.motif}</p>
						{/if}
					</div>
					<div class="deleg-actions">
						{#if d.statut === 'en_attente' && d.aidant_id === $currentUser?.id}
							<button class="btn btn-sm btn-primary" on:click={() => accepter(d.id)}
								>Accepter</button
							>
						{/if}
						{#if d.statut === 'en_attente' || d.statut === 'active'}
							<button class="btn btn-sm btn-danger" on:click={() => revoquer(d.id)}>Révoquer</button
							>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
{/if}

<!-- ── Créer une délégation — une BOÎTE dans la page, pas une modale ──────
     Convertie le 31/08/2026 (#672). Elle avait échappé à #367 parce que
     `lint:formulaires` ne cherchait qu'un `<form>` : celle-ci n'en portait
     aucun, seulement des `.field`. -->
{#if showForm}
	<FormulaireCreation titre="Nouvelle délégation aidant">
		<!--  Un vrai `<form>` (#1329) : la touche Entrée ne soumettait pas. -->
		<form on:submit|preventDefault={creer}>
			<div class="field">
				<label for="d-mandant">Personne aidée (mandant)<EtoileRequis vide={!formMandantId} /></label
				>
				<select id="d-mandant" bind:value={formMandantId}>
					<option value={0} disabled>Choisir…</option>
					{#each users.filter((u) => u.actif) as u (u.id)}
						<option value={u.id}>{nomAffiche(u)} ({u.email})</option>
					{/each}
				</select>
			</div>
			<div class="field">
				<label for="d-aidant">Proche aidant<EtoileRequis vide={!formAidantId} /></label>
				<select id="d-aidant" bind:value={formAidantId}>
					<option value={0} disabled>Choisir…</option>
					{#each users.filter((u) => u.actif && u.id !== formMandantId) as u (u.id)}
						<option value={u.id}>{nomAffiche(u)} ({u.email})</option>
					{/each}
				</select>
			</div>
			<div class="field">
				<label for="d-motif">Motif</label>
				<input
					id="d-motif"
					type="text"
					bind:value={formMotif}
					placeholder="Ex : Assistance personne âgée"
				/>
			</div>
			<div class="field">
				<label for="d-fin">Date de fin</label>
				<input id="d-fin" type="date" bind:value={formDateFin} />
				<!--  Pas de « (optionnel) » : le requis se marque par `*` et rien d'autre
			      (cadre R3). Ce qu'il fallait dire, c'est ce qui se passe sans date. -->
				<span class="aide">Sans date, la délégation reste valable sans limite.</span>
			</div>
			<p class="avertissement">
				&#x26A0;&#xFE0F; L'aidant devra accepter la délégation. Il pourra consulter à la place de la
				personne aidée ce qui lui est adressé, sans agir en son nom. L'accès aidant ne constitue pas
				une procuration d'AG.
			</p>

			<PiedFormulaire
				enCours={saving}
				desactive={!formMandantId || !formAidantId || formMandantId === formAidantId}
				on:annule={() => (showForm = false)}
			/>
		</form>
	</FormulaireCreation>
{/if}

<style>
	/*  L'avertissement juridique du formulaire : il était écrit en `style=` sur
	    la balise, ce que `lint:charte` ne peut pas relire. */
	.avertissement {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0;
		padding: 0.25rem 0.5rem;
		background: var(--color-bg);
		border-radius: var(--radius);
	}
	.deleg-list {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.deleg-card {
		padding: 1rem 1.25rem;
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.deleg-main {
		flex: 1;
		min-width: 0;
	}
	.deleg-people {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.deleg-person {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.deleg-label {
		font-size: var(--fs-2xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-muted);
		font-weight: 600;
	}
	.deleg-name {
		font-weight: 600;
		font-size: var(--fs-lg);
	}
	.deleg-arrow {
		color: var(--color-text-muted);
	}
	.deleg-meta {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-wrap: wrap;
		margin-bottom: 0.25rem;
	}
	.deleg-date {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	.deleg-motif {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0.25rem 0 0;
		font-style: italic;
	}
	.deleg-actions {
		display: flex;
		gap: 0.35rem;
		flex-shrink: 0;
		align-items: flex-start;
		padding-top: 0.25rem;
	}

	/*  La charte porte `.btn-danger` ; cet ecran ecrivait `#dc2626`
    EN DUR au lieu du jeton, donc hors du theme (#607, 28/08/2026). */
	.btn-danger {
		border-color: var(--color-danger);
	}
	@media (hover: hover) and (pointer: fine) {
		.btn-danger:hover {
			background: var(--color-danger);
		}
	}

	/*  🔴 L'EN-TÊTE d'une modale ne s'écrit plus ici : `Modale.svelte` le rend, et
	    `styles/composants.css` le style (`.modal-titre`). #607 avait retiré
	    `.modal-header`, `.modal-close` et `.modal-footer` de ces trois écrans en
	    laissant `.modal-header h3` — la seule des quatre qui n'existait PAS en
	    global, donc la seule que le retrait ne pouvait pas solder. Elle a survécu
	    à l'identique dans les trois, et divergeait du `h2` de la charte. */
	.barre-delegation {
		margin-bottom: 1.25rem;
	}
	.vide-delegations {
		padding: 2rem;
		text-align: center;
		color: var(--color-text-muted);
	}
</style>
