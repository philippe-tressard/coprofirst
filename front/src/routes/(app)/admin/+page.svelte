<script lang="ts">
	import ChargementDiffere from '#lib/components/ChargementDiffere.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { get } from 'svelte/store';
	import {
		admin as adminApi,
		auth as authApi,
		config as configApi,
		instance as instanceApi,
		type CommandeAccesEnAttente,
		type CompteEnAttenteEnrichi,
		type DemandeProfil,
		type TextesLegauxSource,
		type UtilisateurAdmin,
	} from '#lib/api/index.ts';
	import { aRole, droitsOnglet, isAdmin, isOperateur, quandAuthResolue } from '#lib/stores/auth.ts';
	import { ongletsOuverts } from '#lib/onglets-ouverts.ts';
	import { essayer, messagePartiel, TITRE_PARAMETRAGE_ILLISIBLE } from '#lib/chargement.ts';
	import type { ServiceCopropriete } from '#lib/api/index.ts';
	import ChargementPartiel from '#lib/components/ChargementPartiel.svelte';
	//  Les onglets qui ENREGISTRENT ce que `/config/admin` et `/config/textes-legaux` ont lu.
	//  Si la lecture a échoué, leur formulaire serait vide — et enregistré, il
	//  effacerait la configuration (#1459) : ils montrent l'échec à la place.
	const ONGLETS_DU_PARAMETRAGE = [
		'fonctionnement',
		'connexion',
		'pages',
		'legal',
		'whatsapp',
		'smtp',
		'ia',
		'copropriete',
	];
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { defautsDePage } from '#lib/pages.ts';
	import { lieu } from '#lib/lieu.svelte.ts';
	import BarreOnglets from '#lib/components/BarreOnglets.svelte';
	import PorteeOnglet from '#lib/components/PorteeOnglet.svelte';
	import EntetePage from '#lib/components/EntetePage.svelte';
	import {
		CONFIG_SITE_DEFAUT,
		ecrireConfigSite,
		lireConfigSite,
		type SectionSite,
	} from '#lib/configSite.ts';
	import OngletATraiter from '#lib/components/OngletATraiter.svelte';
	import { marquerDonneesAffichees, trackTabView } from '#lib/telemetry.ts';

	//  Onglets
	//  🔴 La liste des onglets vit dans `#lib/pages-roles.ts` (page `admin`) et
	//  NULLE PART AILLEURS, depuis le 01/10/2026 : déclarés comme ceux des autres
	//  pages, ils se renomment et se décrivent dans « Descriptif pages », et
	//  `BarreOnglets` rend leurs deux rangées. Cette page en tenait sa propre liste,
	//  `const ONGLETS = [...] as const` — une seconde liste aurait divergé au
	//  premier onglet ajouté, et l'adressage direct aurait cessé de fonctionner en
	//  silence.
	//
	//  L'onglet actif SE LIT dans l'adresse (`?onglet=`, « sauf admin ») : chaque
	//  onglet est un lien, qui se copie et que le bouton Précédent rejoue. Une clé
	//  inconnue ouvre le premier onglet — le premier OUVERT : l'opérateur qui
	//  n'est pas administrateur n'a que ceux de l'Exploitation (#2029). Une clé
	//  d'avant le rangement par niveau (#2062) est redirigée par `+page.ts`.
	$: ouverts = ongletsOuverts('admin', $droitsOnglet).map((o) => o.id);
	$: demande = $lieu.url.searchParams.get('onglet');
	$: onglet = demande && ouverts.includes(demande) ? demande : ouverts[0];
	$: trackTabView(onglet);

	//  L'onglet « Installations » n'a de sens que sur la RÉFÉRENCE (§4.11, R4 #1880) :
	//  le rôle de l'installation est une donnée, que seule la page peut lire —
	//  `masques`, pas `reserve`. Lu pour l'opérateur seulement (sa route l'exige).
	//  ⚠️ Rien n'est masqué tant que le rôle n'est pas connu : `BarreOnglets` REDIRIGE
	//  l'adresse d'un onglet masqué, et `/admin?onglet=installations` retombait sur le
	//  premier onglet avant même d'avoir lu le rôle (vu par `e2e/registre-installations`).
	let masques: string[] = [];
	quandAuthResolue(async () => {
		if (!get(isOperateur)) return;
		try {
			const etat = await instanceApi.installation();
			masques = etat.role === 'reference' ? [] : ['installations'];
		} catch {
			masques = ['installations'];
		}
	});

	//  Bâtiments (pour affichage)
	let batimentsMap: Record<number, string> = {};
	let erreurBatiments = '';
	async function loadBatiments() {
		[batimentsList, erreurBatiments] = await essayer(authApi.batiments(), []);
		batimentsMap = Object.fromEntries(batimentsList.map((b) => [b.id, `Bât. ${b.numero}`]));
	}

	//  Comptes en attente
	let comptes: CompteEnAttenteEnrichi[] = [];
	let comptesLoading = true;
	/** Non vide = on n'a PAS pu regarder. Distinct de « la liste est vide ». */
	let erreurComptes = '';

	async function loadComptes() {
		comptesLoading = true;
		//  🔴 `essayer` rend `[valeur, erreur]` — jamais l'un sans l'autre (#816).
		//  Ce `try/finally` n'avait AUCUN `catch` : une session expirée ou un 500
		//  rejetait la promesse dans le vide, `comptes` restait à `[]`, et l'écran
		//  annonçait « Aucun compte en attente ». Pas même un toast.
		[comptes, erreurComptes] = await essayer(adminApi.comptesEnAttenteEnrichis(), []);
		comptesLoading = false;
	}

	//  Commandes d'acces
	let commandes: CommandeAccesEnAttente[] = [];
	let commandesLoading = true;
	/** Non vide = on n'a PAS pu regarder. Distinct de « la liste est vide ». */
	let erreurCommandes = '';

	async function loadCommandes() {
		commandesLoading = true;
		[commandes, erreurCommandes] = await essayer(adminApi.commandesAccesEnAttente(), []);
		commandesLoading = false;
	}

	//  Le sous-onglet Maintenance ne charge plus rien lui-même : `TachesPlanifiees`
	//  charge sa synthèse, déplie l'historique de la tâche qu'on ouvre et porte son
	//  bouton de lancement. Les deux cartes qui doublaient tout cela sont parties
	//  avec #299, et avec elles `historique`, `historiqueTelemetrie` et leurs
	//  déclencheurs — précharger ici des tableaux que plus personne n'affiche aurait
	//  laissé deux appels d'API sans lecteur.

	//  Utilisateurs & rôles
	let utilisateurs: UtilisateurAdmin[] = [];
	let utilisateursLoading = true;
	let batimentsList: { id: number; numero: string }[] = [];

	//  🔴 L'échec se DIT (#1459) : ce chargement était un `try/finally` sans
	//  `catch` — un refus laissait la liste vide, sans un mot, et `lint:catch-vide`
	//  ne pouvait pas le voir faute de `catch`.
	let erreurUtilisateurs = '';
	//  🔴 Chargée dès que l'onglet actif en a besoin — et non au CLIC sur
	//  l'onglet, seul déclencheur jusqu'au 30/09/2026 : arrivé par un lien ou un
	//  rechargement sur `?onglet=utilisateurs`, l'écran restait sur « Chargement… »
	//  pour toujours, et l'onglet Site n'avait aucun gestionnaire à proposer.
	let listeDemandee = false;
	$: if ($isAdmin && (onglet === 'utilisateurs' || onglet === 'fonctionnement') && !listeDemandee) {
		listeDemandee = true;
		loadUtilisateurs();
	}
	async function loadUtilisateurs() {
		utilisateursLoading = true;
		[utilisateurs, erreurUtilisateurs] = await essayer(adminApi.utilisateurs(), []);
		utilisateursLoading = false;
	}

	//  🔴 La table des libellés vit dans `#lib/roles` depuis le 06/09/2026 (#801).
	//  Elle était écrite SIX fois — trois ici côté front, trois côté serveur — et
	//  les six avaient dérivé : « Copropriétaire Résident » dans deux écrans,
	//  « Copropriétaire résident » dans le troisième ; « Conseil syndical » ici,
	//  « Membre du Conseil Syndical » dans la notification que le serveur envoie.
	//  Chacune était cohérente avec elle-même : aucun contrôle ne pouvait le voir.

	//  Demandes de modification de profil
	let demandesProfil: DemandeProfil[] = [];
	let demandesProfilLoading = true;
	/** Non vide = on n'a PAS pu regarder. Distinct de « la liste est vide ». */
	let erreurDemandesProfil = '';

	async function loadDemandesProfil() {
		demandesProfilLoading = true;
		//  ⚠️ Le `catch { /* ignore */ }` d'origine est la forme la plus explicite
		//  du défaut : l'échec était écrit, lu, et jeté.
		[demandesProfil, erreurDemandesProfil] = await essayer(adminApi.demandesProfil(), []);
		demandesProfilLoading = false;
	}

	//  Montage
	//  Après l'authentification : l'opérateur qui n'est pas administrateur ne lit
	//  rien de la résidence (#2029), ses deux onglets chargent ce qu'ils montrent.
	quandAuthResolue(async () => {
		if (!get(isAdmin)) return marquerDonneesAffichees();
		//  🔴 Les files de « À traiter » partent D'ABORD, sans attendre le
		//  paramétrage (#1842). Elles venaient après trois lectures en série
		//  (coquille, `/config/admin`, `/config/textes-legaux`) qui ne servent qu'aux
		//  onglets de réglage : +225 ms à chaque ouverture de l'administration.
		//  Les quatre files arrivées : les données de l'onglet par défaut (#1846).
		Promise.all([loadBatiments(), loadComptes(), loadCommandes(), loadDemandesProfil()]).then(() =>
			marquerDonneesAffichees(),
		);
		//  Les services, pour griser l'onglet de celui qui est coupé. Un échec ne
		//  grise rien : l'onglet reste ouvrable, et sa ligne d'état dit le vrai.
		essayer(configApi.services(), []).then(([liste]) => (services = liste));
		// Paramétrage site — lu depuis `/config/admin` (require_admin) et NON depuis le
		// store : depuis l'audit de sécurité du 26/07/2026, `/api/config` est filtré par
		// liste blanche et n'expose plus que les clés de la coquille d'interface. Les
		// champs édités ici (SMTP, WhatsApp, référence de copropriété, gestionnaire du
		// site…) ne sont accessibles qu'à l'admin, ce qui est précisément le rôle requis
		// pour afficher cet écran. Les clés légales en sont exclues (perf) : route dédiée.
		//  🔴 Lu UNE fois (il l'était deux) et jamais en silence (#1459) : un échec
		//  laissait les textes légaux vides, et « Enregistrer » les effaçait.
		//  Les trois lectures partent ENSEMBLE ; aucune ne dépend d'une autre.
		//  Les textes légaux par leur SOURCE, champs compris (#2065) : le rendu public
		//  de `/config/legal`, enregistré, figerait les noms à la place des champs.
		const [, [adminCfg, eAdmin], [legal, eLegal]] = await Promise.all([
			loadSiteConfig(),
			essayer(configApi.admin(), {} as Record<string, string>),
			essayer(configApi.textesLegaux(), null as TextesLegauxSource | null),
		]);
		erreurParametrage = messagePartiel(eAdmin, eLegal);
		const cfg = { ...(get(configStore) as Record<string, string>), ...adminCfg };
		siteConfig = lireConfigSite(cfg, {
			mentions_legales: legal?.textes['mentions_legales'] ?? '',
			politique_confidentialite: legal?.textes['politique_confidentialite'] ?? '',
		});
		textesLegaux = legal;
		//  La configuration des pages est préparée par `OngletDescriptifPages`, qui
		//  la reçoit dans `valeurs` : la page n'a plus à connaître sa forme.
		// WhatsApp : la configuration part telle quelle vers l'onglet dédié.
		waCfgPublique = cfg;
		smtpValeurs = adminCfg;
		parametrageLu = true;
	});

	// ── Paramétrage site ──────────────────────────────────────────
	let siteConfig = { ...CONFIG_SITE_DEFAUT };
	let siteSaving = false;
	$: siteManagerUsers = utilisateurs.filter((u) => !!u.email && aRole(u, 'admin'));
	let erreurParametrage = '';
	//  🔴 Un onglet de réglage ne se monte qu'une fois le paramétrage LU (#1842) :
	//  ses composants lisent leurs valeurs à leur montage, et un formulaire monté
	//  sur les défauts écraserait la configuration en l'enregistrant (#1459).
	//  Les files de « À traiter » ne l'attendent plus, ces onglets-là l'attendent.
	let parametrageLu = false;
	//  Le constat et les champs des textes légaux, pour l'onglet « Pages légales ».
	let textesLegaux: TextesLegauxSource | null = null;
	//  🔴 Une SECTION à la fois (#2057) : chaque bouton n'envoie que les clés de
	//  sa section — quatre boutons en renvoyaient vingt, et un onglet resté ouvert
	//  réécrivait ce qu'un autre venait de changer.
	async function saveSiteConfig(section: SectionSite) {
		siteSaving = true;
		try {
			//  🔴 Le MÊME payload part à l'API et rafraîchit le store. Les deux étaient
			//  écrits séparément, et le second oubliait quatre réglages : après
			//  sauvegarde, le store gardait leurs anciennes valeurs jusqu'au
			//  rechargement de la page (#515).
			const payload = ecrireConfigSite(siteConfig, section);
			await configApi.save(payload);
			configStore.update((c: Record<string, string>) => ({ ...c, ...payload }));
			toast('success', 'Paramètres sauvegardés.');
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur lors de la sauvegarde.'));
		} finally {
			siteSaving = false;
		}
	}

	// ── WhatsApp ──────────────────────────────────
	//  L'onglet est un composant à part (`OngletWhatsApp.svelte`) : il porte son
	//  état, ses appels et son rendu. Ne restent ici que les deux valeurs que la
	//  page a déjà chargées et lui transmet.
	let waCfgPublique: Record<string, string> = {};

	// ── SMTP ────────────────────────────────────────────────────
	// L'onglet vit dans `OngletSmtp.svelte` ; la page ne garde que les valeurs
	// brutes qu'elle a lues, et lui laisse leur interprétation.
	let smtpValeurs: Record<string, string> = {};

	// ── Services ────────────────────────────────────────────────
	//  Une bascule dans « Services » écrit la clé que les onglets de réglages
	//  lisent dans ces deux objets à leur montage : sans ce report, l'onglet IA ou
	//  WhatsApp rouvert réenregistrerait l'ancienne valeur (#1718).
	function apresBascule(cle: string, valeur: string) {
		smtpValeurs = { ...smtpValeurs, [cle]: valeur };
		waCfgPublique = { ...waCfgPublique, [cle]: valeur };
		services = services.map((s) =>
			s.cle_actif === cle ? { ...s, etat: valeur === '1' ? 'actif' : 'coupe' } : s,
		);
	}
	//  L'onglet de réglages d'un service coupé se GRISE, sans se masquer : on y
	//  règle la clé d'API ou le relais avant d'activer. Seuls les onglets qui ne
	//  portent que leur service (`onglet_dedie`, déclaré par le registre).
	let services: ServiceCopropriete[] = [];
	$: ongletsEteints = services
		.filter((s) => s.onglet_dedie && s.etat === 'coupe')
		.map((s) => s.onglet);

	import {
		getPageConfig,
		configStore,
		siteNomStore,
		loadSiteConfig,
	} from '#lib/stores/pageConfig.ts';
	$: _pc = getPageConfig($configStore, 'admin', defautsDePage('admin'));
	$: _siteNom = $siteNomStore;
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage
	titre={_pc.titre}
	descriptif={_pc.descriptif}
	icone={_pc.icone || 'sliders-horizontal'}
