/**
 * Charger une donnée sans confondre « il n'y a rien » et « je n'ai pas pu voir ».
 *
 * ## Pourquoi (#519 puis #522)
 *
 * Le 19/08/2026, l'utilisateur signale : *« J'avais un sondage non terminé qui a
 * disparu ! »* et *« Il y avait 3 annonces non vendues ! à récupérer »*. Rien
 * n'était perdu — deux sondages et trois annonces dormaient en base pendant que
 * l'écran affichait « Aucun sondage » et « Aucune annonce ».
 *
 * La cause tenait en trois caractères : `.catch(() => [])`. Toute erreur —
 * session expirée, 500, réseau — devenait un tableau vide, et l'écran rendait
 * alors **exactement la même chose** que s'il n'y avait rien.
 *
 * 🔴 **Une sortie vide n'est pas un constat** (`standards/04` §1). La règle était
 * écrite pour les contrôles d'infrastructure ; elle vaut mot pour mot pour une
 * liste. Un écran qui affirme une absence qu'il n'a pas constatée provoque la
 * réaction qu'une perte réelle provoquerait — ici une demande de restauration,
 * avec au bout le risque d'écraser des données saines.
 *
 * ## Deux natures de donnée, deux remèdes — et c'est le cœur du sujet
 *
 * Le relevé de #522 a montré que les quinze appels fautifs ne se ressemblaient
 * pas. Les traiter pareil aurait été l'erreur que le ticket signalait
 * explicitement (*« ne pas convertir en masse sans regarder »*) :
 *
 * | Nature | Exemple | Remède |
 * |---|---|---|
 * | **Liste affichée** | les plans, les règlements, mes lots | `EtatListe` — l'échec passe AVANT le vide |
 * | **Donnée de référence** | la liste des bâtiments d'un `<select>`, la table des lots pour un rapprochement | `ChargementPartiel` — un bandeau, car un `<select>` vide et un `<select>` en échec ne se rendent pas de la même façon |
 *
 * Une donnée de référence manquante ne produit pas un écran vide : elle produit
 * un écran **subtilement faux** — des « Bât. ? » à la place des numéros, un
 * rapprochement automatique qui ne trouve rien. C'est plus discret qu'une liste
 * vide, donc plus durable.
 */
import { messageErreur } from '#lib/erreurs.ts';

/**
 * Attend une promesse et rend `[valeur, erreur]` — jamais l'un sans l'autre.
 *
 * ⚠️ Le repli est **obligatoire** et explicite. C'est ce qui distingue cette
 * fonction du `.catch(() => [])` qu'elle remplace : là, le repli était *tout*
 * ce qui restait ; ici, il est ce qu'on affiche **pendant** qu'on dit qu'on n'a
 * pas pu regarder.
 *
 * ```ts
 * const [plans, ePlans] = await essayer(documentsApi.list(id), []);
 * ```
 */
export async function essayer<T>(promesse: Promise<T>, repli: T): Promise<[T, string]> {
	try {
		return [await promesse, ''];
	} catch (e) {
		return [repli, messageErreur(e)];
	}
}

/**
 * Le message d'un chargement partiel, ou `''` si tout est arrivé.
 *
 * Prend les messages d'erreur des données de RÉFÉRENCE d'un écran et en fait la
 * phrase du bandeau. Rendre le premier message plutôt que de les concaténer :
 * quand plusieurs appels échouent, c'est presque toujours la même cause (session
 * expirée, serveur injoignable), et trois fois la même phrase se lit comme trois
 * pannes.
 */
export function messagePartiel(...erreurs: string[]): string {
	return erreurs.find((e) => e) ?? '';
}

/**
 * Le titre d'un paramétrage qu'on n'a pas pu lire — et dont on n'offre donc pas
 * l'enregistrement : un formulaire rempli de valeurs par défaut écraserait la
 * configuration réelle. Écrit une fois : la page Admin et la section de
 * réception des réponses le disent (#1475).
 */
export const TITRE_PARAMETRAGE_ILLISIBLE = 'Paramétrage illisible — rien n’a été modifié';
