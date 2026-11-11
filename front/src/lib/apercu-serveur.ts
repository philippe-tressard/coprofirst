/**
 * **L'aperçu d'une SAISIE, demandé au serveur** — le mécanisme commun (#2633).
 *
 * Arbitré le 11/11/2026 : un formulaire ne compose plus une règle d'affichage
 * sur ce qu'on saisit (« qui la lira », le lieu choisi), il la demande au serveur,
 * qui applique la règle de l'objet enregistré. Les conditions de l'arbitrage :
 *
 * - **~150 ms après le dernier changement** (`DELAI_APERCU_MS`) : une rafale de
 *   choix fait UNE demande ;
 * - **une réponse périmée est ignorée** : chaque réponse est rangée sous la
 *   saisie qui l'a demandée (sa `cle`), et l'écran ne lit que celle de sa saisie
 *   COURANTE — une réponse tardive pour un état quitté ne la remplace pas ;
 * - **la phrase reste en place pendant l'attente**, sans clignoter : tant que la
 *   saisie courante n'a pas sa réponse, l'écran garde la dernière qu'il a montrée
 *   (`place`, une par usage à l'écran) — et hors ligne aussi, sans bloquer la saisie.
 *
 * Le store vaut une FONCTION (`$apercu(saisie, place)`) : un gabarit la relit quand
 * une réponse arrive, sans rien déclarer de plus. Deux aperçus l'emploient :
 * `#lib/apercu-lecture` (la pastille) et `#lib/apercu-perimetre` (le lieu).
 */
import { readable, type Readable } from 'svelte/store';

export const DELAI_APERCU_MS = 150;

export type LireApercu<S, R> = (saisie: S, place: string) => R | null;

export interface ApercuServi<S, R> {
	/** `$store(saisie, place)` — la réponse de cette saisie, ou la dernière montrée. */
	store: Readable<LireApercu<S, R>>;
	/** La réponse de cette saisie, sans délai — pour un geste qui l'attend. */
	immediat: (saisie: S) => Promise<R>;
}

/** Un aperçu servi : `demander` interroge le serveur, `cle` dit quand deux saisies sont la même. */
export function apercuServi<S, R>(
	demander: (saisie: S) => Promise<R>,
	cle: (saisie: S) => string,
): ApercuServi<S, R> {
	const reponses = new Map<string, R>();
	const montrees = new Map<string, R>();
	const enAttente = new Map<string, S>();
	const enVol = new Set<string>();
	let minuteur: ReturnType<typeof setTimeout> | undefined;
	let publier: (lire: LireApercu<S, R>) => void = () => {};

	async function envoyer() {
		const lot = [...enAttente];
		enAttente.clear();
		await Promise.all(
			lot.map(async ([c, saisie]) => {
				enVol.add(c);
				try {
					reponses.set(c, await demander(saisie));
					publier(lire);
				} catch (erreur) {
					//  Hors ligne ou refusé : la dernière réponse montrée reste — la
					//  saisie n'est jamais bloquée par l'aperçu. Rien n'est affecté.
					console.warn('Aperçu du serveur indisponible', erreur);
				} finally {
					enVol.delete(c);
				}
			}),
		);
	}

	const lire: LireApercu<S, R> = (saisie, place) => {
		const c = cle(saisie);
		const connue = reponses.get(c);
		if (connue !== undefined) {
			montrees.set(place, connue);
			return connue;
		}
		if (typeof window !== 'undefined' && !enVol.has(c)) {
			enAttente.set(c, saisie);
			clearTimeout(minuteur);
			minuteur = setTimeout(envoyer, DELAI_APERCU_MS);
		}
		return montrees.get(place) ?? null;
	};

	const store = readable<LireApercu<S, R>>(lire, (set) => {
		publier = (f) => set((saisie, place) => f(saisie, place));
		return () => {
			publier = () => {};
		};
	});

	async function immediat(saisie: S): Promise<R> {
		const c = cle(saisie);
		const connue = reponses.get(c);
		if (connue !== undefined) return connue;
		const lue = await demander(saisie);
		reponses.set(c, lue);
		return lue;
	}

	return { store, immediat };
}
