//  L'ADMINISTRATION : comptes et validations, délégations d'aidant, réglages du
//  site. Ce que seuls l'administrateur et le conseil syndical appellent.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '$lib/api'` du front ne changent pas d'une ligne.
import { api, BASE, buildQuery, postFormData } from './client';
import type { ConsommationIA, UsageIA } from './assistant';
import type { ServiceCopropriete } from './services';
import type { FiltreGestionnaire, PorteeTelemetrie, TableauTelemetrie } from './telemetrie';
import type { User } from './types';
import type { ConstatTextesLegaux, TextesLegauxSource } from './textes-legaux';
import type {
	AccueilArrivantResultat,
	Accuse,
	AutoMatchRelance,
	BailSansLocataire,
	CommandeAccesEnAttente,
	CompositionConseil,
	CompteEnAttenteEnrichi,
	CompteTraite,
	ConfigSauvegarde,
	Delegation,
	DemandeProfil,
	EnvoiEmail,
	EssaiImap,
	EssaiSmtp,
	EssaiWhatsApp,
	ExecutionMaintenance,
	ExecutionSauvegarde,
	ExecutionTache,
	ExecutionTelemetrie,
	InfoSyndicAdmin,
	LancementTache,
	LienCompteLot,
	ModeleEmail,
	ReleveReclassement,
	SanteMaintenance,
	StatutWhatsApp,
	UtilisateurAdmin,
} from './types-administration';

//  Les types de ce que ces routes RENDENT vivent à côté (#1572) : réexportés ici,
//  ils parviennent à `index.ts`, donc à tout `from '$lib/api'`.
export type * from './types-administration';

export const annuaireAdmin = {
	getCS: () => api.get<CompositionConseil>('/admin/annuaire/cs'),
	putCS: (data: unknown) => api.put<Accuse>('/admin/annuaire/cs', data),
	getSyndic: () => api.get<InfoSyndicAdmin>('/admin/annuaire/syndic'),
	putSyndic: (data: unknown) => api.put<Accuse>('/admin/annuaire/syndic', data),
};

export const delegations = {
	list: () => api.get<Delegation[]>('/delegations'),
	create: (data: { mandant_id: number; aidant_id: number; motif?: string; date_fin?: string }) =>
		api.post<Delegation>('/delegations', data),
	//  🔴 `update` A ÉTÉ RETIRÉE le 13/09/2026, avec son endpoint
	//  `PATCH /delegations/{id}` (#934). La question posée était « corriger le
	//  motif ou la date de fin d'une délégation existante est-il un besoin
	//  réel ? » ; la réponse a été **non**.
	//
	//  L'argument qui plaidait pour la garder — révoquer puis recréer impose une
	//  ré-acceptation par l'aidant — reste vrai, mais il décrit un inconfort dans
	//  un cas qui ne se produit pas. Un endpoint d'écriture que rien n'appelle
	//  est une surface, pas une capacité ; et celui-ci passait par
	//  `require_cs_or_admin`, c'est-à-dire qu'un membre du CS pouvait réécrire le
	//  motif d'une délégation entre deux tiers.
	//
	//  L'historique git le rend en une commande le jour où le besoin se
	//  manifeste — et ce jour-là il faudra aussi décider QUI a le droit de
	//  corriger, ce que la version retirée ne tranchait pas.
	accepter: (id: number) => api.post<Delegation>(`/delegations/${id}/accepter`),
	revoquer: (id: number) => api.post<Delegation>(`/delegations/${id}/revoquer`),
	//  🔴 `mesMandants` A ÉTÉ RETIRÉE (#801) : le front lit
	//  `$currentUser.delegations_aidant`, qui arrive avec l'utilisateur — c'est
	//  ce que `Nav.svelte` emploie pour montrer l'entrée « Délégations » à un
	//  aidant (le sélecteur « agir au nom de » a été retiré, #1534).
	//  L'endpoint reste ; la seconde voie de lecture disparaît.
};

