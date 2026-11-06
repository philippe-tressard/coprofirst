/**
 * **Rapprocher un membre de l'annuaire d'un inscrit et de son logement** — à
 * partir du NOM saisi dans sa fiche, en le DEMANDANT au serveur.
 *
 * ## 🔴 La règle a quitté le front (#2522, 05/11/2026)
 *
 * Ce module portait `inscritParNom` et `localisationParNom` : le nom saisi liait
 * la fiche à un inscrit et la localisait par le registre importé — l'appartement
 * l'emportant sur la cave et le parking. Le serveur ne le savait pas : l'app iOS,
 * qui ne recopie aucune règle du site, enregistrait un membre sans lien ni
 * logement, et la page chargeait trois listes (inscrits, lots, registre — l'une
 * des routes les plus lentes) pour un rapprochement fait dans le navigateur.
 *
 * La règle vit dans `utils/annuaire.rapprochement` ; le `PUT` l'applique à ce
 * qu'il reçoit, et l'écran la DEMANDE ici pour la montrer dès la frappe.
 */
import { annuaireAdmin, type Rapprochement } from '#lib/api/index.ts';

/** Le nom le plus court qui vaille une question — le serveur n'en cherche pas plus court. */
const NOM_MIN = 2;

/**
 * Une question par fiche, dont seule la DERNIÈRE réponse compte : la réponse
 * lente à « Ber » ne doit pas écraser celle de « Bernard ».
 *
 * `null` : pas de réponse à appliquer — nom trop court, réponse dépassée, ou
 * échec. ⚠️ Un échec ne se dit pas ici, et c'est voulu : le `PUT` refait le
 * rapprochement côté serveur, donc rien ne se perd — un toast à chaque lettre,
 * en revanche, couvrirait l'écran.
 */
export function rapprochementParNom(localiser: boolean) {
	let derniere = 0;
	return async (nom: string): Promise<Rapprochement | null> => {
		const numero = ++derniere;
		if (nom.trim().length < NOM_MIN) return null;
		try {
			const trouve = await annuaireAdmin.rapprocher(nom, localiser);
			return numero === derniere ? trouve : null;
		} catch {
			return null;
		}
	};
}
