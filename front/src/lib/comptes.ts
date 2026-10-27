/**
 * Valider un compte en attente — le geste, et ce qu'il rend compte.
 *
 * ## Pourquoi ce module (12/09/2026, #889)
 *
 * Le geste était écrit **deux fois** : `admin` et `espace-cs`. Les deux appellent
 * `traiterCompte` puis, si l'on coche « Nouvel Arrivant », `accueilArrivant`.
 * Elles avaient déjà divergé, et pas sur un détail :
 *
 * | | `admin` | `espace-cs` |
 * |---|---|---|
 * | lots résolus automatiquement | annoncés | **tus** |
 * | copropriétaire aidé introuvable | averti | **tu** |
 * | aucun lot trouvé pour un copropriétaire | averti | **tu** |
 * | message d'accueil | « (bienvenue, consignes, demandes syndic/CS) » | « Actions d'accueil envoyées » |
 *
 * L'endpoint rend pourtant le même `auto_match` aux deux. Le conseil syndical
 * validait donc des comptes sans jamais savoir qu'un copropriétaire aidé n'avait
 * pas été retrouvé — l'information existait, elle n'était pas lue.
 *
 * 🔴 `standards/02` §4 bis : quand deux implémentations coexistent, on retient
 * **la plus disante**. C'est elle qui est ici, et les deux écrans l'obtiennent.
 */
import { admin as adminApi, type CompteTraite, type ResultatAutoMatch, type User } from '$lib/api';
import { nomAffiche } from '$lib/noms';

/** Un message à afficher, et le ton sur lequel le dire. */
export interface Annonce {
	ton: 'success' | 'warning' | 'error';
	texte: string;
}

/**
 * Ce que le serveur vient de faire, traduit en une phrase.
 *
 * ⚠️ Séparée de l'appel réseau pour être vérifiable sans rien monter : c'est la
 * partie qui porte les six cas, donc celle qui peut se tromper.
 */
/**  Ce que la validation lit du compte : identifiant, statut, nom de l'aidé(e). */
type CompteAValider = Pick<User, 'id' | 'statut' | 'nom_aide' | 'prenom_aide'>;

export function annonceValidation(reponse: CompteTraite, utilisateur: CompteAValider): Annonce {
	const auto = reponse?.auto_match;
	const aide = auto?.aide_match;
	if (aide?.aide_trouve) {
		const parts = [`Compte activé — aidé(e) : ${aide.aide_nom}`];
		if (aide.lots > 0) parts.push(`${aide.lots} lot(s)`);
		if (aide.tc > 0) parts.push(`${aide.tc} TC`);
		if (aide.vigik > 0) parts.push(`${aide.vigik} vigik`);
		if (aide.delegation) parts.push('délégation créée');
		return { ton: 'success', texte: parts.join(' — ') };
	}
	if (aide && !aide.aide_trouve) {
		const nom = nomAffiche(utilisateur?.prenom_aide, utilisateur?.nom_aide);
		return {
			ton: 'warning',
			texte: `Compte activé — ⚠️ Copropriétaire aidé(e) « ${nom} » non trouvé(e). Affectation manuelle requise.`,
		};
	}
	const locataire = annonceLocataire(auto, utilisateur?.statut);
	if (locataire) return { ton: locataire.ton, texte: `Compte activé — ${locataire.texte}` };
	const resolus = auto?.lots_resolus ?? 0;
	if (resolus > 0) {
		return {
			ton: 'success',
			texte: `Compte activé — ${resolus} lot(s) résolu(s) automatiquement.`,
		};
	}
	const trouves = auto?.lots ?? 0;
	if (trouves > 0) {
		return { ton: 'success', texte: `Compte activé — ${trouves} lot(s) trouvé(s) dans l'import.` };
	}
	//  ⚠️ Un AVERTISSEMENT, pas un succès : un copropriétaire sans lot ne pourra
	//  rien consulter. Le silence de l'espace CS sur ce cas est le défaut que ce
	//  module supprime.
	if (utilisateur?.statut?.startsWith('copropriétaire')) {
		return { ton: 'warning', texte: "Compte activé — ⚠️ Aucun lot trouvé dans l'import." };
	}
	return { ton: 'success', texte: 'Compte activé.' };
}

/**
 * Ce que l'appariement a fait d'un LOCATAIRE — `null` pour tout autre statut.
 *
 * Lue par la validation ET par « Relancer l'appariement » : un locataire resté
 * sans lot se taisait, et l'administration le rattachait à la main sans savoir
 * pourquoi (#2267).
 */