export const admin = {
	// Comptes
	comptesEnAttente: () => api.get<User[]>('/admin/comptes-en-attente'),
	//  🔴 `pendingAccounts` A ÉTÉ SUPPRIMÉE ICI le 06/09/2026 (#801) : même route,
	//  même corps, même retour que `comptesEnAttente` juste au-dessus — un doublon
	//  exact, à une ligne d'écart, dans un fichier qu'on relit rarement en entier.
	//  Elle figurait au relevé des « clients sans appelant » ; le tri a montré
	//  qu'elle n'était ni un manque ni une avance, mais une COPIE. Elle était aussi
	//  la seule des deux dont le nom fût en anglais.
	traiterCompte: (id: number, data: { action: string; motif?: string }) =>
		//  🔴 Le retour est TYPÉ, et c'est le fond du sujet : sans argument de type,
		//  `api.post` rend `{}`, et l'écran qui lit `res.auto_match.…` ne compile
		//  pas. C'est exactement ce qui l'avait fait réécrire l'appel en dur avec
		//  son propre `<any>` — une méthode trop pauvre ne fait pas contourner un
		//  peu, elle fait recopier la route en entier (#801). Le `<any>` posé alors
		//  ici est devenu `CompteTraite`, lu dans `traiter_compte` (#1572).
		api.post<CompteTraite>(`/admin/comptes/${id}/traiter`, data),
	// Commandes accès
	commandesAccesEnAttente: () => api.get<CommandeAccesEnAttente[]>('/admin/commandes-acces'),
	traiterCommandeAcces: (
		id: number,
		data: { action: string; motif_refus?: string; codes?: string[] },
	) => api.post(`/admin/commandes-acces/${id}/traiter`, data),
	// Sauvegardes
	backupConfig: () => api.get<ConfigSauvegarde | null>('/admin/sauvegardes/config'),
	//  L'API n'écrit que ces deux réglages (#2055) : la sauvegarde est quotidienne.
	updateBackupConfig: (
		data: Pick<ConfigSauvegarde, 'heure_execution' | 'nb_versions_conservees'>,
	) => api.put<ConfigSauvegarde>('/admin/sauvegardes/config', data),
	//  Rejoue MAINTENANT les contrôles du job de 06:00, et rend leurs verdicts
	//  (#852). Aucun e-mail n'est envoyé : quelqu'un est devant l'écran.
	relancerControleSante: () =>
		api.post<{ nb: number; problemes: { titre: string; details: string[] }[] }>(
			'/admin/controle-sante',
		),
	// Modèles e-mail
	emailTemplates: () => api.get<ModeleEmail[]>('/admin/modeles-email'),
	//  L'historique des envois — il manquait au client, et l'écran l'appelait en
	//  dur juste à côté de `emailTemplates` (#801). Deux routes du même écran, une
	//  déclarée et l'autre non : c'est ainsi qu'un client se vide de son sens.
	emailsHistorique: () => api.get<EnvoiEmail[]>('/admin/emails/historique'),
	//  Rend le modèle tel que la liste le lit — variables CALCULÉES (#1682).
	updateEmailTemplate: (
		id: number,
		data: Partial<Pick<ModeleEmail, 'sujet' | 'corps_html' | 'actif' | 'intention'>>,
	) => api.patch<ModeleEmail>(`/admin/modeles-email/${id}`, data),
	//  Un SEUL modèle remis au texte du code (#852). Il n'existait que la
	//  remise à zéro globale : réparer un modèle cassé d'un caractère imposait
	//  de détruire les textes choisis pour tous les autres — un remède qu'on
	//  n'applique pas, et le défaut restait donc en place.
	resetEmailTemplate: (id: number) =>
		api.post<ModeleEmail>(`/admin/modeles-email/${id}/reinitialiser`),
	resetEmailTemplates: () => api.post<{ message: string }>('/admin/modeles-email/reinitialiser'),
	// Utilisateurs & rôles
	utilisateurs: () => api.get<UtilisateurAdmin[]>('/admin/utilisateurs'),
	//  🔴 Les deux rendent l'utilisateur MIS À JOUR, et le type le dit depuis le
	//  06/09/2026 (#801). Sans argument de type, `api.post` rend `{}` : l'écran
	//  qui fait `{ ...u, ...updated }` ne compilait pas, et il a donc réécrit
	//  l'appel en dur — avec son propre `<any>` et une URL construite dans un
	//  ternaire, invisible à toute recherche par route. Une méthode trop pauvre
	//  ne fait pas contourner un peu : elle fait recopier la route en entier.
	//
	//  ⚠️ Elles étaient TROIS. `changerRole` a été supprimée le même jour, client
	//  ET endpoint : elle « remplaçait tous les rôles par un seul », donnée pour
	//  de la « compatibilité ascendante » — avec rien, aucun appelant nulle part.
	//  Le produit a des rôles MULTIPLES ; ces deux gestes-ci sont les vrais.
	ajouterRole: (id: number, role: string) =>
		api.post<User>(`/admin/utilisateurs/${id}/ajouter-role`, { role }),
	retirerRole: (id: number, role: string) =>
		api.post<User>(`/admin/utilisateurs/${id}/retirer-role`, { role }),
	// Demandes de modification de profil
	demandesProfil: () => api.get<DemandeProfil[]>('/admin/demandes-profil'),
	//  ⚠️ `motif_refus` accepte `null` et pas seulement `undefined` : l'écran
	//  envoie `refusDemande[id] || null`, donc un null EXPLICITE. Resserrer le
	//  type aurait obligé l'écran à changer ce qu'il transmet — le client suit le
	//  contrat réel, il ne le réécrit pas (#801).
	traiterDemandeProfil: (id: number, data: { action: string; motif_refus?: string | null }) =>
		api.post(`/admin/demandes-profil/${id}/traiter`, data),
	//  🔴 `baux` ET `lierLocataire` ONT ÉTÉ RETIRÉES le 13/09/2026 (#808), avec
	//  leurs endpoints. L'arbitrage du 06/09 était « garder et observer » ; le
	//  relevé livré le 07/09 a observé, et a répondu : **tous les baux en cours
	//  ont leur locataire rattaché**. Le cas ne s'est jamais présenté.
	//
	//  ⚠️ Le relevé reste (`bauxSansLocataire`, plus bas) : c'est lui qui
	//  surveille, et c'est ce qui permettra de rouvrir sur un fait.
	// Audit associations user-lot
	auditUserLots: () => api.get<LienCompteLot[]>('/admin/audit/user-lots'),
	/**
	 *  Les baux en cours dont AUCUN compte locataire n'est rattaché (#808).
	 *
	 *  Le rattachement est automatique, sur l'e-mail exact du bail — il échoue en
	 *  silence quand le locataire s'inscrit avec une autre adresse, ou quand le
	 *  bail est créé après son inscription. Ce relevé est le moyen de le voir.
	 *
	 *  ⚠️ La CATÉGORIE (`compte_probable` / `sans_compte`) vient du serveur, pas
	 *  de l'écran : la recalculer côté client en ferait une seconde règle, et deux
	 *  vues du même relevé pourraient ranger le même bail dans deux cases.
	 */
	bauxSansLocataire: () => api.get<BailSansLocataire[]>('/admin/audit/baux-sans-locataire'),
	/**
	 *  Les tickets dont la catégorie pourrait être plus juste — PROPOSITION SEULE.
	 *
	 *  🔴 Rien n'est écrit par cet appel. Quatre catégories sont nées le
	 *  07/09/2026 et une a disparu : les tickets déjà ouverts portent donc des
	 *  catégories choisies dans une liste qui n'existe plus telle quelle.
	 *
	 *  ⚠️ La PROPOSITION et la CONFIANCE viennent du serveur, pas de l'écran —
	 *  même raison que ci-dessus : les recalculer ici en ferait une seconde
	 *  règle, et deux vues du même relevé proposeraient deux catégories.
	 */
	reclassementTickets: () => api.get<ReleveReclassement>('/admin/audit/reclassement-tickets'),
	supprimerUserLot: (id: number) => api.delete(`/admin/user-lots/${id}`),
	// Télémétrie
	//  🔴 `scope` a été AJOUTÉ ici plutôt que dans l'écran (#801) : `OngletTelemetrie`
	//  écrivait `/telemetry/dashboard?scope=${…}` en dur parce que la méthode ne
	//  savait pas le porter. Une méthode trop pauvre ne fait pas contourner un peu,
	//  elle fait recopier la route en entier — et la route recopiée ne suit plus.
	telemetryDashboard: (scope?: PorteeTelemetrie, gestionnaire?: FiltreGestionnaire) =>
		api.get<TableauTelemetrie>(`/telemetry/dashboard${buildQuery({ scope, gestionnaire })}`),
	//  🔴 `telemetryUsersActive` A ÉTÉ RETIRÉE (#801) : le tableau de bord de
	//  télémétrie porte déjà `kpi.utilisateurs` et `kpi.moy_utilisateurs_jour`,
	//  servis par `telemetryDashboard()` en une requête. L'endpoint
	//  `GET /telemetry/users-active` reste — il rend la LISTE, pas le compte, et
	//  c'est un écran qui n'existe pas encore.
	//  @sans-appelant-direct Appelées depuis CE module par `lancerTache()` et
	//  `historiqueTache()`, jamais depuis un écran. Le relevé les compte comme
	//  orphelines parce qu'il ne regarde que les appels HORS de `lib/api/` — et
	//  c'est volontaire : un client qui ne s'appelle que lui-même serait
	//  précisément le cas à signaler. Ici les deux tables de routes ont rejoint
	//  ce module (#801), et l'appelant réel est `TachesPlanifiees`.
	telemetryAgreger: () => api.post('/admin/telemetry/agreger'),
	telemetryHistorique: () => api.get<ExecutionTelemetrie[]>('/admin/telemetry/historique'), //  @sans-appelant-direct idem

	//  ── Gestes sur un utilisateur — ajoutés le 06/09/2026 (#801) ───────────────
	//
	//  Les six vivaient EN DUR dans `admin/+page.svelte`, et l'un d'eux —
	//  `accueilArrivant` — était recopié à l'identique dans `espace-cs`. Deux
	//  écrans, une route, aucun lien entre eux : le jour où elle change, l'un des
	//  deux suit et l'autre part en 404 sans que rien ne lève.
	modifierUtilisateur: (id: number, data: unknown) =>
		api.patch<User>(`/admin/utilisateurs/${id}`, data),
	supprimerUtilisateur: (id: number) => api.delete(`/admin/utilisateurs/${id}`),
	autoMatchUtilisateur: (id: number) =>
		api.post<AutoMatchRelance>(`/admin/utilisateurs/${id}/auto-match`),
	/**
	 *  Les actions d'accueil d'un nouvel arrivant — bienvenue, consignes,
	 *  demandes au syndic et au CS.
	 *
	 *  🔴 Cet appel était écrit TROIS fois, avec le même corps : deux dans
	 *  `admin/+page.svelte` (validation de compte, puis geste d'accueil isolé) et
	 *  une dans `espace-cs`. Trois copies d'un envoi qui déclenche des e-mails —
	 *  ajouter un champ au corps en aurait laissé deux en arrière, et rien
	 *  n'aurait levé : le message serait simplement parti incomplet.
	 */
	accueilArrivant: (
		id: number,
		data: { batiment?: string | null; ancien_resident?: string | null },
	) => api.post<AccueilArrivantResultat>(`/admin/utilisateurs/${id}/accueil-arrivant`, data),
	/**  L'adresse de la fiche des consignes (PDF), pour un lien — seul
	 *   `LienConsignes` la rend (#1578 ; `lint:lien-consignes`). */
	ficheArrivantUrl: (): string => `${BASE}/admin/fiche-arrivant`,
	banCommunaute: (id: number, data: unknown) =>
		api.patch<User>(`/admin/utilisateurs/${id}/ban-communaute`, data),
	//  ⚠️ Route DISTINCTE de `comptesEnAttente` : `/enrichis` rend les mêmes
	//  comptes avec le rapprochement de lots déjà calculé. Deux endpoints, deux
	//  méthodes — les confondre sous un drapeau donnerait une méthode dont le
	//  retour change de forme selon l'argument.
	comptesEnAttenteEnrichis: () =>
		api.get<CompteEnAttenteEnrichi[]>('/admin/comptes-en-attente/enrichis'),

	/** L'état des tâches planifiées — lu par `TachesPlanifiees`. */
	santeMaintenance: () => api.get<SanteMaintenance>('/admin/maintenance/sante'),

	/**
	 *  L'historique d'une tâche planifiée.
	 *
	 *  🔴 Deux tâches ont leur PROPRE table d'historique, les autres partagent
	 *  celle de la maintenance : c'est le repli ci-dessous, et il vivait dans
	 *  l'écran sous forme d'une table `SOURCE` de routes littérales. Deux de ces
	 *  routes — `/admin/telemetry/historique` et `/admin/telemetry/agreger` —
	 *  étaient DÉJÀ déclarées ici et figuraient au relevé des méthodes « sans
	 *  appelant » (#801). Elles en avaient un ; il passait par une table, donc
	 *  aucune recherche par nom de méthode ne pouvait le voir.
	 *
	 *  ⚠️ Une route rangée dans une table de l'écran reste une route recopiée.
	 *  C'est la forme la plus discrète du contournement, et la plus difficile à
	 *  relever — elle ne ressemble plus à un appel.
	 */
	historiqueTache: (tache: string, limite = 10) => {
		const propre: Record<string, () => Promise<ExecutionTache[]>> = {
			backup: () => api.get<ExecutionSauvegarde[]>('/admin/sauvegardes/historique'),
			telemetrie: () => api.get<ExecutionTelemetrie[]>('/admin/telemetry/historique'),
		};
		return (
			propre[tache]?.() ??
			api.get<ExecutionMaintenance[]>(
				`/admin/maintenance/historique${buildQuery({ tache, limite: String(limite) })}`,
			)
		);
	},

	/**
	 *  Les derniers comptes rendus de `check-reliability.sh` (C1 à C30), tous
	 *  nœuds confondus — lus par `ControlesFiabilite`. Même route que
	 *  `historiqueTache`, mais TYPÉE : l'écran lit `details.constats`, et un
	 *  `any` retypé dans l'écran est ce que `lint:types-locaux` refuse.
	 */
	controlesFiabilite: () =>
		api.get<RapportFiabilite[]>(
			`/admin/maintenance/historique${buildQuery({ tache: 'reliability', limite: '20' })}`,
		),

	/**
	 *  Lance une tâche planifiée à la demande. Rend un 202 : c'est la PRISE EN
	 *  COMPTE qui est confirmée, pas l'exécution.
	 *
	 *  ⚠️ `maintenance` n'exécute PAS `maintenance.sh` — seulement
	 *  `run_maintenance` dans le process de l'API (purges + VACUUM), sur le seul
	 *  nœud qui répond. L'hygiène locale du standby n'est déclenchée par personne
	 *  ici ; l'écran le dit à l'utilisateur, et ce commentaire le rappelle à qui
	 *  ajouterait un appelant.
	 *
	 *  Rend `null` pour une tâche qui ne se lance pas à la main — l'écran ne
	 *  montre alors aucun bouton.
	 */
	lancerTache: (tache: string): Promise<LancementTache> | null => {
		const route = ROUTES_LANCEMENT[tache];
		return route ? api.post<LancementTache>(route) : null;
	},
	/**
	 *  « Cette tâche se lance-t-elle à la main ? » — l'écran y conditionne son
	 *  bouton.
	 *
	 *  ⚠️ Elle interroge `ROUTES_LANCEMENT`, elle ne REDIT pas la liste : une
	 *  seconde énumération des mêmes clés se désaccorderait de la première au
	 *  premier ajout, et l'écran afficherait un bouton qui ne lance rien — ou
	 *  masquerait une tâche qui se lance.
	 */
	tacheLancable: (tache: string) => tache in ROUTES_LANCEMENT,
};

