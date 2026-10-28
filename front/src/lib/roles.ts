/**
 * Comment un **rôle** et un **statut** s'écrivent — jumeau front de
 * `api/app/utils/roles_libelles.py`.
 *
 * ## 🔴 Pourquoi ce fichier (#801, 06/09/2026)
 *
 * La même notion était écrite **six fois** — trois côté serveur, trois ici — et
 * les six avaient dérivé :
 *
 * | Où | `conseil_syndical` | `copropriétaire_résident` |
 * |---|---|---|
 * | API `ajouter_role` | « Membre du Conseil Syndical » | — |
 * | API `retirer_role` | « Conseil Syndical » | — |
 * | API `changer_role` | « Membre du Conseil Syndical » | — |
 * | front `admin` | « Conseil syndical » | « Copropriétaire **R**ésident » |
 * | front `profil` | « Conseil syndical » | « Copropriétaire **R**ésident » |
 * | front `tableau-de-bord` | « Conseil syndical » | « Copropriétaire **r**ésident » |
 *
 * Le même rôle s'annonçait donc autrement selon qu'on l'attribuait ou qu'on le
 * retirait — dans deux notifications que **la même personne** reçoit — et le
 * même statut changeait de casse d'un écran à l'autre. Aucune écriture n'était
 * fausse ; c'est l'ensemble qui n'avait pas de logique.
 *
 * ⚠️ **Aucun garde-fou ne pouvait le voir**, et c'est ce qui l'a laissé passer :
 * six tables cohérentes chacune avec elle-même. Deux tables d'accord entre elles
 * ne prouvent rien (`standards/02` §3 bis) — il fallait les comparer à une
 * référence, et il n'y en avait pas.
 *
 * ## Ce qui est tranché
 *
 * « **Conseil syndical** » et « **Copropriétaire résident** » : l'orthographe
 * française ne met pas de capitale au second terme d'un nom commun composé, et
 * c'était déjà la forme majoritaire. « Membre du Conseil Syndical » disait la
 * même chose en plus long, dans une phrase qui portait déjà le mot « rôle ».
 *
 * ## La duplication front ⇄ API est inévitable — d'où le test
 *
 * Les contextes de build sont `./api` et `./front` : rien de la racine n'entre
 * dans les images (mémoire `project_partage_front_api_impossible`). Le seul
 * motif viable est **copie + concordance exécutée**, celui de `noms.ts`.
 *
 * 🔒 `api/tests/test_roles_libelles.py` lit CE fichier et vérifie que les deux
 * tables portent exactement les mêmes chaînes.
 *
 * ## Rôle ≠ statut, et le produit distingue les deux
 *
 * Le **rôle** dit ce qu'un compte a le droit de faire ; le **statut** dit ce
 * qu'une personne est dans la copropriété. Un copropriétaire bailleur peut être
 * membre du conseil syndical : deux tables, jamais une.
 */

import { parAttribut } from '#lib/table-statuts.ts';

/**  Les rôles — `RoleUtilisateur` côté serveur.

     Le libellé et la teinte se déclarent ENSEMBLE : ils étaient deux tables aux
     cinq mêmes clés, à cent lignes d'écart, et le commentaire de la seconde
     devait rappeler « une clé par entrée de `LIBELLES_ROLE`, sans exception ».
     Un contrat qu'un commentaire doit énoncer est un contrat que la structure
     ne porte pas.  */
const ROLE = parAttribut({
	résident: { libelle: 'Résident', badge: 'badge-gray' },
	propriétaire: { libelle: 'Propriétaire', badge: 'badge-teal' },
	conseil_syndical: { libelle: 'Conseil syndical', badge: 'badge-blue' },
	admin: { libelle: 'Admin', badge: 'badge-orange' },
	externe: { libelle: 'Externe', badge: 'badge-yellow' },
	//  L'opérateur de la plateforme (#1750) : pas un rôle de la copropriété, mais
	//  un compte le porte — `ROLE_OPERATEUR` côté serveur (`models/roles.py`).
	operateur: { libelle: 'Opérateur', badge: 'badge-purple' },
});

export const LIBELLES_ROLE: Record<string, string> = ROLE.libelle;

/**  Les statuts — `StatutUtilisateur` côté serveur.

     Trois attributs, une déclaration : le libellé, sa forme abrégée pour un
     tableau dense, et la teinte. Ils vivaient dans trois tables de sept clés,
     et c'est la copie de la table ABRÉGÉE qui avait perdu `admin_technique`
     (cf. plus bas) — un état sur sept, dans la seule des trois qu'on relit le
     moins.  */
