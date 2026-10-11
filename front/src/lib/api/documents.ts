//  Documents, fichiers et téléversements : trois clients qui manipulent la
//  même notion et vivaient à 400 lignes d'écart.
import { api, BASE, postFormData } from './client';

/**  Un document — `DocumentRead` (`routers/documents_schemas.py`), que rendent la
 *   liste, le dépôt et la correction. Complété le 04/10/2026 (#1572) — il n'en portait
 *   que huit champs sur dix-sept — et venu de `types.ts` à côté de son client. */
export interface Document {
	id: number;
	titre: string;
	/** Vide plutôt qu'absent : le serveur rend `""` (#852). */
	description: string;
	fichier_nom: string;
	taille_octets: number | null;
	mime_type: string;
	categorie_id: number | null;
	contrat_id: number | null;
	ticket_id: number | null;
	evenement_id: number | null;
	/** La fiche de Ma résidence qui porte cette annexe (migration 0278) — une des trois. */
	document_parent_id: number | null;
	diagnostic_rapport_id: number | null;
	regle_residence_id: number | null;
	/** Le droit de lecture (`résidence`, `bâtiment`…). */
	perimetre: string;
	batiment_id: number | null;
	publie_le: string;
	annee: number | null;
	/** Date ISO `AAAA-MM-JJ`. */
	date_ag: string | null;
	/** La date DU document (`AAAA-MM-JJ`) — un règlement (migration 0280). */
	date_document: string | null;
	batiments_ids_json: string | null;
	/** De quoi PARLE le document, en codes de périmètre — descriptif, jamais un
	 *  droit ; `null` quand le ciblage est absent ou illisible. */
	perimetre_cible: string[] | null;
}

/**
 *  Les FICHES de « Ma résidence » qui portent des annexes (migration 0278) — un
 *  plan, un règlement ou un CR d'AG (`document`), un rapport de diagnostic, une
 *  règle. Les clés sont celles de `PORTEURS` (`api/app/utils/annexes.py`).
 */
export type PorteurAnnexes = 'document' | 'diagnostic' | 'regle';

/**  La colonne de `Document` qui rattache une annexe à chaque porteur — lue par
 *   `CHAMP_RATTACHEMENT` ci-dessous et par `annexesParFiche`, écrite ici seule. */
const COLONNE_PORTEUR = {
	document: 'document_parent_id',
	diagnostic: 'diagnostic_rapport_id',
	regle: 'regle_residence_id',
} as const satisfies Record<PorteurAnnexes, keyof Document>;

/**
 *  Les entités auxquelles un document peut se rattacher, **et l'API en exige
 *  une** : `documents.py` refuse en 400 une création qui n'en porte aucune,
 *  parce qu'une ligne orpheline n'aurait plus de source de protection à
 *  consulter (`document_visible`).
 */
export type CibleDocument = 'contrat' | 'ticket' | 'evenement' | 'categorie' | PorteurAnnexes;

/**  Le nom du champ que l'API attend pour chaque rattachement.
 *
 *  ⚠️ Cette table est la SEULE traduction entre l'objet métier et le champ du
 *  formulaire. Recopiée dans les appelants — ce qu'elle était, sous forme de deux
 *  fonctions jumelles — elle diverge au premier rattachement ajouté. */
const CHAMP_RATTACHEMENT: Record<CibleDocument, string> = {
	contrat: 'contrat_id',
	ticket: 'ticket_id',
	evenement: 'evenement_id',
	categorie: 'categorie_id',
	...COLONNE_PORTEUR,
};

