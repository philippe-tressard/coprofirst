/**
 * Le CADRE d'interface, en types : une entité, quatre rendus.
 *
 * Décidé par l'utilisateur le 17/08/2026 (#430), après le relevé des 42 couples
 * menu/entité. Ce fichier ne décrit AUCUNE entité — il décrit la forme que prend
 * la description d'une entité. Les entités elles-mêmes vivent à côté
 * (`ticket.ts`, puis `actualite.ts`, `evenement.ts`…).
 *
 * ## Ce qu'on a mesuré, et qui a fait naître ce fichier
 *
 * Ce que les quatre états ont en commun n'est pas « le formulaire », c'est **la
 * description de l'entité** : la liste de ses sections, leur ordre, ce qu'elles
 * portent, leur caractère requis. Ce qui diffère est le **rendu** (lecture /
 * saisie), la **valeur** (défaut / existante / héritée) et le **geste**
 * (POST / PATCH / évolution tracée).
 *
 * Sans déclaration, chaque état réinvente ce que l'autre portait déjà : **13
 * éditions sur 23 le faisaient**, et **5 seulement** portaient une raison écrite.
 * C'est exactement ce que `lib/pages.ts` a réglé pour l'identité des pages
 * (#401, #420) — une table unique, et un contrôle qui refuse qu'on la recopie.
 *
 * ## R4 est la clé de voûte : une divergence SANS MOTIF est refusée
 *
 * Trois motifs, trois seulement :
 *
 *   • `geste`  — la section est un ACTE qui n'a pas lieu dans cet état. La
 *                Diffusion en édition : une correction n'est pas une nouvelle,
 *                et rejouer les canaux renverrait un message à chaque faute de
 *                frappe rattrapée (incident du triple envoi WhatsApp, 14/08/2026).
 *   • `hérité` — la valeur vient de l'objet porteur. Le titre d'un ticket dans
 *                une évolution : l'entrée se rattache au ticket, elle ne le
 *                renomme pas.
 *   • `api`    — ⚠️ **motif de DETTE, jamais de conception.** Il DOIT citer un
 *                ticket. Une contrainte serveur qu'on subit se note pour être
 *                corrigée, pas pour être entérinée.
 *
 * `npm run lint:etats` refuse une divergence sans motif, un motif `api` sans
 * ticket, une section rendue hors déclaration et un ordre qui s'écarte de
 * `SECTIONS_ORDRE` — « Affaires liées » ajoutée par #1342 ; #1095 avait scindé « Champs spécifiques »
 * en Nature, Au nom de et Mise en avant, trois sections ajoutées (Équipement,
 * Intervenant, Quand), et Photos et
 * Documents n'en font plus qu'une, « Pièces jointes »).
 *
 * ## Ce fichier ne se recopie pas
 *
 * Ni l'ordre des sections, ni leurs libellés, ni la liste des états ne
 * s'écrivent ailleurs. Une seconde table diverge de la première au premier lot
 * suivant — c'est déjà arrivé aux périmètres (#316), aux canaux de notification,
 * aux statuts de ticket (#415) et aux pages (#401).
 */

/**  Les sections du cadre — leur NOMBRE est la longueur de `SECTIONS_ORDRE`, et ne s'écrit nulle part
 *   en toutes lettres (#1541 : « treize » est resté six jours dans CLAUDE.md et `ux-patterns` après
 *   l'entrée d'« Affaires liées », le 26/09/2026, #1342). L'identifiant est technique ; le libellé est à l'écran.
 *
 *   ⚠️ Ce nombre a dit « neuf » jusqu'au 21/09/2026 alors que la liste en
 *   portait treize — dans le fichier qui EST la source de l'ordre (#1124). Un
 *   compte faux dans la déclaration se recopie ensuite partout où on la cite.
 *
 *   🔴 « quand » est entrée le 20/09/2026 avec le chantier v2.0.0 (#1092) :
 *   le Calendrier cesse d'être un objet pour devenir une vue — « tout ce qui
 *   porte une date » —, ce qui suppose qu'une actualité et une affaire
 *   puissent en porter une. C'est la première section ajoutée au cadre depuis
 *   sa pose, et elle l'est parce qu'un OBJET disparaît, pas parce qu'un écran
 *   voulait un champ de plus. */
