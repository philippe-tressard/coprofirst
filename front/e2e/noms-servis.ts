/**
 *  Le NOM d'une personne, tel que le serveur le sert (#2633).
 *
 *  Un e2e ne recopie pas la règle « Prénom NOM » : un compte simulé porte le
 *  `nom_affiche` que le SERVEUR rend, rangé dans `noms-servis.json` et vérifié
 *  contre `utils/noms.nom_affiche` par `api/tests/test_noms_servis_e2e.py`. Une
 *  saisie (`POST /noms/affiche`) répond de même ; une personne absente du fichier
 *  se NOMME dans la sortie : on l'ajoute, le test Python dit si le nom est juste.
 */
import { readFileSync } from 'node:fs';

type Personne = { prenom?: string | null; nom?: string | null };

const DONNEES: { noms: { prenom: string; nom: string; nom_affiche: string }[] } = JSON.parse(
	readFileSync(new URL('./noms-servis.json', import.meta.url), 'utf8'),
);

const cle = (p: Personne) => JSON.stringify([p.prenom ?? '', p.nom ?? '']);
const PAR_CLE = new Map(DONNEES.noms.map((n) => [cle(n), n.nom_affiche]));

/** Le `nom_affiche` que le serveur sert pour cette personne. */
export function nomServi(p: Personne): string {
	const nom = PAR_CLE.get(cle(p));
	if (nom === undefined) throw new Error(`[noms-servis] personne absente : ${cle(p)}`);
	return nom;
}

/** La personne, avec le nom que le serveur lui sert — pour un compte simulé. */
export function avecNomServi<P extends Personne>(p: P): P & { nom_affiche: string } {
	return { ...p, nom_affiche: nomServi(p) };
}

/** La réponse de `POST /noms/affiche`, `undefined` pour une autre route. */
export function reponseNom(chemin: string, requete: { postDataJSON(): unknown }): unknown {
	if (chemin !== '/api/noms/affiche') return undefined;
	const saisie = requete.postDataJSON() as Personne;
	const nom = PAR_CLE.get(cle(saisie));
	if (nom === undefined) {
		console.error(`[noms-servis] personne absente du fichier : ${cle(saisie)}`);
		return undefined;
	}
	return { nom_affiche: nom };
}