export const documents = {
	list: (categorieId?: number, contratId?: number) => {
		const params = new URLSearchParams();
		if (categorieId) params.set('categorie_id', String(categorieId));
		if (contratId) params.set('contrat_id', String(contratId));
		const qs = params.toString();
		return api.get<Document[]>(`/documents${qs ? `?${qs}` : ''}`);
	},
	listCategories: () =>
		api.get<{ id: number; code: string; libelle: string }[]>('/documents/categories'),
	/**  Corriger un document existant.
	 *
	 *   🔴 `description` et `perimetre_cible` ajoutés le 08/09/2026 (#852) :
	 *   *« très peu de champs sont éditables »*. Ils ne suffisaient pas côté
	 *   écran — `DocumentUpdate` ne les acceptait pas non plus, et les ouvrir
	 *   d'un seul côté aurait donné des champs qui ne font rien.
	 */
	update: (
		id: number,
		data: {
			titre?: string;
			description?: string;
			perimetre_cible?: string[];
			annee?: number | null;
			date_ag?: string | null;
			date_document?: string | null;
		},
	) => api.patch<Document>(`/documents/${id}`, data),

	/**  Déposer un document.
	 *
	 *   🔴 **Un objet nommé, plus huit paramètres positionnels** (08/09/2026).
	 *   La signature d'avant était `(titre, categorieId, file, perimetre,
	 *   batimentId, annee, dateAg, perimetreCible)` : trois appels s'y
	 *   alignaient en écrivant `undefined, undefined, undefined` pour atteindre
	 *   le dernier.
	 *
	 *   ⚠️ Ce n'est pas une préférence de style. C'est exactement la forme qui a
	 *   produit le défaut de #470 — un formulaire liait son sélecteur de
	 *   périmètre à la variable d'un AUTRE formulaire, et rien ne levait :
	 *   les types concordaient, `svelte-check` était vert. Un argument nommé se
	 *   trompe moins facilement de place qu'un argument compté.
	 */
	upload: async (options: {
		titre: string;
		categorieId: number;
		file: File;
		/** Ce que le document COUVRE — section 6 du cadre (#852). */
		description?: string;
		/** Le droit de lecture. Distinct du périmètre descriptif ci-dessous. */
		perimetre?: string;
		batimentId?: number;
		annee?: number;
		dateAg?: string;
		/** La date du document (`AAAA-MM-JJ`) — un règlement. */
		dateDocument?: string;
		/**  De quoi PARLE le document, en codes de périmètre (`["bat:3"]`).
		 *
		 *   Remplace `batimentsIdsJson`, qui parlait en identifiants de lignes
		 *   (#470). ⚠️ Descriptif, jamais un droit : ce sont `perimetre` et
		 *   `batimentId` qui gouvernent la lecture. */
		perimetreCible?: string[];
	}): Promise<Document> => {
		//  `postFormData` écarte lui-même les champs absents : plus de `if (x)`
		//  répété pour chaque champ facultatif.
		return postFormData<Document>('/documents', {
			titre: options.titre,
			description: options.description || undefined,
			categorie_id: String(options.categorieId),
			perimetre: options.perimetre ?? 'résidence',
			batiment_id: options.batimentId ? String(options.batimentId) : undefined,
			annee: options.annee ? String(options.annee) : undefined,
			date_ag: options.dateAg,
			date_document: options.dateDocument,
			perimetre_cible: options.perimetreCible?.length
				? JSON.stringify(options.perimetreCible)
				: undefined,
			file: options.file,
		});
	},
	/**
	 *  Attacher un document à l'entité qui le porte — **une seule fonction pour
	 *  les quatre rattachements**.
	 *
	 *  🔴 Elle en remplace deux (12/09/2026), `uploadForContrat` et
	 *  `uploadForPublication`, identiques **à un nom de champ près** :
	 *
	 *      postFormData('/documents', { titre, contrat_id:     String(id), file })
	 *      postFormData('/documents', { titre, publication_id: String(id), file })
	 *
	 *  Trois autres rattachements existent côté API (`ticket_id`, `evenement_id`,
	 *  `categorie_id`) : sans cette fonction, chacun aurait apporté sa copie, et
	 *  les cinq auraient divergé au premier paramètre ajouté — une description, un
	 *  périmètre, un indicateur de confidentialité.
	 *
	 *  ⚠️ `cible` est TYPÉ sur les quatre valeurs que l'API accepte : l'invariant du
	 *  serveur — *une ligne `document` porte toujours un rattachement* — se lit
	 *  ainsi côté client, au lieu d'être redécouvert à chaque appel.
	 */
	uploadPour: (cible: CibleDocument, id: number, titre: string, file: File) =>
		postFormData<Document>('/documents', { titre, [CHAMP_RATTACHEMENT[cible]]: String(id), file }),
	//  Les `Document` d'une affaire — ceux des anciennes publications, que la
	//  0210 lui a rattachés (#1091). Une affaire récente porte les siens en URLs.
	listByTicket: (ticketId: number) => api.get<Document[]>(`/documents?ticket_id=${ticketId}`),
	/** Les documents rattachés à UN objet — les annexes d'une fiche, par exemple. */
	listPour: (cible: CibleDocument, id: number) =>
		api.get<Document[]>(`/documents?${CHAMP_RATTACHEMENT[cible]}=${id}`),
	/**  Toutes les annexes d'une RUBRIQUE de Ma résidence, en un appel, rangées
	 *   sous l'identifiant de leur fiche — au lieu d'un appel par carte. */
	annexesParFiche: async (rubrique: PorteurAnnexes): Promise<Map<number, Document[]>> => {
		const colonne = COLONNE_PORTEUR[rubrique];
		const parFiche = new Map<number, Document[]>();
		for (const d of await api.get<Document[]>(`/documents?annexes_de=${rubrique}`)) {
			const fiche = d[colonne];
			if (fiche !== null) parFiche.set(fiche, [...(parFiche.get(fiche) ?? []), d]);
		}
		return parFiche;
	},
	/**  Retirer le fichier PRINCIPAL d'un document de Ma résidence : sa première
	 *   annexe prend sa place. Refusé s'il est seul — une fiche sans fichier
	 *   n'existe pas (`utils/annexes.retirer_fichier_principal`). */
	retirerFichier: (id: number) => api.delete<Document>(`/documents/${id}/fichier`),
	downloadUrl: (docId: number) => `${BASE}/documents/${docId}/télécharger`,
	delete: (id: number) => api.delete(`/documents/${id}`),
};

