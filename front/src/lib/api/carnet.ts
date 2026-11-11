//  Le CARNET D'ENTRETIEN — ses entrées, ses groupes, son bilan, et le client qui
//  les lit. Sorti de `patrimoine.ts` le 11/11/2026 (#2633) : le fichier passait
//  les 500 lignes, et le carnet est une notion à part (une VUE sur trois tables,
//  `api/app/routers/carnet.py`). `index.ts` réexporte tout : la surface publique
//  ne bouge pas.
import { api } from './client';
import type { ExerciceLu, ResumeAffaires, SyntheseAffaire } from './synthese';

/**  Une entrée du carnet d'entretien — un fait daté qui concerne le bâti.
 *
 *   `equipement` porte le CODE d'un équipement (`'ascenseur'`), pas son
 *   libellé : celui-ci vient du cache des équipements (`#lib/equipements`),
 *   administrés depuis #2442.
 */
export interface EntreeCarnet {
	date: string;
	libelle: string;
	origine: 'contrat' | 'intervention' | 'affaire';
	detail: string;
	/**  Le n° d'une affaire (`TK-109008`) — le pied de la carte le dit, comme celui
	 *   d'une carte d'affaire. Vide pour un contrat ou une intervention. */
	numero?: string | null;
	/**  La VALEUR de la catégorie d'une affaire — l'écran rend son libellé. */
	categorie?: string | null;
	/**  Son libellé (« Panne ») — `""` sans catégorie (#2505). */
	categorie_libelle: string;
	equipement: string | null;
	/**  Les codes de périmètre de la ligne — rendus par `perimetreLabel`, comme
	 *   partout ailleurs. Remplace `batiment_id` : un contrat sur « Parking » n'a
	 *   pas de bâtiment, et n'en est pas moins situé. */
	perimetre: string[];
	/**  La portée en clair, toujours dite — servie (#2505). */
	perimetre_libelle: string;
	lien: string;
	alerte: string | null;
	/**  La synthèse VALIDÉE de l'affaire (#1643) — rendue dans la partie pliée. */
	synthese?: SyntheseAffaire | null;
	/**  L'aperçu de la carte, en HTML riche : « Ce qui s'est passé » d'une synthèse
	 *   validée, sinon la demande de l'affaire ; vide pour un contrat. Le choix est
	 *   fait par le serveur (`carnet_entretien._joindre_syntheses`). */
	extrait: string;
}

/**  Les entrées d'un équipement, dans l'ordre où l'écran les montre. */
export interface GroupeCarnet {
	equipement: string | null;
	/** Le libellé administré de l'équipement, « Sans équipement rattaché » sinon. */
	equipement_libelle: string;
	entrees: EntreeCarnet[];
}

/**  Le carnet — `routers/carnet.CarnetLu`. Le filtre par année, les années
 *   proposées et le regroupement par équipement sont SERVIS (#2505,
 *   `utils/carnet_affichage`) : le site et l'app iOS les lisent. */
export interface Carnet {
	/** Du fait le plus récent au plus ancien, filtrées par l'année demandée. */
	entrees: EntreeCarnet[];
	total: number;
	/** Les mêmes, rangées par équipement, le groupe le plus récent d'abord. */
	groupes: GroupeCarnet[];
	/** Les années qu'on peut choisir, la plus récente d'abord. */
	annees: string[];
}

/**  Un intervenant et la durée moyenne de son étape « Chez le prestataire ». */
export interface PrestataireLent {
	prestataire_id: number;
	nom: string;
	jours: number;
	nombre: number;
}

/**  Les moyennes d'une catégorie d'affaire du carnet sur l'exercice. */
export interface CategorieBilan extends ResumeAffaires {
	categorie: string;
	/**  Son libellé (« Panne ») — servi (#2511). */
	categorie_libelle: string;
	prestataires: PrestataireLent[];
}

/**  Le bilan d'un exercice (#1645) — `routers/carnet.BilanCarnet`. `fin` est le
 *   DERNIER jour de l'exercice, inclus. */
export interface BilanCarnet {
	exercice: ExerciceLu & { debut: string; fin: string };
	exercices: ExerciceLu[];
	categories: CategorieBilan[];
	nombre: number;
}

/**  Le carnet d'entretien — réservé aux copropriétaires, au CS et à l'admin
 *   (décret n° 2001-477, arbitré le 10/09/2026). Le droit est tenu par
 *   `require_proprietaire` côté serveur ; l'écran ne fait que s'y conformer. */
export const carnet = {
	/**  `perimetre` est un CODE de l'arborescence (`'bat:3'`, `'parking'`), pas un
	 *   identifiant de bâtiment : c'est ce qui rend le filtre dynamique — un
	 *   périmètre créé en administration devient filtrable sans rien déployer. */
	lire: (perimetre?: string | null, annee?: string | null) => {
		//  `annee` : une année civile (« 2025 ») ; absente, tout le carnet. Les
		//  contrats en vigueur restent quelle que soit l'année (décret n° 2001-477).
		const params = new URLSearchParams();
		if (perimetre) params.set('perimetre', perimetre);
		if (annee) params.set('annee', annee);
		const requete = params.toString();
		return api.get<Carnet>(`/carnet-entretien${requete ? `?${requete}` : ''}`);
	},
	/**  Le bilan d'un exercice — RÉSERVÉ au conseil syndical (`require_cs_or_admin`,
	 *   arbitré le 04/10/2026). `exercice` est l'année où il commence ; absent,
	 *   l'exercice en cours. */
	metriques: (exercice?: number | null) =>
		api.get<BilanCarnet>(`/carnet-entretien/metriques${exercice ? `?exercice=${exercice}` : ''}`),
};
