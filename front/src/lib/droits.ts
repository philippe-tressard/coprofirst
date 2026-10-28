/**
 * Qui peut **éditer**, qui peut **commenter** — le pendant écran de
 * `api/app/auth/deps.py`.
 *
 * ## La règle (arbitrée le 18/08/2026)
 *
 * > « Seul l'auteur peut l'éditer ou le commenter, avec l'admin (en cas de Pb),
 * >   mais aussi le CS peut commenter, pas éditer (s'il est au courant de
 * >   certaines choses et influer sur le workflow ou émettre un commentaire) »
 *
 * | Geste | Qui |
 * |---|---|
 * | **éditer** le contenu | l'auteur · le « saisi pour » · l'admin |
 * | **commenter**, faire avancer le workflow | les mêmes **+ le conseil syndical** |
 *
 * ## 🔴 Pourquoi ce fichier existe malgré la duplication apparente
 *
 * La règle est écrite **deux fois**, ici et côté serveur, et c'est inévitable :
 * les contextes de build sont `./api` et `./front`, rien de la racine n'entre
 * dans les images (cf. la note sur le partage front/api). Le seul pattern viable
 * est la copie assumée, avec les **mêmes mots dans le même ordre** pour qu'on
 * puisse les comparer d'un coup d'œil.
 *
 * ⚠️ **C'est le serveur qui décide.** Ceci n'est qu'un confort d'écran : cacher
 * un bouton n'a jamais protégé quoi que ce soit (`standards/03` §1).
 *
 * ⚠️ Mais l'écran doit dire **la même chose** que le serveur, ni plus ni moins.
 * Plus large, il propose un geste qui finira en 403 — l'utilisateur lit « Accès
 * refusé » pour un bouton que l'interface lui a tendu. Plus étroit, il rend une
 * capacité introuvable : c'est ainsi que le crayon des entrées d'Historique a
 * paru absent pendant une journée alors qu'il venait d'être livré.
 *
 * ## Ce à quoi cette règle ne s'applique PAS
 *
 * Les **actualités** et les **événements** appartiennent au conseil syndical, pas
 * à un résident : leur serveur exige `require_cs_or_admin`, et l'écran suit.
 * Appliquer « l'auteur seul » leur ferait perdre l'édition collégiale — un membre
 * du CS ne pourrait plus corriger la publication d'un collègue absent.
 *
 * La distinction n'est pas cosmétique : un ticket est **la demande de quelqu'un**,
 * une actualité est **la parole du conseil**.
 */

import type { User } from '#lib/api/index.ts';
import { aRole } from '#lib/stores/auth.ts';

/** Ce que ces fonctions savent lire d'un objet — rien de plus. */
export interface ObjetPossede {
	auteur_id?: number | null;
	/** Propre aux tickets : la personne POUR QUI la demande a été saisie. */
	saisi_pour_user_id?: number | null;
}

/**
 * Corriger le CONTENU : titre, description, périmètre, pièces jointes.
 *
 * ⚠️ « Saisi pour » compte comme auteur, et c'est la raison d'être du champ : un
 * membre du CS qui dépose un ticket au nom d'un résident ne le dépossède pas de
 * sa demande. Sans cela, ce résident serait le seul à ne pas pouvoir corriger ce
 * qui parle de lui.
 */
export function peutEditer(
	objet: ObjetPossede | null | undefined,
	userId: number | undefined,
	estAdmin: boolean,
): boolean {
	if (estAdmin) return true;
	//  Sans identité, on ne tranche pas : on n'affiche pas un bouton dont on
	//  ignore s'il aboutira (`standards/04` §2 — un contrôle qui ne peut pas
	//  mesurer ne conclut pas au vert).
	if (userId === undefined || userId === null || !objet) return false;
	return objet.auteur_id === userId || objet.saisi_pour_user_id === userId;
}

/**
 * Ajouter une entrée d'Historique, et faire avancer le workflow.
 *
 * Les mêmes, **plus le conseil syndical** — c'est lui qui suit les dossiers.
 * Écrit en appelant `peutEditer`, comme côté serveur : les deux listes ne
 * peuvent alors pas diverger.
 */
export function peutCommenter(
	objet: ObjetPossede | null | undefined,
	userId: number | undefined,
	estAdmin: boolean,
	estCS: boolean,
): boolean {
	return peutEditer(objet, userId, estAdmin) || estCS;
}

/** Combien de comptes ACTIFS portent les rôles qui ne restent jamais vacants. */
export interface Titulaires {
	admin: number;
	operateur: number;
}

/** Le décompte que `gestesAdminOperateur` attend, lu dans la liste des comptes. */
export function compterTitulaires(comptes: (User & { actif?: boolean })[]): Titulaires {
	const actifs = comptes.filter((c) => c.actif !== false);
	return {
		admin: actifs.filter((c) => aRole(c, 'admin')).length,
		operateur: actifs.filter((c) => aRole(c, 'operateur')).length,
	};
}

/**
 * Les gestes sur les rôles **Admin** et **Opérateur** (Admin › Utilisateurs) —
 * le pendant écran de `_exiger_geste_operateur` et `_exiger_un_autre_titulaire`
 * (`api/app/routers/admin/utilisateurs.py`), dans le même ordre :
 *
 * - Opérateur ne s'accorde qu'à un administrateur, mais se garde sans lui :
 *   Admin se retire à un opérateur, qui n'ouvre plus de `/admin` que sa
 *   supervision (16/10/2026, #2029) ;
 * - tout administrateur l'accorde ou le retire, à lui-même compris (15/10/2026) ;
 * - Admin et Opérateur se retirent, à soi-même compris, sauf à leur dernier
 *   titulaire actif.
 */
export function gestesAdminOperateur(
	cible: User,
	titulaires: Titulaires,
): { accorder: boolean; retirer: boolean; retirerAdmin: boolean } {
	const cibleOperateur = aRole(cible, 'operateur');
	return {
		accorder: !cibleOperateur && aRole(cible, 'admin'),
		retirer: cibleOperateur && titulaires.operateur > 1,
		retirerAdmin: titulaires.admin > 1,
	};
}
