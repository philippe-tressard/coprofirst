/**
 * **L'aperçu de la pastille de lecture d'une SAISIE** — `POST /lectures/apercu`
 * (#2633), par le mécanisme commun `#lib/apercu-serveur` (délai, réponse périmée
 * ignorée, dernière phrase gardée pendant l'attente et hors ligne).
 */
import { lectures, type ApercuLecture, type SaisieLecture } from '#lib/api/index.ts';
import { apercuServi } from '#lib/apercu-serveur.ts';

export type { LireApercu } from '#lib/apercu-serveur.ts';

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

const servi = apercuServi<SaisieLecture, ApercuLecture>(lectures.apercu, cle);

/** `$apercuLecture(saisie, place)` — l'aperçu de cette saisie, ou le dernier montré. */
export const apercuLecture = servi.store;

/** L'aperçu de cette saisie, sans délai — pour un geste qui l'attend (l'alerte d'une correction). */
export const apercuImmediat = servi.immediat;