export type IdSection =
	| 'titre'
	| 'nature'
	| 'equipement'
	| 'suivi'
	| 'quand'
	| 'intervenant'
	| 'perimetre'
	| 'description'
	| 'pieces_jointes'
	| 'affaires_liees'
	| 'au_nom_de'
	| 'mise_en_avant'
	| 'destinataires'
	| 'diffusion';

/**
 * 🔴 **L'ordre des sections — il ne se discute plus, et il vaut aussi pour
 * l'AFFICHAGE** (mesuré : l'affichage n'empruntait le motif d'aucun formulaire,
 * 0 cas sur 42).
 *
 * 🔴 **Une section ne se fusionne pas TOUTE SEULE.** Autant de sections
 * déclarées que de sections rendues — même voisines, même courtes, même
 * héritées de la même valeur. Ce qui est interdit est la fusion *à l'écran* de
 * ce que la table sépare : elle crée une section que rien ne déclare, donc que
 * rien ne contrôle.
 *
 * ⚠️ **Photos et Documents ÉTAIENT deux sections, et n'en font plus qu'une**
 * (#1095, 20/09/2026, arbitré à l'écran). Cette clause disait le contraire, en
 * rouge, depuis le 17/08 : *« le mode "pièces jointes unifiées" d'`EvolForm`
 * n'est pas une variante légitime : c'est une divergence à corriger »*. Elle est
 * réécrite ICI, dans le lot qui change la décision — une consigne laissée en
 * arrière réclamerait la séparation qu'on vient d'abandonner, et quelqu'un la
 * rétablirait de bonne foi.
 *
 * 🔴 Ce n'est pas la clause qui s'assouplit, c'est la TABLE qui a changé : la
 * fusion se déclare, donc elle se contrôle. Fusionner sans déclarer reste
 * interdit, et c'est tout ce que la règle a jamais voulu dire.
 */
export const SECTIONS_ORDRE: readonly IdSection[] = [
	'titre',
	'nature',
	'equipement',
	'suivi',
	'quand',
	'intervenant',
	'perimetre',
	'description',
	'pieces_jointes',
	//  Affaires liées après les Pièces jointes (26/09/2026, #1342) : ce qui
	//  accompagne l'objet — un fichier, une autre affaire —, avant de dire
	//  pour qui et à qui.
	'affaires_liees',
	'au_nom_de',
	//  Destinataires AVANT Mise en avant (23/09/2026, #1096) : « elles sont
	//  complémentaires » — à qui l'on parle, puis comment on le met en avant.
	'destinataires',
	'mise_en_avant',
	'diffusion',
];

/**
 * Le libellé de chaque section, écrit UNE fois.
 *
 * ⚠️ *Destinataires* (5) et *Diffusion* (9) parlent tous deux de « à qui »,
 * séparés par quatre sections : les intitulés doivent lever l'ambiguïté —
 * Destinataires = qui est concerné **dans l'application** ; Diffusion = par
 * quels canaux on prévient **à l'extérieur**.
 */
export const SECTIONS_LIBELLE: Readonly<Record<IdSection, string>> = {
	titre: 'Titre',
	nature: 'Nature',
	equipement: 'Équipement',
	suivi: 'Suivi',
	quand: 'Quand',
	intervenant: 'Intervenant',
	perimetre: 'Périmètre',
	description: 'Description',
	pieces_jointes: 'Pièces jointes',
	affaires_liees: 'Affaires liées',
	au_nom_de: 'Au nom de',
	mise_en_avant: 'Mise en avant',
	destinataires: 'Destinataires',
	diffusion: 'Diffusion',
};

