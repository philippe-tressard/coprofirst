/**
 * La **teinte d'un périmètre** — quelle couleur porte sa pastille, et pourquoi
 * celle-là.
 *
 * ## La règle, telle qu'elle a été arbitrée (13/09/2026)
 *
 * > « La couleur des catégories de niveau *n* hérite de la catégorie de
 * >   niveau 1. »
 * > « Si plusieurs catégories de niveau 1 : mettre celle du bâtiment s'il n'y en
 * >   a qu'un, sinon celle de toute la copropriété. »
 *
 * Une pastille dit d'un coup d'œil **où ça se passe**. Tout ce qui vit sous
 * « Bât. 1 » porte la couleur du bâtiment 1 ; tout ce qui vit sous « Locaux
 * techniques » porte la sienne, et les deux sont **différentes**.
 *
 * ## 🔴 « Premier niveau » n'est PAS une profondeur — troisième correction
 *
 * Signalé à l'écran le 13/09/2026, après deux corrections qui n'avaient pas
 * tenu :
 *
 * > « Pourquoi la même couleur en périmètre niveau 1 : orange pour Bâtiment 1
 * >   **et** Locaux techniques › Local eau ? »
 *
 * Les deux versions précédentes comptaient les `parent` : niveau 0 la racine,
 * 1 ses enfants, etc. **L'arbre réel n'a pas cette forme.** `Bâtiments` est un
 * nœud d'ORGANISATION — on ne le cible pas, on choisit un bâtiment — tandis que
 * `Locaux techniques` est lui-même un espace de tête, que l'on cible. Compter
 * les parents mettait donc `bat:1` et `locaux-techniques/local-eau` au **même**
 * rang, et `locaux-techniques` au rang au-dessus : la rangée des « têtes »
 * comptait des dizaines d'entrées au lieu de dix, et le modulo de la palette
 * rendait les collisions certaines. Le local eau tombait sur la couleur du
 * bâtiment 1.
 *
 * 🔴 **La bonne définition existait déjà dans le dépôt** — `perimetresNiveau1`,
 * extraite de `PerimetrePicker` le 10/09 : *une racine sélectionnable, ou
 * l'enfant d'un regroupement racine*. C'est exactement la rangée que le
 * sélecteur affiche (Copropriété entière · Bât. 1-4 · Parking · AFUL · Espaces
 * verts · Cheminements · Locaux techniques). En écrire une seconde ici était la
 * duplication, et les deux ont divergé sur le seul cas qui comptait.
 *
 * Le prédicat vit donc **ici**, dans le module pur, et `arbre.ts` l'importe :
 * une seule notion de « tête », éprouvable sans navigateur.
 *
 * ## Pourquoi un module à part, sans aucun import `#lib`
 *
 * La règle est une décision PURE : elle ne lit ni store, ni API, ni DOM.
 * L'isoler ici la rend éprouvable par `npm run lint:teinte`, sans navigateur et
 * sans arborescence réelle — le motif du dépôt pour toute décision qu'on ne peut
 * pas voir à l'œil (`boot-role-guard.sh`, puis `listeDepliable.ts`).
 *
 * ⚠️ Aucun import de `#lib/…` ici, et ce n'est pas un oubli : le script de
 * self-test importe ce fichier par son chemin relatif, et un alias Vite ne se
 * résout pas sous `node --experimental-strip-types`.
 */

/**
 * Ce que la teinte a besoin de savoir d'un nœud — rien de plus.
 *
 * ⚠️ `selectionnable` en fait partie depuis le 13/09/2026 : c'est lui, et non la
 * profondeur, qui distingue un regroupement d'un espace de tête.
 */
export interface NoeudTeinte {
	code: string;
	parent: string | null;
	selectionnable: boolean;
}

/**
 * Couleur DÉRIVÉE du code : la table de sept clés en dur laissait en gris tout
 * périmètre créé depuis l'administration, et tout bâtiment au-delà du quatrième.
 *
 * ⚠️ **Elle doit rester plus longue que la rangée des têtes.** Le seed en pose
 * dix (Copropriété entière, quatre bâtiments, Parking, AFUL, Espaces verts,
 * Cheminements, Locaux techniques) ; à neuf couleurs, la dixième reprenait la
 * première — et c'est ainsi que « Local eau » a porté la couleur du bâtiment 1.
 * Les quatre dernières sont la marge dont dispose l'administration avant que le
 * modulo ne recommence à confondre deux espaces.
 */
