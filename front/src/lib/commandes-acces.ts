/**
 * Accepter une commande de badge — un geste, écrit une fois (#1194, V3).
 *
 * Deux écrans acceptent une commande : l'administration et l'espace du conseil
 * syndical. Chacun appelait l'API à sa façon, et aucun ne posait le badge :
 * une commande acceptée ne créait rien, et le badge remis au résident
 * n'existait ni dans sa liste ni au parc.
 *
 * Le geste demande désormais les codes des badges remis, quand on les connaît :
 * le serveur les pose sur le lot commandé, et le demandeur en est porteur avec
 * les autres copropriétaires du lot. Laisser vide accepte sans rien créer.
 */
import { admin as adminApi } from '#lib/api/index.ts';
import { demander } from '#lib/saisie.ts';

/** Rend `false` si l'on renonce, `true` une fois la commande acceptée. */
export async function accepterCommandeAcces(id: number): Promise<boolean> {
	const saisie = await demander({
		titre: 'Accepter la commande',
		message:
			'Les codes des badges remis seront posés sur le lot commandé. Laissez vide si vous ne les connaissez pas encore.',
		libelle: 'Codes, séparés par des virgules',
		placeholder: '4521, 417D5927',
		libelleValider: 'Accepter',
		requis: false,
	});
	if (saisie === null) return false;
	const codes = saisie.split(/[,;\s]+/).filter(Boolean);
	await adminApi.traiterCommandeAcces(id, { action: 'accepter', codes });
	return true;
}

/** Refuser — le motif part au demandeur ; il vit ici avec l'acceptation. */
export const refuserCommandeAcces = (id: number, motif?: string) =>
	adminApi.traiterCommandeAcces(id, { action: 'refuser', motif_refus: motif });
