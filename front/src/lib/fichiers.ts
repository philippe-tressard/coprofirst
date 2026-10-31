/**
 * Pièces jointes — une seule définition de « qu'est-ce qu'une image », « quel
 * nom afficher » et « quels types accepter ».
 *
 * Ces trois règles étaient recopiées dans les pages : le test d'image huit fois,
 * le nom dérivé de l'URL sept fois, la liste `accept` trois fois. Une pièce
 * jointe ajoutée au mauvais endroit tombait alors dans la mauvaise colonne
 * (`.gif` classé « document », vignette jamais affichée) sans que rien ne le
 * signale.
 *
 * La liste blanche qui FAIT AUTORITÉ est celle du serveur
 * (`api/app/routers/uploads.py`) : celle-ci ne fait que filtrer le sélecteur de
 * fichiers du navigateur, elle ne protège rien. Les deux doivent rester
 * alignées — `api/tests/test_pieces_jointes.py` le vérifie.
 */

/** Formats d'image acceptés par `_save_image` (ALLOWED_MIME côté API). */
import type { CibleDocument } from '#lib/api/documents.ts';

export const ACCEPT_PHOTOS =
	'image/jpeg,image/png,image/webp,image/gif,image/avif,image/bmp,image/tiff';

/** Documents acceptés par `POST /uploads/fichier` (ALLOWED_DOC_MIME côté API). */
export const ACCEPT_DOCUMENTS = 'application/pdf,text/plain,.pdf,.doc,.docx,.xls,.xlsx,.txt';

/** Les deux à la fois, pour un sélecteur unique « pièce jointe ». */
export const ACCEPT_FICHIERS = `${ACCEPT_PHOTOS},${ACCEPT_DOCUMENTS}`;

/**
 * Ce que l'écran ANNONCE d'acceptable, sous le bouton — « Image, PDF, Word,
 * Excel, texte ».
 *
 * 🔴 Ici, et pas dans le composant. `FichiersUpload` les récitait en dur sous
 * un commentaire qui affirmait l'inverse — *« les types acceptés ne sont pas
 * récités à la main : ils DÉCOULENT de `ACCEPT_DOCUMENTS` »* —, et le mode
 * MIXTE n'annonçait donc que les documents : « 0/10 · PDF, Word, Excel,
 * texte » au-dessus d'un contrôle qui accepte les photos (signalé à l'écran le
 * 21/09/2026).
 *
 * ⚠️ Une consigne qui décrit une dérivation qui n'existe pas est pire qu'une
 * valeur en dur assumée : on la croit, et on ne va pas voir.
 *
 * Les trois se tiennent avec les `ACCEPT_*` juste au-dessus : ajouter une
 * extension là-haut se dit ici, sous les yeux, dans le même fichier.
 */
export const LIBELLE_TYPES: Readonly<Record<'photos' | 'documents' | 'mixte', string>> = {
	//  Vide : « Image » sous un bouton « Ajouter une photo » n'apprend rien.
	photos: '',
	documents: 'PDF, Word, Excel, texte',
	mixte: 'Image, PDF, Word, Excel, texte',
};

/** Nombre maximum de pièces jointes par objet.
 *
 *  Il était écrit À LA MAIN dans chaque appel de `FichiersUpload` — 5 sur les
 *  tickets, le calendrier et les évolutions, 6 sur les actualités, 2 sur les
 *  petites annonces. Trois limites pour la même notion, qu'aucun écran
 *  n'annonçait de la même façon (16/08/2026).
 *
 *  Porté ici, il se change une fois pour tout le site — et le libellé du
 *  composant l'annonce, donc il ne peut plus mentir. Valeur retenue par
 *  l'utilisateur : la plus disante des trois, élargie à 10.
 *
 *  🔴 « UNE FOIS POUR TOUT LE SITE » ÉTAIT FAUX, et l'est resté deux semaines
 *  (corrigé le 01/09/2026). Deux objets ont leur propre plafond, et ce ne sont
 *  pas des oublis — ils sont **bornés côté serveur**, pour des raisons qui leur
 *  appartiennent :
 *
 *    · petite annonce  → 5  (`routers/annonces.py`, refus au-delà)
 *    · affiche de hall → 2  (`utils/annonce_hall.py` : au-delà, l'affiche
 *                            déborde du feuillet et le format n'est plus tenu ;
 *                            `POST /annonces-hall` refuse en 422)
 *
 *  Les deux vivent dans `#lib/annonces.ts`, avec leur raison.
 *
 *  ⚠️ Et le plus important : **cette constante-ci n'est bornée par AUCUN
 *  routeur**. C'est un confort d'interface, pas une limite — un client qui poste
 *  cinquante URLs passe. Même statut que `ACCEPT_*` ci-dessus, dont l'en-tête le
 *  dit déjà : « celle-ci ne fait que filtrer le sélecteur de fichiers du
 *  navigateur, elle ne protège rien ». C'est vrai du nombre aussi.
 *
 *  🔒 `api/tests/test_plafonds_pieces_jointes.py` rapproche chaque plafond
 *  annoncé de celui que le serveur applique — et constate que celui-ci n'en a
 *  aucun. Il a été écrit après qu'un écran ait promis dix photos là où le
 *  serveur en refusait plus de deux : le conseiller perdait sa saisie sur un 422
 *  qu'il ne pouvait pas prévoir.
 */