const STATUT = parAttribut({
	copropriétaire_résident: {
		libelle: 'Copropriétaire résident',
		abrege: 'Copro. résident',
		badge: 'badge-green',
	},
	copropriétaire_bailleur: {
		libelle: 'Copropriétaire bailleur',
		abrege: 'Copro. bailleur',
		badge: 'badge-blue',
	},
	locataire: { libelle: 'Locataire', abrege: 'Locataire', badge: 'badge-purple' },
	syndic: { libelle: 'Syndic', abrege: 'Syndic', badge: 'badge-orange' },
	mandataire: { libelle: 'Mandataire', abrege: 'Mandataire', badge: 'badge-gray' },
	aidant: { libelle: 'Aidant (proche)', abrege: 'Aidant (proche)', badge: 'badge-yellow' },
	admin_technique: {
		libelle: 'Compte technique',
		abrege: 'Compte technique',
		badge: 'badge-orange',
	},
});

export const LIBELLES_STATUT: Record<string, string> = STATUT.libelle;

/**  Les profils qu'un utilisateur peut DEMANDER depuis son profil — ni aidant
 *   (une délégation), ni compte technique. */
export const STATUTS_DEMANDABLES = [
	'copropriétaire_résident',
	'copropriétaire_bailleur',
	'locataire',
	'mandataire',
	'syndic',
] as const;

/**
 *  Les statuts, ABRÉGÉS — pour un tableau dense (#828).
 *
 *  🔴 Écrite DEUX fois dans `admin/+page.svelte`, à trente lignes d'écart et
 *  dans le même fichier (`statutLabels` et `statutLabelsAdmin`). Les deux
 *  copies différaient d'une clé : `admin_technique` manquait à la seconde, si
 *  bien qu'une demande de profil émanant d'un compte technique affichait
 *  `admin_technique` — la valeur brute de l'énumération. Un libellé manquant
 *  ne lève pas, il s'imprime.
 *
 *  ⚠️ Ce n'est PAS le `LIBELLES_STATUT_COURT` du serveur, qui existe pour une
 *  raison opposée : masquer si la personne habite son lot ou le loue
 *  (`utils/roles_libelles.py` — « Copropriétaire » tout court). L'administration
 *  a précisément besoin de cette distinction ; elle abrège pour la place, pas
 *  pour taire. Trois notions, trois tables, et c'est voulu.
 *
 *  🔒 `test_roles_libelles.py` exige une clé par entrée de `LIBELLES_STATUT`,
 *  sans exception — le contrat que `BADGE_ROLE` et `BADGE_STATUT` ont déjà, et
 *  qui aurait attrapé le trou d'`admin_technique`.
 */
export const LIBELLES_STATUT_ABREGE: Record<string, string> = STATUT.abrege;

/**
 *  Anciennes clés encore présentes en base ou dans des réponses d'API.
 *
 *  ⚠️ Elles sont **à part**, et pas mêlées aux deux tables ci-dessus : celles-ci
 *  décrivent les énumérations actuelles et sont vérifiées contre le serveur.
 *  Fondre l'ancien dans le nouveau ferait échouer la concordance — ou, pire,
 *  obligerait à ajouter ces clés côté serveur pour faire passer le test, donc à
 *  ressusciter ce qu'on est en train de retirer.
 */
const LIBELLES_HERITES: Record<string, string> = {
	bailleur: 'Copropriétaire bailleur',
};

/** « conseil_syndical » → « Conseil syndical ». Une clé inconnue est rendue
 *  **telle quelle** : un libellé manquant doit se voir, pas s'effacer. */
export function libelleRole(role: string | null | undefined): string {
	if (!role) return '';
	return LIBELLES_ROLE[role] ?? LIBELLES_HERITES[role] ?? LIBELLES_STATUT[role] ?? role;
}

/** « copropriétaire_résident » → « Copropriétaire résident ». */
export function libelleStatut(statut: string | null | undefined): string {
	if (!statut) return '';
	return LIBELLES_STATUT[statut] ?? LIBELLES_HERITES[statut] ?? LIBELLES_ROLE[statut] ?? statut;
}

/*  ══════════════════════════════════════════════════════════════════════════
    LA TEINTE — le second demi du vocabulaire, resté recopié (#819)

    #809 a fait de ce fichier la source unique des LIBELLÉS de rôle et de
    statut. La COULEUR, elle, est restée écrite dans les écrans : `/admin` et
    `/profil` importaient tous deux `libelleRole`, puis recopiaient la table des
    badges trois lignes plus bas.

    🔴 Ce que la copie coûtait déjà : `/profil` ne connaissait ni
    `propriétaire` ni `externe`. Un compte portant l'un de ces rôles s'affichait
    en **gris** sur son propre profil et en **teal** ou **jaune** dans
    l'administration. Rien ne le signalait — le repli `?? 'badge-gray'` rend un
    badge parfaitement normal, et c'est ce qui rend l'oubli durable.

    ⚠️ DEUX tables, et la divergence est VOULUE. Le même mot n'a pas la même
    teinte selon qu'on le lit comme un rôle ou comme un statut :

        copropriétaire_bailleur   rôle → violet    statut → bleu
        locataire                 rôle → gris      statut → violet
        mandataire                rôle → jaune     statut → gris

    C'est la distinction que le produit fait partout (le rôle dit ce qu'un
    compte a le droit de faire, le statut ce qu'une personne EST) et que
    `LIBELLES_STATUT_COURT` acte déjà côté serveur. Les aligner effacerait
    l'information au lieu de l'unifier.
    ══════════════════════════════════════════════════════════════════════════ */

