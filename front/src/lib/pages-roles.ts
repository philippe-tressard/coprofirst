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
					'Synthèses et indicateurs : kanban, tableau des affaires, prestataires, renouvellements de contrats et de diagnostics, et relance syndic.',
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
		descriptif:
			'Administration de la plateforme, réservée aux admins : ce qui attend un geste, les utilisateurs et leur activité, la configuration du site et ses référentiels.',
		//  Les onglets de l'administration — déclarés ici depuis le 01/10/2026 pour
		//  être renommés et décrits dans « Descriptif pages » comme ceux des autres
		//  pages. L'adresse reste `?onglet=` (« sauf admin ») ; cette liste fait foi
		//  pour `admin/+page.svelte`, qui n'en tient plus de seconde.
		onglets: [
			{
				id: 'a_traiter',
				route: '/admin',
				label: 'À traiter',
				groupe: '👥 Gestion utilisateurs',
				descriptif:
					"Ce qui attend un geste de l'administrateur : comptes à valider, commandes d'accès, demandes de modification de profil.",
			},
			{
				id: 'utilisateurs',
				route: '/admin?onglet=utilisateurs',
				label: 'Utilisateurs',
				groupe: '👥 Gestion utilisateurs',
				descriptif: 'Tous les comptes : statut, bâtiment, rôles, modification et suppression.',
			},
			{
				id: 'telemetry',
				route: '/admin?onglet=telemetry',
				label: 'Télémétrie',
				groupe: '👥 Gestion utilisateurs',
				descriptif:
					"Statistiques d'utilisation : qui utilise quoi, et quand — par jour, sur 30 jours, sur 12 mois ou par année.",
			},
			{
				id: 'emails',
				route: '/admin?onglet=emails',
				label: 'Modèles e-mail',
				groupe: '👥 Gestion utilisateurs',
				descriptif:
					"Le texte et la mise en page de chaque courriel envoyé par le site, avec l'historique des envois.",
			},
			{
				id: 'import_lots',
				route: '/admin?onglet=import_lots',
				label: 'Import Lots',
				groupe: '👥 Gestion utilisateurs',
				descriptif:
					'Importer la liste des lots et de leurs copropriétaires depuis un tableur du syndic.',
			},
			{
				id: 'import_tc',
				route: '/admin?onglet=import_tc',
				label: 'Import TC',
				groupe: '👥 Gestion utilisateurs',
				descriptif: 'Importer le parc de télécommandes et le rapprocher des lots.',
			},
			{
				id: 'import_vigik',
				route: '/admin?onglet=import_vigik',
				label: 'Import Vigik',
				groupe: '👥 Gestion utilisateurs',
				descriptif: 'Importer le parc de badges Vigik et le rapprocher des lots.',
			},
			{
				id: 'audit_lots',
				route: '/admin?onglet=audit_lots',
				label: 'Audit lots',
				groupe: '👥 Gestion utilisateurs',
				descriptif:
					'Les associations entre comptes et lots, pour repérer et retirer les affectations erronées.',
			},
			{
				id: 'services',
				route: '/admin?onglet=services',
				label: 'Services',
				groupe: '⚙️ Configuration',
				descriptif:
					"Les services de la copropriété sur un seul écran : ce qui est activé, ce qu'on perd en le coupant, et le lien vers ses réglages.",
			},
			{
				id: 'site',
				route: '/admin?onglet=site',
				label: 'Paramétrage site',
				groupe: '⚙️ Configuration',
				descriptif: 'Les réglages généraux du site.',
			},
			{
				id: 'copropriete',
				route: '/admin?onglet=copropriete',
				label: 'Fiche copropriété',
				groupe: '⚙️ Configuration',
				descriptif: "L'identité et les références de la copropriété.",
			},
			{
				id: 'perimetres',
				route: '/admin?onglet=perimetres',
				label: 'Périmètres',
				groupe: '⚙️ Configuration',
				descriptif: "L'arborescence des bâtiments et des espaces que l'on peut viser.",
			},
			{
				id: 'pages',
				route: '/admin?onglet=pages',
				label: 'Descriptif pages',
				groupe: '⚙️ Configuration',
				descriptif:
					"L'icône, le libellé de menu, le titre, la description et les onglets de chaque page, et leur ordre dans le menu.",
			},
			{
				id: 'legal',
				route: '/admin?onglet=legal',
				label: 'Pages légales',
				groupe: '⚙️ Configuration',
				descriptif: 'Les mentions légales et la politique de confidentialité.',
			},
			{
				id: 'whatsapp',
				route: '/admin?onglet=whatsapp',
				label: 'WhatsApp',
				groupe: '⚙️ Configuration',
				descriptif:
					'Le canal de diffusion de la résidence : connexion du groupe et pied des messages.',
			},
			{
				id: 'smtp',
				route: '/admin?onglet=smtp',
				label: 'SMTP',
				groupe: '⚙️ Configuration',
				descriptif: "L'envoi des courriels et la relève des réponses par courriel.",
			},
			{
				id: 'ia',
				route: '/admin?onglet=ia',
				label: 'Assistant IA',
				groupe: '⚙️ Configuration',
				descriptif: "Le fournisseur, la clé et le réglage de chaque usage de l'assistant.",
			},
			{
				id: 'maintenance',
				route: '/admin?onglet=maintenance',
				label: 'Maintenance',
				groupe: '⚙️ Configuration',
				descriptif: 'Les tâches automatiques, leur historique et leur déclenchement manuel.',
			},
			{
				id: 'installations',
				route: '/admin?onglet=installations',
				label: 'Installations',
				groupe: '⚙️ Configuration',
				descriptif:
					'Les installations CoproFirst inscrites au registre de la référence : leur état, leur contrat, leurs services.',
				reserve: 'operateur',
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
