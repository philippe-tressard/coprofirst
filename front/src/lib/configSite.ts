/**
 * Le paramétrage du site — la correspondance entre la configuration stockée
 * (des chaînes, à plat) et le formulaire de l'administration (des types).
 *
 * ## Pourquoi ce fichier (#515)
 *
 * La même liste de clés était écrite **trois fois** dans `admin/+page.svelte` :
 * une fois pour lire, une fois pour envoyer à l'API, une fois pour rafraîchir
 * `configStore` — trois objets littéraux de treize entrées, sur une seule ligne
 * chacun.
 *
 * 🔴 **Et les trois avaient déjà divergé.** La mise à jour du store omettait
 * `relance_syndic_delai_jours`, `whatsapp_footer`, `email_footer` et
 * `reference_copro` : après une sauvegarde, le store affichait encore les
 * anciennes valeurs de ces quatre réglages, jusqu'au rechargement de la page.
 * Personne ne l'avait vu, parce que le défaut ne se voit qu'en comparant deux
 * lignes de 900 caractères.
 *
 * Une seule fonction produit désormais le payload, et les deux appels l'utilisent.
 *
 * ## Une section, ses clés — et rien d'autre (#2057)
 *
 * 🔴 Cette fonction renvoyait **vingt clés** à chaque appel, et quatre boutons
 * l'appelaient : Paramètres généraux, Pied de page, Pages légales et le pied des
 * messages WhatsApp. `email_footer` et `reference_copro` y partaient en plus de
 * leur propre onglet (SMTP, Fiche copropriété) : un onglet resté ouvert
 * réécrivait en silence ce qu'un autre venait de changer.
 *
 * Chaque section a désormais son écrivain (`ECRIVAINS`), et une clé n'appartient
 * qu'à une section — la même partition que la liste blanche de l'API
 * (`api/app/utils/reglages.PAR_ONGLET`), que `test_reglages_liste_blanche.py`
 * confronte à ce fichier.
 *
 * Le nom de la résidence n'est plus ici (#2056) : il se saisit dans la Fiche
 * copropriété, seule source.
 *
 * ⚠️ Ce module ne connaît **que** les onglets Fonctionnement et Connexion. Les pages
 * (`page_config_*`), WhatsApp et les mentions légales ont leurs propres chemins,
 * et `mentions_legales` / `politique_confidentialite` se lisent par un endpoint
 * séparé (`/config/textes-legaux`, leur SOURCE, champs compris — jamais le rendu
 * public de `/config/legal`, #2065) — c'est pourquoi `lireConfigSite` les reçoit à part.
 */
import { delaiArchivageJours } from '$lib/archivage';
import { ecrireReglagePied, lireReglagePied, type ReglagePied } from '$lib/piedDePage';

export interface ConfigSite {
	url: string;
	email_admin: string;
	login_sous_titre: string;
	mentions_legales: string;
	politique_confidentialite: string;
	/** L'adresse où exercer ses droits sur ses données, nommée par les textes légaux (#2065). */
	contact_donnees: string;
	archivage_delai_jours: number;
	relance_syndic_delai_jours: number;
	notify_ticket_bug_email: boolean;
	notify_new_user_created_email: boolean;
	site_manager_user_id: string;
	whatsapp_footer: string;
	/** Lu ici pour être LIÉ à l'onglet SMTP, seul à l'écrire. */
	email_footer: string;
	/** Lu ici pour être LIÉ à la Fiche copropriété, seule à l'écrire. */
	reference_copro: string;
	/** Le pied de page : éléments masqués, année de création, texte libre (`$lib/piedDePage`). */
	pied_de_page: ReglagePied;
}

/**
 * Le nom de la RÉSIDENCE quand la configuration n'en porte pas — **neutre**.
 *
 * 🔴 Il valait « 5Hostachy » ici et dans `siteNomStore` : le nom de CETTE
 * copropriété, affiché chez toute autre le temps que sa configuration arrive
 * (#1725). Même valeur que `NOM_SITE_PAR_DEFAUT` côté API (`utils/liens.py`),
 * tenue par `api/tests/test_plateforme.py`.
 */
export const NOM_SITE_PAR_DEFAUT = 'Ma Résidence';

