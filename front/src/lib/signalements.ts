import { signalements as signalementsApi } from '#lib/api/index.ts';
import { tenter } from '#lib/erreurs.ts';
import { demander } from '#lib/saisie.ts';

/**
 * **Signaler un contenu au conseil syndical** — demander le motif, l'envoyer,
 * et le dire.
 *
 * ## Pourquoi (12/09/2026)
 *
 * Le geste était écrit **deux fois**, au caractère près, dans deux fichiers qui
 * n'ont rien d'autre en commun : `PageCommunaute` (annonces, idées, sondages de
 * la liste) et `sondages/[id]` (le détail d'un sondage). Même question posée à
 * l'utilisateur, même contrôle du motif vide, même envoi, même phrase de
 * confirmation.
 *
 * 🔴 Et elles avaient déjà commencé à diverger sur ce qui suit l'envoi : l'une
 * rechargeait la liste de modération du conseil syndical, l'autre non. C'est
 * précisément ce qui distingue les deux écrans — d'où le rappel `apres`, et
 * rien d'autre.
 *
 * ⚠️ Le motif est **obligatoire** : un signalement sans motif oblige le conseil
 * syndical à deviner ce qu'on lui reproche. Le formulaire le refuse, ce qui vaut
 * mieux que les deux `toast('error', 'Le motif est obligatoire')` d'origine —
 * ils arrivaient après coup, une fois la boîte refermée.
 *
 * @param apres  Ce que l'écran fait de son côté quand le signalement est parti
 *               (recharger sa liste de modération, par exemple).
 */
export async function signaler(
	cibleType: string,
	cibleId: number,
	apres?: () => void,
): Promise<void> {
	const motif = await demander({
		titre: 'Signaler au conseil syndical',
		message: 'Le motif sera transmis au conseil syndical, avec le contenu concerné.',
		libelle: 'Pourquoi signalez-vous ce contenu ?',
		placeholder: 'Propos déplacés, information fausse, publication en double…',
		libelleValider: 'Signaler',
	});
	if (motif === null) return;
	await tenter(async () => {
		await signalementsApi.creer(cibleType, cibleId, motif);
		apres?.();
	}, 'Signalement transmis au conseil syndical');
}
