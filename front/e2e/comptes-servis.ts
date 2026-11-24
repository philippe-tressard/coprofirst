/**
 *  Le compte simulé, tel que le serveur le sert : son `est_moderateur` (#2633) et
 *  son `acces_menu` (#2969).
 *
 *  Un e2e ne recopie pas une règle du serveur : chaque champ vient d'une table
 *  vérifiée contre le code de l'API — `moderateurs-servis.json` par
 *  `api/tests/test_moderateurs_servis_e2e.py`, `acces-menu-servis.json` par
 *  `api/tests/test_acces_menu.py`. `simulerApi` l'applique à toute réponse de
 *  `/api/auth/me` ; un compte absent d'une table se NOMME.
 */
import { readFileSync } from 'node:fs';

type Compte = {
	role?: string | null;
	roles?: string[] | null;
	statut?: string | null;
	delegations_aidant?: unknown[] | null;
	est_moderateur?: boolean;
	acces_menu?: string[];
};

const lire = <T>(fichier: string): T =>
	JSON.parse(readFileSync(new URL(fichier, import.meta.url), 'utf8'));

const MODERATEURS = lire<{ comptes: { roles: string[]; est_moderateur: boolean }[] }>(
	'./moderateurs-servis.json',
);
const MENUS = lire<{
	comptes: { statut: string | null; roles: string[]; aidant: boolean; acces_menu: string[] }[];
}>('./acces-menu-servis.json');

const cle = (roles: string[]) => JSON.stringify([...roles].sort());
const cleMenu = (statut: string | null | undefined, roles: string[], aidant: boolean) =>
	JSON.stringify([statut ?? null, [...roles].sort(), aidant]);

const PAR_ROLES = new Map(MODERATEURS.comptes.map((c) => [cle(c.roles), c.est_moderateur]));
const MENU_PAR_COMPTE = new Map(
	MENUS.comptes.map((c) => [cleMenu(c.statut, c.roles, c.aidant), c.acces_menu]),
);

/** Le compte, avec les champs que le serveur lui sert — sauf ceux qu'il porte déjà. */
export function compteServi(corps: unknown): unknown {
	const compte = corps as Compte | null;
	if (!compte || typeof compte !== 'object') return corps;
	const roles = compte.roles?.length ? compte.roles : compte.role ? [compte.role] : [];
	const servi = { ...compte };
	if (servi.est_moderateur === undefined) {
		const moderateur = PAR_ROLES.get(cle(roles));
		if (moderateur === undefined)
			throw new Error(`[moderateurs-servis] rôles absents : ${cle(roles)}`);
		servi.est_moderateur = moderateur;
	}
	if (servi.acces_menu === undefined) {
		const k = cleMenu(compte.statut, roles, (compte.delegations_aidant?.length ?? 0) > 0);
		const menu = MENU_PAR_COMPTE.get(k);
		if (menu === undefined) throw new Error(`[acces-menu-servis] compte absent : ${k}`);
		servi.acces_menu = menu;
	}
	return servi;
}
