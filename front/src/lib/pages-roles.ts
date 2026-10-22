/**
 * Les pages réservées à un RÔLE — conseil syndical, délégations, administration.
 *
 * ## Pourquoi un second fichier (12/09/2026, #928)
 *
 * `pages.ts` a franchi son plafond de modularité en recevant l'onglet
 * « Badges & télécommandes ». C'est une TABLE : elle grossit légitimement quand
 * le produit gagne un écran, et la faire maigrir en raccourcissant des
 * descriptifs serait raboter — ce qu'`ux-patterns` §0 interdit.
 *
 * La coupe suit donc ce que les pages SONT : d'un côté celles que tout résident
 * ouvre, de l'autre celles qu'un rôle ouvre. Même geste que `routes-onglets.ts`,
 * qui a quitté `pages.ts` le 05/09 pour la même raison.
 *
 * ⚠️ La table reste UNE : `PAGES` les concatène, et `lint:pages` continue de
 * refuser une route écrite ailleurs. Deux fichiers, une source.
 *
 * ⚠️ `import type` et non `import` : le type vit dans `pages.ts`, qui importe ce
 * fichier-ci. Un import de VALEUR serait circulaire ; un import de TYPE est
 * effacé à la compilation, donc il n'existe pas à l'exécution.
 */
import type { PageDef } from './pages';

