/**
 * Les imports d'ACCÈS — télécommandes et badges Vigik — décrits, pas recopiés.
 *
 * ## Pourquoi ce fichier existe (27/08/2026, #453)
 *
 * `OngletImportTelecommandes.svelte` (349 l.) et `OngletImportVigik.svelte`
 * (329 l.) étaient **identiques à 87 %** — 263 lignes communes sur 314. Le même
 * écran, le même geste, le même tableau, écrits deux fois : téléverser un fichier
 * Excel, rapprocher automatiquement, corriger les liaisons à la main, résoudre ou
 * ignorer.
 *
 * Ce qui les distinguait n'était **jamais du comportement** — sauf un cas, décrit
 * plus bas — mais des DONNÉES : le jeu d'endpoints, les colonnes du tableau, le
 * vocabulaire (« la télécommande » / « le badge Vigik »), et une tuile de
 * statistique. C'est donc une table, et l'écran devient unique.
 *
 * ## ✅ La divergence que la factorisation a révélée — et qui est comblée
 *
 * `remettreEnAttente` n'existait **que pour les télécommandes**, côté front comme
 * côté serveur : un import Vigik ignoré par erreur était **définitivement perdu**,
 * là où le même geste se rattrape sur une télécommande.
 *
 * Ce n'était pas une décision mais un oubli, resté invisible tant que les deux
 * écrans étaient deux fichiers — chacun paraissait complet. **Comblé le
 * 28/08/2026 (#576)**, en miroir exact de l'endpoint des télécommandes.
 *
 * ⚠️ Le champ est redevenu **OBLIGATOIRE**, et c'est le point : tant qu'il restait
 * optionnel, le mécanisme d'exception survivait à l'exception, et le prochain
 * type d'import pouvait l'omettre sans que rien ne le dise. C'est la leçon de la
 * prop `marge` d'`EntetePage` (`ux-patterns` §13) : *tant que le mécanisme
 * d'exception existe, l'exception se reproduit.*
 */
import {
	acces as accesApi,
	type AppariementImport,
	type CompteImportTableur,
	type LigneImportAcces,
	type LigneImportAccesBrute,
	type LigneImportTelecommandeBrute,
	type LigneImportVigikBrute,
	type LotPourBadge,
	type RattachementImport,
	type StatsImportAcces,
	type StatutLigneImport,
} from '#lib/api/index.ts';

//  Le type vit à côté du client qui le rend (#1572) ; réexporté pour ses lecteurs.
export type { LotPourBadge };
import { parAttribut } from '#lib/table-statuts.ts';

/**  Une ligne de la liste, quel que soit le type d'import — ce que rend `api.list`. */
export type LigneImport =
	LigneImportAcces<LigneImportTelecommandeBrute> | LigneImportAcces<LigneImportVigikBrute>;

/** Une colonne du tableau, propre à un type d'import. */
export interface ColonneImport {
	entete: string;
	/** Lue sur la ligne d'import ; `—` si absente. */
	cle: string;
	/** Rendue en `<code>` — pour une référence ou un numéro de badge. */
	code?: boolean;
}

/** Une case à cocher supplémentaire du formulaire d'édition. */
export interface ChampBooleen {
	cle: string;
	libelle: string;
}

export interface ModeleImportAcces {
	/** Sert au `<title>` et n'apparaît nulle part ailleurs. */
	titre: string;
	/** Ce qu'on crée en résolvant, au singulier avec son article : « le badge Vigik ». */
	objet: string;
	/** Colonnes du fichier Excel, affichées en aide au-dessus du sélecteur. */
	colonnesAttendues: string;
	/** Colonnes propres à ce type, insérées avant les indices du fichier. */
	colonnes: ColonneImport[];
	/** La colonne qui identifie l'objet — sans elle, on ne peut pas rattacher. */
	colonneCle: ColonneImport;
	/** La nature des lots où va ce badge : l'appartement pour un Vigik, le
	 *  parking pour une télécommande (`types_lot` côté serveur). */
	natureLot: string;
	/** Cases supplémentaires du formulaire d'édition. */
	champsBooleens: ChampBooleen[];
	/** Décorations du statut — icônes que seul un type porte. */
	decorationsStatut: (imp: LigneImportAccesBrute) => { icone: string; titre: string }[];
	api: {
		upload: (file: File, remplacer: boolean) => Promise<CompteImportTableur>;
		list: (statut?: string) => Promise<LigneImport[]>;
		stats: () => Promise<StatsImportAcces>;
		autoMatch: () => Promise<AppariementImport>;
		/** Le rattachement en masse : chaque ligne dont le lot est connu (#1194). */
		rattacher: () => Promise<RattachementImport>;
		patch: (id: number, data: unknown) => Promise<LigneImportAccesBrute>;
		/** L'objet créé diffère d'un type à l'autre ; l'écran ne lit que la ligne. */
		resoudre: (id: number) => Promise<{ import_id: number }>;
		ignorer: (id: number) => Promise<{ statut: StatutLigneImport }>;
		/**  Rattrape un import ignoré par erreur. OBLIGATOIRE depuis #576 : les
		 *   deux objets ont le même cycle d'import, donc les mêmes gestes. */
		remettreEnAttente: (id: number) => Promise<{ statut: StatutLigneImport }>;
		/** 🔒 Administrateur : supprimer une ligne erronée (23/09/2026). */
		supprimer: (id: number) => Promise<unknown>;
	};
}