/**
 * **Les libellés de section ABANDONNÉS** — l'ancien nom, et celui qui l'a
 * remplacé.
 *
 * 🔴 Pourquoi une table et pas une simple mémoire (#1094, 21/09/2026). Le cadre
 * a renommé quatre sections en deux jours, et `SectionWorkflow` affichait
 * encore « Workflow » deux lots après la bascule : son intitulé était écrit EN
 * DUR, et `lint:etats` ne le voyait pas — il ne lit que les fichiers qui
 * consomment une entité déclarée, et ce composant-là n'en consomme aucune.
 *
 * ⚠️ Un intitulé LIBRE reste libre : « Le contrat », « L'entreprise »,
 * « Prompt » ne sont pas des sections du cadre, et les exiger dans la table
 * ferait crier le contrôle sur du légitime. Ce qui est interdit, c'est
 * d'afficher un nom que le cadre a explicitement abandonné.
 *
 * 🔴 **Deux entrées, et pas quatre.** « Périmètre » et « Options de
 * publication » ont aussi été renommés, et ils ne sont PAS ici : ce sont des
 * mots communs, qui servent ailleurs légitimement — « Filtrer par périmètre »,
 * « Nouveau périmètre de premier niveau », « Périmètre d'affichage » d'une
 * affiche de hall. Le contrôle les a tous signalés au premier passage, et il
 * avait tort six fois sur sept.
 *
 * Ne restent que les mots qui n'ont **aucun autre emploi** dans le produit. Un
 * contrôle qui crie sur du légitime finit désarmé — c'est la leçon de C16, et
 * elle vaut ici comme ailleurs.
 *
 * 🔒 `npm run lint:vocabulaire-ecran` lit cette table comme il lit `motDeCode`
 * dans les entités et `motAbandonne` dans `#lib/gestes` : trois sources, une
 * règle — un mot qu'on a cessé de dire ne se réécrit nulle part.
 */
export const SECTIONS_LIBELLE_ABANDONNE: Readonly<Record<string, IdSection>> = {
	Workflow: 'suivi',
	'Champs spécifiques': 'nature',
};

/** Les quatre rendus d'une même entité. */
export type Etat = 'affichage' | 'creation' | 'edition' | 'evolution';

/**
 * Les QUATRE motifs de divergence, et il n'y en a pas d'autre (R4).
 *
 * 🔴 `categorie` est entré le 21/09/2026 (#1095) : une section que la CATÉGORIE
 * de l'objet n'appelle pas — l'Équipement et l'Intervenant ne concernent que le
 * bâti. C'est une absence légitime et conditionnelle, là où `nature` dit « cet
 * objet ne porte jamais la notion » et `api` « on ne sait pas encore le faire ».
 *
 * ⚠️ `api` reste une **dette, jamais un choix**, et exige son ticket.
 */
export type Motif = 'geste' | 'hérité' | 'categorie' | 'api';

export interface Divergence {
	motif: Motif;
	/** Pourquoi, en une phrase — lisible en revue comme en lot suivant. */
	explication: string;
	/** Forme « #431 ». **Obligatoire** quand `motif === 'api'` : une dette a un ticket. */
	ticket?: string;
}

/**
 *  Les explications de divergence PARTAGÉES par plusieurs entités.
 *
 *  🔴 Une explication recopiée est une explication qui divergera. Celle-ci
 *  l'était **quatre fois**, au caractère près — événement, publication, ticket,
 *  sondage (#824). Ce n'est pas une particularité de ces quatre-là : c'est une
 *  règle du cadre, et elle doit s'écrire là où le cadre se déclare.
 *
 *  ⚠️ Une explication propre à UNE entité reste chez elle. Ce qui monte ici,
 *  c'est ce que plusieurs entités disent parce que la règle est la même — pas
 *  ce qui se trouve formulé pareil par hasard. Le test de l'appartenance : si
 *  l'on corrigeait la phrase, faudrait-il la corriger partout ? Ici oui.
 */
