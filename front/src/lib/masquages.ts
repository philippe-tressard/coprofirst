import { masquages as masquagesApi } from '#lib/api/index.ts';
import { confirmerPuis } from '#lib/confirmation.ts';

/**
 * **Masquer ce que publie un autre résident** — pour soi seul (#2861).
 *
 * Le geste des magasins d'applications (« bloquer un utilisateur abusif »),
 * tranché le 17/11/2026 : rien n'est supprimé, rien n'est dit à l'autre, et le
 * masque se retire dans le Profil. La règle — ce qui se masque, qui ne se masque
 * pas — vit au serveur (`utils/masquage`) ; l'écran ne la redit pas, il propose
 * le geste là où le NOM de l'auteur s'affiche, et le serveur refuse avec son
 * motif ce qui ne se masque pas.
 *
 * Écrit une fois, comme `signaler` : la réponse, l'annonce et la suite d'une
 * affaire l'appellent.
 *
 * @param apres  Ce que l'écran fait quand le masque est posé (recharger sa liste).
 */
export async function masquer(auteurId: number, nom: string, apres?: () => void): Promise<void> {
	await confirmerPuis(
		{
			titre: `Masquer ce que publie ${nom} ?`,
			message:
				'Vous ne verrez plus ses annonces, ses réponses ni ses messages dans les affaires. ' +
				'Rien n’est supprimé, et cette personne n’en est pas avertie. ' +
				'Vous pourrez revenir sur ce choix dans votre profil.',
			libelleConfirmer: 'Masquer',
		},
		`Ce que publie ${nom} est masqué pour vous`,
		async () => {
			await masquagesApi.masquer(auteurId);
			apres?.();
		},
	);
}