/>
<ChargementPartiel
	erreur={messagePartiel(erreurParametrage, erreurBatiments)}
	consequence={erreurParametrage
		? 'Les onglets de paramétrage restent fermés : enregistrés vides, ils effaceraient la configuration.'
		: 'Les numéros de bâtiment peuvent manquer dans les listes.'}
/>

<!--  Les deux rangées — les six groupes, puis les onglets du groupe actif
      (#2062) — sont rendues par `BarreOnglets` depuis la table (`groupe`), avec
      le descriptif de l'onglet actif dessous, comme sur toutes les pages. -->
<BarreOnglets
	pageId="admin"
	actif={onglet}
	{masques}
	comptes={{ a_traiter: comptes.length + commandes.length + demandesProfil.length }}
	eteints={ongletsEteints}
/>
<PorteeOnglet {onglet} />

{#if onglet === 'a_traiter'}
	<OngletATraiter
		bind:comptes
		{comptesLoading}
		{erreurComptes}
		bind:commandes
		{commandesLoading}
		{erreurCommandes}
		bind:demandesProfil
		{demandesProfilLoading}
		{erreurDemandesProfil}
		{batimentsMap}
	/>
{:else if onglet === 'utilisateurs'}
	<ChargementDiffere charger={() => import('#lib/components/OngletUtilisateurs.svelte')}>
		{#snippet contenu(OngletUtilisateurs)}
			<OngletUtilisateurs
				bind:utilisateurs
				chargement={utilisateursLoading}
				erreur={erreurUtilisateurs}
				{batimentsList}
				{batimentsMap}
				recharger={loadUtilisateurs}
			/>
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'maintenance'}
	<ChargementDiffere charger={() => import('#lib/components/OngletMaintenance.svelte')}>
		{#snippet contenu(OngletMaintenance)}
			<OngletMaintenance />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'installation'}
	<ChargementDiffere charger={() => import('#lib/components/CarteInstallation.svelte')}>
		{#snippet contenu(CarteInstallation)}
			<CarteInstallation />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'installations'}
	<ChargementDiffere charger={() => import('#lib/components/OngletInstallations.svelte')}>
		{#snippet contenu(OngletInstallations)}
			<OngletInstallations />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'emails'}
	<ChargementDiffere charger={() => import('#lib/components/OngletModelesEmail.svelte')}>
		{#snippet contenu(OngletModelesEmail)}
			<OngletModelesEmail />
		{/snippet}
	</ChargementDiffere>
{:else if !parametrageLu && ONGLETS_DU_PARAMETRAGE.includes(onglet)}
	<EtatListe chargement />
{:else if erreurParametrage && ONGLETS_DU_PARAMETRAGE.includes(onglet)}
	<EtatListe erreur={erreurParametrage} titreErreur={TITRE_PARAMETRAGE_ILLISIBLE} />
{:else if onglet === 'services'}
	<ChargementDiffere charger={() => import('#lib/components/OngletServices.svelte')}>
		{#snippet contenu(OngletServices)}
			<OngletServices {apresBascule} />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'fonctionnement'}
	<ChargementDiffere charger={() => import('#lib/components/OngletFonctionnement.svelte')}>
		{#snippet contenu(OngletFonctionnement)}
			<OngletFonctionnement bind:siteConfig {siteSaving} {siteManagerUsers} {saveSiteConfig} />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'connexion'}
	<ChargementDiffere charger={() => import('#lib/components/OngletConnexion.svelte')}>
		{#snippet contenu(OngletConnexion)}
			<OngletConnexion bind:siteConfig {siteSaving} {saveSiteConfig} />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'pages'}
	<ChargementDiffere charger={() => import('#lib/components/OngletDescriptifPages.svelte')}>
		{#snippet contenu(OngletDescriptifPages)}
			<OngletDescriptifPages valeurs={smtpValeurs} />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'legal'}
	{#if textesLegaux}
		{@const source = textesLegaux}
		<ChargementDiffere charger={() => import('#lib/components/OngletLegal.svelte')}>
			{#snippet contenu(OngletLegal)}
				<OngletLegal
					bind:siteConfig
					{siteSaving}
					saveSiteConfig={() => saveSiteConfig('legal')}
					constat={source.etat}
					champs={source.champs}
				/>
			{/snippet}
		</ChargementDiffere>
	{/if}
{:else if onglet === 'whatsapp'}
	<ChargementDiffere charger={() => import('#lib/components/OngletWhatsApp.svelte')}>
		{#snippet contenu(OngletWhatsApp)}
			<OngletWhatsApp
				cfgPublique={waCfgPublique}
				bind:footer={siteConfig.whatsapp_footer}
				footerSaving={siteSaving}
				onSaveFooter={() => saveSiteConfig('pied_whatsapp')}
			/>
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'smtp'}
	<ChargementDiffere charger={() => import('#lib/components/OngletSmtp.svelte')}>
		{#snippet contenu(OngletSmtp)}
			<OngletSmtp bind:emailFooter={siteConfig.email_footer} valeurs={smtpValeurs} />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'ia'}
	<!--  Les mêmes valeurs que le SMTP : c'est `adminCfg`, la configuration
	      complète lue une fois au chargement. Un second appel pour les mêmes
	      clés donnerait deux vérités à quelques millisecondes d'écart. -->
	<ChargementDiffere charger={() => import('#lib/components/OngletIA.svelte')}>
		{#snippet contenu(OngletIA)}
			<OngletIA valeurs={smtpValeurs} />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'telemetry'}
	<ChargementDiffere charger={() => import('#lib/components/OngletTelemetrie.svelte')}>
		{#snippet contenu(OngletTelemetrie)}
			<OngletTelemetrie />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'copropriete'}
	<ChargementDiffere charger={() => import('#lib/components/OngletCopropriete.svelte')}>
		{#snippet contenu(OngletCopropriete)}
			<OngletCopropriete
				bind:referenceCopro={siteConfig.reference_copro}
				urlPublique={siteConfig.url}
			/>
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'perimetres'}
	<ChargementDiffere charger={() => import('#lib/components/OngletPerimetres.svelte')}>
		{#snippet contenu(OngletPerimetres)}
			<OngletPerimetres />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'lots'}
	<ChargementDiffere charger={() => import('#lib/components/OngletLots.svelte')}>
		{#snippet contenu(OngletLots)}
			<OngletLots />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'audit_lots'}
	<ChargementDiffere charger={() => import('#lib/components/OngletAuditLots.svelte')}>
		{#snippet contenu(OngletAuditLots)}
			<OngletAuditLots />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'imports'}
	<ChargementDiffere charger={() => import('#lib/components/OngletImports.svelte')}>
		{#snippet contenu(OngletImports)}
			<OngletImports />
		{/snippet}
	</ChargementDiffere>
{/if}

<style>
	/* `.sticky-head`, `.config-section`, `.config-section-title` et `.muted` sont
   passées dans `app.css` le 11/08/2026 : scopées ici, elles ne suivaient pas les
   composants extraits de cette page. (`.backup-header` y était aussi, et en est
   repartie avec les deux cartes qui l'utilisaient — #299.) */
	/*  `.tabs` et `.tab-btn` sont dans `app.css` : partagées avec
    `LiensEcransAdmin.svelte`, elles ne peuvent pas vivre dans un style scopé. */
	/*  `.badge-count` est parti avec le balisage, dans `Onglet.svelte` : une règle
    laissée ici ne s'appliquerait plus (Svelte scope au fichier) et tromperait le
    prochain lecteur — c'est la régression du 14/08, deux fois répétée. */
	/*  🔴 `.refus-inline` est partie le 07/09/2026 avec le balisage qu'elle
	    habillait : `AccepterRefuser.svelte` porte le geste « accepter · refuser
	    avec motif », qui était écrit TROIS fois ici. `.input-sm` est montée dans
	    la charte — la page l'emploie encore trois fois, le composant une, et
	    deux écritures d'une même règle divergent au premier ajustement. */
	/*  `code` et `.intro-texte` sont partis avec l'onglet « Pages légales », leur
	    seul usage (`OngletLegal.svelte`, #2065). */
	/*  🔴 `.badge-orange` et `.badge-purple` retirees le 28/08/2026 (#607) :
    la charte les porte, et cet ecran en donnait une TROISIEME teinte —
    `delegations` en avait une deuxieme. Meme notion, trois couleurs. */
</style>