export const DIFFUSION_NE_SE_LIT_PAS: Divergence = {
	motif: 'geste',
	explication: "On n'affiche pas un envoi : la diffusion a eu lieu, elle ne se lit pas.",
};

export interface SectionDeclaree {
	id: IdSection;
	/** Ce que la section porte à l'écran. Vide seulement si `sansObjet`. */
	objet?: string;
	/** Marqué par `*` et rien d'autre — jamais « (optionnel) » (R3). */
	requis?: boolean;
	/**
	 * L'intitulé réellement affiché, quand il diffère du nom de la section.
	 *
	 * Une section qui ne contient qu'UN champ ne répète pas son nom : le titre de
	 * section DEVIENT le libellé du champ (`SectionFormulaire`). « Champs
	 * spécifiques » ne s'écrit jamais à l'écran — c'est « Saisi pour » qui s'y
	 * lit. R3 demande que ce libellé soit le même d'un formulaire à l'autre :
	 * il se déclare donc ici, et `lint:etats` refuse tout autre intitulé.
	 *
	 * ⚠️ **Une LISTE quand la section groupe plusieurs champs nommés.** La section 2
	 * du ticket en porte deux — « Catégorie » et « Saisi pour » —, chacun avec son
	 * intitulé : une section reste UNE section (elle ne se fusionne ni ne se
	 * scinde), mais rien n'oblige son contenu à tenir sous un seul nom. Déclarer
	 * les deux est ce qui permet à `lint:etats` de continuer à refuser un intitulé
	 * inventé sur place.
	 */
	titreEcran?: string | readonly string[];
	/**
	 * Les états où la section est ABSENTE, chacun avec son motif.
	 * Une absence non déclarée ici est un écart : `lint:etats` la refuse.
	 */
	absente?: Partial<Record<Etat, Divergence>>;
	/**
	 * **Repliée par défaut** — l'intitulé et un résumé d'une ligne, cliquables.
	 *
	 * 🔴 Ce n'est PAS une absence, et ce n'est pas une fusion : la section garde
	 * son intitulé, son rang et sa déclaration. C'est un troisième état de
	 * présence (#1095, 20/09/2026), qui existe parce qu'un formulaire dont toutes
	 * les sections sont dépliées d'office est illisible au pouce.
	 *
	 * ## La règle, et elle est mécaniquement vérifiable
	 *
	 *     obligatoire → déplié   ·   facultatif → plié
	 *
	 * Elle se déduit de `requis`, donc `lint:etats` la CALCULE : un pliage
	 * conforme n'a rien à déclarer. Un pliage qui s'en écarte exige
	 * `exceptionPliage`, et le contrôle échoue sans lui.
	 *
	 * ⚠️ **Et toujours, une valeur autre que le défaut rouvre la section
	 * d'office.** Cette partie-là n'est pas déclarative : elle vit dans le rendu
	 * (`SectionFormulaire`), parce qu'elle dépend de ce que l'objet PORTE, pas de
	 * ce que la table dit. Une section pliée qui cacherait une valeur saisie
	 * serait pire que pas de pliage du tout.
	 */
	pliee?: boolean;
	/**
	 * Pourquoi ce pliage s'écarte de la règle — **obligatoire** quand il s'en
	 * écarte, refusé quand il ne s'en écarte pas.
	 *
	 * Les trois du 20/09/2026 : « Au nom de » et « Destinataires » sont
	 * obligatoires et **pliés** (le défaut est juste dans la quasi-totalité des
	 * cas) ; « Pièces jointes » est facultatif et **déplié** (c'est le premier
	 * geste sur téléphone).
	 *
	 * ⚠️ Le contrôle refuse aussi une exception qui ne sert plus : une règle
	 * changée laisserait sinon derrière elle des justifications sans objet, et
	 * c'est ainsi qu'une liste d'exceptions devient une liste de passe-droits.
	 */
	exceptionPliage?: string;
	/**
	 * L'entité ne porte PAS cette notion, dans aucun état — et voici pourquoi.
	 *
	 * À distinguer d'une divergence : « un sondage n'a pas de pièces jointes »
	 * n'est pas un écart entre deux états, c'est une absence de notion. Le
	 * contrat n'est pas « toutes les entités ont tout », c'est « quand une
	 * entité a une de ces notions, elle est à la même place et a la même tête ».
	 */
	sansObjet?: string;
	/**
	 * **Sans objet pour UNE nature d'affaire** — la section reste visible, grisée,
	 * pliée et inactive, avec ce motif (23/09/2026, arbitré à l'écran).
	 *
	 * Demandé : *« un seul “+ Nouvelle affaire” comprenant toutes les sections
	 * Affaires et Actualités ; selon le choix de la catégorie, les sections
	 * peuvent changer. Prévoir toutes les sections, grisées, pliées et inactives
	 * pour celles inappropriées, qui doivent être sans données »*.
	 *
	 * À distinguer de `sansObjet` (l'entité ne porte jamais la notion, la
	 * section n'est pas rendue) et d'`absente` (un ÉTAT ne la porte pas) : ici
	 * c'est la NATURE de l'objet, qui change quand on change de catégorie — la
	 * section doit donc rester à sa place, pour qu'on voie ce qui s'éteint.
	 */
	//  Clés : la NATURE (`actualite`, `suivie`) et, depuis le 23/09/2026 (#1092),
	//  deux conditions de plus : `resident` (le geste est au conseil) et
	//  `horsBati` (la catégorie ne porte pas sur le bâti) ; et `bug` (#1191) : un
	//  bogue du site ne garde que Titre, Nature, Suivi, Description, Pièces jointes.
	inactivePour?: Partial<Record<ConditionInactive, string>>;
}

