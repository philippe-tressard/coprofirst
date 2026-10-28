/**
 * **Une liste d'affaires et ses gestes** — ce que la page décide pour les
 * cartes qu'elle montre : laquelle est dépliée, laquelle est en correction,
 * laquelle attend une Suite, et les appels d'API de chaque geste.
 *
 * ## Pourquoi un module (15/10/2026)
 *
 * Un lien vers une affaire (`/tickets/42`, celui des courriels, du groupe et de
 * « Copier le lien ») ouvrait une FICHE à part — en-tête, boutons d'état, fil
 * de messages, Historique — quand la liste et le fil d'activité montrent la
 * CARTE dépliée. Une même affaire, deux rendus qui se lisaient différemment
 * (signalé à l'écran). Le lien direct rend désormais la carte, seule et
 * dépliée : il lui faut donc les mêmes gestes que la page Affaires.
 *
 * Ils vivaient dans `tickets/+page.svelte` — cent cinquante lignes d'état et
 * d'appels. Les recopier dans la fiche aurait fait deux écritures libres de
 * diverger au premier geste ajouté ; c'est ce qui était arrivé au fil, que la
 * liste et la fiche câblaient chacune de leur côté (le crayon manquait à
 * l'une, la corbeille à l'autre, 18/08/2026). Les deux écrans appellent ce
 * module, et ne gardent que ce qui leur est propre : la page Affaires ses
 * filtres et ses onglets, le lien direct son fil de messages.
 *
 * ## Une carte dépliée à la fois
 *
 * L'ouverture est UN identifiant, basculé par `#lib/accordeon` — la page la
 * tenait dans un `Set` remis à un élément, forme déclarée en exception du
 * contrôle d'accordéon et qui en sort avec ce module.
 */
import { derived, get, writable, type Writable } from 'svelte/store';
import { goto } from '$app/navigation';

import { tickets as ticketsApi, type Ticket, type TicketEvolution } from '#lib/api/index.ts';
import { basculer } from '#lib/accordeon.ts';
import { toast } from '#lib/components/Toast.svelte';
import { ARCHIVAGE, SUPPRESSION, confirmerPuis } from '#lib/confirmation.ts';
import { messageErreur } from '#lib/erreurs.ts';
import { chargeCorrection, type ChargeUtileEvolution } from '#lib/evolutions.ts';
import { optionsRapides } from '#lib/options-rapides.ts';
import { estActualite, lienReponse, type GestesTicket } from '#lib/tickets.ts';

/** Ce que les cartes lisent — les props d'état de `ListeTickets`. */
export interface EtatAffairesEnListe {
	expandedIds: Set<number>;
	evolsMap: Record<number, TicketEvolution[]>;
	evolsErreurs: Record<number, string>;
	ticketEnEdition: number | null;
	ticketEnOptions: number | null;
	optionsRapidesEnCours: boolean;
	ticketEnEvolution: number | null;
	evolutionEnCours: boolean;
	evolEnEdition: number | null;
	evolCorrectionEnCours: boolean;
}

interface EtatInterne {
	deplie: number | null;
	fils: Record<number, TicketEvolution[]>;
	filsCharges: number[];
	erreurs: Record<number, string>;
	enEdition: number | null;
	enEvolution: number | null;
	evolutionEnCours: boolean;
	evolEnEdition: number | null;
	correctionEnCours: boolean;
}

export interface ReglagesAffairesEnListe {
	/** Après une suppression définitive — le lien direct quitte une page devenue vide. */
	apresSuppression?: (t: Ticket) => void;
	/** 💬 Répondre : le lien direct ouvre son formulaire sur place. Sans lui, la
	 *  liste mène à la page de l'affaire, formulaire ouvert — c'est là que vit le
	 *  fil des messages, et l'envoi (`tickets/[id]`) : il ne s'écrit pas deux fois. */
	repondre?: (t: Ticket) => void;
}

/** Une actualité n'affiche pas de numéro : on la nomme par son titre. */
const designation = (t: Ticket) =>
	estActualite(t) ? `L'actualité « ${t.titre} »` : `L'affaire ${t.numero}`;

