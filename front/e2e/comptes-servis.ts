/**
 *  Le compte simulé, tel que le serveur le sert : son `est_moderateur` (#2633).
 *
 *  Un e2e ne recopie pas la règle « conseil syndical ou administration » : le
 *  champ vient de `moderateurs-servis.json`, vérifié contre `auth/deps.est_moderateur`
 *  par `api/tests/test_moderateurs_servis_e2e.py`. `simulerApi` l'applique à toute
 *  réponse de `/api/auth/me` ; un jeu de rôles absent du fichier se NOMME.
 */
import { readFileSync } from 'node:fs';

type Compte = { role?: string | null; roles?: string[] | null; est_moderateur?: boolean };

const DONNEES: { comptes: { roles: string[]; est_moderateur: boolean }[] } = JSON.parse(
	readFileSync(new URL('./moderateurs-servis.json', import.meta.url), 'utf8'),
);

const cle = (roles: string[]) => JSON.stringify([...roles].sort());
const PAR_ROLES = new Map(DONNEES.comptes.map((c) => [cle(c.roles), c.est_moderateur]));

/** Le compte, avec le `est_moderateur` que le serveur lui sert — sauf s'il le porte déjà. */
export function compteServi(corps: unknown): unknown {
	const compte = corps as Compte | null;
	if (!compte || typeof compte !== 'object' || compte.est_moderateur !== undefined) return corps;
	const roles = compte.roles?.length ? compte.roles : compte.role ? [compte.role] : [];
	const servi = PAR_ROLES.get(cle(roles));
	if (servi === undefined) throw new Error(`[moderateurs-servis] rôles absents : ${cle(roles)}`);
	return { ...compte, est_moderateur: servi };
}
