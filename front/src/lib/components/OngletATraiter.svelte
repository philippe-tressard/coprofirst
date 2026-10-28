<!--
  L'onglet **À traiter** de l'administration : les trois files qui attendent un
  geste de l'administrateur — comptes à valider, commandes d'accès, demandes de
  modification de profil.

  ## Pourquoi un onglet, et trois sections (01/10/2026)

  Demandé : *« regroupe en 3 sections pliables Comptes en attente, Commandes
  d'accès et Demandes profil »*. Elles étaient trois onglets de la rangée
  « Gestion utilisateurs », chacun avec sa pastille : la même question — « qu'y
  a-t-il à traiter ? » — se lisait en trois clics.

  Les trois sections sont des `SectionRepliee` en accordéon (`#lib/accordeon`,
  règle 17 de `ux-patterns`) : une seule dépliée à la fois. À l'arrivée, c'est
  la première qui a quelque chose à montrer qui s'ouvre — une demande, ou un
  échec de lecture.

  ## Ce que la page garde

  Les trois CHARGEMENTS : la pastille de l'onglet additionne les trois files dès
  l'ouverture de l'administration, alors que ce composant n'est monté qu'onglet
  ouvert. Les listes arrivent donc liées, et les gestes qui les vident vivent ici.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import { nomAffiche } from '#lib/noms.ts';
	import {
		admin as adminApi,
		type CommandeAccesEnAttente,
		type CompteEnAttenteEnrichi,
		type DemandeProfil,
		type User,
	} from '#lib/api/index.ts';
	import { badgeRole, badgeStatut, libelleRole, LIBELLES_STATUT_ABREGE } from '#lib/roles.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { validerCompte } from '#lib/comptes.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { accepterCommandeAcces, refuserCommandeAcces } from '#lib/commandes-acces.ts';
	import { fmtDatetimeShort as fmt } from '#lib/date.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import AccepterRefuser from '#lib/components/AccepterRefuser.svelte';
	//  ⏱ La boîte de validation attend le geste « Valider » (#1844).
	import ChargementDiffere from '#lib/components/ChargementDiffere.svelte';
	import SectionRepliee from '#lib/components/SectionRepliee.svelte';

	export let comptes: CompteEnAttenteEnrichi[] = [];
	export let comptesLoading = true;
	/** Non vide = on n'a PAS pu regarder. Distinct de « la liste est vide ». */
	export let erreurComptes = '';
	export let commandes: CommandeAccesEnAttente[] = [];
	export let commandesLoading = true;
	export let erreurCommandes = '';
	export let demandesProfil: DemandeProfil[] = [];
	export let demandesProfilLoading = true;
	export let erreurDemandesProfil = '';
	export let batimentsMap: Record<number, string> = {};

	type SectionATraiter = 'comptes' | 'acces' | 'demandes_profil';
	let ouverte: SectionATraiter | null = null;

	//  Le compteur d'une section : `null` tant qu'on n'a pas regardé, ou si l'on
	//  n'a pas pu — « 0 » se lirait « rien à traiter » (`SectionRepliee`).
	const compteDe = (liste: readonly unknown[], chargement: boolean, erreur: string) =>
		chargement || erreur ? null : liste.length;

	//  Une seule fois, quand les trois files ont répondu : la première qui a
	//  quelque chose à montrer s'ouvre. Toutes vides, tout reste plié — les
	//  compteurs à zéro disent déjà qu'il n'y a rien.
	let ouvertureFaite = false;
	$: if (!ouvertureFaite && !comptesLoading && !commandesLoading && !demandesProfilLoading) {
		ouvertureFaite = true;
		const aMontrer: [SectionATraiter, boolean][] = [
			['comptes', comptes.length > 0 || !!erreurComptes],
			['acces', commandes.length > 0 || !!erreurCommandes],
			['demandes_profil', demandesProfil.length > 0 || !!erreurDemandesProfil],
		];
		ouverte = aMontrer.find(([, oui]) => oui)?.[0] ?? null;
	}

	//  Comptes en attente
	async function refuserCompte(id: number, motif: string) {
		try {
			await adminApi.traiterCompte(id, { action: 'refuser', motif });
			toast('info', 'Compte refusé.');
			comptes = comptes.filter((c) => c.user.id !== id);
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	// Validation (comptes en attente + Nouvel Arrivant)
	let cvModal: { user: User; lotsPrevus: number } | null = null;
	let cvNewArrivant = false;
	let cvBatiment = '';
	let cvAncienResident = '';
	let cvSubmitting = false;

	function openCompteValidation(item: CompteEnAttenteEnrichi) {
		const u = item.user;
		cvModal = { user: u, lotsPrevus: item.lots_prevus ?? 0 };
		cvNewArrivant = false;
		cvBatiment = u.batiment_id ? (batimentsMap[u.batiment_id] ?? '') : '';
		cvAncienResident = '';
	}

	//  🔴 Le compte rendu de la validation vit dans `#lib/comptes` depuis le
	//  12/09/2026 : l'espace CS en portait une version plus PAUVRE, qui taisait
	//  les lots résolus et l'avertissement sur un copropriétaire aidé introuvable.
	//  `standards/02` §4 bis — entre deux implémentations, la plus disante.
	async function confirmerCompteValidation() {
		if (!cvModal) return;
		const u = cvModal.user;
		cvSubmitting = true;
		try {
			const annonces = await validerCompte(u, {
				nouvelArrivant: cvNewArrivant,
				batiment: cvBatiment,
				ancienResident: cvAncienResident,
			});
			comptes = comptes.filter((c) => c.user.id !== u.id);
			for (const a of annonces) toast(a.ton, a.texte);
			cvModal = null;
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			cvSubmitting = false;
		}
	}

	//  Commandes d'accès
	async function accepterCommande(id: number) {
		try {
			if (!(await accepterCommandeAcces(id))) return;
			toast('success', 'Commande acceptée.');
			commandes = commandes.filter((c) => c.id !== id);
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function refuserCommande(id: number, motif: string) {
		try {
			await refuserCommandeAcces(id, motif);
			toast('info', 'Commande refusée.');
			commandes = commandes.filter((c) => c.id !== id);
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	//  Demandes de modification de profil
	async function approuverDemande(id: number) {
		try {
			await adminApi.traiterDemandeProfil(id, { action: 'approuver' });
			toast('success', 'Demande approuvée.');
			demandesProfil = demandesProfil.filter((d) => d.id !== id);
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function rejeterDemande(id: number, motif: string) {
		try {
			await adminApi.traiterDemandeProfil(id, {
				action: 'rejeter',
				motif_refus: motif || null,
			});
			toast('info', 'Demande rejetée.');
			demandesProfil = demandesProfil.filter((d) => d.id !== id);
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}
</script>

<SectionRepliee
	titre="Comptes en attente"
	compte={compteDe(comptes, comptesLoading, erreurComptes)}
	ouvert={ouverte === 'comptes'}
	surBascule={() => (ouverte = basculer(ouverte, 'comptes'))}
	enSerie
>
	{#if comptesLoading || erreurComptes || comptes.length === 0}
		<EtatListe
			chargement={comptesLoading}
			erreur={erreurComptes}
			vide={comptes.length === 0}
			titreErreur="Impossible d’afficher les comptes en attente"
			titreVide="Aucun compte en attente"
			messageVide="Tous les comptes ont été traités."
		/>
	{:else}
		<div class="card">
			<table class="table">
				<thead>
					<tr>
						<th>Nom</th><th>Statut</th><th>Rôle(s)</th><th>Bât.</th><th>Lots import</th><th
							>Inscription</th
						><th>Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each comptes as item (item.user.id)}
						{@const u = item.user}
						<tr>
							<td class="nom-compte"
								>{nomAffiche(u)}
								{#if u.statut === 'locataire' && u.nom_proprietaire}
									<div class="precision">
										&#x1F464; Prop. : {u.nom_proprietaire}
									</div>
								{/if}
								{#if (u.statut === 'aidant' || u.statut === 'mandataire') && u.nom_aide}
									<div class="precision">
										&#x1F464; Aidé : {u.prenom_aide}
										{u.nom_aide}
									</div>
								{/if}
							</td>
							<td
								><Badge teinte={badgeStatut(u.statut)}
									>{LIBELLES_STATUT_ABREGE[u.statut] ?? u.statut}</Badge
								></td
							>
							<td>
								<div class="liste-roles">
									{#each u.roles?.length ? u.roles : [u.role] as r (r)}
										<Badge teinte={badgeRole(r)}>{libelleRole(r)}</Badge>
									{/each}
								</div>
							</td>
							<td class="muted"
								>{u.batiment_id ? (batimentsMap[u.batiment_id] ?? `#${u.batiment_id}`) : '—'}</td
							>
							<td>
								{#if item.lots_prevus > 0}
									<span
										class="badge badge-green"
										title="{item.lots_prevus} lot(s) trouvé(s) dans l'import"
										>✓ {item.lots_prevus}</span
									>
								{:else if u.statut?.startsWith('copropriétaire')}
									<span class="badge badge-orange" title="Pas trouvé dans l'import Lots">⚠ 0</span>
								{:else}
									<span class="muted">—</span>
								{/if}
							</td>
							<td class="text-muted-sm">{fmt(u.cree_le)}</td>
							<td>
								<div class="action-row">
									<AccepterRefuser
										libelleAccepter="Valider →"
										onAccepter={() => openCompteValidation(item)}
										onRefuser={(motif) => refuserCompte(u.id, motif)}
									/>
								</div>
							</td>
						</tr>
						<!--  🔴 Le formulaire s'ouvre SOUS la ligne du compte, pas dans une
						      fenêtre (#889, arbitrage du 11/09/2026). Dans un tableau, « à la
						      place du corps de la carte » se dit en une ligne de plus qui
						      s'étend sur toutes les colonnes : l'objet ne bouge pas, et le
						      formulaire reste attaché à lui.

						      C'est le MÊME composant que l'espace CS — les deux écrans en
						      portaient chacun une copie, qui avait déjà dérivé. -->
						{#if cvModal?.user?.id === u.id}
							<tr class="ligne-formulaire">
								<td colspan="7">
									<ChargementDiffere
										charger={() => import('#lib/components/ValidationCompte.svelte')}
									>
										{#snippet contenu(ValidationCompte)}
											<ValidationCompte
												utilisateur={u}
												precision={(cvModal?.lotsPrevus ?? 0) > 0
													? `${cvModal?.lotsPrevus} lot(s) détecté(s) dans l'import`
													: ''}
												enCours={cvSubmitting}
												bind:nouvelArrivant={cvNewArrivant}
												bind:batiment={cvBatiment}
												bind:ancienResident={cvAncienResident}
												onAnnuler={() => (cvModal = null)}
												onValider={confirmerCompteValidation}
											/>
										{/snippet}
									</ChargementDiffere>
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</SectionRepliee>

<SectionRepliee
	titre="Commandes d'accès"
	compte={compteDe(commandes, commandesLoading, erreurCommandes)}
	ouvert={ouverte === 'acces'}
	surBascule={() => (ouverte = basculer(ouverte, 'acces'))}
	enSerie
>
	{#if commandesLoading || erreurCommandes || commandes.length === 0}
		<EtatListe
			chargement={commandesLoading}
			erreur={erreurCommandes}
			vide={commandes.length === 0}
			titreErreur="Impossible d’afficher les commandes d’accès"
			titreVide="Aucune commande en attente"
			messageVide="Toutes les demandes d’accès ont été traitées."
		/>
	{:else}
		<div class="card">
			<table class="table">
				<thead>
					<tr><th>Utilisateur</th><th>Type</th><th>Lot</th><th>Date</th><th>Actions</th></tr>
				</thead>
				<tbody>
					{#each commandes as cmd (cmd.id)}
						<tr>
							<td class="nom-compte">#{cmd.user_id}</td>
							<td><span class="badge badge-blue">{cmd.type}</span></td>
							<td class="muted">{cmd.lot_id ?? ''}</td>
							<td class="text-muted-sm">{fmt(cmd.cree_le)}</td>
							<td>
								<div class="action-row">
									<AccepterRefuser
										onAccepter={() => accepterCommande(cmd.id)}
										onRefuser={(motif) => refuserCommande(cmd.id, motif)}
									/>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</SectionRepliee>

<SectionRepliee
	titre="Demandes de profil"
	compte={compteDe(demandesProfil, demandesProfilLoading, erreurDemandesProfil)}
	ouvert={ouverte === 'demandes_profil'}
	surBascule={() => (ouverte = basculer(ouverte, 'demandes_profil'))}
	enSerie
>
	{#if demandesProfilLoading || erreurDemandesProfil || demandesProfil.length === 0}
		<EtatListe
			chargement={demandesProfilLoading}
			erreur={erreurDemandesProfil}
			vide={demandesProfil.length === 0}
			titreErreur="Impossible d’afficher les demandes de profil"
			titreVide="Aucune demande en attente"
			messageVide="Toutes les demandes de modification de profil ont été traitées."
		/>
	{:else}
		<div class="card">
			<table class="table">
				<thead>
					<tr
						><th>Résident</th><th>Statut actuel</th><th>Bâtiment actuel</th><th
							>Changement souhaité</th
						><th>Motif</th><th>Date</th><th>Actions</th></tr
					>
				</thead>
				<tbody>
					{#each demandesProfil as d (d.id)}
						<tr>
							<td>
								<div class="demandeur">{d.utilisateur_nom}</div>
								<div class="text-muted-sm">
									{d.utilisateur_email}
								</div>
							</td>
							<td
								><span class="valeur"
									>{(d.statut_actuel && LIBELLES_STATUT_ABREGE[d.statut_actuel]) ??
										d.statut_actuel ??
										'—'}</span
								></td
							>
							<td><span class="valeur">{d.batiment_actuel ?? '—'}</span></td>
							<td>
								{#if d.statut_souhaite}
									<div class="valeur">
										Type : <strong
											>{LIBELLES_STATUT_ABREGE[d.statut_souhaite] ?? d.statut_souhaite}</strong
										>
									</div>
								{/if}
								{#if d.batiment_nom_souhaite}
									<div class="valeur">
										Bât. : <strong>{d.batiment_nom_souhaite}</strong>
									</div>
								{/if}
							</td>
							<td class="motif-demande">{d.motif ?? '—'}</td>
							<td class="text-muted-md">{fmt(d.cree_le)}</td>
							<td>
								<div class="action-row">
									<AccepterRefuser
										libelleAccepter="✓ Approuver"
										libelleRefuser="✗ Rejeter"
										onAccepter={() => approuverDemande(d.id)}
										onRefuser={(motif) => rejeterDemande(d.id, motif)}
									/>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</SectionRepliee>

<style>
	/*  La ligne qui accueille le formulaire de validation, sous celle du compte.
	    Elle n'a ni bordure haute ni fond propre : les deux lignes doivent se lire
	    comme un seul objet, sinon le formulaire semble concerner le compte
	    suivant. Partie de `admin/+page.svelte` avec le balisage qu'elle habille. */
	.ligne-formulaire > td {
		border-top: none;
		background: var(--color-neutre-fond);
		padding: 1rem;
	}
	.nom-compte {
		font-weight: 500;
	}
	.precision {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		margin-top: 0.15rem;
	}
	.liste-roles {
		display: flex;
		gap: 0.25rem;
		flex-wrap: wrap;
	}
	.demandeur {
		font-weight: 600;
	}
	.valeur {
		font-size: var(--fs-md);
	}
	.motif-demande {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		max-width: 140px;
		white-space: pre-wrap;
	}
</style>
