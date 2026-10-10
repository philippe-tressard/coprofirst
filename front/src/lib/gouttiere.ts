/**
 *  Ce qui CLASSE un objet, tel que la gouttière d'une carte l'écrit
 *  (`Gouttiere.svelte`) : pictogramme au trait, libellé entier (infobulle) et
 *  mot abrégé en petites capitales — il tient dans `--largeur-gouttiere`.
 *
 *  La page Affaires est devenue le standard du site le 10/10/2026 (#1819) : sa
 *  gouttière porte la date, puis la nature ; celle d'un contrat, son
 *  équipement ; d'un prestataire, sa catégorie ; d'une annonce, son type… Le
 *  type vit ici pour que chaque notion déclare son classement sans recopier sa
 *  forme.
 */
export type ClasseGouttiere = { icone: string; libelle: string; abrege: string };

/**  Le pictogramme et le mot abrégé d'une valeur — `[icone, abrege]`. */
export type MarqueGouttiere = readonly [icone: string, abrege: string];

/**  Le classement d'une valeur d'une table `{ val, label }`, avec ses marques de
 *   gouttière — `null` si la valeur est inconnue ou sans marque : ce que l'objet
 *   n'a pas ne s'invente pas. Le libellé entier est celui de la table, sans son
 *   émoji de tête. */
export function classeDe(
	table: readonly { val: string; label: string }[],
	marques: Readonly<Record<string, MarqueGouttiere>>,
	val: string | null | undefined,
): ClasseGouttiere | null {
	const t = table.find((x) => x.val === val);
	const m = val ? marques[val] : undefined;
	if (!t || !m) return null;
	return { icone: m[0], abrege: m[1], libelle: t.label.replace(/^[^\p{L}]+/u, '') };
}
