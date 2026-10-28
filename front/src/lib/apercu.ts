/**
 * Le geste **« voir avant d'envoyer »**, écrit une fois pour tous les écrans qui
 * diffusent (#498).
 *
 * ## Pourquoi un module et pas quelques lignes dans le formulaire
 *
 * Neuf formulaires cochent des canaux de diffusion (`CanauxNotification` en
 * porte huit, l'annonce de hall le neuvième). Écrire l'ouverture, le chargement
 * et les trois sorties dans chacun, c'est neuf états à tenir cohérents — et
 * `standards/02` §2 dit ce qui arrive ensuite.
 *
 * Il est né du garde-fou de modularité : l'aperçu ajoutait 77 lignes à
 * `FormulaireTicket.svelte`, déjà au-dessus de 500. Le contrôle a donc imposé
 * tout de suite la forme partagée qu'il aurait fallu écrire au deuxième écran.
 *
 * ## Ce qu'il ne fait PAS
 *
 * 🔴 Il ne compose rien. Le message est rendu **par le serveur**, avec les mêmes
 * fonctions que l'envoi. Un aperçu reconstruit côté écran deviendrait faux à la
 * première évolution d'un gabarit, et personne ne s'en apercevrait — puisque
 * c'est justement l'aperçu qu'on regarderait pour le vérifier (`standards/04` §14).
 *
 * ## Usage
 *
 * ```svelte
 * const apercu = creerApercu(() => ticketsApi.apercuDiffusion(brouillon));
 * // …
 * {#if $apercu.ouvert}
 *   <ApercuDiffusionModale apercu={$apercu.donnees} chargement={$apercu.chargement} … />
 * {/if}
 * ```
 */
import { writable, type Readable } from 'svelte/store';
import { type ApercuDiffusion } from '#lib/api/index.ts';
import { messageErreur } from '#lib/erreurs.ts';
import { toast } from '#lib/components/Toast.svelte';

export interface EtatApercu {
	ouvert: boolean;
	chargement: boolean;
	donnees: ApercuDiffusion | null;
}

export interface Apercu extends Readable<EtatApercu> {
	/** Demande la composition au serveur et ouvre la modale. */
	ouvrir: () => Promise<void>;
	/** Ferme sans rien envoyer — la saisie de l'appelant reste intacte. */
	fermer: () => void;
}

const VIDE: EtatApercu = { ouvert: false, chargement: false, donnees: null };

export function creerApercu(charger: () => Promise<ApercuDiffusion>): Apercu {
	const { subscribe, set } = writable<EtatApercu>({ ...VIDE });

	async function ouvrir() {
		set({ ouvert: true, chargement: true, donnees: null });
		try {
			set({ ouvert: true, chargement: false, donnees: await charger() });
		} catch (e) {
			//  🔴 Un aperçu indisponible ne BLOQUE pas la diffusion : l'objet reste
			//  le but, l'aperçu est un confort. On referme et on le dit, plutôt que
			//  de retenir l'utilisateur devant une modale vide dont il ne saurait
			//  pas quoi faire.
			set({ ...VIDE });
			toast('error', messageErreur(e, "Aperçu indisponible — l'envoi reste possible."));
		}
	}

	return { subscribe, ouvrir, fermer: () => set({ ...VIDE }) };
}
