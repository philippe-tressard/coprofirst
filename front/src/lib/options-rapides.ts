import { writable } from 'svelte/store';

import { tenter } from '#lib/erreurs.ts';

/**
 * **Le panneau d'options rapides d'une liste** — quel objet est ouvert, s'il
 * attend le serveur, et comment on enregistre.
 *
 * ## Pourquoi ce fichier (12/09/2026)
 *
 * Demandé à l'écran : *« si une publication a une option cochée, une icône
 * spécifique permet juste de changer cet état […] applique cette fonctionnalité
 * à tous les types de page qui ont la section Options de publication »*.
 *
 * Le chemin court existait sur **Actualités** seulement. L'étendre aux tickets
 * et aux événements demandait, dans chaque page, le même échafaudage : un état
 * « quel objet est ouvert », un drapeau d'attente, un `tenter` qui appelle,
 * recoud la liste et referme. Trois copies — et le contrôle de modularité a
 * refusé les trois, à raison : **la longueur cachait une duplication**.
 *
 * ⚠️ Ce module ne rend AUCUN balisage. Le bouton est `BoutonOptions`, le
 * panneau `PanneauOptionsPublication` ; ici vit seulement ce que trois pages
 * répétaient — l'état et le geste.
 *
 * ```ts
 * const options = optionsRapides<Ticket>();
 * // ouvrir depuis la carte :
 * options.ouvrir(t);
 * // enregistrer, en recousant la liste APRÈS la réponse :
 * options.enregistrer(
 * 	() => ticketsApi.update(t.id, data),
 * 	(maj) => (ticketList = ticketList.map((x) => (x.id === maj.id ? { ...x, ...maj } : x))),
 * );
 * ```
 */
export function optionsRapides<T extends { id: number }>() {
	/** L'objet dont le panneau est ouvert, ou `null`. */
	const ouvertId = writable<number | null>(null);
	/** Le panneau attend-il le serveur ? */
	const enCours = writable(false);

	return {
		ouvertId,
		enCours,
		ouvrir: (objet: T) => ouvertId.set(objet.id),
		fermer: () => ouvertId.set(null),
		/**
		 * Appelle le serveur, recoud la liste, referme.
		 *
		 * 🔴 **Dans cet ordre, et pas un autre.** Recoudre avant la réponse
		 * montrerait un état enregistré qui ne l'est pas — et le laisserait faux
		 * si la requête échoue. Le panneau reste alors ouvert, sur les valeurs que
		 * l'utilisateur venait de choisir : il n'a pas à les ressaisir.
		 */
		async enregistrer(appel: () => Promise<T>, recoudre: (maj: T) => void): Promise<void> {
			enCours.set(true);
			await tenter(async () => {
				recoudre(await appel());
				ouvertId.set(null);
			}, 'Options mises à jour');
			enCours.set(false);
		},
	};
}