export const PALETTE_PERIMETRE = [
	'#ef4444',
	'#3b82f6',
	'#22c55e',
	'#f59e0b',
	'#f97316',
	'#8b5cf6',
	'#ec4899',
	'#0ea5e9',
	'#14b8a6',
	'#84cc16',
	'#e11d48',
	'#6366f1',
	'#a16207',
];

/**
 * La couleur de « toute la copropriété » — le repli de ce qu'on ne sait pas
 * rattacher à UN espace de tête.
 *
 * ⚠️ Hors palette, et volontairement : c'est un gris neutre. Reprendre une
 * couleur de la palette ferait passer « non rattaché » pour « rattaché à ce
 * bâtiment-là », ce qui est exactement le défaut qu'on corrige. C'est déjà le
 * gris que porte la pastille « 🏘️ Copropriété » du périmètre par défaut.
 */
export const TEINTE_COPROPRIETE = '#6b7280';

/**  La même normalisation que l'arbre : un code se compare **sans casse ni
 *   espaces**. Sans elle, « Bat:1 » et « bat:1 » seraient deux périmètres. */
const cle = (code: string) => (code ?? '').trim().toLowerCase();

/**
 * Le premier segment d'un code — « bât. 1/ascenseur » → « bât. 1 ».
 *
 * 🔴 LE CODE PORTE LUI-MÊME LA HIÉRARCHIE, et c'est ce qui sauve l'affichage
 * quand l'arbre ne répond pas (13/09/2026). Les codes administrés s'écrivent en
 * chemin — `locaux-techniques/local-eau`, `cheminements/portillon` — parce que
 * l'écran de création compose `parent + "/" + slug`.
 *
 * ⚠️ C'est un REPLI, pas la règle : l'arbre reste la source, parce qu'un code
 * peut être plat (`aful`, `parking`) tout en ayant un parent. Mais quand il ne
 * répond pas — cache pas encore rempli, nœud supprimé cité par un contenu
 * ancien — le premier segment est infiniment mieux que rien : deux branches
 * distinctes gardent deux couleurs distinctes.
 */
const premierSegment = (code: string) => (code ?? '').split('/')[0] || code;

/**
 * Un nœud d'**organisation** : une racine qu'on ne cible pas (« Bâtiments »,
 * « Cave »).
 *
 * 🔴 C'est LA notion qui définit le premier niveau, et elle ne se déduit pas
 * d'une profondeur. `Bâtiments` est une racine comme `Locaux techniques`, mais
 * l'une se choisit et l'autre pas : le sélecteur remonte donc les bâtiments dans
 * la première rangée et laisse les locaux techniques dans la leur. Deux formes
 * d'arbre, un seul niveau visible.
 *
 * ⚠️ Même définition que `perimetresNiveau1` (`#lib/perimetres/arbre`), qui
 * l'importe d'ici : ce qui fait une pastille de tête à la SAISIE est exactement
 * ce qui donne sa couleur à la LECTURE. Les deux ont divergé tant qu'elles
 * étaient écrites deux fois, et l'écran l'a montré.
 */
export function estRegroupement(n: NoeudTeinte | undefined): boolean {
	return !!n && n.parent === null && !n.selectionnable;
}

/**
 * Le code qui DONNE la couleur : l'espace de **tête** dont le nœud dépend — le
 * bâtiment, le parking, les locaux techniques.
 *
 * On remonte tant que le parent existe **et n'est pas un regroupement** : le
 * regroupement n'est pas une destination, il ne peut donc pas porter de couleur
 * (tous les bâtiments auraient la même).
 *
 * ⚠️ Repli sur le premier segment du code quand l'arbre n'est pas chargé : la
 * pastille garde une couleur stable et se corrigera au chargement, même choix
 * que `perimetreDuBatiment`.
 *
 * ⚠️ Borné par `vus` : un cycle écrit en base ne doit pas figer l'écran.
 */