/**
 * La nature d'une affaire, qui décide des sections actives : une ACTUALITÉ
 * (catégorie « Actualité ») informe ; une affaire SUIVIE se traite. Même mot
 * que le serveur (`utils/nature_affaire`) pour le premier ; le second n'y a pas
 * de nom, parce qu'il n'y décide de rien.
 */
export type NatureAffaire = 'actualite' | 'suivie';

/** Ce qui éteint une section : la nature, le rôle, ou une catégorie hors bâti. */
export type ConditionInactive = NatureAffaire | 'resident' | 'horsBati' | 'bug';

export interface EntiteDeclaree {
	/** Identifiant technique — `ticket`, `actualite`… */
	id: string;
	/**
	 * **Nom de l'entité à l'écran** — celui que le résident lit.
	 *
	 * 🔴 Il peut DIFFÉRER de `id`, et deux le font : le modèle s'appelle
	 * `Ticket` et l'écran dit « Affaire » ; le modèle dit `Publication` et
	 * l'écran « Actualité » (#1094, #1107). C'est la même distinction que pour
	 * `TicketEvolution` / « Suite » : le modèle garde son nom, l'écran parle
	 * français.
	 *
	 * ⚠️ Ce champ portait le mot de CODE jusqu'au 21/09/2026 — « Publication »,
	 * « Ticket » — alors que sa propre description disait « à l'écran ». La
	 * source du bon mot existait donc, et affirmait le mauvais.
	 */
	libelle: string;
	/**
	 * Le mot que le CODE emploie et que l'écran ne doit **jamais** montrer.
	 *
	 * Absent quand le code et l'écran disent la même chose (une annonce est une
	 * annonce). Présent pour les deux entités renommées — c'est lui, et lui
	 * seul, que `npm run lint:vocabulaire-ecran` cherche dans les libellés.
	 *
	 * 🔴 Déclaré ICI et nulle part ailleurs : un troisième renommage n'ajoutera
	 * qu'une ligne, et le contrôle le suivra sans qu'on y pense. Une liste
	 * recopiée dans le contrôle aurait divergé au premier.
	 */
	motDeCode?: string;
	/** Le bouton de création — ex. « Nouvelle actualité ». */
	libelleNouveau: string;
	/** Le titre de la boîte d'édition — ex. « Modifier l'actualité ».
	 *
	 * ⚠️ Écrit en toutes lettres plutôt que composé depuis `libelle`, et c'est
	 * une décision : « Nouvelle actualité », « Nouvel événement », « Nouveau
	 * sondage » demandent le genre ET l'élision, que rien ne devine d'un nom.
	 * Le 13/09/2026, un gabarit `{objet}` a rendu « Visibilité **du
	 * publication** » pour cette raison exacte ; la réponse avait alors été de
	 * *supprimer le besoin* — on était dans le formulaire de l'objet, où le
	 * nommer n'apprend rien. Ici le besoin ne se supprime pas : un bouton en
	 * tête de page ne dit QUE le nom de ce qu'il crée. Deux chaînes déclarées
	 * coûtent moins qu'une grammaire, et le garde-fou vérifie qu'elles
	 * contiennent bien `libelle`. */
	libelleModifier: string;
	/** Les sections déclarées, dans l'ordre de `SECTIONS_ORDRE`. */
	sections: readonly SectionDeclaree[];
}

