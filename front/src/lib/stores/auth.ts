import { onMount } from 'svelte';
import { writable, derived } from 'svelte/store';
import type { User } from '#lib/api/index.ts';
import type { DroitsOnglet } from '#lib/onglets-ouverts.ts';
import {
	estBailleur,
	estCoproprietaire,
	estGestionnaire,
	estLocataire,
	estResident,
} from '#lib/roles.ts';

export const currentUser = writable<User | null>(null);

export const isAuthenticated = derived(currentUser, ($u) => $u !== null);

/**
 * Le pendant front de `Utilisateur.has_role` (`api/app/models/core.py`).
 *
 * Il n'en existait **aucun** : chaque store dérivé recomposait à la main la même
 * cascade `roles.includes(x) || role === x`, et chaque écran recomposait par
 * dessus sa propre condition de visibilité. Rien n'obligeait ces écritures à
 * rester d'accord entre elles, ni avec le serveur — c'est ce qu'a montré la
 * rangée de raccourcis du tableau de bord, où la règle « qui voit l'Espace CS »
 * était écrite une fois dans la page et une fois dans le calcul de son compteur
 * (#399).
 *
 * ⚠️ C'est une fonction, pas un store : elle se teste, se compose, et sert aussi
 * bien dans un `$:` que dans une table de configuration (`#lib/raccourcis.ts`).
 * Elle ne décide de **rien** côté serveur — le front n'est jamais le gardien
 * d'un droit, il n'en est que le reflet.
 */
export function aRole(user: User | null, ...roles: string[]): boolean {
	if (!user) return false;
	const portes: string[] = user.roles?.length ? user.roles : user.role ? [user.role] : [];
	return roles.some((r) => portes.includes(r));
}

export const isAdmin = derived(currentUser, ($u) => aRole($u, 'admin'));

export const isCS = derived(currentUser, ($u) => aRole($u, 'conseil_syndical', 'admin'));

/**
 * L'opérateur de la plateforme (#1750, spec §4.7) : il supervise l'installation
 * — santé, contrôles, base — sans lire aucune donnée de la copropriété. Distinct
 * de l'administrateur, qui gère la résidence ; un même compte peut porter les
 * deux. Le serveur refuse les routes de supervision à qui ne l'est pas
 * (`require_operateur`) : ce dérivé n'en est que le reflet.
 */
export const isOperateur = derived(currentUser, ($u) => aRole($u, 'operateur'));

/**
 * Qui ouvre l'administration (`/admin`) : l'administrateur, et l'opérateur qui
 * ne l'est pas — réduite alors à sa supervision (`#lib/onglets-ouverts`, #2029).
 * Le menu et la garde d'`admin/+layout.svelte` posent cette question-ci.
 */
export const isAdminOuOperateur = derived(currentUser, ($u) => aRole($u, 'admin', 'operateur'));

//  🔴 Ces trois dérivées recomposaient la cascade `roles ?? [role]` à la main,
//  DEUX LIGNES sous `aRole` qui la porte (#1041). Le fichier qui définit la règle
//  était donc le premier à ne pas l'employer — et `aRole` traite un cas qu'elles
//  oubliaient : un compte qui n'a que l'ancien champ `role`, sans `roles`.

// Vrai si l'utilisateur a au moins un rôle résidentiel (propriétaire, résident, ou aidant avec délégation active)
export const hasResidentRole = derived(
	currentUser,
	($u) => aRole($u, 'propriétaire', 'résident') || $u?.statut === 'aidant',
);

/**
 * Copropriétaire, conseil syndical ou administration.
 *
 * 🔴 Cette question était écrite DEUX FOIS, à l'identique, dans `calendrier` et
 * `tableau-de-bord` — la cascade des trois rôles en clair, sous le nom `canSeeAG`
 * (#1041). Le nom dit ici la POPULATION et non l'usage : c'est elle qui voit une
 * assemblée générale aujourd'hui, et ce sera elle qui verra autre chose demain.
 * Un nom qui décrit un usage n'est appelé que par cet usage (`standards/02`
 * §4 septies).
 */
export const isProprioOuCS = derived(currentUser, ($u) =>
	aRole($u, 'propriétaire', 'conseil_syndical', 'admin'),
);

// Vrai si l'utilisateur n'est QUE admin (sans rôle résidentiel ni CS)
export const isAdminOnly = derived(
	currentUser,
	($u) =>
		aRole($u, 'admin') && !aRole($u, 'propriétaire', 'résident') && !aRole($u, 'conseil_syndical'),
);