export function annonceLocataire(
	auto: Partial<ResultatAutoMatch> | undefined,
	statut: string | undefined,
): Annonce | null {
	if (statut !== 'locataire' || !auto) return null;
	const office = auto.lots_d_office ?? 0;
	if (office > 0) {
		return {
			ton: 'success',
			texte: `rattaché d'office à ${office} lot(s) du fichier des lots, badges remis.`,
		};
	}
	const badges = auto.badges_remis ?? 0;
	if (badges > 0) return { ton: 'success', texte: `${badges} badge(s) de ses lots remis.` };
	if ((auto.baux ?? 0) > 0 || (auto.rattache ?? 0) > 0) {
		return { ton: 'success', texte: 'rattaché à son bail ou à son bailleur.' };
	}
	return {
		ton: 'warning',
		texte:
			'⚠️ aucun lot désigné sans ambiguïté : il le déclarera dans « Mes lots », ou à rattacher à la main.',
	};
}

/** Ce que l'accueil d'un nouvel arrivant déclenche — dit en toutes lettres. */
export const ANNONCE_ACCUEIL =
	"Actions d'accueil envoyées (bienvenue, consignes, demandes syndic/CS).";

export interface ValidationDemandee {
	nouvelArrivant: boolean;
	batiment: string;
	ancienResident: string;
}

/**
 * Valide le compte, puis déclenche l'accueil si demandé.
 *
 * Rend les annonces à afficher, dans l'ordre — l'appelant les passe au toast.
 * Lève `ApiError` : c'est l'écran qui sait comment le dire.
 *
 * ⚠️ L'accueil part APRÈS la validation et jamais avant : il écrit au syndic et
 * au conseil syndical au sujet d'un compte qui doit exister.
 */
export async function validerCompte(
	utilisateur: CompteAValider,
	demande: ValidationDemandee,
): Promise<Annonce[]> {
	const reponse = await adminApi.traiterCompte(utilisateur.id, { action: 'valider' });
	const annonces: Annonce[] = [annonceValidation(reponse, utilisateur)];
	if (demande.nouvelArrivant) {
		await adminApi.accueilArrivant(utilisateur.id, {
			batiment: demande.batiment || null,
			ancien_resident: demande.ancienResident || null,
		});
		annonces.push({ ton: 'success', texte: ANNONCE_ACCUEIL });
	}
	return annonces;
}

//  🔴 `messageErreur` a été RETIRÉE d'ici le 12/09/2026 : elle existait AUSSI
//  dans `$lib/erreurs`, sous le même nom, et les deux ne disaient pas la même
//  chose.
//
//      ici        e.message ?? 'Erreur'
//      erreurs.ts 401 → « votre session a expiré, rechargez la page »
//                 403 → le message du serveur, ou « vous n'avez pas accès »
//                 réseau → « impossible de joindre le serveur »
//
//  ⚠️ L'ironie est instructive : ce fichier est né en retenant **la version la
//  plus disante** de la validation d'un compte, et il portait la version la
//  moins disante du message d'erreur. Deux écrans — `admin` et `espace-cs` —
//  l'importaient d'ici : un 401 leur affichait le message brut du serveur au
//  lieu de dire quoi faire, alors que #519 avait tranché le contraire.
//
//  Elle vit désormais dans `$lib/erreurs`, et là seulement.

/**
 * **Le formulaire d'un compte, en administration** — vierge ou repris.
 *
 * ## 🔴 Pourquoi ici (15/09/2026)
 *
 * Les **huit mêmes clés** étaient énumérées **deux fois** dans
 * `admin/+page.svelte` : la déclaration et `openEdit()`. Ajouter un champ
 * demandait de le poser aux deux endroits — et un champ manqué à l'un des deux
 * donne un formulaire qui affiche une valeur vide sur un compte qui la porte,
 * puis l'efface à l'enregistrement. **En silence.**
 *
 * C'est le troisième écran de la journée à porter ce défaut, après le
 * calendrier (2 écritures), les contrats (3) et les baux (4).
 */
export interface FormulaireCompte {
	nom: string;
	prenom: string;
	email: string;
	telephone: string;
	societe: string;
	statut: string;
	batiment_id: number | null;
	actif: boolean;
	/** Où la personne habite — `0` est le rez-de-chaussée, jamais une absence. */
	etage: number | null;
	/** Pour un locataire : le nom de son bailleur, tel qu'il l'a saisi (#1155). */
	nom_proprietaire: string;
}