export function codeDeTeinte(
	code: string,
	lire: (code: string) => NoeudTeinte | undefined,
): string {
	let n = lire(code);
	//  🔴 L'arbre ne connaît pas ce code — cache pas encore rempli, ou périmètre
	//  supprimé cité par un contenu ancien. Le code porte alors sa propre
	//  hiérarchie : « bât. 1/ascenseur » donne « bât. 1 », et deux branches
	//  distinctes gardent deux couleurs distinctes.
	//
	//  ⚠️ Rendre le code ENTIER ici était le défaut du 13/09 : toutes les
	//  pastilles retombaient alors sur le même repli, et l'écran perdait ses
	//  couleurs par bâtiment.
	if (!n) return premierSegment(code);
	const vus = new Set<string>();
	while (n.parent && !vus.has(cle(n.code))) {
		vus.add(cle(n.code));
		const parent = lire(n.parent);
		if (!parent || estRegroupement(parent)) break;
		n = parent;
	}
	return n.code;
}

/**
 * Les codes de **premier niveau** d'une liste de nœuds, dans son ordre — la
 * rangée de têtes.
 *
 * 🔴 Un nœud de tête est une **racine sélectionnable**, ou l'**enfant d'un
 * regroupement racine**. Ce n'est pas une profondeur : voir `estRegroupement`.
 *
 * ⚠️ Un regroupement n'en fait jamais partie, même si rien ne vit dessous : il
 * n'est pas une cible, donc pas un endroit, donc pas une couleur.
 */
export function premierNiveauDe(
	codes: readonly string[],
	lire: (code: string) => NoeudTeinte | undefined,
): string[] {
	return codes.filter((c) => {
		const n = lire(c);
		if (!n || !n.selectionnable) return false;
		return n.parent === null || estRegroupement(lire(n.parent));
	});
}

/**
 * Le RANG d'un code parmi les nœuds de premier niveau, ou `-1` s'il n'en est pas.
 *
 * ⚠️ Comparaison par `cle()` — sans casse ni espaces, comme l'arbre. Une
 * comparaison stricte rendrait `-1` sur une simple différence de casse, et le
 * code retomberait sur le repli sans que rien ne le dise.
 */
export function rangPremierNiveau(code: string, premierNiveau: readonly string[]): number {
	return premierNiveau.findIndex((c) => cle(c) === cle(code));
}

/**
 * La couleur d'un code, une fois la teinte choisie.
 *
 * 🔴 **Par RANG, pas par condensat.** Un condensat réparti sur treize couleurs
 * collisionne dès le cinquième nœud (paradoxe des anniversaires). Deux espaces
 * de premier niveau tombaient donc régulièrement sur la même teinte, et la
 * pastille disait « même endroit » de deux lieux sans rapport — l'inverse exact
 * de ce qu'elle existe pour dire.
 *
 * Le rang garantit **N couleurs distinctes pour les N premiers**. Au-delà de la
 * palette, la collision est inévitable : treize couleurs ne peuvent pas en
 * distinguer quatorze. C'est pourquoi la palette doit rester plus longue que la
 * rangée des têtes — à neuf pour dix têtes, « Local eau » reprenait la couleur
 * du bâtiment 1 (13/09/2026).
 *
 * ⚠️ **Rang inconnu → un condensat du code de tête**, pas le gris de la
 * copropriété. La version du 13/09 rendait le gris dans ce cas, et l'écran a
 * perdu TOUTES ses couleurs par bâtiment d'un coup : quand l'arbre ne répond
 * pas, le rang est inconnu pour tout le monde, et un repli unique repeint la
 * page entière.
 *
 * Le condensat porte alors sur le **code de tête** — « bât. 1 » et non « bât.
 * 1/ascenseur » —, si bien que l'héritage tient même sans arbre.
 *
 * ⚠️ Le gris de la copropriété reste pour ce qui n'a **aucun** code de tête —
 * une chaîne vide. Il ne peut pas se confondre avec un bâtiment : il n'est pas
 * dans la palette.
 *
 * @param rang  L'index du code parmi les nœuds de premier niveau, ou `-1`.
 */
export function teinteDuCode(base: string, rang = -1): string {
	if (rang >= 0) return PALETTE_PERIMETRE[rang % PALETTE_PERIMETRE.length];
	const tete = premierSegment(base);
	if (!tete) return TEINTE_COPROPRIETE;
	let s = 0;
	for (let i = 0; i < tete.length; i++) s = (s * 31 + tete.charCodeAt(i)) >>> 0;
	return PALETTE_PERIMETRE[s % PALETTE_PERIMETRE.length];
}