export const MAX_FICHIERS = 10;

/**
 *  Le titre d'un document déposé : celui qu'on a saisi, sinon le nom de son
 *  fichier sans extension. C'est la règle de « Sans titre, chaque fichier prend
 *  le sien » — Diagnostics et les rubriques de la Résidence (#1479) la partagent.
 */
export function titreOuNomDuFichier(saisi: string, fichier: File): string {
	return saisi.trim() || fichier.name.replace(/\.[^.]+$/, '');
}

/** Extensions produites par nos propres endpoints d'upload d'image. */
const EXTENSIONS_IMAGE = /\.(jpe?g|png|webp|gif|avif|bmp|tiff?)$/i;

/**
 * Préfixe technique posé par `nom_stocke` (api/app/utils/fichiers.py) :
 * 32 caractères hexadécimaux suivis d'un `_`. Il rend l'URL non devinable mais
 * n'a aucun sens pour un lecteur.
 */
const PREFIXE_UUID = /^[0-9a-f]{32}_/i;

/** Cette URL désigne-t-elle une image affichable en vignette ? */
export function estImage(url: string): boolean {
	return EXTENSIONS_IMAGE.test(url || '');
}

/**
 * Nom lisible d'une pièce jointe, déduit de son URL.
 *
 * Les fichiers téléversés avant le 03/08/2026 sont nommés `{uuid}.pdf` : le nom
 * d'origine n'était pas conservé, il n'y a rien à en tirer. Depuis, ils sont
 * nommés `{uuid}_{nom}.pdf` et le nom réapparaît.
 */
export function nomFichier(url: string): string {
	let base = (url || '').split('/').pop() || url || '';
	try {
		base = decodeURIComponent(base);
	} catch {
		/* URL mal encodée : on garde la forme brute plutôt que d'échouer */
	}
	return base.replace(PREFIXE_UUID, '') || base;
}

/**
 * Le TYPE d'un fichier, en trois lettres, tel qu'on l'affiche sur sa vignette.
 *
 * 🔴 Demandé le 11/09/2026 : « mettre une vignette nommée de la façon suivante
 * type de fichier: NOM (ex : PDF: MON NOM) ». Le type EST l'information la plus
 * utile d'une liste de pièces jointes — on cherche « le PDF », pas « le
 * cinquième ».
 *
 * ⚠️ Il vient de l'EXTENSION et non du type MIME : les listes de pièces jointes
 * ne portent que des URLs, le MIME n'y est plus. C'est aussi ce que l'œil lit.
 */
export function typeFichier(nomOuUrl: string): string {
	const nom = nomFichier(nomOuUrl);
	const point = nom.lastIndexOf('.');
	if (point <= 0) return 'FICHIER';
	const ext = nom.slice(point + 1).toUpperCase();
	//  Les familles bureautiques portent plusieurs extensions pour un même
	//  format : les ramener au nom que tout le monde emploie évite « XLSX » à
	//  côté de « XLS » pour deux tableurs.
	const FAMILLES: Record<string, string> = {
		JPEG: 'JPG',
		XLSX: 'EXCEL',
		XLS: 'EXCEL',
		DOCX: 'WORD',
		DOC: 'WORD',
		PPTX: 'POWERPOINT',
		PPT: 'POWERPOINT',
		TXT: 'TEXTE',
	};
	return FAMILLES[ext] ?? ext;
}

/**
 * Le nom SANS son extension — elle est déjà dite par le type, et la répéter
 * allonge la vignette pour rien (« PDF: contrat.pdf »).
 */
export function nomSansExtension(nomOuUrl: string): string {
	const nom = nomFichier(nomOuUrl);
	const point = nom.lastIndexOf('.');
	return point > 0 ? nom.slice(0, point) : nom;
}

/** Pièce jointe telle que la manipulent les formulaires (EvolForm, uploads). */
export interface PieceJointe {
	url: string;
	nom: string;
	type: 'image' | 'document';
}

/**
 * Liste d'URLs stockées → pièces jointes affichables.
 *
 * Trois pages construisaient cet objet à la main pour pré-remplir `EvolForm` en
 * mode édition, chacune avec sa propre copie du test d'image et du nom.
 */
