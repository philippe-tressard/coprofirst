/**
 * La pastille de lecture d'un objet ENREGISTRÉ — une affaire, et depuis #1373
 * une petite annonce, une idée ou un sondage — `#lib/lecture` appliqué à lui.
 *
 * Séparé de `#lib/lecture` pour une seule raison : trancher « le périmètre
 * est-il restreint ? » demande l'ARBRE des périmètres, un état chargé à
 * l'exécution que le contrôle `lint:lecture` n'a pas. Le calcul reste pur
 * là-bas ; ici, on ne fait que lui fournir ses entrées.
 */
import { concerneTous } from '#lib/perimetres/index.ts';
import {
	destinatairesParDefaut,
	lectureCiblee,
	lectureDe,
	type EntreeLecture,
	type Lecture,
} from '#lib/lecture.ts';
import { estActualite } from '#lib/tickets.ts';
import type { Ticket } from '#lib/api/index.ts';

/** Ce que le FORMULAIRE sait de la nature — la pastille de sa section. */
export type NatureLue = {
	actualite: boolean;
	categorie?: string;
	/** Une Étude & travaux sort du conseil en AG (standard du 30/09/2026). */
	statut?: string;
};

/**
 * Le périmètre vise-t-il MOINS que la copropriété ? Miroir de
 * `a_portee_globale` côté serveur — la même question que la case 🔒 pose
 * (`CaseReservePerimetre`). Vide = aucune restriction, comme au serveur.
 */
export function perimetreRestreint(perimetre: string[] | null | undefined): boolean {
	return !!perimetre && perimetre.length > 0 && !concerneTous(perimetre);
}

/**  Ce qui décide de la lecture d'une affaire, hors de ses choix — d'un objet
 *   enregistré comme d'une saisie en cours (`FormulaireTicket`). */
export function natureLue(s: { categorie?: string | null; statut?: string | null }): NatureLue {
	return {
		actualite: estActualite(s),
		categorie: s.categorie ?? undefined,
		statut: s.statut ?? undefined,
	};
}

/**  Les Destinataires qu'une Suite présélectionne sur une AFFAIRE sans choix
 *   du conseil (#1343), selon l'état qu'elle lui donne — une Étude & travaux
 *   mise en AG s'ouvre aux copropriétaires (standard du 30/09/2026) ; `null`
 *   pour une actualité, qui a les siens. */
export function destinatairesParDefautDuTicket(t: Ticket): ((statut: string) => string[]) | null {
	return estActualite(t)
		? null
		: (statut) => destinatairesParDefaut(natureLue({ ...t, statut: statut || t.statut }));
}

/**  Personne d'autre que le conseil — et l'auteur — ne la lit : rien ne sort,
 *   ni sur le groupe ni au hall. Cochée « Confidentielle », Destinataires =
 *   Conseil syndical seul, ou fermée par sa catégorie sans choix du conseil
 *   (#1436). Miroir de `reservee_au_conseil`, qui seul décide. */
export function lueDuSeulConseil(
	categorie: string | null | undefined,
	statut: string | null | undefined,
	confidentiel: boolean,
	publicCible: EntreeLecture['publicCible'],
): boolean {
	const nature = natureLue({ categorie, statut });
	return (
		lectureDe({
			...nature,
			confidentiel,
			publicCible,
			perimetreRestreint: false,
			reservePerimetre: false,
		}).profils.length === 0
	);
}

export function ticketLuDuSeulConseil(t: Ticket): boolean {
	return lectureDuTicket(t).profils.length === 0;
}

/**  Ce que la pastille LIT d'une affaire — une `Ticket` entière, ou une affaire
 *   du Suivi des affaires (`AffaireOuverte`, #2089), qui n'en porte que ceci. */
export type ChampsLecture = Pick<
	Ticket,
	'categorie' | 'statut' | 'confidentiel' | 'public_cible' | 'perimetre_cible' | 'reserve_perimetre'
>;

export function lectureDuTicket(t: ChampsLecture): Lecture {
	return lectureDe({
		...natureLue(t),
		confidentiel: t.confidentiel === true,
		publicCible: t.public_cible,
		perimetreRestreint: perimetreRestreint(t.perimetre_cible),
		reservePerimetre: t.reserve_perimetre === true,
	});
}

/** Ce qu'une annonce, une idée ou un sondage dit de ses lecteurs. */
export type ObjetCible = {
	public_cible?: string[] | string | null;
	perimetre_cible?: string[] | null;
};

/**  Qui lit cet objet ciblé (#1373) — la règle `cible_visible`, qui restreint
 *   toujours au périmètre. */
export function lectureDuCiblage(o: ObjetCible, masculin = false): Lecture {
	return lectureCiblee({
		publicCible: o.public_cible,
		perimetreRestreint: perimetreRestreint(o.perimetre_cible),
		masculin,
	});
}
