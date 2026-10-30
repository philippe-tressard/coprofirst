<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import EntetePage from '#lib/components/EntetePage.svelte';
	import ChangementMotDePasse from '#lib/components/ChangementMotDePasse.svelte';
	import { clesHeritees, DEFAUTS_NOTIFS } from '#lib/preferences.ts';
	import { LIBELLES_STATUT, STATUTS_DEMANDABLES } from '#lib/roles.ts';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import ChoixTheme from '#lib/components/ChoixTheme.svelte';
	import PreferencesAffichageNotifs from '#lib/components/PreferencesAffichageNotifs.svelte';
	import { onMount } from 'svelte';
	import { currentUser, setUser } from '#lib/stores/auth.ts';
	import {
		auth as authApi,
		lots as lotsApi,
		uploads as uploadsApi,
		type MaDemandeProfil,
		type MonLot,
		type User,
	} from '#lib/api/index.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import ImageUpload from '#lib/components/ImageUpload.svelte';
	import {
		getPageConfig,
		configStore,
		siteNomStore,
		defautsDePage,
	} from '#lib/stores/pageConfig.ts';
	import ChargementPartiel from '#lib/components/ChargementPartiel.svelte';
	import HistoriqueDemandes from '#lib/components/HistoriqueDemandes.svelte';
	import { STATUT_DEMANDE_BADGE, STATUT_DEMANDE_LABEL } from '#lib/demandes.ts';
	import { essayer, messagePartiel } from '#lib/chargement.ts';
	import DroitsRgpd from '#lib/components/DroitsRgpd.svelte';
	import InformationsCompte from '#lib/components/InformationsCompte.svelte';
	import ChampsEtage from '#lib/components/ChampsEtage.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import DemarcheArrivant from '#lib/components/DemarcheArrivant.svelte';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import ChampAdresseCompte from '#lib/components/ChampAdresseCompte.svelte';
	import { adresseChangee, annonceLienEnvoye } from '#lib/comptes.ts';

	$: _pc = getPageConfig($configStore, 'profil', defautsDePage('profil'));
	$: _siteNom = $siteNomStore;

	// ── Infos personnelles ─────────────────────────────────────────────────────
	let prenom = '';
	let nom = '';
	let telephone = '';
	/**  L'étage de CHAQUE lot, par identifiant — `Lot.etage`, donc une donnée de
	 *   PATRIMOINE, distincte de la précédente : un bailleur a un lot au 4ᵉ et
	 *   habite ailleurs. Écrite par son occupant depuis le 09/09/2026 (#835) —
	 *   c'est lui qui sait à quel étage il vit. */
	let etagesLot: Record<number, number | null> = {};
	let champsEtage: ChampsEtage;
	let societe = '';
	let fonction = '';
	let email = '';
	/** Exigé seulement si l'adresse change (#1549) — puis vidé, jamais gardé. */
	let motDePasseAdresse = '';
	let saving = false;
	let uploadingAvatar = false;

	// ── Notifications ─────────────────────────────────────────────────────────
	let valeursNotifs: Record<string, boolean> = { ...DEFAUTS_NOTIFS };
	//  Les clés jamais réglées : l'écran dit alors « hérité », plutôt que de laisser
	//  croire à un choix que personne n'a fait (#1147).
	let heritees: Set<string> = new Set(Object.keys(DEFAUTS_NOTIFS));
	let restreindreAMesBatiments = false;

	// ── Lots ──────────────────────────────────────────────────────────────────
	let mesLots: MonLot[] = [];

	// ── Demandes de modif profil ───────────────────────────────────────────────
	let demandes: MaDemandeProfil[] = [];
	let demandesLoading = true;
	/** Non vide = une des trois listes du profil n'a pas pu être chargée. */
	let erreurChargement = '';
	let showDemandeForm = false;
	let batiments: { id: number; numero: string }[] = [];
	let demandeStatut = '';
	let demandeBatimentId: number | null = null;
	let demandeMotif = '';
	let savingDemande = false;

	$: demandePending = demandes.find((d) => d.statut_demande === 'en_attente') ?? null;

	// ── Labels ─────────────────────────────────────────────────────────────────

	//  🔴 Libellés dans `#lib/roles` (#801) — voir l'en-tête de ce module : la
	//  table était écrite six fois, et celle-ci écrivait « Copropriétaire
	//  Résident » là où le tableau de bord écrivait « Copropriétaire résident ».

	//  ⚠️ Le vocabulaire d'une demande vit dans `#lib/demandes` : cette page ET
	//  `HistoriqueDemandes` le lisent. Je l'avais d'abord emporté avec la table
	//  extraite — la page s'en sert aussi, quarante lignes plus haut.

	// ── Init ──────────────────────────────────────────────────────────────────
	//  L'initialisation suit le STORE, pas le montage : le layout `(app)` peuple
	//  `currentUser` dans SON `onMount`, et les `onMount` des enfants s'exécutent
	//  AVANT ceux du parent. Sur un rechargement direct de /profil, cette page
	//  lisait donc un store vide et laissait prénom, nom et e-mail blancs —
	//  « Enregistrer » aurait écrasé les vraies valeurs (signalé le 14/08/2026).
	//  Le drapeau évite d'écraser une saisie en cours quand `setUser` réassigne.
	let champsInitialises = false;
	$: if ($currentUser && !champsInitialises) {
		champsInitialises = true;
		initialiserDepuis($currentUser);
	}

	function initialiserDepuis(u: User) {
		prenom = u.prenom ?? '';
		nom = u.nom ?? '';
		telephone = u.telephone ?? '';
		societe = u.societe ?? '';
		fonction = u.fonction ?? '';
		email = u.email ?? '';
		//  La démarche « Nouvel arrivant » s'initialise dans `DemarcheArrivant`.

		//  Préférences d'e-mail. L'ancien format (huit clés `*_app` / `*_mail`) est
		//  converti par la migration 0145 ; le repli sur les défauts couvre les
		//  comptes qu'elle n'aurait pas atteints — un compte créé entre le
		//  déploiement de l'API et celui du front, par exemple.
		heritees = clesHeritees(u.preferences_notifications);
		try {
			const lues = JSON.parse(u.preferences_notifications || '{}');
			for (const cle of Object.keys(DEFAUTS_NOTIFS)) {
				valeursNotifs[cle] = typeof lues?.[cle] === 'boolean' ? lues[cle] : DEFAUTS_NOTIFS[cle];
			}
		} catch {
			valeursNotifs = { ...DEFAUTS_NOTIFS };
		}
		valeursNotifs = valeursNotifs; // Svelte 4 : réassigner pour propager
		restreindreAMesBatiments = u.restreindre_a_mes_batiments ?? false;
	}

	onMount(async () => {
		//  🔴 Aucune de ces trois listes n'a d'état « vide » à l'écran : elles se
		//  rendent `{#if …length > 0}`. Un échec ne produisait donc RIEN — ni
		//  liste, ni message —, et la ligne « Lot(s) » disparaissait comme si le
		//  compte n'en avait aucun (#522). D'où le bandeau plutôt qu'un état de
		//  liste : il n'y a pas de vide à distinguer, il y a un silence à rompre.
		const [[lots, eLots], [bats, eBats]] = await Promise.all([
			essayer<MonLot[]>(lotsApi.mesList(), []),
			essayer<{ id: number; numero: string }[]>(authApi.batiments(), []),
		]);
		mesLots = lots;
		batiments = bats;
		etagesLot = Object.fromEntries(mesLots.map((l) => [l.id, l.etage ?? null]));

		const [dem, eDem] = await essayer<MaDemandeProfil[]>(authApi.mesDemandes(), []);
		demandes = dem;
		demandesLoading = false;
		erreurChargement = messagePartiel(eLots, eBats, eDem);
	});

	// ── Actions ───────────────────────────────────────────────────────────────
	async function saveProfile() {
		saving = true;
		//  🔴 Une autre adresse n'est qu'une DEMANDE (#1549) : le serveur éprouve le
		//  mot de passe, envoie le lien à la nouvelle adresse et l'avis à l'actuelle,
		//  qui reste celle du compte jusqu'au clic. L'écran le dit, au lieu
		//  d'annoncer « mis à jour » une adresse qui ne l'est pas encore.
		const emailChanged = adresseChangee(email, $currentUser?.email);
		const annonce = emailChanged ? annonceLienEnvoye(email) : 'Profil mis à jour';
		await tenter(async () => {
			const updated = await authApi.updateMe({
				prenom,
				nom,
				telephone: telephone || null,
				societe: societe || null,
				fonction: fonction || null,
				...(emailChanged ? { email, mot_de_passe_actuel: motDePasseAdresse } : {}),
			});
			//  Les DEUX étages s'écrivent dans le composant qui les saisit : `Lot.etage`
			//  est une autre table avec une autre règle d'accès (#835), et l'étage
			//  personnel part par `PATCH /auth/me` — lequel prévient le gestionnaire du
			//  site quand la saisie contredit le lot.
			mesLots = await champsEtage.enregistrerEtagesDeLots();
			setUser((await champsEtage.enregistrerEtagePersonnel()) ?? updated);
			//  Le champ revient à l'adresse du compte — toujours l'ancienne — et le
			//  mot de passe ne reste pas dans la page.
			email = updated.email ?? email;
			motDePasseAdresse = '';
		}, annonce);
		saving = false;
	}

	async function handleAvatarChange(e: CustomEvent<File>) {
		uploadingAvatar = true;
		await tenter(
			async () => {
				const { url } = await uploadsApi.avatar(e.detail);
				const updated = { ...$currentUser!, photo_url: url };
				setUser(updated);
			},
			'Photo de profil mise à jour',
			'Erreur upload',
		);
		uploadingAvatar = false;
	}

	async function saveNotifs(valeurs: Record<string, boolean>, restreindre: boolean) {
		const prefs = JSON.stringify(valeurs);
		await tenter(
			async () => {
				const updated = await authApi.updateMe({
					preferences_notifications: prefs,
					restreindre_a_mes_batiments: restreindre,
				});
				setUser(updated);
				valeursNotifs = valeurs;
				//  Enregistrer, c'est choisir : plus rien n'est hérité après ce geste,
				//  même si la valeur n'a pas bougé. Le laisser afficher « hérité »
				//  après un enregistrement redirait le contraire de ce qui vient
				//  d'être fait.
				heritees = new Set();
				restreindreAMesBatiments = restreindre;
			},
			'Préférences enregistrées',
			"Erreur lors de l'enregistrement",
		);
	}

	async function soumettreDemandeModif() {
		if (!demandeStatut && !demandeBatimentId) {
			toast('error', "Sélectionnez au moins un changement (profil d'utilisateur ou bâtiment)");
			return;
		}
		savingDemande = true;
		await tenter(async () => {
			const d = await authApi.demanderModification({
				statut_souhaite: demandeStatut || null,
				batiment_id_souhaite: demandeBatimentId || null,
				motif: demandeMotif || null,
			});
			demandes = [d, ...demandes];
			showDemandeForm = false;
			demandeStatut = '';
			demandeBatimentId = null;
			demandeMotif = '';
		}, 'Demande envoyée au conseil syndical');
		savingDemande = false;
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'user'} />

