/**
 *  Comparer et transformer du texte français — écrit une fois.
 *
 *  ## Pourquoi ce module (18/09/2026)
 *
 *  Le dépliement Unicode qui retire les accents — `normalize('NFD')` suivi du
 *  retrait des signes combinants — était recopié **cinq fois** :
 *
 *  | Où | Pour quoi faire |
 *  |---|---|
 *  | `espace-cs` (`normalizeStr`) | rapprocher un membre d'un inscrit par son NOM |
 *  | `espace-cs` (`etageFromRaw`) | lire un étage saisi « 1ER » ou « 1er » |
 *  | `faq` (`normalizeText`) | chercher dans les questions sans se soucier des accents |
 *  | `OngletConsommations` | fabriquer le code d'un type de compteur |
 *  | `OngletPerimetres` | fabriquer le code d'un périmètre |
 *
 *  🔴 **Deux d'entre elles avaient déjà dérivé, sur la forme la plus fragile
 *  qui soit** : quatre écrivent la plage des signes combinants en échappements
 *  (la plage U+0300 à U+036F), la cinquième avec les caractères EUX-MÊMES —
 *  des accents flottants, invisibles dans un éditeur, qu'une conversion
 *  d'encodage ou un copier-coller suffit à perdre. Le jour où cette plage se
 *  vide, le code continue de tourner : il ne retire simplement plus rien, et
 *  « Périmètre » cesse de correspondre à « perimetre » sans qu'aucune erreur ne
 *  s'affiche. C'est `standards/02` §2 dans sa forme la plus discrète — des
 *  copies qui *ont l'air* identiques.
 *
 *  ## Deux notions, et elles ne se confondent pas
 *
 *  - **`replier`** rend la forme *comparable* d'un texte : on la calcule des
 *    deux côtés d'une comparaison, on ne l'affiche jamais et on ne la stocke
 *    jamais.
 *  - **`slug`** fabrique un *code* destiné à être stocké. Il est immuable une
 *    fois posé (un code de périmètre vit dans les contenus publiés), donc il ne
 *    se recalcule pas : ce module le produit au moment de la création, et plus
 *    jamais ensuite.
 *
 *  Les confondre reviendrait à comparer des textes avec des tirets à la place
 *  des espaces — ou à stocker un libellé en guise de code.
 *
 *  ⚠️ Ce module ne connaît ni les noms de personnes (`$lib/noms`) ni les étages
 *  (`$lib/utils`) : il ne sait que du texte. C'est ce qui lui permet de servir
 *  cinq appelants qui n'ont rien d'autre en commun.
 *
 *  Autotest : `node --experimental-strip-types scripts/check-texte.mjs --selftest`
 */

/**  La plage des signes diacritiques combinants, écrite en ÉCHAPPEMENTS.
 *
 *  🔴 Jamais avec les caractères eux-mêmes : ce sont des accents sans lettre
 *  porteuse, que rien ne rend visible dans un éditeur et qu'un changement
 *  d'encodage emporte en silence. La variante qui les écrivait ainsi vivait
 *  dans `OngletPerimetres` — elle fonctionnait, et c'est bien le problème :
 *  rien n'aurait signalé qu'elle a cessé.
 */
const SIGNES_COMBINANTS = /[\u0300-\u036f]/g;

/**
 *  Le texte sans ses accents, **casse et espaces conservés**.
 *
 *  À employer quand la casse porte un sens — la lecture d'un étage saisi
 *  « 1ER » ou « 1er » passe ensuite par `toUpperCase()`, pas par `replier`.
 */
export function sansAccents(texte: string | null | undefined): string {
	return (texte ?? '').normalize('NFD').replace(SIGNES_COMBINANTS, '');
}

/**
 *  La forme **comparable** d'un texte : sans accents, en minuscules, sans bords.
 *
 *  Elle se calcule des deux côtés de la comparaison — jamais d'un seul, sans
 *  quoi « Périmètre » ne rejoindrait jamais « perimetre ».
 */
export function replier(texte: string | null | undefined): string {
	return sansAccents(texte).toLowerCase().trim();
}

/**
 *  **Tous les mots de la recherche, n'importe où dans le texte** — sans accents
 *  ni casse, des deux côtés. La règle des affaires (`recherche_affaires.py`),
 *  appliquée à ce qu'un écran a déjà reçu. Une recherche vide laisse tout passer.
 *
 *  Écrite chez les prestataires (`correspondRecherche`) jusqu'au 23/10/2026 ;
 *  remontée ici quand les trois tableaux d'import ont reçu la leur (#2173) — une
 *  règle rangée chez un appelant est recopiée par le suivant (`standards/02`
 *  §4 sexies).
 *
 *  @param texte ce que la ligne MONTRE, morceaux déjà assemblés ou non.
 */
export function contientTousLesMots(
	texte: string | null | undefined | readonly (string | number | null | undefined)[],
	recherche: string | null | undefined,
): boolean {
	const mots = replier(recherche).split(/\s+/).filter(Boolean);
	if (!mots.length) return true;
	const cible = replier(
		Array.isArray(texte) ? texte.filter((m) => m != null && m !== '').join(' ') : (texte as string),
	);
	return mots.every((m) => cible.includes(m));
}

/**
 *  Le **code** d'un libellé : minuscules sans accents, tout le reste réduit au
 *  séparateur, sans séparateur aux bords.
 *
 *  @param separateur `-` pour un code de périmètre, `_` pour un type de
 *  compteur. Les deux existaient avant ce module, et la différence est
 *  volontaire : les codes déjà stockés ne se réécrivent pas.
 */
export function slug(texte: string | null | undefined, separateur: '-' | '_' = '-'): string {
	const bord = new RegExp(`^${separateur}|${separateur}$`, 'g');
	return replier(texte)
		.replace(/[^a-z0-9]+/g, separateur)
		.replace(bord, '');
}