export const fichiersApi = {
	/**
	 * Upload un fichier (photo ou document PDF/Word/Excel) destiné à être joint à
	 * un ticket, une affaire ou un commentaire. Ne demande aucun élément parent :
	 * l'URL est connue avant la création, ce qui permet de la passer dans le
	 * payload — et donc de la joindre à l'e-mail envoyé au syndic.
	 * Retourne { url, nom, type }
	 */
	upload: (file: File): Promise<{ url: string; nom: string; type: string }> =>
		postFormData('/uploads/fichier', { file }),
};

async function uploadFile(path: string, file: File): Promise<{ url: string }> {
	return postFormData(path, { file });
}

/**  Le compte rendu commun aux trois imports de tableur (lots, Vigik, télécommandes)
 *   — le `stats` des `importer_depuis_bytes` de `utils/import_*.py`. Chaque import
 *   peut y ajouter le sien (`ResultatImportLots`). */
export interface CompteImportTableur {
	importes: number;
	ignores: number;
	doublons: number;
	/** Une phrase par ligne refusée (« Ligne 12 — bâtiment inconnu… »). */
	erreurs: string[];
}

export function uploadExcel<T = CompteImportTableur>(
	path: string,
	file: File,
	remplacer = false,
): Promise<T> {
	//  Le libellé reste distinct : un import de tableur qui échoue ne se raconte pas
	//  comme un téléversement de pièce jointe. C'est la SEULE des cinq divergences
	//  de libellé qui portait un sens ; les quatre autres disaient la même chose.
	return postFormData<T>(
		`${path}${remplacer ? '?remplacer=true' : ''}`,
		{ file },
		{
			libelleErreur: 'Erreur import',
		},
	);
}

export const uploads = {
	avatar: (file: File) => uploadFile('/uploads/avatar', file),
	residence: (file: File) => uploadFile('/uploads/residence', file),
};