export function fichiersDepuisUrls(urls: string[] | null | undefined): PieceJointe[] {
	return (urls ?? []).map((url) => ({
		url,
		nom: nomFichier(url),
		type: estImage(url) ? ('image' as const) : ('document' as const),
	}));
}

/** Sépare une liste d'URLs en photos (vignettes) et documents (liens). */
export function separerFichiers(urls: string[] | null | undefined): {
	photos: string[];
	documents: string[];
} {
	const liste = urls ?? [];
	return {
		photos: liste.filter(estImage),
		documents: liste.filter((u) => !estImage(u)),
	};
}

/**
 * Attacher des fichiers à une publication, un par un, dans l'ordre.
 *
 * Les deux chemins de `FormulaireActualite` faisaient la même boucle : celui qui
 * ajoute des documents à une publication existante, et celui qui téléverse ce
 * qui avait été retenu pendant la création (la publication n'ayant pas encore
 * d'identifiant au moment du choix). Extraite le 31/08/2026, sur refus de
 * modularité — et le contrôle désignait bien une duplication, pas une longueur.
 *
 * ⚠️ **Séquentiel, et c'est voulu** : l'API attribue son ordre d'affichage à
 * l'arrivée. Un `Promise.all` les remonterait dans un ordre imprévisible.
 *
 * Elle **laisse remonter** l'erreur : chaque appelant décide s'il la signale ou
 * s'il poursuit — ils n'en font pas la même chose, et c'est légitime.
 */
export interface DocumentAttache {
	id: number;
	titre?: string;
	fichier_nom?: string;
}

/**
 *  Attacher des fichiers à l'entité qui les porte, **une fois qu'elle existe**.
 *
 *  🔴 Elle s'appelait `attacherAPublication` et ne savait faire que cela
 *  (12/09/2026). Or le geste ne doit RIEN à la publication : c'est
 *  « enregistrer l'objet, puis lui attacher ce qui attendait ». Le contrat en
 *  avait besoin à l'identique, et le réécrire aurait donné la deuxième copie —
 *  celle qui diverge sur la gestion d'erreur ou sur l'ordre.
 *
 *  ⚠️ `cible` est le type de `#lib/api` : ajouter un rattachement côté API le
 *  rend disponible ici sans toucher à cette fonction.
 */
export async function attacherA(
	cible: CibleDocument,
	id: number,
	fichiers: Iterable<File>,
): Promise<DocumentAttache[]> {
	const { documents } = await import('#lib/api/documents.ts');
	const crees: DocumentAttache[] = [];
	for (const f of fichiers) {
		crees.push(await documents.uploadPour(cible, id, f.name, f));
	}
	return crees;
}

/**
 * Attacher des fichiers à un objet **qui vient d'être créé**, sans jamais faire
 * échouer cette création.
 *
 * ## Pourquoi (12/09/2026)
 *
 * Deux écrans écrivaient ce geste — les actualités (#531) et les contrats
 * (#921) — et **ils divergeaient déjà sur ce qui compte** :
 *
 * | | en cas d'échec |
 * |---|---|
 * | actualités | un `catch` vide, commenté « la publication existe » — **silence** |
 * | contrats | un message : « créé, mais un document n'a pas pu être joint » |
 *
 * 🔴 Le silence est le mauvais choix, et il ne se voit pas : l'objet apparaît
 * dans la liste, l'utilisateur croit son document joint, et rien ne l'a détrompé.
 * C'est la version **la plus disante** qui est retenue ici, pour les deux.
 *
 * ⚠️ L'échec n'est JAMAIS propagé : l'objet est bel et bien enregistré, et lever
 * ferait afficher « erreur » sur une création réussie. On dit ce qui manque, et
 * on s'arrête là.
 */
export async function attacherApres(
	cible: CibleDocument,
	id: number,
	fichiers: File[],
	objet: string,
): Promise<void> {
	if (!fichiers.length || !id) return;
	try {
		await attacherA(cible, id, fichiers);
	} catch {
		const { toast } = await import('#lib/components/Toast.svelte');
		toast('error', `${objet} — mais un document n’a pas pu être joint.`);
	}
}

/**
 * Remet un fichier PRODUIT par l'écran ou reçu du serveur au navigateur, qui le
 * télécharge sous `nom` — l'export de télémétrie, le PDF du Suivi des affaires.
 *
 * Écrit une fois le 16/10/2026 : le lien éphémère `blob:` vivait dans l'export de
 * télémétrie, et le PDF en demandait un second.
 */
export function enregistrerFichier(contenu: Blob, nom: string): void {
	const url = URL.createObjectURL(contenu);
	const a = document.createElement('a');
	a.href = url;
	a.download = nom;
	a.click();
	URL.revokeObjectURL(url);
}