export const IMPORT_TELECOMMANDES: ModeleImportAcces = {
	titre: 'Import Télécommandes',
	objet: 'la télécommande',
	colonnesAttendues: 'Copropriétaire | Locataire | Télécommandes',
	colonnes: [],
	colonneCle: { entete: 'Référence', cle: 'reference', code: true },
	natureLot: 'parking',
	champsBooleens: [{ cle: 'refuse_par_locataire', libelle: 'Locataire a refusé' }],
	decorationsStatut: (imp) => {
		const d = [];
		if (imp.refuse_par_locataire) d.push({ icone: '\u{1F6B7}', titre: 'Locataire a refusé' });
		else if (imp.chez_locataire) d.push({ icone: '\u{1F464}', titre: 'TC chez le locataire' });
		return d;
	},
	api: {
		upload: accesApi.uploadImportTC,
		list: accesApi.listImportsTC,
		stats: accesApi.statsImportsTC,
		autoMatch: accesApi.autoMatchImportsTC,
		rattacher: accesApi.rattacherImportsTC,
		patch: accesApi.patchImportTC,
		resoudre: accesApi.resoudreImportTC,
		ignorer: accesApi.ignorerImportTC,
		remettreEnAttente: accesApi.remettreEnAttenteImportTC,
		supprimer: accesApi.supprimerImportTC,
	},
};

export const IMPORT_VIGIK: ModeleImportAcces = {
	titre: 'Import Vigik',
	objet: 'le badge Vigik',
	colonnesAttendues: 'BATIMENT | APPARTEMENT | NOM DU COPROPRIÉTAIRE | NOM LOCATAIRE | N° CLÉS',
	colonnes: [
		{ entete: 'Bât.', cle: 'batiment_raw' },
		{ entete: 'Appt.', cle: 'appartement_raw' },
	],
	colonneCle: { entete: 'Code', cle: 'code', code: true },
	natureLot: 'appartement',
	champsBooleens: [],
	decorationsStatut: () => [],
	api: {
		upload: accesApi.uploadImportVigik,
		list: accesApi.listImportsVigik,
		stats: accesApi.statsImportsVigik,
		autoMatch: accesApi.autoMatchImportsVigik,
		rattacher: accesApi.rattacherImportsVigik,
		patch: accesApi.patchImportVigik,
		resoudre: accesApi.resoudreImportVigik,
		ignorer: accesApi.ignorerImportVigik,
		//  ✅ Divergence COMBLÉE le 28/08/2026 (#576) : l'endpoint existe désormais,
		//  en miroir exact de celui des télécommandes. Les deux objets ont le même
		//  cycle d'import, donc les mêmes gestes — l'asymétrie venait de l'ordre
		//  dans lequel les deux écrans ont été écrits, pas d'un arbitrage.
		remettreEnAttente: accesApi.remettreEnAttenteImportVigik,
		supprimer: accesApi.supprimerImportVigik,
	},
};

/** Les cinq statuts, communs aux deux types. */
const { libelle, badge } = parAttribut({
	en_attente: { libelle: 'En attente', badge: 'badge-orange' },
	proprietaire_lie: { libelle: 'Compte trouvé', badge: 'badge-blue' },
	resolu: { libelle: 'Rattaché', badge: 'badge-green' },
	ignore: { libelle: 'Ignoré', badge: 'badge-gray' },
});

export const STATUT_BADGE: Record<string, string> = badge;
export const STATUT_LABEL: Record<string, string> = libelle;

/**
 * Les lots à proposer pour un badge — une écriture pour les deux formulaires
 * (import et parc, #1194). Ceux de sa nature d'abord (l'appartement pour un
 * Vigik, le parking pour une télécommande), puis les autres ; dans chaque
 * groupe par NOM du copropriétaire : c'est lui qu'on cherche, et la frappe des
 * premières lettres y saute dans la liste (retour du 23/09/2026).
 */
export function lotsPourBadge(lots: LotPourBadge[], nature: string): LotPourBadge[] {
	//  Sans nom connu → en fin de groupe : un numéro seul ne se cherche pas par nom.
	const parNom = (a: LotPourBadge, b: LotPourBadge) =>
		!a.coproprietaire !== !b.coproprietaire
			? a.coproprietaire
				? -1
				: 1
			: (a.coproprietaire ?? '').localeCompare(b.coproprietaire ?? '', 'fr');
	return [
		...lots.filter((l) => l.type === nature).sort(parNom),
		...lots.filter((l) => l.type !== nature).sort(parNom),
	];
}

/** « DUPONT Jean — Parking 450 » : le nom d'abord, c'est lui qu'on cherche. */
export const libelleLotPourBadge = (l: LotPourBadge) =>
	`${l.coproprietaire ? `${l.coproprietaire} — ` : ''}${l.libelle}`;