/** La déclaration d'une section, ou `undefined` si l'entité est incomplète. */
export function section(entite: EntiteDeclaree, id: IdSection): SectionDeclaree | undefined {
	return entite.sections.find((s) => s.id === id);
}

/**
 * Cette section est-elle rendue dans cet état ?
 *
 * ⚠️ **C'est le SEUL portail.** Un écran qui décide lui-même (`{#if !modeEdition}`)
 * rouvre la divergence silencieuse que le cadre supprime — `lint:etats` refuse
 * qu'une section soit gouvernée par autre chose que cet appel.
 */
export function sectionPresente(entite: EntiteDeclaree, etat: Etat, id: IdSection): boolean {
	const s = section(entite, id);
	if (!s || s.sansObjet) return false;
	return !s.absente?.[etat];
}

/**
 * Pourquoi cette section est-elle INACTIVE ici — ou `''` si elle ne l'est pas.
 *
 * Une section inactive se rend grisée, pliée, sans données, avec ce motif
 * (`SectionFormulaire inactive=`). Deux sources, dans cet ordre :
 *
 *   1. une **condition** déclarée (`inactivePour`), dans l'ordre où l'appelant
 *      les donne — la nature d'abord, puis le rôle, puis la catégorie ;
 *   2. une **absence de l'état** qui tient à la catégorie ou à une dette
 *      (`absente[etat]`, motifs `categorie` et `api`) : l'Équipement et
 *      l'Intervenant ne se saisissent pas à la création, et pas encore en
 *      correction (#1097). Ils restent visibles, pour qu'on sache qu'ils existent.
 *
 * ⚠️ Les absences de motif `geste` ou `hérité` ne sont PAS des sections
 * inactives : elles n'ont pas de sens dans ce geste-là, et les montrer grisées
 * ferait croire à une case qu'on pourrait débloquer.
 */
export function motifInactif(
	entite: EntiteDeclaree,
	etat: Etat,
	id: IdSection,
	conditions: readonly ConditionInactive[],
): string {
	const s = section(entite, id);
	if (!s) return '';
	for (const c of conditions) {
		const motif = s.inactivePour?.[c];
		if (motif) return motif;
	}
	const absence = s.absente?.[etat];
	return absence && (absence.motif === 'categorie' || absence.motif === 'api')
		? absence.explication
		: '';
}

/** Les sections rendues dans cet état, **dans l'ordre déclaré**. */
export function sectionsDe(entite: EntiteDeclaree, etat: Etat): SectionDeclaree[] {
	return entite.sections.filter((s) => sectionPresente(entite, etat, s.id));
}

/** La divergence déclarée pour cette section dans cet état, s'il y en a une. */
export function divergence(entite: EntiteDeclaree, etat: Etat, id: IdSection): Divergence | null {
	return section(entite, id)?.absente?.[etat] ?? null;
}
