/**
 * L'INSTANCE elle-même — son rôle dans la distribution (#1761) et l'export vérifié
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
};
