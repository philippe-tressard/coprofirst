import Confirmation from '#lib/components/Confirmation.svelte';
import { tenter } from '#lib/erreurs.ts';
import { modaleImperative } from '#lib/modale-imperative.ts';

/**
 * Demande confirmation, dans la charte du site. Rend `true` si l'on confirme.
 *
 * ```ts
 * if (!(await confirmer('Archiver cet événement ?'))) return;
 * if (!(await confirmer({ message: '…', libelleConfirmer: 'Supprimer', danger: true })))
 * 	return;
 * ```
 *
 * ⚠️ **La forme COURTE n'est pas un raccourci de confort.** Trente-cinq des
 * quarante appels d'origine ne portent qu'une phrase ; leur imposer un objet
 * aurait fait passer chacun de une ligne à cinq — et un geste de conversion qui
 * quintuple le code est un geste qu'on ne fait pas. Le contrôle de modularité
 * l'a refusé au premier écran converti, ce qui était la bonne réponse.
 *
 * ## Pourquoi un appel IMPÉRATIF et non un composant posé dans la page
 *
 * Quarante sites demandaient confirmation avec `confirm()` natif. Les convertir
 * en composant déclaratif aurait imposé, à chacun, un état d'ouverture, une
 * variable pour l'action en attente, et un gestionnaire — soit quarante fois le
 * même échafaudage, dans quarante écrans qui n'ont rien d'autre en commun.
 * C'est très exactement la duplication que ce lot retire.
 *
 * L'appel garde la forme d'origine : une ligne, une condition, un `return`.
 * Seul l'`await` s'ajoute.
 *
 * ⚠️ Le montage, le démontage et la résolution unique — ainsi que le refus par
 * défaut côté serveur, où il n'y a pas de fenêtre — sont dans
 * `#lib/modale-imperative`, partagés avec `demander()`.
 */
export function confirmer(
	options:
		| string
		| {
				titre?: string;
				message: string;
				libelleConfirmer?: string;
				libelleAnnuler?: string;
				danger?: boolean;
		  },
): Promise<boolean> {
	if (typeof options === 'string') options = { message: options };
	//  Le montage, le démontage et la résolution unique vivent dans
	//  `modaleImperative` : `demander()` s'en sert aussi, et les recopier aurait
	//  recopié avec eux les quatre pièges que ce fichier a déjà payés une fois.
	//  ⚠️ Le refus par défaut est `false` — sans fenêtre, on n'exécute rien.
	return modaleImperative<boolean>(
		Confirmation,
		{
			titre: options.titre ?? 'Confirmer',
			message: options.message,
			libelleConfirmer: options.libelleConfirmer ?? 'Confirmer',
			libelleAnnuler: options.libelleAnnuler ?? 'Annuler',
			danger: options.danger ?? false,
		},
		false,
	);
}

/**
 * Les options d'une suppression DÉFINITIVE — rouge, et qui le dit.
 *
 * 🔴 Vingt-deux des quarante `confirm()` d'origine écrivaient une variante de
 * « Supprimer définitivement X ? Cette action est irréversible. » — même phrase,
 * ponctuation près, dans vingt-deux fichiers. C'est la duplication que ce lot
 * retire, et c'est aussi ce qui la rendait dangereuse : rien ne garantissait que
 * la vingt-troisième dirait « irréversible ».
 *
 * ⚠️ `danger: true` n'est pas décoratif. La boîte native donnait exactement le
 * même aspect à « archiver » — qui se défait — et à « supprimer » — qui ne se
 * défait pas. Le rouge est ce qui rétablit la différence.
 */
export function SUPPRESSION(quoi: string) {
	return {
		titre: 'Supprimer définitivement',
		message: `${quoi}

Cette action est irréversible.`,
		libelleConfirmer: 'Supprimer',
		danger: true,
	};
}