<ChargementPartiel
	erreur={erreurChargement}
	consequence="Vos lots, la liste des bâtiments et l'historique de vos demandes peuvent être absents de cet écran."
/>

<div class="largeur-saisie">
	<!-- ── Avatar + Infos personnelles ──────────────────────────────────────── -->
	<section class="card carte-profil">
		<h2 class="section-title">Informations personnelles</h2>

		<div class="avatar-profil">
			<ImageUpload
				currentUrl={$currentUser?.photo_url}
				placeholder="&#x1F464;"
				label="Changer la photo"
				shape="circle"
				previewSize="100px"
				uploading={uploadingAvatar}
				on:change={handleAvatarChange}
			/>
		</div>

		<form on:submit|preventDefault={saveProfile}>
			<div class="form-grid">
				<div class="field">
					<label for="p-prenom">Prénom<EtoileRequis vide={!prenom} /></label>
					<input id="p-prenom" type="text" bind:value={prenom} required />
				</div>
				<div class="field">
					<label for="p-nom">Nom<EtoileRequis vide={!nom} /></label>
					<input id="p-nom" type="text" bind:value={nom} required />
				</div>
			</div>
			<ChampAdresseCompte
				id="p-email"
				bind:adresse={email}
				adresseActuelle={$currentUser?.email ?? ''}
				bind:motDePasse={motDePasseAdresse}
			/>
			<div class="field">
				<label for="p-tel">Téléphone</label>
				<input id="p-tel" type="tel" bind:value={telephone} placeholder="+33 6 00 00 00 00" />
			</div>
			<ChampsEtage bind:this={champsEtage} bind:etagesLot lots={mesLots} />
			<div class="field">
				<label for="p-societe">Société</label>
				<input
					id="p-societe"
					type="text"
					bind:value={societe}
					placeholder="Ex : Agence Dupont, Cabinet ABC…"
				/>
			</div>
			<div class="field">
				<label for="p-fonction">Fonction</label>
				<input
					id="p-fonction"
					type="text"
					bind:value={fonction}
					placeholder="Ex : Gestionnaire, Mandataire…"
				/>
			</div>
			<div class="form-actions">
				<button type="submit" class="btn btn-primary" disabled={saving}>
					{saving ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</form>
	</section>

	<!-- ── Informations résidence ────────────────────────────────────────────── -->
	<section class="card carte-profil">
		<h2 class="section-title">Résidence &amp; statut</h2>

		<InformationsCompte lots={mesLots} />

		<!-- Demande de modification -->
		{#if demandePending}
			<div class="bloc-demande">
				<EncartAvertissement>
					<strong>Demande en attente</strong> :
					{#if demandePending.statut_souhaite}
						changement de type vers «&nbsp;{LIBELLES_STATUT[demandePending.statut_souhaite] ??
							demandePending.statut_souhaite}&nbsp;»
					{/if}
					{#if demandePending.statut_souhaite && demandePending.batiment_nom_souhaite}&nbsp;+&nbsp;{/if}
					{#if demandePending.batiment_nom_souhaite}
						déménagement vers {demandePending.batiment_nom_souhaite}
					{/if}
					<span class="etat-demande"
						><Badge teinte={STATUT_DEMANDE_BADGE[demandePending.statut_demande]}>
							{STATUT_DEMANDE_LABEL[demandePending.statut_demande]}
						</Badge></span
					>
				</EncartAvertissement>
			</div>
		{:else}
			<button
				class="btn btn-outline btn-sm bloc-demande"
				on:click={() => (showDemandeForm = !showDemandeForm)}
			>
				{showDemandeForm ? 'Annuler' : '✏️ Demander une modification (profil / bâtiment)'}
			</button>
		{/if}

		{#if showDemandeForm && !demandePending}
			<div class="demande-form bloc-demande">
				<p class="aide intro-demande">
					Les modifications du profil d'utilisateur et du bâtiment sont soumises à validation du
					conseil syndical.
				</p>
				<!--  Des pastilles, libellés lus dans `#lib/roles` (#1329) : ils étaient
				      recopiés ici. -->
				<ChoixPastilles
					options={STATUTS_DEMANDABLES.map((v) => ({ val: v, label: LIBELLES_STATUT[v] }))}
					bind:valeur={demandeStatut}
					tous="Inchangé"
					libelle="Nouveau profil d'utilisateur"
					libelleVisible
					defilante={false}
				/>
				<div class="field">
					<label for="dm-bat">Bâtiment souhaité</label>
					<select id="dm-bat" bind:value={demandeBatimentId}>
						<option value={null}>— Inchangé —</option>
						{#each batiments as bat (bat.id)}
							<option value={bat.id}>Bât. {bat.numero}</option>
						{/each}
					</select>
				</div>
				<div class="field">
					<label for="dm-motif">Motif / justification</label>
					<textarea
						id="dm-motif"
						rows="2"
						bind:value={demandeMotif}
						placeholder="Expliquez brièvement…"></textarea>
				</div>
				<div class="form-actions">
					<button
						class="btn btn-primary btn-sm"
						disabled={savingDemande}
						on:click={soumettreDemandeModif}
					>
						{savingDemande ? 'Envoi…' : 'Envoyer la demande'}
					</button>
				</div>
			</div>
		{/if}

		<!-- Historique des demandes -->
		<HistoriqueDemandes {demandes} chargement={demandesLoading} statutLabels={LIBELLES_STATUT} />
	</section>

	<DemarcheArrivant {batiments} />

	<ChangementMotDePasse />

	<!-- ── Le thème de cet appareil (#2174, S5) ───────────────────────────── -->
	<ChoixTheme />

	<!-- ── Ce que j'affiche, ce que je reçois ──────────────────────────────── -->
	<PreferencesAffichageNotifs
		valeurs={valeursNotifs}
		{heritees}
		bind:restreindre={restreindreAMesBatiments}
		onSave={saveNotifs}
	/>

	<!-- ── RGPD — extrait dans `DroitsRgpd` le 22/09/2026 (modularité) ── -->
	<DroitsRgpd />
</div>

<style>
	/*  `.section-title` : la charte porte tout (composants.css). Retiree le 28/08/2026 (#607). */
	.demande-form {
		background: var(--color-neutre-fond);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 1rem;
	}
	.carte-profil {
		margin-bottom: 1.5rem;
	}
	.avatar-profil {
		display: flex;
		justify-content: center;
		margin-bottom: 1.25rem;
	}
	.bloc-demande {
		margin-top: 1rem;
	}
	.etat-demande {
		margin-left: 0.5rem;
	}
	.intro-demande {
		margin-bottom: 0.75rem;
	}
</style>