export const PAGES_ROLES: PageDef[] = [
	{
		id: 'espace-cs',
		href: '/espace-cs',
		nom: 'Espace CS',
		titre: 'Espace Conseil Syndical (CS)',
		navLabel: 'Espace CS',
		icone: 'shield-half',
		descriptif:
			'Tableau de bord des membres du Conseil Syndical (CS) : suivi des comptes, reporting, relance syndic et demandes d\'accès — réservé au Conseil Syndical. Les affaires de la résidence se traitent depuis la page <a href="/tickets">Affaires</a>.',
		onglets: [
			{
				id: 'validations',
				route: '/espace-cs',
				label: '✅ Comptes & accès',
				descriptif: "Comptes en attente, demandes d'accès et validations à traiter.",
			},
			{
				//  🔴 Onglet DÉDIÉ (12/09/2026) : « Comptes & accès » est une FILE DE
				//  TRAVAIL, dont la valeur est d'être courte ; le parc de badges est un
				//  RÉFÉRENTIEL qu'on consulte. Les mêler ferait cesser de lire la file.
				id: 'badges',
				route: '/espace-cs/badges',
				label: '\u{1F3F7}\uFE0F Badges & télécommandes',
				descriptif:
					'Tous les badges Vigik et télécommandes de la copropriété, avec leur porteur et leur lot. Vue de consultation : un badge s’enregistre par l’import du syndic, ou par son porteur.',
			},
			{
				id: 'reporting',
				route: '/espace-cs/reporting',
				label: '\u{1F4CA} Reporting',
				descriptif:
					'Synthèses et indicateurs du conseil syndical, de l’état des affaires ouvertes aux échéances des contrats — à consulter ou à exporter.',
			},
			{
				id: 'annonces-hall',
				route: '/espace-cs/annonces-hall',
				label: '\u{1F4C4} Annonces Hall',
				descriptif:
					"Créez une annonce à afficher dans le hall des bâtiments : PDF à la charte de la résidence, envoyé par mail aux membres du CS concernés, puis conservé dans l'historique.",
			},
			{
				id: 'annuaire',
				route: '/espace-cs/annuaire',
				label: '\u{1F4D2} Annuaire CS & Syndic',
				descriptif: 'Coordonnées des membres du CS et du syndic.',
			},
			//  « ⚖️ Règlement » a rejoint Ma résidence le 11/10/2026 : il s'ouvre aux
			//  copropriétaires (`pages.ts`). L'ancienne adresse redirige — sa route.
			{
				//  Né le 05/10/2026 d'un transfert refusé (numéro d'affaire mal tapé)
				//  que seul l'administrateur pouvait relire : chaque message reçu à
				//  l'adresse des affaires, avec ce que le site en a fait et pourquoi.
				id: 'courriels',
				route: '/espace-cs/courriels',
				label: '\u{1F4E8} Courriels affaires',
				descriptif:
					"Ce que le site a fait de chaque message reçu à l'adresse des affaires — réponses du syndic, fils transférés par le conseil : ajouté à une affaire, refusé ou ignoré, et pourquoi. Un message refusé se corrige puis se transfère de nouveau.",
			},
		],
	},
	{
		id: 'admin',
		href: '/admin',
		nom: 'Paramétrage',
		titre: 'Paramétrage',
		navLabel: 'Admin',
		icone: 'sliders-horizontal',
		reserveeAdmin: true,
		descriptif:
			'Administration de la plateforme, réservée aux admins : ce qui attend un geste, les utilisateurs et leur activité, la configuration du site et ses référentiels.',
		//  Les onglets de l'administration — déclarés ici depuis le 01/10/2026 pour
		//  être renommés et décrits dans « Descriptif pages » comme ceux des autres
		//  pages. L'adresse reste `?onglet=` (« sauf admin ») ; cette liste fait foi
		//  pour `admin/+page.svelte`, qui n'en tient plus de seconde.
		//
		//  🔴 RANGÉS PAR NIVEAU depuis le 21/10/2026 (#2062, maquette validée) : six
		//  groupes, un par question — qui sont les gens, quoi charger, comment la
		//  copropriété est réglée, quels services tournent, comment le site se
		//  présente, comment tourne le serveur. `BarreOnglets` rend une rangée de
		//  GROUPES, puis les onglets du groupe actif. Une clé retirée (`site`,
		//  `import_*`) reste servie : `$lib/admin-adresses`.
		onglets: [
			{
				id: 'a_traiter',
				route: '/admin',
				label: 'À traiter',
				groupe: '👥 Personnes',
				descriptif:
					"Ce qui attend un geste de l'administrateur : comptes à valider, commandes d'accès, demandes de modification de profil.",
			},
			{
				id: 'utilisateurs',
				route: '/admin?onglet=utilisateurs',
				label: 'Utilisateurs',
				groupe: '👥 Personnes',
				descriptif: 'Tous les comptes : statut, bâtiment, rôles, modification et suppression.',
			},
			{
				id: 'audit_lots',
				route: '/admin?onglet=audit_lots',
				label: 'Audit lots',
				groupe: '👥 Personnes',
				descriptif:
					'Les associations entre comptes et lots, pour repérer et retirer les affectations erronées.',
			},
			{
				id: 'telemetry',
				route: '/admin?onglet=telemetry',
				label: 'Télémétrie',
				groupe: '👥 Personnes',
				descriptif:
					"Statistiques d'utilisation : qui utilise quoi, et quand — par jour, sur 30 jours, sur 12 mois ou par année.",
			},
			{
				id: 'imports',
				route: '/admin?onglet=imports',
				label: 'Imports',
				groupe: '📥 Imports',
				descriptif:
					'Charger un tableur du syndic — lots et copropriétaires, télécommandes ou badges Vigik — et le rapprocher des lots.',
			},
			{
				id: 'copropriete',
				route: '/admin?onglet=copropriete',
				label: 'Identité',
				groupe: '🏢 Copropriété',
				descriptif: "L'identité et les références de la copropriété : nom, adresse, logo, syndic.",
			},
			{
				id: 'perimetres',
				route: '/admin?onglet=perimetres',
				label: 'Périmètres',
				groupe: '🏢 Copropriété',
				descriptif: "L'arborescence des bâtiments et des espaces que l'on peut viser.",
			},
			{
				id: 'fonctionnement',
				route: '/admin?onglet=fonctionnement',
				label: 'Fonctionnement',
				groupe: '🏢 Copropriété',
				descriptif:
					'Les délais d’archivage et de relance, le gestionnaire du site et les alertes qu’il reçoit.',
			},
			{
				id: 'legal',
				route: '/admin?onglet=legal',
				label: 'Pages légales',
				groupe: '🏢 Copropriété',
				descriptif: 'Les mentions légales et la politique de confidentialité.',
			},
			{
				id: 'services',
				route: '/admin?onglet=services',
				label: 'Services',
				groupe: '🔌 Services',
				descriptif:
					"Les services de la copropriété sur un seul écran : ce qui est activé, ce qu'on perd en le coupant, et le lien vers ses réglages.",
			},
			{
				id: 'smtp',
				route: '/admin?onglet=smtp',
				label: 'Courriel',
				groupe: '🔌 Services',
				descriptif: "L'envoi des courriels et la relève des réponses par courriel.",
			},
			{
				id: 'whatsapp',
				route: '/admin?onglet=whatsapp',
				label: 'WhatsApp',
				groupe: '🔌 Services',
				descriptif:
					'Le canal de diffusion de la résidence : connexion du groupe et pied des messages.',
			},
			{
				id: 'ia',
				route: '/admin?onglet=ia',
				label: 'Assistant IA',
				groupe: '🔌 Services',
				descriptif: "Le fournisseur, la clé et le réglage de chaque usage de l'assistant.",
			},
			{
				id: 'pages',
				route: '/admin?onglet=pages',
				label: 'Menu et pages',
				groupe: '🎨 Présentation',
				descriptif:
					"L'icône, le libellé de menu, le titre, la description et les onglets de chaque page, et leur ordre dans le menu.",
			},
			{
				id: 'connexion',
				route: '/admin?onglet=connexion',
				label: 'Connexion et pied de page',
				groupe: '🎨 Présentation',
				descriptif: 'Le sous-titre de la page de connexion, et ce que dit le pied de chaque page.',
			},
			{
				id: 'emails',
				route: '/admin?onglet=emails',
				label: 'Modèles e-mail',
				groupe: '🎨 Présentation',
				descriptif:
					"Le texte et la mise en page de chaque courriel envoyé par le site, avec l'historique des envois.",
			},
			{
				id: 'installation',
				route: '/admin?onglet=installation',
				label: 'Installation',
				groupe: '🛠 Exploitation',
				descriptif:
					'Cette installation : son rôle, sa version, son inscription au registre et son bail.',
				reserve: 'operateur',
				ouvertOperateur: true,
			},
			{
				id: 'maintenance',
				route: '/admin?onglet=maintenance',
				label: 'Maintenance',
				groupe: '🛠 Exploitation',
				descriptif: 'Les tâches automatiques, leur historique et leur déclenchement manuel.',
				ouvertOperateur: true,
			},
			{
				id: 'installations',
				route: '/admin?onglet=installations',
				label: 'Installations',
				groupe: '🛠 Exploitation',
				descriptif:
					'Les installations CoproFirst inscrites au registre de la référence : leur état, leur contrat, leurs services.',
				reserve: 'operateur',
				ouvertOperateur: true,
			},
		],
	},
	{
		id: 'delegations',
		href: '/delegations',
		nom: 'Délégations',
		titre: 'Délégations aidant',
		navLabel: 'Délégations',
		icone: 'heart-handshake',
		descriptif:
			"Gestion des accès délégués pour les proches aidants : un proche peut consulter à votre place ce qui vous est adressé, sans pouvoir agir en votre nom ni que cela constitue une procuration d'assemblée générale.",
	},
];
