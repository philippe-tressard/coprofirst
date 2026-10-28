/**
 *  La recherche libre de la page Affaires, et le filtre de la liste qui en dépend.
 *
 *  ## Pourquoi (27/09/2026)
 *
 *  Le filtre « Catégorie » cède la place à une recherche libre, la plus
 *  exhaustive possible (maquette A, avec l'extrait et les Archives de la C). La
 *  règle de correspondance vit au SERVEUR (`app/utils/recherche_affaires.py`) :
 *  il est seul à lire les suites, les messages et les documents, et une seconde
 *  règle ici pour les champs que la liste connaît déjà dirait deux choses sur
 *  la même liste. Ce module ne fait que demander, patienter et filtrer.
 *
 *  Il porte aussi le filtre de la liste (état, nature, archives), sorti de la
 *  page le même jour : elle était à 494 lignes pour un plafond de 500.
 */
import { writable } from 'svelte/store';
import { tickets as ticketsApi, type CorrespondanceAffaire, type Ticket } from '#lib/api/index.ts';
import { messageErreur } from '#lib/erreurs.ts';
import { suiviCorrespond } from '#lib/tickets.ts';

/** En dessous, une frappe n'est pas encore une recherche. */
export const RECHERCHE_MIN = 2;
/** Le temps de finir un mot avant d'interroger le serveur. */
const DELAI_FRAPPE_MS = 250;

/** « Trouvé dans … » — la fin de phrase, selon l'endroit rendu par le serveur. */
export const TROUVE_DANS: Record<CorrespondanceAffaire['ou'], string> = {
	numero: 'le numéro',
	titre: 'le titre',
	categorie: 'la catégorie',
	lieu: 'le lieu',
	personne: 'le nom de l’auteur',
	prestataire: 'le prestataire',
	equipement: 'l’équipement',
	description: 'la description',
	suite: 'une suite',
	message: 'un message',
	piece_jointe: 'une pièce jointe',
};

/** Ce qui DATE un extrait : une suite ou un message a un moment et un auteur. */
export const SOURCE_DATEE: Partial<Record<CorrespondanceAffaire['ou'], string>> = {
	suite: 'Suite',
	message: 'Message',
};

export interface EtatRecherche {
	/** Le texte réellement cherché — vide quand aucune recherche n'est active. */
	terme: string;
	enCours: boolean;
	erreur: string;
	/** Dans l'ordre de pertinence ; `null` tant qu'aucune recherche n'a répondu. */
	resultats: CorrespondanceAffaire[] | null;
}

const REPOS: EtatRecherche = { terme: '', enCours: false, erreur: '', resultats: null };

/**
 *  Une recherche qui attend la fin de la frappe, et n'écoute que sa DERNIÈRE
 *  réponse : une réponse lente à « fui » ne doit pas écraser celle de « fuite ».
 */
export function rechercheAffaires() {
	const etat = writable<EtatRecherche>(REPOS);
	let minuterie: ReturnType<typeof setTimeout> | undefined;
	let derniere = 0;

	function chercher(texte: string) {
		clearTimeout(minuterie);
		const terme = texte.trim();
		const numero = ++derniere;
		if (terme.length < RECHERCHE_MIN) {
			etat.set(REPOS);
			return;
		}
		etat.update((e) => ({ ...e, enCours: true }));
		minuterie = setTimeout(async () => {
			try {
				const resultats = await ticketsApi.rechercher(terme);
				if (numero === derniere) etat.set({ terme, enCours: false, erreur: '', resultats });
			} catch (e) {
				if (numero === derniere)
					etat.set({ terme, enCours: false, erreur: messageErreur(e), resultats: null });
			}
		}, DELAI_FRAPPE_MS);
	}

	return { subscribe: etat.subscribe, chercher };
}

/**
 *  L'affaire a-t-elle quitté la liste pour les Archives ?
 *
 *  🔴 `archivee` est calculé par le SERVEUR (`app/utils/archivage.py`, #515) et
 *  transporté. Le recalculer ici en ferait une seconde règle : la liste et les
 *  Archives trancheraient séparément — le bug du 17/07/2026 sur les actualités.
 *  L'écran appliquait la sienne, 7 jours sur `mis_a_jour_le`, quand le site en
 *  annonçait 30 (#515).
 */
export const estArchive = (t: { archivee?: boolean }): boolean => t.archivee === true;

/**
 *  Les affaires que la liste montre.
 *
 *  Sans recherche : les affaires actives, dans l'ordre d'activité. Avec : celles
 *  que le serveur a trouvées, dans SON ordre (la pertinence), archives comprises
 *  si on les demande. Puis, dans les deux cas, l'état et la nature.
 *
 *  ⚠️ `optionsStatut` se calcule AVANT ce filtre, sur les affaires actives : c'est
 *  cet ensemble qui donne les boutons de Suivi. Calculé après, il n'en resterait
 *  qu'un, celui qu'on vient de choisir.
 */
export function filtrerAffaires(
	tickets: Ticket[],
	{
		resultats,
		inclureArchives,
		statut,
		nature,
		optionsStatut,
	}: {
		resultats: CorrespondanceAffaire[] | null;
		inclureArchives: boolean;
		statut: string;
		nature: string;
		optionsStatut: { value: string; statuts: readonly string[] }[];
	},
): Ticket[] {
	const parId = new Map(tickets.map((t) => [t.id, t]));
	const base = resultats
		? resultats
				.map((r) => parId.get(r.ticket_id))
				.filter((t): t is Ticket => !!t && (inclureArchives || !estArchive(t)))
		: tickets.filter((t) => !estArchive(t));
	return base.filter(
		(t) =>
			(!statut || suiviCorrespond(optionsStatut, statut, t.statut)) &&
			(!nature || (t.natures ?? []).includes(nature)),
	);
}

/** Combien d'affaires ARCHIVÉES la recherche a trouvées — pour les proposer. */
export function archiveesTrouvees(
	tickets: Ticket[],
	resultats: CorrespondanceAffaire[] | null,
): number {
	if (!resultats) return 0;
	const archivees = new Set(tickets.filter(estArchive).map((t) => t.id));
	return resultats.filter((r) => archivees.has(r.ticket_id)).length;
}
