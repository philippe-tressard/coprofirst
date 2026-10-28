//  Supprimer un `Document` de la bibliothèque — une écriture pour tous les écrans.
//
//  🔴 Elle vivait dans la page Résidence, qui l'avait déjà factorisée pour ses
//  trois sections (plan, règlement, CR d'AG). La carte d'une actualité en avait
//  besoin à son tour (#1178) : la recopier aurait refait la divergence que la
//  factorisation de Résidence avait retirée (« Plan supprimé » contre « Supprimé »).
//
//  Seul change ce qu'on retire de quelle liste : c'est le paramètre `retirer`.
//  Le serveur exige le conseil syndical ou l'admin (`require_cs_or_admin`).

import { documents as documentsApi } from '#lib/api/index.ts';
import { confirmerPuis, SUPPRESSION } from '#lib/confirmation.ts';

export async function supprimerDocument(
	id: number,
	quoi: string,
	retirer: (id: number) => unknown | Promise<unknown>,
) {
	await confirmerPuis(SUPPRESSION(quoi), 'Document supprimé', async () => {
		await documentsApi.delete(id);
		await retirer(id);
	});
}