/**
 * Les gestes d'une liste d'affaires, branchés sur `liste` — que le module
 * recoud après chaque réponse du serveur.
 */
export function affairesEnListe(liste: Writable<Ticket[]>, reglages: ReglagesAffairesEnListe = {}) {
	const interne = writable<EtatInterne>({
		deplie: null,
		fils: {},
		filsCharges: [],
		erreurs: {},
		enEdition: null,
		enEvolution: null,
		evolutionEnCours: false,
		evolEnEdition: null,
		correctionEnCours: false,
	});
	const poser = (p: Partial<EtatInterne>) => interne.update((e) => ({ ...e, ...p }));

	//  Le crayon ouvre les huit sections ; dépingler n'en touche qu'une
	//  (12/09/2026). L'état et le geste viennent de `#lib/options-rapides`.
	const options = optionsRapides<Ticket>();

	const etat = derived(
		[interne, options.ouvertId, options.enCours],
		([e, ouvertId, enCours]): EtatAffairesEnListe => ({
			expandedIds: new Set(e.deplie === null ? [] : [e.deplie]),
			evolsMap: e.fils,
			evolsErreurs: e.erreurs,
			ticketEnEdition: e.enEdition,
			ticketEnOptions: ouvertId,
			optionsRapidesEnCours: enCours,
			ticketEnEvolution: e.enEvolution,
			evolutionEnCours: e.evolutionEnCours,
			evolEnEdition: e.evolEnEdition,
			evolCorrectionEnCours: e.correctionEnCours,
		}),
	);

	/** Recoudre une affaire de la liste avec la réponse du serveur. */
	const recoudre = (maj: Partial<Ticket> & { id: number }) =>
		liste.update((l) => l.map((x) => (x.id === maj.id ? { ...x, ...maj } : x)));

	async function chargerFil(id: number) {
		try {
			const fil = await ticketsApi.evolutions(id);
			interne.update((e) => ({
				...e,
				fils: { ...e.fils, [id]: fil },
				filsCharges: [...new Set([...e.filsCharges, id])],
				erreurs: { ...e.erreurs, [id]: '' },
			}));
		} catch (err) {
			//  Dit, jamais avalé (29/09/2026) : avalé, un 403 rendait un fil VIDE (TK-124285).
			interne.update((e) => ({ ...e, erreurs: { ...e.erreurs, [id]: messageErreur(err) } }));
		}
	}

	//  Ouvrir un formulaire déplie sa carte et referme l'autre : deux formulaires
	//  ouverts sur le même écran, c'est deux « Enregistrer » pour deux gestes
	//  différents à quelques centimètres.
	//  ⚠️ Le panneau d'options se referme avec eux : son « Annuler » appelle
	//  `annuler`, qui ne le fermait pas — le bouton restait sans effet.
	function fermerFormulaires() {
		poser({ enEvolution: null, enEdition: null });
		options.fermer();
	}

	async function basculerCarte(t: Ticket) {
		const ouvert = basculer(get(interne).deplie, t.id);
		poser({ deplie: ouvert });
		fermerFormulaires();
		if (ouvert !== null && !get(interne).filsCharges.includes(ouvert)) await chargerFil(ouvert);
	}

	/** Déplier une carte, sans la replier si elle l'est déjà — un lien profond. */
	async function deplier(t: Ticket) {
		if (get(interne).deplie !== t.id) await basculerCarte(t);
	}

	//  UN point d'entrée (#426) : le formulaire porte les DEUX gestes, et lequel a
	//  été fait se lit dans les pastilles — celle de l'état courant est active.
	function evoluerOuvrir(t: Ticket) {
		options.fermer();
		poser({ enEdition: null, enEvolution: t.id, deplie: t.id });
	}

	function modifier(t: Ticket) {
		options.fermer();
		poser({ enEvolution: null, enEdition: t.id, deplie: t.id });
	}

	function optionsOuvrir(t: Ticket) {
		poser({ enEvolution: null, enEdition: null, deplie: t.id });
		options.ouvrir(t);
	}

	const optionsEnregistrer = (t: Ticket, data: unknown) =>
		options.enregistrer(() => ticketsApi.update(t.id, data), recoudre);

	async function evoluer(t: Ticket, brut: unknown) {
		const data = brut as ChargeUtileEvolution;
		poser({ evolutionEnCours: true });
		try {
			//  🔴 La charge utile ENTIÈRE : un relais qui énumérait ses champs jetait
			//  ce qu'il ne nommait pas — le périmètre (#529), puis les options, puis
			//  les destinataires d'une actualité (#1091).
			await ticketsApi.addEvolution(t.id, { ...data, contenu: data.contenu || undefined });
			if (data.type === 'etat') recoudre({ id: t.id, statut: data.nouveau_statut ?? t.statut });
			await chargerFil(t.id);
			poser({ enEvolution: null });
			toast('success', data.type === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (err) {
			toast('error', messageErreur(err));
		} finally {
			poser({ evolutionEnCours: false });
		}
	}

	async function evolCorriger(t: Ticket, brut: unknown) {
		const evolId = get(interne).evolEnEdition;
		if (evolId === null) return;
		poser({ correctionEnCours: true });
		try {
			//  🔄 TOUTES les sections d'une Suite se corrigent, Suivi compris
			//  (01/10/2026) : la charge vient de `chargeCorrection` (#529).
			await ticketsApi.updateEvolution(
				t.id,
				evolId,
				chargeCorrection(brut as ChargeUtileEvolution),
			);
			await chargerFil(t.id);
			poser({ evolEnEdition: null });
			toast('success', 'Entrée corrigée');
		} catch (err) {
			toast('error', messageErreur(err));
		} finally {
			poser({ correctionEnCours: false });
		}
	}

	//  🔴 Effacer une entrée du fil — le serveur revérifie le droit. Une
	//  transition d'état est refusée (422) et n'affiche pas de corbeille.
	async function evolSupprimer({ ticket: t, evolId }: { ticket: Ticket; evolId: number }) {
		try {
			await ticketsApi.deleteEvolution(t.id, evolId);
			await chargerFil(t.id);
			toast('success', 'Entrée supprimée');
		} catch (err) {
			toast('error', messageErreur(err));
		}
	}

	//  📦 Archiver, et non supprimer, depuis la liste (24/09/2026, `ux-patterns` §8).
	async function archiver(t: Ticket) {
		await confirmerPuis(ARCHIVAGE(designation(t)), 'Archivée', async () => {
			recoudre(await ticketsApi.update(t.id, { archive_manuel: true }));
		});
	}

	async function supprimer(t: Ticket) {
		const fait = await confirmerPuis(
			SUPPRESSION(designation(t)),
			'Suppression effectuée',
			async () => {
				await ticketsApi.delete(t.id);
				liste.update((l) => l.filter((x) => x.id !== t.id));
			},
		);
		if (fait) reglages.apresSuppression?.(t);
	}

	//  Le PATCH inscrit une CORRECTION dans le fil : sans ce rechargement, la
	//  carte afficherait l'affaire corrigée au-dessus d'un fil qui n'en dit rien.
	async function modifie(maj: Ticket) {
		recoudre(maj);
		await chargerFil(maj.id);
		poser({ enEdition: null });
	}

	const gestes: GestesTicket = {
		basculer: basculerCarte,
		evoluerOuvrir,
		modifier,
		optionsOuvrir,
		optionsEnregistrer,
		supprimer,
		archiver,
		evoluer,
		evolModifier: (id) => poser({ evolEnEdition: id }),
		evolCorriger,
		evolSupprimer,
		evolAnnuler: () => poser({ evolEnEdition: null }),
		modifie,
		annuler: fermerFormulaires,
		filChange: (t) =>
			ticketsApi.get(t.id).then(modifie, (err) => toast('error', messageErreur(err))),
		repondre: reglages.repondre ?? ((t) => goto(lienReponse(t))),
	};

	return { etat, gestes, deplier, chargerFil };
}
