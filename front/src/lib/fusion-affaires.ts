import { get } from 'svelte/store';
import { goto } from '$app/navigation';
import { page } from '$app/state';
import DialogueFusion from '$lib/components/DialogueFusion.svelte';
import ModaleFusionAffaires from '$lib/components/ModaleFusionAffaires.svelte';
import { toast } from '$lib/components/Toast.svelte';
import {
	suiviAffaires,
	tickets as ticketsApi,
	type AffaireLiee,
	type CandidateFusion,
	type Ticket,
} from '$lib/api';
import { messageErreur } from '$lib/erreurs';
import { modaleImperative } from '$lib/modale-imperative';
import { isCS } from '$lib/stores/auth';
import { STATUT_TICKET_LABELS, estActualite, estTicketClos, lienTicket } from '$lib/tickets';

/**
 * **À la clôture, demander s'il faut fusionner les affaires liées** (#1704).
 *
 * Écrit une fois pour les trois gestes qui clôturent une affaire — la Suite
 * (`SuiteAffaire`), le glissement au kanban (`VueKanbanAffaires`) et la
 * correction de l'affaire (`FormulaireTicket`) : la question ne dépend pas du
 * chemin pris pour clore.
 *
 * Rend :
 * - `[]` quand il n'y a rien à demander — l'état ne CLÔT pas (déjà close, ou
 *   un état actif), le lecteur n'est pas du conseil, aucune liée n'est
 *   ouverte — ou qu'on clôt sans fusionner ;
 * - les identifiants cochés ;
 * - `null` quand on renonce, ou que la liste n'a pas pu être lue : le geste
 *   de clôture ne part pas. Clore sans avoir pu poser la question ferait
 *   passer « je n'ai pas pu regarder » pour « il n'y avait rien ».
 *
 * ⚠️ Le CONSEIL seul fusionne (`utils/fusion_affaires`) — la liste des
 * candidates lui est réservée, d'où la garde sur `isCS`.
 */
export async function demanderFusion(
	ticket: { id: number; numero: string; statut: string },
	statut: string | undefined,
): Promise<number[] | null> {
	if (!get(isCS) || !estTicketClos(statut) || estTicketClos(ticket.statut)) return [];
	let candidates: CandidateFusion[];
	try {
		candidates = await ticketsApi.candidatesFusion(ticket.id);
	} catch (e) {
		toast('error', messageErreur(e));
		return null;
	}
	if (!candidates.length) return [];
	return modaleImperative<number[] | null>(
		DialogueFusion,
		{ numero: ticket.numero, etat: STATUT_TICKET_LABELS[statut ?? ''] ?? statut, candidates },
		null,
	);
}

/** Une affaire telle que `FusionAffaires` la nomme. */
export type AffaireAFusionner = Pick<AffaireLiee, 'id' | 'numero' | 'titre'>;
/** Ce que la fusion rend (`POST /suivi-affaires/fusions`). */
export type FusionFaite = Awaited<ReturnType<typeof suiviAffaires.fusions.fusionner>>;

/** L'affaire qu'on corrige, telle que la fusion depuis ses liées la lit. */
export type AffaireCorrigee = AffaireLiee & {
	categorie?: string | null;
	fusionnee?: boolean;
	affaires_liees?: AffaireLiee[];
};

/**
 * **Fusionner se propose-t-il depuis la correction de cette affaire ?** (#2173)
 *
 * Une affaire ouverte — ni actualité, ni déjà absorbée — qui a au moins UNE
 * affaire liée ENREGISTRÉE encore ouverte et NON absorbée — une absorbée hérite
 * de l'état de sa principale, « Chez le syndic » sans plus rien à fusionner
 * (#2186) : deux affaires à fusionner au moins,
 * comme la paire liée que le Suivi rassemble (#2083). Les liens ajoutés dans la
 * correction ne comptent pas tant qu'ils ne sont pas enregistrés : le serveur ne
 * fusionne que des affaires liées entre elles.
 *
 * ⚠️ Le CONSEIL seul fusionne : la garde `isCS` est chez l'appelant, qui la lit
 * en store (`$isCS`) pour que le bouton suive l'utilisateur chargé.
 */