/**  La teinte d'un RÔLE — désormais INSÉPARABLE de son libellé : elle est
 *   déclarée dans la même entrée, donc « une clé par entrée » n'est plus une
 *   règle à vérifier, c'est la forme de la table. */
export const BADGE_ROLE: Record<string, string> = ROLE.badge;

/**  La teinte d'un STATUT, même principe. */
export const BADGE_STATUT: Record<string, string> = STATUT.badge;

/**  Les anciennes clés, lues COMME DES RÔLES — à part, pour la même raison que
 *   `LIBELLES_HERITES` : elles ne doivent pas entrer dans la concordance avec
 *   les énumérations du serveur. */
const BADGE_HERITES: Record<string, string> = {
	locataire: 'badge-gray',
	copropriétaire_résident: 'badge-teal',
	copropriétaire_bailleur: 'badge-purple',
	bailleur: 'badge-purple',
	syndic: 'badge-orange',
	mandataire: 'badge-yellow',
};

/** La classe de badge d'un rôle. Repli gris : une teinte inconnue ne doit pas
 *  faire disparaître le badge, seulement le rendre neutre. */
export function badgeRole(role: string | null | undefined): string {
	if (!role) return 'badge-gray';
	return BADGE_ROLE[role] ?? BADGE_HERITES[role] ?? 'badge-gray';
}

/**
 * Les badges à afficher pour une liste de rôles — **sans libellé répété**.
 *
 * 🔴 DEUX RÔLES PEUVENT RENDRE LE MÊME LIBELLÉ, et c'est voulu : `bailleur` est
 * l'alias hérité de `copropriétaire_bailleur`, tous deux « Copropriétaire
 * bailleur » (`LIBELLES_HERITES`). Un compte qui porte les deux — ce que rien
 * n'interdit en base — produisait donc deux badges identiques.
 *
 * Sur `/profil` c'était disgracieux. Sur `/admin`, la colonne « Rôles actifs »
 * les rendait par `{#each … (d.label)}` : deux clés égales, donc
 * `each_key_duplicate`, **erreur fatale de Svelte** — l'écran Utilisateurs se
 * figeait entièrement, et plus aucune navigation ne répondait ensuite
 * (16/09/2026, second incident du même jour après `pages_order`).
 *
 * ⚠️ Le dédoublonnage porte sur le LIBELLÉ, pas sur le rôle : ce sont les
 * libellés qui s'affichent, et deux alias du même rôle ne méritent qu'un badge.
 * La teinte retenue est celle du premier rôle rencontré.
 */
export function badgesDeRoles(
	roles: (string | null | undefined)[],
): { label: string; cls: string }[] {
	const vus = new Set<string>();
	const badges: { label: string; cls: string }[] = [];
	for (const role of roles) {
		const label = libelleRole(role);
		if (!label || vus.has(label)) continue;
		vus.add(label);
		badges.push({ label, cls: badgeRole(role) });
	}
	return badges;
}

/** La classe de badge d'un statut. */
export function badgeStatut(statut: string | null | undefined): string {
	if (!statut) return 'badge-gray';
	return BADGE_STATUT[statut] ?? 'badge-gray';
}

