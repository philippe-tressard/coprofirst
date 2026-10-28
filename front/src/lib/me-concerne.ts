/**
 * La pastille « Ce qui me concerne » des listes d'affaires et du fil (#2215).
 *
 * 🔴 Elle FILTRE ce que la liste montre déjà : le serveur n'envoie que ce que le
 * lecteur a le droit de lire, et pose sur chaque élément `me_concerne` — la règle
 * de l'accès elle-même (`visibility.concerne`). Rien n'est recomposé ici : ni
 * bâtiment, ni circulation, ni arbre. Un élément sans lieu (`null`) s'adresse à
 * toute la copropriété, et reste.
 *
 * Elle ne s'offre que s'il y a de quoi filtrer : « mes périmètres » vides (un
 * compte sans rattachement ni lot), elle se tait.
 */
import { lots, type MesPerimetres } from '#lib/api/patrimoine.ts';

/** La valeur de la pastille retenue ; `''` = tout. */
export const ME_CONCERNE = 'moi';
export const OPTIONS_PORTEE = [{ val: ME_CONCERNE, label: 'Ce qui me concerne' }] as const;

export function aDeQuoiFiltrer(mes: MesPerimetres | null): boolean {
	return !!mes && (mes.batiments.length > 0 || mes.desservis.length > 0);
}

/** Garde ce qui me concerne quand la pastille est retenue — et tout sinon. */
export function selonPortee<T extends { me_concerne?: boolean | null }>(
	elements: T[],
	portee: string,
): T[] {
	return portee === ME_CONCERNE ? elements.filter((e) => e.me_concerne !== false) : elements;
}

/** La pastille est-elle à offrir ? Une lecture qui échoue la tait, sans gêner la liste. */
export async function offrirLaPastille(): Promise<boolean> {
	try {
		return aDeQuoiFiltrer(await lots.mesPerimetres());
	} catch {
		return false;
	}
}
