/**
 * L'INSTANCE elle-même — son rôle dans la distribution (#1761), son inscription au
 * registre de la référence (R2 #1878) et l'export vérifié
 * de sa base (#1749) : Admin › Maintenance, cartes `CarteInstallation` et
 * `CarteExportCopropriete`.
 *
 * À part d'`administration.ts` et de `types-administration.ts`, qui dépassaient le
 * plafond de 500 lignes avec eux (#1747) : comme `services.ts`, le domaine vit
 * dans son module, client et types ensemble.
 */

import { api } from './client';

/**  `GET /admin/installation` (`routers/admin/installation.py`, #1761) : le rôle de
 *   l'installation dans la distribution, et l'écart de sa version à la branche suivie. */
export interface EtatInstallation {
	/** `reference` | `replique` | `inconnu` — absent du `.env`, jamais « référence ». */
	role: 'reference' | 'replique' | 'inconnu';
	libelle: string;
	/** `main` | `replica` ; `null` quand le rôle est inconnu. */
	branche: string | null;
	/** Le commit de l'image ; vide pour une image construite sans lui. */
	empreinte: string;
	demarree_le: string;
	verification_active: boolean;
	/** `a_jour` | `en_retard` | `ecart` | `non_verifie` — jamais « à jour » faute de mesure. */
	etat: 'a_jour' | 'en_retard' | 'ecart' | 'non_verifie';
	retard: number;
	detail: string;
	/** Une installation commune à plusieurs copropriétés (#1894) — un constat (#2400). */
	commune: boolean;
	/** `null` : la déclaration de l'installation commune ne peut pas servir. */
	nombre_coproprietes: number | null;
	detail_coproprietes: string;
}

/**  `POST /admin/export-copropriete/verifier` (#1749) : la base exportée puis
 *   réimportée dans une base jetable — se restaure-t-elle à l'identique ? */
export interface VerificationRestauration {
	restaurable: boolean;
	tables: number;
	lignes: number;
	revision: string | null;
	/** Tables présentes en base mais absentes des modèles : NON exportées. */
	ignorees: string[];
	ecarts: string[];
	duree_secondes: number;
}

/**  `GET /admin/export-copropriete/dernier` : le dernier export entier du volume
 *   des sauvegardes, lu dans son manifeste ; tout à zéro s'il n'y en a aucun. */
export interface DernierExport {
	archive: string | null;
	octets: number;
	cree_le: string | null;
	tables: number;
	lignes: number;
	fichiers: number;
}

/**  L'administrateur de l'installation, tel que la référence le connaît (R2 #1878). */
export interface ContactInstallation {
	prenom: string;
	nom: string;
	courriel: string;
	telephone?: string | null;
}

/**  `GET /admin/installation/inscription` (`routers/admin/inscription.py`, R2 #1878) :
 *   l'inscription de l'installation au registre de la référence, CONSTATÉE — rien
 *   ne l'applique encore (R6). */
export interface InscriptionInstallation {
	/** `reference` | `essai` | `limitee` | `active` | `suspendue`. */
	etat: 'reference' | 'essai' | 'limitee' | 'active' | 'suspendue';
	/** Pourquoi cet état, en clair — chaque raison de ne pas croire un bail se nomme. */
	raison: string;
	identifiant: string | null;
	canal: string | null;
	version_cible: string | null;
	/** Les libellés des services que la référence autorise ; `null` = aucune restriction (#1880). */
	services: string[] | null;
	/** L'époque de la référence qui a signé le bail (D24). */
	epoque: number | null;
	echeance: string | null;
	renouvellement_en_retard: boolean;
	inscrite_le: string | null;
	dernier_renouvellement_le: string | null;
	/** Le dernier rapport nocturne accepté par la référence (R3 #1879). */
	dernier_rapport_le: string | null;
	derniere_erreur: string | null;
	contact: ContactInstallation | null;
	conditions_acceptees: number | null;
	conditions_en_vigueur: number;
	/** Ni la référence, ni une installation d'essai ne s'inscrivent. */
	peut_s_inscrire: boolean;
	/** `INSTALLATION_ESSAI` posé hors d'un hôte local : refusé. */
	essai_refuse: boolean;
	registre_url: string;
}

/**  `GET /admin/installation/conditions` : le texte en vigueur, tel qu'il s'archive. */
export interface ConditionsInscription {
	version: number;
	empreinte: string;
	texte: string;
}

/**  `POST /admin/installation/inscription` : le contact, et la version des
 *   conditions MONTRÉE — refusée si elle a changé depuis. */
export interface DemandeInscriptionInstallation extends ContactInstallation {
	conditions_acceptees: number;
	accepte: boolean;
}

export const instance = {
	/** Le rôle de l'installation et l'écart de sa version — lu par `CarteInstallation` (#1761). */
	installation: () => api.get<EtatInstallation>('/admin/installation'),
	/** Exporte puis réimporte la base dans une base jetable — lu par `CarteExportCopropriete` (#1749). */
	verifierRestauration: () =>
		api.post<VerificationRestauration>('/admin/export-copropriete/verifier'),
	/** Lance l'export complet (tables et fichiers) dans le volume des sauvegardes. */
	exporterCopropriete: () => api.post<{ archive: string }>('/admin/export-copropriete'),
	/** Le dernier export entier, lu dans son manifeste. */
	dernierExport: () => api.get<DernierExport>('/admin/export-copropriete/dernier'),
	/** L'inscription au registre, constatée — lu par `CarteInstallation` (R2 #1878). */
	inscription: () => api.get<InscriptionInstallation>('/admin/installation/inscription'),
	/** Le texte des conditions d'inscription en vigueur. */
	conditionsInscription: () => api.get<ConditionsInscription>('/admin/installation/conditions'),
	/** Déclare l'installation à la référence — ou rectifie son contact. */
	inscrire: (corps: DemandeInscriptionInstallation) =>
		api.post<InscriptionInstallation>('/admin/installation/inscription', corps),
	/** Demande le bail maintenant, sans attendre la nuit. */
	renouvelerBail: () => api.post<InscriptionInstallation>('/admin/installation/bail'),
};