/**
 * Le formulaire d'un compte — vide, ou rempli depuis un compte existant.
 *
 * ⚠️ `actif` vaut `true` par défaut : un compte qu'on crée est actif, et
 * proposer l'inverse ferait d'un oubli de case une désactivation.
 */
export function formulaireCompte(
	u?: { [K in keyof FormulaireCompte]?: FormulaireCompte[K] | null } | null,
): FormulaireCompte {
	return {
		nom: u?.nom ?? '',
		prenom: u?.prenom ?? '',
		email: u?.email ?? '',
		telephone: u?.telephone ?? '',
		societe: u?.societe ?? '',
		statut: u?.statut ?? '',
		batiment_id: u?.batiment_id ?? null,
		actif: u?.actif ?? true,
		etage: u?.etage ?? null,
		nom_proprietaire: u?.nom_proprietaire ?? '',
	};
}

/**
 * Les ÉTIQUETTES d'un compte dans la liste des utilisateurs — Loti, TC, Vigik,
 * Bail —, avec ce que chacune dit dans ses trois états (26/09/2026).
 *
 * L'ÉTAT vient du serveur (`utils/etiquettes_compte`) : lui seul connaît les
 * types de lots du compte. Ici, les mots. Les quatre blocs étaient recopiés
 * dans la page, sans info-bulle : un rouge ne disait pas de quoi il manquait.
 */
export const ETIQUETTES_COMPTE: readonly {
	cle: 'loti' | 'tc' | 'vigik' | 'bail';
	libelle: string;
	ok: string;
	manque: string;
	sansObjet: string;
}[] = [
	{
		cle: 'loti',
		libelle: 'Loti',
		ok: 'Rattaché à au moins un lot',
		manque: 'Aucun lot rattaché',
		sansObjet: '',
	},
	{
		cle: 'tc',
		libelle: 'TC',
		ok: 'Porte une télécommande',
		manque: 'Un parking, mais aucune télécommande',
		sansObjet: 'Sans objet : aucun parking',
	},
	{
		cle: 'vigik',
		libelle: 'Vigik',
		ok: 'Porte un badge Vigik',
		manque: 'Un appartement, mais aucun Vigik',
		sansObjet: 'Sans objet : aucun appartement',
	},
	{
		cle: 'bail',
		libelle: 'Bail',
		ok: 'Un bail enregistré',
		manque: 'Bailleur ou locataire, mais aucun bail enregistré',
		sansObjet: 'Sans objet : ni bailleur, ni locataire',
	},
];

/**
 * L'adresse saisie est-elle une AUTRE adresse que celle du compte (#1549) ?
 *
 * Changer l'adresse d'un compte demande le mot de passe de qui agit, puis la
 * confirmation de la nouvelle par un lien : l'écran ne demande le mot de passe
 * que si c'est bien un changement. La casse et les espaces n'en font pas un —
 * le serveur compare de même (`auth/adresse_compte.normaliser_adresse`), et il
 * reste seul juge : l'écran ne fait que savoir quoi demander.
 */
export function adresseChangee(
	saisie: string | null | undefined,
	actuelle: string | null | undefined,
): boolean {
	return formeAdresse(saisie) !== '' && formeAdresse(saisie) !== formeAdresse(actuelle);
}

/** Minuscules, espaces retirés — rien de plus, comme côté serveur. */
function formeAdresse(adresse: string | null | undefined): string {
	return (adresse ?? '').trim().toLowerCase();
}

/**
 * Ce que l'écran annonce une fois le changement demandé — la nouvelle adresse
 * n'est PAS encore celle du compte, et c'est ce qu'il faut dire.
 *
 * `parUnTiers` : l'administrateur change l'adresse d'un autre compte ; c'est
 * alors le titulaire qui confirmera, pas celui qui lit l'annonce.
 */
export function annonceLienEnvoye(nouvelle: string, parUnTiers = false): string {
	const adresse = formeAdresse(nouvelle);
	return parUnTiers
		? `Un lien de confirmation a été envoyé à ${adresse}. L’adresse actuelle reste celle du compte jusqu’à ce que son titulaire clique dessus.`
		: `Un lien de confirmation a été envoyé à ${adresse}. Votre adresse actuelle reste celle du compte jusqu’à ce que vous cliquiez dessus.`;
}