// ─────────────────────────────────────────────────────────────────────────────
//  Ce qu'une personne EST — les prédicats, et non le littéral (15/09/2026)
// ─────────────────────────────────────────────────────────────────────────────
//
//  🔴 Le même test était réécrit d'un écran à l'autre :
//
//  | Notion | Écrite dans |
//  |---|---|
//  | « est locataire » | `OngletAcces`, `AccesConnexes`, `calendrier`, `mon-lot`, `residence`, `tableau-de-bord` — **six** fichiers |
//  | « est bailleur » | `OngletAcces`, `mon-lot` |
//  | « est syndic **ou** mandataire » | `PageCommunaute`, `sondages/[id]` |
//  | « est bailleur **ou** résident » | `mon-lot`, **deux fois dans le même fichier** |
//
//  ⚠️ Et `mon-lot` définissait `isLocataire` en ligne 92 tout en recomposant
//  `$currentUser?.statut === 'locataire'` aux lignes 172 et 449 : la dérivée
//  existait, dans le fichier même, et n'était pas employée.
//
//  ⚠️ Plus grave, le commentaire de `sondages/[id]` affirmait *« cet écran ne
//  réécrit pas la règle d'accès à la Communauté »* — juste au-dessus de la ligne
//  qui la réécrit. Le seul endroit qui parlait du sujet disait que le problème
//  n'existait pas.
//
//  🔒 **Pourquoi des prédicats et pas des constantes.** `STATUT.LOCATAIRE`
//  supprimerait le littéral sans nommer la QUESTION posée, et les deux notions
//  composées (« gestionnaire », « copropriétaire ») resteraient écrites à
//  chaque appel — c'est-à-dire là où elles peuvent diverger. Ce sont elles qui
//  coûtent, pas la chaîne.
//
//  ⚠️ Ces prédicats décrivent ce qu'on AFFICHE, jamais ce qu'on autorise. Les
//  droits sont tranchés par le serveur (`auth/deps`), et un écran qui montrerait
//  un bouton de trop ne donne aucun accès. Les employer pour « protéger »
//  quelque chose serait la faute que `standards/03` §1 nomme.

/**  Le statut d'une personne, quelle que soit la forme sous laquelle il arrive. */
type PorteurDeStatut = { statut?: string | null } | null | undefined;

const statutDe = (p: PorteurDeStatut): string => p?.statut ?? '';

/**  Locataire — il occupe sans posséder. */
export const estLocataire = (p: PorteurDeStatut): boolean => statutDe(p) === 'locataire';

/**  Copropriétaire qui LOUE son lot. */
export const estBailleur = (p: PorteurDeStatut): boolean =>
	statutDe(p) === 'copropriétaire_bailleur';

/**  Copropriétaire qui HABITE son lot. */
export const estResident = (p: PorteurDeStatut): boolean =>
	statutDe(p) === 'copropriétaire_résident';

/**  Copropriétaire, qu'il habite son lot ou le loue.
 *
 *  La notion que `mon-lot` composait deux fois : « qui possède un lot et peut
 *  donc en consulter les baux ». Qu'il y habite ne change rien à cette
 *  question-là. */
export const estCoproprietaire = (p: PorteurDeStatut): boolean => estBailleur(p) || estResident(p);

/**  Le GESTIONNAIRE — syndic ou mandataire.
 *
 *  Ce n'est pas un résident de la copropriété : il gère pour le compte du
 *  syndicat. C'est ce qui lui ferme la Communauté, dont l'API porte la règle et
 *  le motif de refus. */
export const estGestionnaire = (p: PorteurDeStatut): boolean =>
	statutDe(p) === 'syndic' || statutDe(p) === 'mandataire';

/**  Celui qui agit POUR quelqu'un d'autre — aidant (proche) ou mandataire.
 *
 *  C'est ce qui donne un sens au champ `nom_aide` : la personne représentée.
 *  Un aidant n'est pas un gestionnaire, et l'annuaire du conseil syndical a
 *  besoin d'afficher « Aidé : … » pour les deux.
 *
 *  ⚠️ **`mandataire` appartient aux DEUX notions**, et ce n'est pas une erreur :
 *  il gère pour le compte du syndicat (`estGestionnaire`, ce qui lui ferme la
 *  Communauté) *et* il représente une personne nommée (`agitPourAutrui`, ce qui
 *  fait afficher qui). Deux questions différentes sur le même statut — les
 *  fondre en une donnerait une réponse fausse à l'une des deux.
 *
 *  🔴 Trouvée par `lint:statuts` lui-même, dans `espace-cs` : mon relevé à la
 *  main l'avait manquée. Un contrôle voit ce qu'une lecture ne voit pas. */
export const agitPourAutrui = (p: PorteurDeStatut): boolean =>
	statutDe(p) === 'aidant' || statutDe(p) === 'mandataire';

/**  Les clés sur lesquelles ces prédicats se prononcent.
 *
 *  🔒 Lue par `npm run lint:statuts`, qui vérifie qu'aucune n'est inconnue de
 *  `LIBELLES_STATUT` ET que cette liste est exactement l'ensemble des chaînes
 *  que les prédicats ci-dessus comparent (`statutDe(p) === '…'`) : ajouter un
 *  prédicat, c'est donc l'ajouter ici. Un prédicat bâti sur une chaîne fautive —
 *  un accent oublié dans « copropriétaire_résident » — serait **toujours faux**,
 *  et rien ne le signalerait : l'écran afficherait simplement moins de choses.
 *  (Rétabli le 02/10/2026, #1577 : ce commentaire l'affirmait déjà, et plus
 *  aucun contrôle ne lisait la liste.) */
export const STATUTS_TESTES = [
	'locataire',
	'copropriétaire_bailleur',
	'copropriétaire_résident',
	'syndic',
	'mandataire',
	'aidant',
] as const;
