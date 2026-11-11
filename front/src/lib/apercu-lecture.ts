/**
 * **L'aperçu de la pastille de lecture d'une SAISIE** — demandé au serveur (#2633).
 *
 * Arbitré le 11/11/2026 : le formulaire ne compose plus « qui la lira », il le
 * demande (`POST /lectures/apercu`), par la même règle que l'objet enregistré.
 * Les conditions de l'arbitrage, et où elles se tiennent :
 *
 * - **~150 ms après le dernier changement** (`DELAI_APERCU_MS`) : une rafale de
 *   cases cochées fait UNE demande ;
 * - **une réponse périmée est ignorée** : chaque réponse est rangée sous la
 *   saisie qui l'a demandée (`cle`), et l'écran ne lit que celle de sa saisie
 *   COURANTE — une réponse tardive pour un état déjà quitté ne la remplace pas ;
 * - **la phrase reste en place pendant l'attente**, sans clignoter : tant que la
 *   saisie courante n'a pas sa réponse, l'écran garde la dernière qu'il a montrée
 *   (`place`, une par usage à l'écran) — et hors ligne, il la garde aussi, sans
 *   bloquer la saisie.
 *
 * Le store vaut une FONCTION (`$apercuLecture(saisie, place)`) : un gabarit la
 * relit quand une réponse arrive, sans rien déclarer de plus.
 */
import { readable } from 'svelte/store';
import { lectures, type ApercuLecture, type SaisieLecture } from '#lib/api/index.ts';

export const DELAI_APERCU_MS = 150;

/** Les réponses, par saisie — une saisie déjà vue ne se redemande pas. */
const reponses = new Map<string, ApercuLecture>();
/** La dernière réponse MONTRÉE par chaque usage — ce qui reste pendant l'attente. */
const montrees = new Map<string, ApercuLecture>();
const enAttente = new Map<string, SaisieLecture>();
const enVol = new Set<string>();
let minuteur: ReturnType<typeof setTimeout> | undefined;
let publier: (lire: LireApercu) => void = () => {};

export type LireApercu = (saisie: SaisieLecture, place: string) => ApercuLecture | null;

/** La forme canonique d'une saisie : deux ordres de codes sont la même saisie. */
function cle(s: SaisieLecture): string {
	return JSON.stringify([
		s.categorie ?? null,
		s.statut ?? null,
		!!s.confidentiel,
		[...(s.public_cible ?? [])].sort(),
		[...(s.perimetre_cible ?? [])].sort(),
		!!s.reserve_perimetre,
	]);
}

async function envoyer() {
	const lot = [...enAttente];
	enAttente.clear();
	await Promise.all(
		lot.map(async ([c, saisie]) => {
			enVol.add(c);
			try {
				reponses.set(c, await lectures.apercu(saisie));
				publier(lire);
			} catch (erreur) {
				//  Hors ligne ou refusé : la dernière phrase montrée reste — la
				//  saisie n'est jamais bloquée par l'aperçu. Rien n'est affecté.
				console.warn('Aperçu de lecture indisponible', erreur);
			} finally {
				enVol.delete(c);
			}
		}),
	);
}

const lire: LireApercu = (saisie, place) => {
	const c = cle(saisie);
	const connue = reponses.get(c);
	if (connue) {
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

/** `$apercuLecture(saisie, place)` — l'aperçu de cette saisie, ou le dernier montré. */
export const apercuLecture = readable<LireApercu>(lire, (set) => {
	publier = (f) => set((saisie, place) => f(saisie, place));
	return () => {
		publier = () => {};
	};
});

/** L'aperçu de cette saisie, sans délai — pour un geste qui l'attend (l'alerte d'une correction). */
export async function apercuImmediat(saisie: SaisieLecture): Promise<ApercuLecture> {
	const c = cle(saisie);
	const connue = reponses.get(c);
	if (connue) return connue;
	const lue = await lectures.apercu(saisie);
	reponses.set(c, lue);
	return lue;
}