/**
 * **Confirmer, agir, et le dire** — le geste destructif complet, en un appel.
 *
 * ```ts
 * await confirmerPuis(SUPPRESSION('Ce relevé'), 'Supprimé', async () => {
 * 	await prestApi.deleteReleve(id);
 * 	releves = releves.filter((r) => r.id !== id);
 * });
 * ```
 *
 * ## Pourquoi (12/09/2026)
 *
 * Le motif était écrit **sept fois**, au caractère près, dans trois écrans :
 * `prestataires` (×3), `calendrier` (×3) et `OngletConsommations` (×1) —
 * confirmer, `try`, appeler, mettre à jour l'état, `toast('success', …)`,
 * `catch`, `toast('error', 'Erreur')`. Dix lignes pour une intention.
 *
 * 🔴 Et elles avaient **déjà divergé** sur le point qui compte : six écrivaient
 * `toast('error', 'Erreur')`, la septième rendait le message du serveur. Six
 * gestes sur sept disaient donc « Erreur » là où l'API expliquait *pourquoi* —
 * un quota dépassé, un document encore référencé, une session expirée.
 *
 * Le `catch` passe désormais par `messageErreur`, qui sait distinguer un 401
 * (« votre session a expiré, rechargez la page ») d'un serveur injoignable. Les
 * sept gestes y gagnent, sans qu'aucun appelant ait à le demander.
 *
 * ⚠️ La mise à jour de l'état va DANS `action`, et c'est voulu : elle n'a de
 * sens que si l'appel a réussi, et chaque écran range la sienne à sa façon —
 * filtrer une liste, remplacer un élément, recharger une table. Un paramètre de
 * plus aurait obligé les sept à se ressembler là où ils n'ont aucune raison de
 * le faire.
 *
 * @returns `true` si le geste a eu lieu, `false` s'il a été refusé ou a échoué.
 */
export async function confirmerPuis(
	question: Parameters<typeof confirmer>[0],
	succes: string,
	//  🔴 Le rappel en DERNIER, et ce n'est pas cosmétique : placé au milieu, il
	//  force le formateur à éclater l'appel sur neuf lignes, et la factorisation
	//  rendait alors les écrans PLUS longs qu'avant. La convention JS — le rappel
	//  ferme l'appel — garde la forme compacte que le motif d'origine avait.
	action: () => Promise<unknown>,
	//  Le repli passe APRÈS le rappel, pour la même raison : le placer avant
	//  aurait éclaté les huit appels qui n'en ont pas besoin.
	repli?: string,
): Promise<boolean> {
	if (!(await confirmer(question))) return false;
	//  Le `try`/`toast`/`catch` vit dans `tenter` : l'écrire ici aussi donnerait
	//  deux gestions d'erreur pour une intention, et c'est précisément ce que ce
	//  lot retire.
	return tenter(action, succes, repli);
}

/**
 * Les options d'un ARCHIVAGE — le pendant de `SUPPRESSION`, et volontairement
 * SANS le rouge : archiver se défait (`standards/11` §14).
 *
 * La phrase dit où l'objet se retrouve. Elle était écrite dans l'écran des
 * affaires ; les prestataires et les contrats la prennent ici (#1538) plutôt
 * que d'en écrire deux autres.
 */
export function ARCHIVAGE(quoi: string, ou = "l'onglet Archives") {
	return { titre: 'Archiver', message: `${quoi} rejoindra ${ou}.`, libelleConfirmer: 'Archiver' };
}

/**
 * **📦 Ranger ou ressortir** — le geste réversible complet, en un appel.
 *
 * Ranger demande confirmation (`ARCHIVAGE`) ; ressortir non : le geste ne
 * retire rien de la vue de personne, il rend. Écrit une fois pour les deux
 * onglets qui l'emploient — prestataires et contrats (#1538).
 */
export function archiverPuis(
	quoi: string,
	ou: string,
	archivee: boolean,
	action: () => Promise<unknown>,
): Promise<boolean> {
	return archivee
		? confirmerPuis(ARCHIVAGE(quoi, ou), 'Archivé', action)
		: tenter(action, 'Restauré');
}