// ─────────────────────────────────────────────────────────────────────────────
//  Ce que l'utilisateur COURANT est — des dérivées, pas des recopies
// ─────────────────────────────────────────────────────────────────────────────
//
//  🔴 Les écrans réinventaient ces dérivées, une par une :
//
//      $: isLocataire = $currentUser?.statut === 'locataire';
//
//  …écrit tel quel dans SIX fichiers (`OngletAcces`, `AccesConnexes`,
//  `calendrier`, `mon-lot`, `residence`, `tableau-de-bord`), alors que
//  `isCS`, `isAdmin` et `isProprio` vivaient ICI depuis toujours. La règle la
//  plus déployée existait ; ces écrans ne la suivaient pas.
//
//  ⚠️ Et `mon-lot` définissait sa propre `isLocataire` tout en recomposant le
//  test deux lignes plus loin : une duplication n'a pas besoin de traverser le
//  dépôt pour diverger.
//
//  🔒 La QUESTION est posée par `#lib/roles` (`estLocataire`…), pour qu'elle
//  serve aussi à une personne qui n'est pas l'utilisateur courant — un membre
//  de l'annuaire du conseil syndical. Ici on ne fait que l'appliquer au
//  courant. Deux endroits, deux rôles, une seule écriture de la règle.
//
//  ⚠️ Ces dérivées disent ce qu'on AFFICHE, jamais ce qu'on autorise : les
//  droits sont tranchés par le serveur (`auth/deps`).

export const isLocataire = derived(currentUser, estLocataire);
export const isBailleur = derived(currentUser, estBailleur);
export const isResident = derived(currentUser, estResident);
/** Copropriétaire, qu'il habite son lot ou le loue. */
export const isCoproprietaire = derived(currentUser, estCoproprietaire);
/** Syndic ou mandataire — il gère, il n'habite pas. */
export const isGestionnaire = derived(currentUser, estGestionnaire);

/** Ce que l'utilisateur courant est, pour juger d'un onglet (`ongletsOuverts`). */
export const droitsOnglet = derived(
	[isAdmin, isOperateur, isProprioOuCS, isLocataire, isGestionnaire],
	([administrateur, operateur, proprioOuCS, locataire, gestionnaire]): DroitsOnglet => ({
		administrateur,
		operateur,
		proprioOuCS,
		locataire,
		gestionnaire,
	}),
);

/**
 * L'état d'authentification est-il RÉSOLU ?
 *
 * Faux tant que `authApi.me()` n'a pas répondu — succès comme échec. À ne pas
 * confondre avec `isAuthenticated`, qui vaut faux dans **deux** cas très
 * différents : « pas connecté » et « on ne sait pas encore ».
 *
 * Cette distinction n'existait pas, et un garde d'accès la confondait :
 * `admin/+layout.svelte` testait `$isAdmin` dans son `onMount`, en même temps que
 * `(app)/+layout.svelte` chargeait l'utilisateur. Le garde décidait donc toujours
 * sur une valeur encore vide, et **toute adresse `/admin/**` ouverte directement
 * — lien partagé, favori, F5 — renvoyait au tableau de bord, y compris pour un
 * administrateur.** En navigation interne l'utilisateur était déjà chargé, d'où un
 * défaut invisible depuis toujours (trouvé le 12/08/2026 en vérifiant
 * `/admin/patrimoine` dans un navigateur).
 *
 * Un garde doit attendre de SAVOIR avant de refuser : ne rien rendre pendant
 * l'attente, refuser sur un « non » avéré, jamais sur un « pas encore ».
 */
export const authResolue = writable(false);

export function setUser(user: User | null) {
	currentUser.set(user);
	authResolue.set(true);
}

/** L'authentification a répondu, sans utilisateur (visiteur non connecté). */
export function marquerAuthResolue() {
	authResolue.set(true);
}

/**
 * Exécuter `action` UNE fois, quand l'utilisateur est connu — à appeler pendant
 * l'initialisation d'un composant, à la place d'un `onMount` qui lirait un rôle.
 *
 * 🔴 Svelte monte la PAGE avant le LAYOUT : l'`onMount` d'un écran s'exécute avant
 * celui de `(app)/+layout.svelte`, qui charge l'utilisateur. Sur un chargement
 * direct ou un rechargement, `$isCS`, `$isLocataire`, `$currentUser`… y valent
 * encore `false` / `null`, et seule une navigation interne rend l'écran juste.
 * Deux récidives le même jour (#1486, 30/09/2026) : la file de modération jamais
 * demandée, et un bailleur qui voyait tous ses lots « Vacant ».
 *
 * Le remède était recopié écran par écran (`let charge = false; $: if
 * ($authResolue && !charge) { … }`) : il vit ici. 🔒 `npm run lint:gardes-auth`
 * refuse un rôle lu dans un `onMount`.
 */
export function quandAuthResolue(action: () => unknown): void {
	onMount(() => {
		let fait = false;
		return authResolue.subscribe((resolue) => {
			if (!resolue || fait) return;
			fait = true;
			void action();
		});
	});
}
