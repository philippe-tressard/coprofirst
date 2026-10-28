/**
 * **Les gestes propres à une actualité** — côté écran.
 *
 * Deux à ce jour : la promouvoir en affaire suivie (#1094), et retrouver où
 * mène une ancienne adresse d'actualité. Les autres — supprimer, enregistrer
 * les options, ajouter une Suite — sont ceux de TOUTE affaire depuis le
 * 23/09/2026 (#1091, lot 4) : ils vivent dans la page des affaires
 * (`GestesTicket`), et une seconde écriture ici divergerait au premier écart.
 *
 * ## La promotion : une actualité devient une affaire suivie (#1094)
 *
 * Une actualité qui dérape — « attention, fuite au 3e » — obligeait à rouvrir
 * une affaire et **tout retaper**. Depuis que l'actualité EST une affaire, la
 * promotion n'est plus une conversion : la même affaire change de catégorie,
 * le serveur lui donne un état de suivi (`nature_affaire.statut_pour`), et
 * rien ne bouge — ni le titre, ni les pièces, ni l'adresse déjà envoyée.
 *
 * ## Les anciennes adresses (#1094, puis #1091)
 *
 * Les courriels et messages d'une actualité portaient `/actualites#pub-42`. Le
 * serveur rend **410** avec l'affaire née de la publication — et **404** pour un
 * identifiant réellement inconnu, qu'on laisse alors tranquille plutôt que
 * d'annoncer une affaire qui n'existe pas.
 */
import { goto } from '$app/navigation';

import {
	calendrier as calApi,
	publications as pubsApi,
	tickets as ticketsApi,
} from '#lib/api/index.ts';
import type { Ticket } from '#lib/api/types.ts';
import { confirmerPuis } from '#lib/confirmation.ts';
import { TICKET } from '#lib/entites/ticket.ts';
import { lienTicket } from '#lib/tickets.ts';

/**
 * La catégorie que reçoit une actualité promue. « Question » : la plus neutre,
 * celle qui ne présume de rien — le conseil la précise ensuite à la correction,
 * comme il précisait le statut d'une promotion avant le 23/09/2026.
 */
const CATEGORIE_DE_PROMOTION = 'question';

/**
 * Promouvoir une actualité, après confirmation, et suivre l'affaire.
 *
 * ⚠️ La confirmation n'est pas une politesse : l'actualité **quitte le filtre
 * Actualité** et entre dans un suivi. Le texte le dit avec les mots du lecteur —
 * et jamais ceux du modèle.
 *
 * @param remplacer ce que l'écran fait de l'affaire rendue par le serveur : il
 *   la range à sa place, et c'est sa carte d'affaire qui s'affiche désormais.
 * @returns `true` si la promotion a eu lieu.
 */
export async function promouvoirActualite(
	pub: Pick<Ticket, 'id' | 'titre'>,
	remplacer: (maj: Ticket) => void,
): Promise<boolean> {
	const libelle = TICKET.libelle.toLowerCase();
	const fait = await confirmerPuis(
		{
			titre: `En faire une ${libelle}`,
			message:
				`« ${pub.titre} » deviendra une ${libelle} à suivre. Le titre, la description ` +
				'et les pièces jointes restent — rien n’est à ressaisir, et son adresse ne change pas.',
			libelleConfirmer: `En faire une ${libelle}`,
		},
		`${TICKET.libelle} ouverte — le suivi peut commencer.`,
		async () => {
			remplacer(await ticketsApi.update(pub.id, { categorie: CATEGORIE_DE_PROMOTION }));
		},
		'Impossible de promouvoir cette actualité',
	);
	//  Le lecteur suit l'objet : il vient de demander un suivi, c'est sur la
	//  fiche de l'affaire qu'il le mène.
	if (fait) goto(lienTicket(pub.id));
	return fait;
}

/**
 * **L'ancienne adresse mène à l'affaire** — la moitié qui rattrape.
 *
 * @returns `true` si l'on a redirigé — l'appelant n'a alors plus rien à faire.
 */
export async function suivrePublicationPromue(pubId: number): Promise<boolean> {
	return suivreVersAffaire(pubsApi.get(pubId));
}

/**  Même geste pour un ancien lien d'événement `#ev-N` (#1092, lot 5) : les
 *   événements sont devenus des affaires, et le serveur répond de la même façon. */
export async function suivreEvenementPromu(evId: number): Promise<boolean> {
	return suivreVersAffaire(calApi.get(evId));
}

/**  Le 410 `promu_en_affaire` mène à la fiche ; tout autre échec ne mène NULLE
 *   PART — se tromper enverrait le lecteur sur l'affaire de quelqu'un d'autre.
 *   Écrit une fois pour les deux anciennes adresses. */
async function suivreVersAffaire(appel: Promise<unknown>): Promise<boolean> {
	try {
		await appel;
		//  Un 2xx n'existe plus sur cette route : on ne redirige pas sur un
		//  succès qu'on ne comprend pas.
		return false;
	} catch (e: unknown) {
		const detail = (e as { data?: { detail?: { promu_en_affaire?: number } } })?.data?.detail;
		const id = detail?.promu_en_affaire;
		//  ⚠️ Tout autre échec — 404, 403, réseau — ne redirige RIEN. Se tromper
		//  ici enverrait le lecteur sur l'affaire de quelqu'un d'autre.
		if (typeof id !== 'number') return false;
		goto(lienTicket(id));
		return true;
	}
}
