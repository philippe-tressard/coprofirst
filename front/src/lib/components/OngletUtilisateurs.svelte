<!--
  **L'onglet « Utilisateurs » de l'administration** — la liste, ses filtres, et
  les gestes sur un compte : rôles, correction, accueil d'un arrivant,
  bannissement de la communauté, suppression.

  ## Pourquoi il vit ici (#779, 30/09/2026)

  `admin/+page.svelte` en portait 284 lignes de balisage et une centaine de
  script, alors que la plupart de ses onglets tiennent en une ligne. C'est un
  découpage (scinder), pas une factorisation : rien n'était écrit deux fois.
  Le bloc a sa responsabilité propre — les comptes —, son état, ses modales et
  ses styles, et ne partage avec la page que la liste, qu'elle charge parce que
  l'onglet Site en lit aussi les gestionnaires possibles.
-->
<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import IconeAction from '$lib/components/IconeAction.svelte';
	import { messageErreur } from '$lib/erreurs';
	import { admin as adminApi, type UtilisateurAdmin } from '$lib/api';
	import {
		adresseChangee,
		annonceLienEnvoye,
		ETIQUETTES_COMPTE,
		formulaireCompte,
	} from '$lib/comptes';
	import { fmtDate } from '$lib/date';
	import { comparerParNom, nomAffiche } from '$lib/noms';
	import { badgeStatut, badgesDeRoles, libelleRole, LIBELLES_STATUT_ABREGE } from '$lib/roles';
	import { aRole, currentUser, setUser } from '$lib/stores/auth';
	import { compterTitulaires } from '$lib/droits';
	import GestesRolesCompte from '$lib/components/GestesRolesCompte.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import FiltresUtilisateurs from '$lib/components/FiltresUtilisateurs.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import FormulaireUtilisateur from '$lib/components/FormulaireUtilisateur.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import ModaleAccueilArrivant from '$lib/components/ModaleAccueilArrivant.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { confirmerPuis, SUPPRESSION } from '$lib/confirmation';

	/** La liste des comptes — chargée par la page (l'onglet Site la lit aussi). */
	export let utilisateurs: UtilisateurAdmin[] = [];
	export let chargement = false;
	/** Non vide = la liste n'a pas pu être lue : elle ne se dit pas vide (#1459). */
	export let erreur = '';
	export let batimentsList: { id: number; numero: string }[] = [];
	export let batimentsMap: Record<number, string> = {};
	/** Relit la liste (la page la charge : l'onglet Site en lit aussi les comptes). */
	export let recharger: () => unknown = () => {};

	$: titulaires = compterTitulaires(utilisateurs);
	$: pourSoi = roleEnCours?.user.id === $currentUser?.id;

	let userSearch = '';
	let userStatutFilter = '';
	let userCompteFilter = '';
	let roleEnCours: { user: UtilisateurAdmin; role: string; action: 'ajouter' | 'retirer' } | null =
		null;
	let editUser: UtilisateurAdmin | null = null;
	let editForm = formulaireCompte();
	/** Le mot de passe de l'administrateur, si l'adresse change (#1549) — jamais gardé. */
	let motDePasseAdmin = '';

	async function relancerAutoMatch(userId: number, userNom: string) {
		try {
			const res = await adminApi.autoMatchUtilisateur(userId);
			const lots = res?.auto_match?.lots_resolus ?? 0;
			const lotsM = res?.auto_match?.lots ?? 0;
			if (lots > 0) toast('success', `${userNom} — ${lots} lot(s) résolu(s) automatiquement.`);
			else if (lotsM > 0)
				toast('success', `${userNom} — ${lotsM} lot(s) matché(s) (en attente de résolution).`);
			else toast('info', `${userNom} — Aucun import trouvé pour ce nom.`);
			await recharger();
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur auto-match'));
		}
	}

	//  L'accueil d'un arrivant : sa modale porte son état et son envoi.
	let accueilPour: UtilisateurAdmin | null = null;

	function demanderRole(u: UtilisateurAdmin, role: string, action: 'ajouter' | 'retirer') {
		roleEnCours = { user: u, role, action };
	}

	async function confirmerRole() {
		if (!roleEnCours) return;
		const { user, role, action } = roleEnCours;
		try {
			//  🔴 Les deux méthodes EXISTAIENT dans le client et n'étaient appelées
			//  nulle part (#801) : l'écran construisait l'URL dans un ternaire, ce
			//  qui la rendait invisible à toute recherche par route. C'est la forme
			//  la plus tenace du contournement — la chaîne recopiée ne ressemble
			//  même plus à une route.
			const updated = await (action === 'ajouter'
				? adminApi.ajouterRole(user.id, role)
				: adminApi.retirerRole(user.id, role));
			toast(
				'success',
				`Rôle ${libelleRole(role)} ${action === 'ajouter' ? 'ajouté à' : 'retiré de'} ${nomAffiche(user)}.`,
			);
			utilisateurs = utilisateurs.map((u) => (u.id === user.id ? { ...u, ...updated } : u));
			//  Un rôle qu'on se retire à soi-même vaut aussitôt : sans Admin, la garde
			//  d'`admin/+layout.svelte` ramène au tableau de bord — ou, à l'opérateur,
			//  `BarreOnglets` ramène sur sa supervision (#2029).
			if ($currentUser && user.id === $currentUser.id) {
				setUser({ ...$currentUser, role: updated.role, roles: updated.roles });
			}
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			roleEnCours = null;
		}
	}

	function openEdit(u: UtilisateurAdmin) {
		editForm = formulaireCompte(u);
		editUser = u;
		motDePasseAdmin = '';
	}

	async function saveEdit() {
		if (!editUser) return;
		//  Une autre adresse n'est qu'une DEMANDE (#1549) : le mot de passe de
		//  l'administrateur, un lien à la nouvelle adresse, un avis à l'actuelle —
		//  qui reste celle du compte jusqu'à ce que le titulaire clique.
		const changee = adresseChangee(editForm.email, editUser.email);
		try {
			const updated = await adminApi.modifierUtilisateur(editUser.id, {
				...editForm,
				...(changee ? { mot_de_passe_actuel: motDePasseAdmin } : {}),
			});
			utilisateurs = utilisateurs.map((u) => (u.id === editUser!.id ? { ...u, ...updated } : u));
			toast(
				'success',
				changee
					? `Utilisateur mis à jour. ${annonceLienEnvoye(editForm.email, true)}`
					: 'Utilisateur mis à jour.',
			);
			editUser = null;
			motDePasseAdmin = '';
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	/**  Supprimer un compte — confirmé par `SUPPRESSION`, comme toute suppression
	 *   définitive (`lint:suppression-confirmee`, #779). La modale écrite ici à la
	 *   main disait la même chose autrement, et rendait « Erreur » là où l'API
	 *   expliquait pourquoi : `confirmerPuis` passe par `messageErreur`. */
	function supprimerUtilisateur(u: UtilisateurAdmin) {
		return confirmerPuis(
			SUPPRESSION(`Le compte de ${nomAffiche(u)} (${u.email}).`),
			`${nomAffiche(u)} supprimé.`,
			async () => {
				await adminApi.supprimerUtilisateur(u.id);
				utilisateurs = utilisateurs.filter((x) => x.id !== u.id);
			},
		);
	}

	async function toggleBanCommunaute(u: UtilisateurAdmin) {
		const isBanned =
			u.communaute_interdit ||
			(u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date());
		const interdit = !isBanned;
		try {
			const updated = await adminApi.banCommunaute(u.id, { interdit });
			utilisateurs = utilisateurs.map((x) => (x.id === u.id ? { ...x, ...updated } : x));
			if (interdit) {
				const msg = updated.communaute_interdit
					? `${nomAffiche(u)} banni définitivement de la communauté.`
					: `${nomAffiche(u)} banni de la communauté pour 1 mois (probatoire).`;
				toast('success', msg);
			} else {
				toast('success', `${nomAffiche(u)} réautorisé à la communauté.`);
			}
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	$: nbCS = utilisateurs.filter((u) => (u.roles ?? [u.role]).includes('conseil_syndical')).length;

	$: filteredUsers = utilisateurs
		.filter((u) => {
			if (userStatutFilter && u.statut !== userStatutFilter) return false;
			if (userCompteFilter === 'actif' && !u.actif) return false;
			if (userCompteFilter === 'inactif' && u.actif) return false;
			if (!userSearch.trim()) return true;
			const q = userSearch.toLowerCase();
			return (
				(u.prenom + ' ' + u.nom).toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
			);
		})
		.sort(comparerParNom);

	// Rôles actifs : affiche les rôles réels (P·R·E·CS·A) depuis u.roles
	function userBatimentLabel(u: UtilisateurAdmin): string {
		if (u.batiment_id && batimentsMap[u.batiment_id]) return batimentsMap[u.batiment_id];
		if (u.batiment_nom) return u.batiment_nom;
		if (u.batiment_id) return `Bât. ${u.batiment_id}`;
		return '—';
	}
</script>

{#if chargement || erreur}
	<EtatListe {chargement} {erreur} titreErreur="Impossible d’afficher les utilisateurs" />
{:else}
	<!--  Recherche, filtres en pastilles, compteurs (#1329). -->
	<FiltresUtilisateurs
		bind:recherche={userSearch}
		bind:statut={userStatutFilter}
		bind:compte={userCompteFilter}
		affiches={filteredUsers.length}
		total={utilisateurs.length}
		{nbCS}
	/>

	{#if filteredUsers.length === 0}
		<div class="empty-state"><h3>Aucun résultat</h3></div>
	{:else}
		<div class="card">
			<table class="table">
				<thead>
					<tr
						><th>Nom</th><th>E-mail</th><th>Type</th><th>Bâtiment</th><th>Compte</th><th
							>Rôles actifs</th
						><th>Ajouter / Retirer un rôle</th><th>Actions</th></tr
					>
				</thead>
				<tbody>
					{#each filteredUsers as u (u.id)}
						<tr class:row-cs={aRole(u, 'conseil_syndical')} class:row-inactive={!u.actif}>
							<td class="nom-compte">
								{nomAffiche(u)}
								{#if u.statut === 'locataire' && u.nom_proprietaire}
									<div class="precision-compte">
										🏠 Bailleur : {u.nom_proprietaire}
									</div>
								{/if}
								<!--  Trois états, dont « sans objet » en gris (26/09/2026) : l'état
								      vient du serveur, les mots de `$lib/comptes`. -->
								<div class="user-tags">
									{#each ETIQUETTES_COMPTE as t (t.cle)}
										{@const e = u.etiquettes?.[t.cle] ?? 'manque'}
										<span
											class="utag"
											class:utag-ok={e === 'ok'}
											class:utag-manque={e === 'manque'}
											class:utag-sans_objet={e === 'sans_objet'}
											title={e === 'ok' ? t.ok : e === 'manque' ? t.manque : t.sansObjet}
											>{t.libelle}</span
										>
									{/each}
								</div>
							</td>
							<td class="text-muted-md">{u.email}</td>
							<td>
								<Badge teinte={badgeStatut(u.statut)}>
									{LIBELLES_STATUT_ABREGE[u.statut] ?? u.statut ?? '—'}
								</Badge>
							</td>
							<td>
								<span class="badge badge-gray">{userBatimentLabel(u)}</span>
							</td>
							<td>
								{#if u.actif}
									<span class="badge badge-green">Actif</span>
								{:else if u.email_verifie === false}
									<span class="badge badge-orange" title="Email non vérifié">Email non vérifié</span
									>
								{:else}
									<span class="badge badge-gray">En attente</span>
								{/if}
								<!--  #1580 : averti de sa suppression pour inactivité ; s'efface à la reconnexion. -->
								{#if u.purge_avertie_le}
									<div
										class="purge-avertie"
										title="Supprimé trente jours après cet avertissement s'il ne se reconnecte pas"
									>
										⏳ Inactif, averti le {fmtDate(u.purge_avertie_le)}
									</div>
								{/if}
							</td>
							<td>
								<div class="liste-badges">
									{#each badgesDeRoles(u.roles?.length ? u.roles : [u.role]) as d (d.label)}
										<Badge teinte={d.cls}>{d.label}</Badge>
									{/each}
								</div>
							</td>
							<td>
								<GestesRolesCompte {u} {titulaires} demander={demanderRole} />
							</td>
							<td>
								<div class="action-row">
									<button
										class="btn-icon-edit"
										aria-label="Modifier"
										title="Modifier"
										on:click={() => openEdit(u)}><IconeAction icone="pencil" /></button
									>
									<button
										class="btn-icon"
										aria-label="Accueil nouvel arrivant"
										title="Accueil nouvel arrivant"
										on:click={() => (accueilPour = u)}><IconeAction icone="home" /></button
									>
									{#if u.actif && !u.has_lots}
										<button
											class="btn-icon"
											aria-label="Rejouer auto-match lots"
											title="Rejouer auto-match lots"
											on:click={() => relancerAutoMatch(u.id, nomAffiche(u))}
											><IconeAction icone="refresh-cw" /></button
										>
									{/if}
									<button
										class={u.communaute_interdit ||
										(u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date())
											? 'btn-icon-success'
											: 'btn-icon-warn'}
										aria-label={u.communaute_interdit ||
										(u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date())
											? 'Autoriser la communauté'
											: 'Interdire la communauté'}
										title={u.communaute_interdit
											? 'Banni définitivement — cliquer pour débannir'
											: u.communaute_ban_jusqu_au &&
												  new Date(u.communaute_ban_jusqu_au) > new Date()
												? 'Banni 1 mois (probatoire) — cliquer pour débannir'
												: 'Interdire la communauté'}
										on:click={() => toggleBanCommunaute(u)}
									>
										<!--  Au trait (10/10/2026) : banni pour de bon, banni pour un
										      mois — le sablier dit le temps qui reste —, ou autorisé et
										      le cadenas pose l'interdiction. Il n'y a pas de cadenas
										      OUVERT au catalogue : le sablier dit mieux l'état probatoire. -->
										<IconeAction
											icone={u.communaute_interdit
												? 'ban'
												: u.communaute_ban_jusqu_au &&
													  new Date(u.communaute_ban_jusqu_au) > new Date()
													? 'hourglass'
													: 'lock'}
										/>
									</button>
									<button
										class="btn-icon-danger"
										aria-label="Supprimer"
										title="Supprimer"
										on:click={() => void supprimerUtilisateur(u)}
										><IconeAction icone="trash-2" /></button
									>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{/if}

<!-- Modal de confirmation rôle -->
{#if roleEnCours}
	<Modale
		titre="Confirmer"
		classeBoite="modal-box card modal-sm"
		on:fermer={() => (roleEnCours = null)}
	>
		<p class="question-role">
			{roleEnCours.action === 'ajouter' ? 'Ajouter' : 'Retirer'} le rôle
			<strong>{libelleRole(roleEnCours.role)}</strong>
			{roleEnCours.action === 'ajouter' ? 'à' : 'de'}
			<strong>{pourSoi ? 'votre compte' : nomAffiche(roleEnCours.user)}</strong> ?
			<br />
			{#if pourSoi && roleEnCours.action === 'retirer' && roleEnCours.role === 'admin'}
				<span class="text-muted-sm">
					{aRole(roleEnCours.user, 'operateur')
						? "Vous n'y garderez que la supervision de la plateforme."
						: "Vous perdrez aussitôt l'accès à l'administration."}
				</span>
			{:else if !pourSoi}
				<span class="text-muted-sm"> Cette personne recevra une notification. </span>
			{/if}
		</p>
		<div class="modal-footer">
			<button class="btn btn-outline" on:click={() => (roleEnCours = null)}>Annuler</button>
			<button class="btn btn-primary" on:click={confirmerRole}>Confirmer</button>
		</div>
	</Modale>
{/if}

<!-- Modal édition utilisateur -->
<!-- Éditer un objet existant → la modale, qui déclare son geste (§14 bis, #640). -->
{#if editUser}
	<!--  La CORRECTION d'un utilisateur — la même boîte que partout depuis le
	      06/09/2026 (`ux-patterns` §14 bis). `cle` fait remonter le formulaire
	      quand on passe d'un utilisateur à un autre : la liste est longue, et
	      sans elle le second clic serait muet. -->
	<FormulaireCreation titre="Modifier l'utilisateur" cle={editUser}>
		<FormulaireUtilisateur
			bind:editForm
			adresseActuelle={editUser.email}
			bind:motDePasse={motDePasseAdmin}
			statutLabels={LIBELLES_STATUT_ABREGE}
			{batimentsList}
			onAnnuler={() => (editUser = null)}
			onEnregistrer={saveEdit}
		/>
	</FormulaireCreation>
{/if}

{#if accueilPour}
	<ModaleAccueilArrivant
		utilisateur={accueilPour}
		{batimentsMap}
		on:fermer={() => (accueilPour = null)}
	/>
{/if}

<style>
	.row-cs td {
		background: #eff6ff;
	}
	.row-inactive td {
		opacity: 0.6;
	}
	/*  La charte porte fond, bordure, rayon, curseur et couleur ;
    seuls la taille et le remplissage sont propres a cet ecran (#607, 28/08/2026). */
	.btn-outline {
		font-size: var(--fs-sm);
		padding: 0.3rem 0.7rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.btn-outline:hover {
			border-color: var(--color-primary);
			color: var(--color-primary);
		}
	}
	.user-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem;
		margin-top: 0.15rem;
	}
	.purge-avertie {
		margin-top: 0.15rem;
		font-size: var(--fs-xs);
		color: var(--color-warning-texte);
	}
	.utag {
		font-size: 0.6rem;
		font-weight: 600;
		padding: 0.05rem 0.35rem;
		border-radius: 4px;
		line-height: 1.3;
	}
	.utag-ok {
		background: #d4edda;
		color: #155724;
	}
	.utag-manque {
		background: #f8d7da;
		color: #721c24;
	}
	.utag-sans_objet {
		background: var(--color-neutre-fond);
		color: var(--color-text-muted);
	}
	.nom-compte {
		font-weight: 500;
	}
	.precision-compte {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		margin-top: 0.15rem;
	}
	.liste-badges {
		display: flex;
		gap: 0.3rem;
		flex-wrap: wrap;
	}
	.question-role {
		font-size: var(--fs-base);
		margin-bottom: 1rem;
	}
</style>