/**  Les tâches qu'on peut déclencher à la demande, et par quelle route. Table
 *   déplacée de `TachesPlanifiees.svelte` le 06/09/2026 (#801) : une table de
 *   routes est un morceau de client, où qu'elle soit écrite. */
const ROUTES_LANCEMENT: Record<string, string> = {
	maintenance: '/admin/maintenance/lancer',
	backup: '/admin/sauvegardes/maintenant',
	telemetrie: '/admin/telemetry/agreger',
};

/**  Un message WhatsApp planifié (`GET /config/whatsapp-scheduled`). */
export interface MessagePlanifieWhatsApp {
	id: number;
	label: string;
	message: string;
	cron_rule: string;
	enabled: boolean;
	mis_a_jour_le: string | null;
}

/**  Un envoi WhatsApp journalisé (`GET /config/whatsapp-logs`). */
export interface JournalEnvoiWhatsApp {
	id: number;
	/** Le « Nom du canal » réglé dans Admin › WhatsApp, vide s'il n'est pas renseigné. */
	canal: string;
	label: string;
	message: string;
	statut: string;
	erreur: string | null;
	envoye_le: string | null;
}

export const config = {
	//  ⚠️ Appelée par `loadSiteConfig()` (`stores/pageConfig`), qui écrivait
	//  `fetch('/api/config')` en dur jusqu'au 12/09/2026 — un contournement du
	//  client que `lint:client-api` ne voyait pas (il ne lit pas les stores) et
	//  que `lint:client-appele` ne voyait pas non plus (`config.get` passait pour
	//  appelée grâce aux neuf autres `.get` du client). Deux angles morts, et
	//  la méthode entre les deux (#932).
	get: (): Promise<Record<string, string>> => api.get<Record<string, string>>('/config'),
	/**  Les deux textes légaux — mentions légales et politique de confidentialité.
	 *
	 *   🔴 Ils sont EXCLUS de `/config` à dessein (ce sont deux longs HTML, servis
	 *   à chaque chargement de page sinon), d'où une route à part. Elle était
	 *   écrite **trois fois en dur** — `mentions-legales`, `politique-de-confidentialite`
	 *   et l'administration — chacune avec son `try`/`catch` muet, parce que le
	 *   client n'offrait rien (12/09/2026, #932). */
	legal: (): Promise<Record<string, string>> => api.get<Record<string, string>>('/config/legal'),
	save: (data: Record<string, string>): Promise<void> => api.put('/config', data),
	/**  Les textes légaux tels que l'administration les édite : la source, et non le
	 *   rendu de `legal()`, qui figerait les noms d'aujourd'hui à la place des champs
	 *   (#2065). Réservé à l'administrateur. */
	textesLegaux: () => api.get<TextesLegauxSource>('/config/textes-legaux'),
	/**  « J'ai relu ces textes » : refusé (409) tant que l'un dit « À RENSEIGNER ». */
	declarerRelus: () => api.post<ConstatTextesLegaux>('/config/textes-legaux/relecture', {}),

	//  ── Réglages d'administration et bancs d'essai (#801) ──────────────────────
	//
	//  Sept routes que trois écrans écrivaient en dur. Elles rejoignent `config`
	//  parce que c'est ce qu'elles sont — la configuration du site et les essais
	//  qui la valident — et non un objet `whatsapp` de plus : un objet par écran
	//  redonnerait le découpage que le client existe pour éviter.
	admin: (): Promise<Record<string, string>> => api.get<Record<string, string>>('/config/admin'),
	testerSmtp: (email: string) => api.post<EssaiSmtp>('/config/smtp-test', { email }),
	testerImap: () => api.post<EssaiImap>('/config/imap-test', {}),
	/**  Interroge VRAIMENT le modèle configuré (`utils/llm.tester`). Trois champs
	 *   remplis ne prouvent rien : une clé se révoque, un modèle se renomme. */
	llmTest: (usage: string) =>
		api.post<{
			ok: boolean;
			usage: string;
			fournisseur: string;
			modele: string;
			reponse: string;
			duree_ms: number;
		}>(`/config/llm-test?usage=${encodeURIComponent(usage)}`, {}),
	/**  Les USAGES de l'assistant — la SEULE liste (#984) : l'écran rend un bloc
	 *   par entrée. Les valeurs courantes, elles, viennent de `admin()`. */
	llmUsages: () => api.get<UsageIA[]>('/config/llm-usages'),
	/**  Les services de la copropriété et leur état — la SEULE liste (#1718).
	 *   Un interrupteur s'écrit par `save({ [cle_actif]: '1' | '0' })`. */
	services: () => api.get<ServiceCopropriete[]>('/config/services'),
	/**  Ce que l'assistant a consommé, par mois, usage et modèle — lu par
	 *   `ConsommationIA`, dans l'onglet Maintenance (#1383). */
	llmConsommation: () => api.get<ConsommationIA>('/config/llm-consommation'),
	/**  Les modèles que la clé enregistrée peut RÉELLEMENT appeler, demandés au
	 *   fournisseur. `listable: false` n'est pas une erreur : Azure n'expose pas
	 *   ses déploiements, et une clé peut synthétiser sans avoir le droit de
	 *   s'inventorier. L'écran retombe alors sur la saisie libre, en disant
	 *   pourquoi (`motif`). */
	llmModeles: () =>
		api.get<{
			listable: boolean;
			motif: string;
			modeles: { id: string; libelle: string }[];
		}>('/config/llm-modeles'),

	whatsappStatut: () => api.get<StatutWhatsApp>('/config/whatsapp-status'),
	/**  L'image du QR code d'appairage, pour un `<img>`. `horodatage` change
	 *   l'adresse à chaque rafraîchissement : sans lui, le navigateur
	 *   resservirait le QR expiré de son cache (#1578). */
	whatsappQrUrl: (horodatage: number): string => `${BASE}/config/whatsapp-qr?t=${horodatage}`,
	whatsappJournaux: () => api.get<JournalEnvoiWhatsApp[]>('/config/whatsapp-logs'),
	whatsappPlanifies: () => api.get<MessagePlanifieWhatsApp[]>('/config/whatsapp-scheduled'),
	modifierWhatsappPlanifie: (id: number, data: unknown) =>
		api.put<Accuse>(`/config/whatsapp-scheduled/${id}`, data),
	testerWhatsapp: (message: string) =>
		api.post<EssaiWhatsApp>('/config/whatsapp-test', { message }),

	/**  Le logo de la résidence (#1728), servi PUBLIQUEMENT — le logo neutre s'il
	 *   n'y en a pas. `version` (le nom du fichier, clé `site_logo`) change
	 *   l'adresse quand le logo change : sans elle, le navigateur garderait l'ancien. */
	logoUrl: (taille: number, version?: string | null): string =>
		`${BASE}/config/logo.png?taille=${taille}${version ? `&v=${encodeURIComponent(version)}` : ''}`,
	televerserLogo: (fichier: File) =>
		postFormData<{ site_logo: string }>('/config/logo', { file: fichier }),
	supprimerLogo: () => api.delete<{ site_logo: null }>('/config/logo'),
};

/**
 *  Un compte rendu des contrôles de fiabilité (`check-reliability.sh`).
 *
 *  Il n'arrive que quand l'ensemble des constats CHANGE, et au moins une fois
 *  par jour (`lib-notification.sh`) : le plus récent d'un nœud est donc son
 *  état courant, pas un instantané d'il y a un quart d'heure.
 */
export interface RapportFiabilite {
	id: number;
	noeud: string | null;
	/** `succes` · `avertissement` (des WARN) · `erreur` (au moins un FAIL). */
	statut: string;
	/** Depuis quand ces constats tiennent : l'heure du dernier CHANGEMENT. */
	cree_le: string;
	/** Le dernier passage du contrôleur — prolongé à chaque quart d'heure (#1396). */
	terminee_le: string | null;
	details: {
		fail: number;
		warn: number;
		/** Les constats qui ne nomment que CE nœud (depuis #1396 ; tous, avant). */
		constats: string[];
		/** Ceux qui portent sur les deux nœuds — dits par l'actif seul. */
		communs?: string[];
		/** Ce nœud porte-t-il les communs ? Absent d'un rapport d'avant #1396. */
		porte_communs?: boolean;
	} | null;
}
