/**
 * Traduire une erreur d'appel API en une phrase **actionnable** pour l'écran.
 *
 * ## Pourquoi (#519)
 *
 * Trois listes de la Communauté portaient `.catch(() => [])` : toute erreur
 * devenait un tableau vide, et l'écran affichait « Aucun sondage » — le même
 * rendu que s'il n'y avait rien. L'utilisateur a cru ses données détruites.
 *
 * Distinguer l'échec du vide ne suffit pas : encore faut-il **dire quoi faire**.
 * « Une erreur est survenue » n'est pas plus actionnable que « aucun sondage » ;
 * « votre session a expiré, rechargez la page » l'est.
 *
 * ⚠️ Écrit ici et non dans une page : tout écran qui charge une liste en a
 * besoin, et #515 va en demander sur sept pages. Une copie par écran divergerait
 * au premier message ajusté.
 */
import { ApiError, CHEMINS_SANS_RENOUVELLEMENT } from '#lib/api/index.ts';
import { toast } from '#lib/components/Toast.svelte';

/**
 *  @param repli  Ce qu'on dit quand l'erreur n'est PAS une réponse du serveur
 *                — réseau coupé, serveur injoignable. Ajouté le 12/09/2026 :
 *                quarante-cinq des cent vingt-sept copies manuelles portaient
 *                un repli contextuel (« Impossible de charger vos lots »), qui
 *                vaut mieux qu'une phrase générique et qu'on aurait perdu en
 *                les factorisant.
 */
export function messageErreur(e: unknown, repli?: string): string {
	if (e instanceof ApiError) {
		//  401 : le cas le plus fréquent, et le seul que l'utilisateur peut régler
		//  lui-même. Le nommer évite de chercher une panne qui n'existe pas.
		if (e.status === 401) {
			//  🔴 Un 401 ne veut pas dire la même chose partout (18/09/2026).
			//
			//  Sur `/auth/login`, il signifie « identifiants refusés » et le
			//  serveur l'explique ; ailleurs, « cette session n'est plus valide ».
			//  Répondre « votre session a expiré » à qui vient de se tromper de
			//  mot de passe est faux, et c'est pour cela que trois écrans
			//  d'authentification gardaient leur propre ternaire : le message
			//  partagé les aurait dégradés.
			//
			//  La liste n'est pas réécrite ici : c'est celle qui gouverne déjà le
			//  renouvellement (`#lib/api/client.ts`). Une seule liste, deux
			//  usages — et `lint:session` la surveille.
			if (e.chemin && CHEMINS_SANS_RENOUVELLEMENT.includes(e.chemin))
				return e.message || 'Identifiants refusés.';
			//  Le cas le plus fréquent, et le seul que l'utilisateur peut régler
			//  lui-même. Le nommer évite de chercher une panne qui n'existe pas.
			return 'Votre session a expiré — rechargez la page pour vous reconnecter.';
		}
		//  403 : le serveur a répondu et refuse. Son message est plus précis que
		//  tout ce qu'on pourrait écrire ici (accès suspendu, profil non autorisé).
		if (e.status === 403) return e.message || 'Vous n’avez pas accès à cette rubrique.';
		return e.message || 'Le serveur n’a pas répondu correctement.';
	}
	//  Ni ApiError ni rien de connu : réseau coupé, serveur injoignable.
	return repli ?? 'Impossible de joindre le serveur — vérifiez votre connexion.';
}

/**
 * **Tenter un geste, et dire ce qui s'est passé** — `try` / `toast` / `catch`,
 * écrit une fois.
 *
 * ```ts
 * submitting = true;
 * await tenter(async () => {
 * 	await prestApi.create(payload);
 * 	prestataires = await prestApi.list();
 * }, 'Prestataire ajouté');
 * submitting = false;
 * ```
 *
 * ## Pourquoi (12/09/2026)
 *
 * Le bloc `try { … toast('success') } catch (e) { toast('error', e instanceof
 * ApiError ? e.message : 'Erreur') }` est écrit **127 fois dans 41 fichiers**.
 * Quatre-vingt-deux de ces copies retombent sur le mot « Erreur », qui
 * n'apprend rien — alors que `messageErreur` sait dire *« votre session a
 * expiré, rechargez la page »*.
 *
 * 🔴 Ce n'est pas une duplication cosmétique : c'est **la même information
 * perdue 82 fois**. Le serveur explique pourquoi il refuse — un quota, un
 * document encore référencé, une session morte — et l'écran répond « Erreur ».
 *
 * ⚠️ Le drapeau d'attente reste chez l'appelant. Le passer ici demanderait une
 * référence que Svelte ne donne pas, et le rendre obligerait les appelants à
 * l'écrire pareil — ils ne le nomment pas pareil (`submitting`,
 * `notationSaving`, `envoi`), et ce n'est pas un défaut : ils n'en ont pas le
 * même nombre.
 *
 * @param repli  Ce qu'on dit quand l'erreur n'est PAS une réponse du serveur —
 *               réseau coupé, serveur injoignable. Quarante-quatre des copies
 *               manuelles en portaient un, contextuel (« Chargement impossible »,
 *               « Erreur upload ») : le paramètre existe pour qu'aucune ne se
 *               perde à la conversion. Sans lui, factoriser aurait DÉGRADÉ le
 *               message dans ces quarante-quatre cas — une factorisation qui
 *               appauvrit le rendu n'est pas une factorisation, c'est un
 *               nivellement.
 *
 * @returns `true` si le geste a abouti.
 */
export async function tenter(
	action: () => Promise<unknown>,
	succes?: string,
	repli?: string,
): Promise<boolean> {
	try {
		await action();
		if (succes) toast('success', succes);
		return true;
	} catch (e) {
		toast('error', messageErreur(e, repli));
		return false;
	}
}

/**
 * Vrai quand l'échec CONSTATE une absence : le serveur a répondu 404.
 *
 * 🔴 « Introuvable » et « illisible » ne sont pas la même chose (#816). Un 500,
 * une session expirée ou une coupure réseau n'ont rien constaté : les rendre
 * comme une absence affiche un écran vide — et un formulaire vide, enregistré,
 * écrase ce qu'il n'a pas pu lire (fiche de la copropriété, #1459).
 */
export function estAbsent(e: unknown): boolean {
	return e instanceof ApiError && e.status === 404;
}