export function fusionPossible(affaire: AffaireCorrigee | null | undefined): boolean {
	return (
		!!affaire &&
		!estTicketClos(affaire.statut) &&
		!estActualite(affaire) &&
		!affaire.fusionnee &&
		(affaire.affaires_liees ?? []).some((l) => !estTicketClos(l.statut) && !l.fusionnee)
	);
}

/** La plus ancienne d'abord — celle qui absorbe (`fusion_en_cours.affaires_du_groupe`). */
const parAnciennete = (a: AffaireLiee, b: AffaireLiee) =>
	new Date(a.cree_le).getTime() - new Date(b.cree_le).getTime() || a.id - b.id;

/**
 * **Fusionner les affaires liées depuis la correction d'une affaire** (#2173).
 *
 * Le geste du Suivi (#2083), sans rien en récrire : les affaires fusionnables
 * sont celles que le serveur propose déjà à la clôture (`GET /tickets/{id}/fusion`
 * — ouvertes, ni absorbées, ni actualités, ni fusion écartée) ; la boîte est
 * `FusionAffaires`, dans une fenêtre (`ModaleFusionAffaires` dit pourquoi).
 *
 * Rend ce que la fusion a fait, ou `null` quand on renonce, qu'il n'y a rien à
 * fusionner (on le dit — avec le MOTIF du serveur quand une liée s'y refuse,
 * #2186 : un message générique taisait pourquoi), ou que la liste n'a pas pu
 * être lue (on le dit aussi).
 */
export async function fusionnerLiees(affaire: AffaireLiee): Promise<FusionFaite | null> {
	if (!get(isCS)) return null;
	let candidates: CandidateFusion[];
	try {
		candidates = await ticketsApi.candidatesFusion(affaire.id);
	} catch (e) {
		toast('error', messageErreur(e));
		return null;
	}
	const fusionnables = candidates.filter((c) => c.fusionnable);
	const refusees = candidates.filter((c) => !c.fusionnable);
	if (!fusionnables.length) {
		toast(
			'info',
			refusees.length
				? `Fusion impossible : ${refusees.map((c) => `${c.numero} est ${c.motif}`).join(' ; ')}.`
				: 'Aucune affaire liée ne peut être fusionnée avec celle-ci.',
		);
		return null;
	}
	return modaleImperative<FusionFaite | null>(
		ModaleFusionAffaires,
		{
			affaires: [affaire, ...fusionnables].sort(parAnciennete),
			horsFusion: refusees,
		},
		null,
	);
}

/**
 * **Après une fusion faite depuis la correction** (#2173) : l'affaire corrigée
 * relue — l'appelant la rend comme une correction enregistrée, ce qui referme
 * le formulaire —, puis la PRINCIPALE ouverte à son adresse.
 *
 * Pourquoi l'y conduire : la fusion a réécrit son titre et sa description, versé
 * les Suites des autres, et close celles-ci. Une liste ouverte ne recoud qu'une
 * affaire à la fois : les absorbées y resteraient « ouvertes » jusqu'au
 * rechargement. La page de la principale montre le résultat, à jour.
 *
 * Rend `null` si l'affaire n'a pas pu être relue (on le dit) : le formulaire
 * reste ouvert, l'adresse de la principale aussi.
 */
export async function apresFusion(affaireId: number, r: FusionFaite): Promise<Ticket | null> {
	let relue: Ticket | null = null;
	try {
		relue = await ticketsApi.get(affaireId);
	} catch (e) {
		toast('error', messageErreur(e));
	}
	const cible = lienTicket(r.principale_id);
	if (page.url.pathname !== cible) void goto(cible);
	return relue;
}
