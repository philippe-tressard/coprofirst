/**
 *  L'APERÇU de la pastille de lecture, simulé — `POST /lectures/apercu` (#2633).
 *
 *  Un e2e ne recopie pas la règle « qui la lit » : il rend la réponse que le
 *  SERVEUR donne à cette saisie, rangée dans `apercus-lecture.json` et vérifiée
 *  contre la règle par `api/tests/test_apercus_lecture_e2e.py`. Une saisie
 *  absente du fichier répond 500 et se NOMME dans la sortie : on l'ajoute au
 *  fichier, le test Python dit alors si la réponse est juste.
 */
import { readFileSync } from 'node:fs';

type Saisie = {
	categorie?: string | null;
	statut?: string | null;
	confidentiel?: boolean;
	public_cible?: string[];
	perimetre_cible?: string[];
	reserve_perimetre?: boolean;
};

const DONNEES: { reponses: { saisie: Saisie; apercu: unknown }[] } = JSON.parse(
	readFileSync(new URL('./apercus-lecture.json', import.meta.url), 'utf8'),
);

/** La forme canonique d'une saisie — celle de `#lib/apercu-lecture` (`cle`). */
export function cleSaisie(s: Saisie): string {
	return JSON.stringify([
		s.categorie ?? null,
		s.statut ?? null,
		!!s.confidentiel,
		[...(s.public_cible ?? [])].sort(),
		[...(s.perimetre_cible ?? [])].sort(),
		!!s.reserve_perimetre,
	]);
}

const PAR_CLE = new Map(DONNEES.reponses.map((r) => [cleSaisie(r.saisie), r.apercu]));

/** La réponse du serveur à l'aperçu demandé, `undefined` pour une autre route (ou une
 *  saisie inconnue du fichier, nommée dans la sortie). */
export function reponseApercu(chemin: string, requete: { postDataJSON(): unknown }): unknown {
	if (chemin !== '/api/lectures/apercu') return undefined;
	const saisie = requete.postDataJSON() as Saisie;
	const reponse = PAR_CLE.get(cleSaisie(saisie));
	if (reponse === undefined) {
		console.error(`[apercus-lecture] saisie absente du fichier : ${JSON.stringify(saisie)}`);
	}
	return reponse;
}

/** La pastille qu'un objet enregistré SERT (`lecture`) — celle de l'aperçu de ses
 *  propres champs, la même règle (`test_lectures_apercu.py` le prouve au serveur). */
export function lectureServie(saisie: Saisie): unknown {
	const reponse = PAR_CLE.get(cleSaisie(saisie)) as { lecture: unknown } | undefined;
	if (!reponse) throw new Error(`[apercus-lecture] saisie absente : ${JSON.stringify(saisie)}`);
	return reponse.lecture;
}