/** L'état initial du formulaire, avant tout chargement. */
export const CONFIG_SITE_DEFAUT: ConfigSite = {
	url: '',
	email_admin: '',
	login_sous_titre: 'Votre espace numérique de résidence',
	mentions_legales: '',
	politique_confidentialite: '',
	contact_donnees: '',
	archivage_delai_jours: 30,
	relance_syndic_delai_jours: 30,
	notify_ticket_bug_email: false,
	notify_new_user_created_email: false,
	site_manager_user_id: '',
	whatsapp_footer: '— Le Conseil Syndical',
	email_footer: '',
	reference_copro: '',
	pied_de_page: lireReglagePied({}),
};

/** Configuration stockée → formulaire. */
export function lireConfigSite(
	cfg: Record<string, string>,
	legal: { mentions_legales?: string; politique_confidentialite?: string } = {},
): ConfigSite {
	return {
		url: cfg['site_url'] ?? '',
		email_admin: cfg['site_email'] ?? '',
		login_sous_titre: cfg['login_sous_titre'] ?? CONFIG_SITE_DEFAUT.login_sous_titre,
		mentions_legales: legal.mentions_legales ?? '',
		politique_confidentialite: legal.politique_confidentialite ?? '',
		contact_donnees: cfg['contact_donnees_personnelles'] ?? '',
		//  Le réglage unique et son repli vivent dans `$lib/archivage` : les
		//  recopier ici rouvrirait exactement la divergence que #515 referme.
		archivage_delai_jours: delaiArchivageJours(cfg),
		relance_syndic_delai_jours: parseInt(cfg['relance_syndic_delai_jours'] ?? '30') || 30,
		notify_ticket_bug_email: cfg['notify_ticket_bug_email'] === '1',
		notify_new_user_created_email: cfg['notify_new_user_created_email'] === '1',
		site_manager_user_id: cfg['site_manager_user_id'] ?? '',
		whatsapp_footer: cfg['whatsapp_footer'] ?? CONFIG_SITE_DEFAUT.whatsapp_footer,
		email_footer: cfg['email_footer'] ?? CONFIG_SITE_DEFAUT.email_footer,
		reference_copro: cfg['reference_copro'] ?? '',
		pied_de_page: lireReglagePied(cfg),
	};
}

/** Les sections du paramétrage qui s'enregistrent chacune par son bouton. */
export type SectionSite =
	'fonctionnement' | 'connexion' | 'pied_de_page' | 'legal' | 'pied_whatsapp';

/**
 * Formulaire → configuration stockée, SECTION PAR SECTION (#2057).
 *
 * 🔴 **Un seul producteur, deux consommateurs** : l'appel d'enregistrement et la
 * mise à jour du store. C'est ce partage qui empêche le store de conserver des
 * valeurs périmées — le défaut que ce module a mis au jour.
 */
const ECRIVAINS: Record<SectionSite, (c: ConfigSite) => Record<string, string>> = {
	//  Copropriété › Fonctionnement — « Paramètres généraux » jusqu'au rangement
	//  par niveau (#2062), qui en a sorti le sous-titre de connexion.
	fonctionnement: (c) => ({
		//  `site_url` ne s'écrit pas : l'API la dérive de l'installation (#2058).
		site_email: c.email_admin,
		archivage_delai_jours: String(
			c.archivage_delai_jours || CONFIG_SITE_DEFAUT.archivage_delai_jours,
		),
		relance_syndic_delai_jours: String(c.relance_syndic_delai_jours),
		notify_ticket_bug_email: c.notify_ticket_bug_email ? '1' : '0',
		notify_new_user_created_email: c.notify_new_user_created_email ? '1' : '0',
		site_manager_user_id: c.site_manager_user_id || '',
	}),
	//  Présentation › Connexion et pied de page : deux sections, deux boutons.
	connexion: (c) => ({
		login_sous_titre: c.login_sous_titre,
	}),
	pied_de_page: (c) => ecrireReglagePied(c.pied_de_page),
	legal: (c) => ({
		mentions_legales: c.mentions_legales,
		politique_confidentialite: c.politique_confidentialite,
		//  L'adresse des droits sur les données, nommée par les textes légaux (#2065).
		contact_donnees_personnelles: c.contact_donnees,
	}),
	pied_whatsapp: (c) => ({
		whatsapp_footer: c.whatsapp_footer,
	}),
};

export function ecrireConfigSite(c: ConfigSite, section: SectionSite): Record<string, string> {
	return ECRIVAINS[section](c);
}
