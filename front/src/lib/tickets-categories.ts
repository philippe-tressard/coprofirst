/**
 * Les **catégories d'une affaire** — la table, ses dérivés, et le repère 📒.
 *
 * Extrait de `tickets.ts` le 21/09/2026 : le fichier passait 500 lignes en
 * accueillant le drapeau `carnet`, et la modularité (rang 1) se règle « au fil
 * de l'eau » — on découpe quand on y touche.
 *
 * ⚠️ `tickets.ts` **réexporte** tout ce module : aucun écran n'a changé
 * d'import, et `#lib/tickets` reste la porte du domaine. Ce qui a changé est le
 * FICHIER que les contrôles lisent — `check-choix-requis.mjs`,
 * `test_categories_ticket_concordance.py` et `test_manuel_ne_recopie_rien.py`
 * pointent ici.
 */

export interface CategorieTicket {
	/** Valeur envoyée à l'API — jamais traduite. */
	value: string;
	/** Libellé seul. */
	label: string;
	/** Pastille de contexte. */
	emoji: string;
	/** Ce que la catégorie recouvre, pour aider à choisir à la création. */
	description: string;
	/**
	 *  Cette catégorie alimente-t-elle le **carnet d'entretien** ?
	 *
	 *  Demandé à l'écran le 21/09/2026 : *« Identifie visuellement différemment
	 *  les catégories qui sont prises en compte légalement dans le Carnet
	 *  d'entretien »*. Une affaire close dans l'une d'elles y apparaît
	 *  définitivement — ce n'est pas une nuance de rangement, c'est un document
	 *  qu'un acquéreur peut réclamer.
	 *
	 *  🔴 **La liste fait autorité côté SERVEUR** (`CATEGORIES_BATI`,
	 *  `app/utils/carnet_entretien.py`) : c'est elle qui filtre réellement. Ce
	 *  drapeau en est la copie d'affichage — inévitable, les contextes de build
	 *  Docker étant `./api` et `./front` — et
	 *  `api/tests/test_categories_ticket_concordance.py` refuse qu'ils
	 *  divergent, dans les deux sens. Sans ce test, l'écran promettrait une
	 *  inscription au carnet que le serveur ne ferait pas.
	 */
	carnet?: boolean;
	/**
	 *  Réservée au conseil syndical (#1091) — le résident ne la voit pas dans la
	 *  grille de choix. La règle fait autorité côté SERVEUR
	 *  (`CATEGORIES_RESERVEES_AU_CS`, qui refuse en 403) : ce drapeau n'en est
	 *  que l'affichage.
	 */
	reserveCS?: boolean;
	/**
	 *  EN TÊTE de la grille, pleine ligne, suivie d'un filet — et filtrée par sa
	 *  NATURE plutôt que par sa catégorie (#1092). C'est « Actualité » : on
	 *  choisit d'abord entre informer et faire traiter (23/09/2026, un seul
	 *  formulaire, variante A arbitrée à l'écran). Elle avait son propre bouton
	 *  et son propre formulaire pendant quelques heures : deux façons de créer
	 *  la même chose, retirées à la demande.
	 */
	enTete?: boolean;
}

/**  La marque posée sur une catégorie du carnet, et la phrase qui l'explique.
 *
 *  Une marque sans légende est un symbole que personne ne décode : les deux
 *  s'écrivent ici, ensemble, et l'écran les lit — il n'en recopie aucune. */
/**  La phrase qui explique le repère — et elle doit décrire la FORME retenue.
 *
 *   🔴 Elle commençait par 📒, qui était le repère jusqu'au 22/09/2026.
 *   Signalé à l'écran : *« je trouve illisible le logo carnet d'entretien : ne
 *   peut-on pas plutôt modifier le cadre (un bord jaune par exemple) »*. Un emoji
 *   posé après un libellé qui commence déjà par celui de sa catégorie en faisait
 *   deux dans une pastille de vingt caractères — et il disparaît sur le fond
 *   bleu de la pastille retenue.
 *
 *   ⚠️ Une légende qui décrirait encore l'emoji renverrait à un signe absent :
 *   c'est le genre de texte qu'on ne relit jamais, parce qu'il a été juste. */
export const LEGENDE_CARNET =
	'Les catégories marquées d’un liseré doré alimentent le carnet d’entretien : une ' +
	'affaire résolue dans l’une d’elles y est consignée, rangée sous l’équipement ' +
	'que le conseil syndical désigne, consultable par tout copropriétaire ' +
	'(décret n° 2001-477).';

/**
 *  Les huit catégories, **dans l'ordre de fréquence attendue** en copropriété.
 *
 *  🔴 L'ordre est une décision, pas le résidu de celui où on les a écrites. Sur
 *  deux lignes de quatre :
 *
 *      Panne · Nuisance & propreté · Accès & accueil · Espaces verts
 *      Sinistre · Étude & travaux · Question · Bug
 *
 *  ⚠️ « Accès & accueil » A ÉTÉ REMONTÉE en 3ᵉ le 07/09/2026, et c'est un
 *  effet du lot précédent : depuis que cocher « Nouvel arrivant » ouvre un
 *  ticket de suivi, chaque emménagement en produit un. Elle était 6ᵉ, donc en
 *  seconde ligne — reléguée au moment même où elle devenait fréquente.
 *
 *  ⚠️ L'alphabétique a été écarté : il mettrait « Bug » en tête et « Sinistre »
 *  en avant-dernier. Un ordre qui ne dit rien du métier oblige à lire les huit
 *  entrées à chaque fois ; celui-ci fait que la plupart des gens s'arrêtent aux
 *  trois premières.
 *
 *  ⚠️ « Sinistre » en seconde ligne est assumé : quelqu'un qui a un dégât des
 *  eaux lit les huit vignettes de toute façon. Le formulaire sert à choisir
 *  vite, pas à contempler une taxonomie.
 */
export const CATEGORIES_TICKET: readonly CategorieTicket[] = [
	{
		value: 'panne',
		label: 'Panne',
		carnet: true,
		emoji: '\u{1F6E0}️',
		//  🔴 « éclairage » et « fuite » sont NOMMÉS, et « à réparer » conclut.
		//  Questionné le 07/09/2026 : *« une fuite goutte-à-goutte dans les communs,
		//  Panne ou Sinistre ? Idem pour une ampoule grillée. »* Les deux sont des
		//  pannes — mais la description ne le disait pas, et c'est ce qui rendait la
		//  question nécessaire. Quelqu'un qui cherche « Électricité » ne trouvait
		//  rien.
		description: 'Ascenseur, chauffage, éclairage, fuite, porte — à réparer',
	},
	/*  🔴 UNE SEULE CATÉGORIE, après avoir essayé d'en faire deux (07/09/2026).

	    J'avais séparé « Nuisance » et « Propreté » sur l'argument « deux
	    prestataires différents ». Signalé le soir même : *« très sincèrement,
	    Propreté je la regrouperais dans Nuisance en complétant le libellé »*.
	    C'est juste, et l'erreur était la mienne — trois signes le disaient déjà :

	    • dans les faits le GESTE est le même : le conseil relaie au syndic ou au
	      prestataire, il ne fait pas deux choses différentes ;
	    • le recouvrement, je l'avais ADMIS en écrivant qu'« un encombrant
	      abandonné dans le hall est les deux à la fois » ;
	    • et j'avais dû EXPLIQUER LA FRONTIÈRE dans le manuel. Une frontière qu'il
	      faut expliquer est une frontière qui n'existe pas.

	    Le critère du projet — « une catégorie ne se justifie que si elle change ce
	    qu'on FAIT du ticket » — était le bon ; c'est mon application qui était
	    fausse, en prenant « qui exécute in fine » pour « qui traite ». */
	{
		value: 'nuisance',
		label: 'Nuisance & propreté',
		emoji: '\u{1F4E2}',
		//  Raccourcie le 25/09/2026 (#1310) : quatre lignes dans sa vignette. Le
		//  manuel garde la liste entière (parties communes, encombrants).
		description: 'Bruit, odeurs, stationnement…',
	},
	{
		value: 'acces_accueil',
		label: 'Accès & accueil',
		//  ⚠️ Le badge et la télécommande N'Y SONT PAS, et c'est délibéré :
		//  `CommandeAcces` porte déjà le lot, la quantité, le motif et son propre
		//  workflow (écran « Accès & sécurité »). Un ticket y perdrait tout. Cette
		//  catégorie est pour ce qui n'a AUCUN circuit dédié — l'interphone, la
		//  boîte aux lettres, et le suivi d'un emménagement.
		emoji: '\u{1F511}',
		description: 'Interphone, boîte aux lettres, emménagement',
	},
	{
		value: 'espaces_verts',
		label: 'Espaces verts',
		carnet: true,
		emoji: '\u{1F333}',
		description: 'Élagage, haies, arrosage, allées…',
	},
	{
		value: 'sinistre',
		label: 'Sinistre',
		carnet: true,
		//  ⚠️ La description porte les mots du RÉSIDENT — « dégât des eaux »,
		//  « fuite » — là où le libellé porte celui de l'assureur. Le sinistre est
		//  ce qui déclenche une déclaration sous cinq jours ouvrés ; c'est la
		//  procédure qui fait la catégorie, pas la cause.
		emoji: '\u{1F4A7}',
		//  🔴 « Dégât CONSTATÉ » ouvre la description, et ce mot fait tout le
		//  travail. La frontière avec « Panne » n'est pas l'eau, c'est le DOMMAGE :
		//  une fuite qu'on répare est une panne ; de l'eau chez le voisin, un
		//  plafond taché, un parquet gondolé — il y a un tiers lésé et un délai
		//  d'assurance, c'est un sinistre.
		//  Raccourcie le 25/09/2026 (#1310) : la déclaration à l'assurance est
		//  dite par le manuel, la vignette garde le mot qui tranche.
		description: 'Dégât constaté : eau, incendie, vandalisme…',
	},
	{
		value: 'etude_travaux',
		label: 'Étude & travaux',
		carnet: true,
		//  Réservée au conseil depuis le 23/09/2026 (#1098) : lancer une étude
		//  est une décision ; un résident signale une panne ou pose une question.
		reserveCS: true,
		emoji: '\u{1F3D7}️',
		description: 'Diagnostic, sondage, devis, chantier suivi par le conseil',
	},
	{
		//  Le passage d'un prestataire — visite, maintenance, récurrente ou non
		//  (#1092, lot 5) : les maintenances du calendrier en deviennent.
		value: 'entretien',
		label: 'Entretien',
		carnet: true,
		reserveCS: true,
		emoji: '\u{1F9F0}',
		description: 'Visite ou maintenance d’un prestataire, récurrente ou non',
	},
	{ value: 'question', label: 'Question', emoji: '❓', description: 'Information, procédure…' },
	{
		value: 'bug',
		label: 'Bug',
		emoji: '\u{1F41B}',
		//  Arbitré à l'écran le 30/08/2026. « le site ou l'application » décrivait
		//  le support ; le résident, lui, cherche le NOM de ce qu'il utilise —
		//  et il n'a pas à savoir si sa gêne vient du site ou de la PWA.
		description: 'Pb technique sur le site',
	},
	{
		value: 'actualite',
		label: 'Actualité',
		emoji: '\u{1F4F0}',
		//  Une INFORMATION, pas une demande : personne n'agit, elle périme (#1091).
		description: 'Information — suivi optionnel',
		reserveCS: true,
		enTete: true,
	},
];

//: Emoji seul — la pastille de contexte d'une carte. Repli sur 📋 : une catégorie
//: retirée du référentiel ne doit pas laisser une carte sans repère.
export const CATEGORIE_TICKET_EMOJI: Record<string, string> = Object.fromEntries(
	CATEGORIES_TICKET.map((c) => [c.value, c.emoji]),
);

//: « 🛠️ Panne » — la forme complète, celle des filtres, des badges et des choix.
export const CATEGORIE_TICKET_LABELS: Record<string, string> = Object.fromEntries(
	CATEGORIES_TICKET.map((c) => [c.value, `${c.emoji} ${c.label}`]),
);

//  Elles vivaient en QUATRE endroits le 17/08/2026 : la grille de choix de
//  `FormulaireTicket` (valeur + libellé + description), la table `CATEGORIES` de
//  la fiche d'un ticket, la table `CAT_ICON` de la liste, et six boutons de
//  filtre écrits en dur dans le balisage de cette même liste. Aucune n'était
//  dérivée d'une autre — exactement le motif qui avait fait diverger les statuts
//  (#415), à ceci près qu'ici l'écart n'a pas encore eu le temps de se produire.
//
//  ⚠️ La catégorie **qualifie le titre** : elle appartient à la section 1 du
//  cadre (#430), pas à une section « Détails ».

/** Emoji d'une catégorie, jamais vide. */
export function categorieTicketEmoji(categorie: string | undefined | null): string {
	return CATEGORIE_TICKET_EMOJI[categorie ?? ''] ?? '\u{1F4CB}';
}

/** « 🛠️ Panne », valeur brute à défaut (jamais vide). */
export function categorieTicketLabel(categorie: string | undefined | null): string {
	return CATEGORIE_TICKET_LABELS[categorie ?? ''] ?? categorie ?? '';
}

/**
 *  Les catégories telles que `ChoixPastilles` les attend — `val`/`label`/`desc`,
 *  et le repère 📒 des catégories du carnet.
 *
 *  🔴 Elle vivait dans `FormulaireTicket`, qui est le seul écran à s'en servir.
 *  Elle remonte ici le 21/09/2026 pour deux raisons : le formulaire dépassait
 *  500 lignes, et surtout la marque du carnet se déduit de la TABLE — la poser
 *  chez l'appelant aurait mis la règle (« quelles catégories sont marquées »)
 *  à distance de la donnée qui la porte.
 *
 *  ⚠️ `CATEGORIES_TICKET` parle en `value`/`description`, `ChoixPastilles` en
 *  `val`/`desc` : l'adaptation se fait ici, et non par une variante du
 *  composant — une variante ajoutée pour accueillir un écart existant ne
 *  factorise pas, elle entérine.
 */
/**
 *  La grille de CHOIX d'une catégorie : sans les catégories réservées au
 *  conseil, pour qui n'en est pas (#1091). `OPTIONS_CATEGORIE` reste entière —
 *  elle sert aussi à NOMMER la catégorie d'une affaire déjà créée.
 */
export function optionsCategorie(estCS: boolean) {
	const reservees = new Set(CATEGORIES_TICKET.filter((c) => c.reserveCS).map((c) => c.value));
	return OPTIONS_CATEGORIE.filter((o) => estCS || !reservees.has(o.val));
}

//  La rangée de filtres par catégorie n'existe plus (27/09/2026) : la page
//  Affaires cherche un mot, et le serveur cherche aussi le libellé de la
//  catégorie (`app/utils/recherche_affaires.py`).

export const OPTIONS_CATEGORIE: readonly {
	val: string;
	label: string;
	desc: string;
	marquee?: boolean;
	marqueAide?: string;
	enTete?: boolean;
}[] = CATEGORIES_TICKET.map((c) => ({
	val: c.value,
	label: `${c.emoji} ${c.label}`,
	desc: c.description,
	marquee: !!c.carnet,
	enTete: !!c.enTete,
	//  ⚠️ OBLIGATOIRE dès que `marquee` est vrai : un liseré ne dit rien à un
	//  lecteur d'écran. L'équivalent textuel compte plus qu'avec un emoji, pas
	//  moins — un emoji, au moins, s'annonçait.
	marqueAide: c.carnet ? 'consignée au carnet d’entretien' : undefined,
}));

/**
 *  Le filtre de la vue Affaires, arbitré le 23/09/2026 (#1092) : *« Actualité :
 *  si catégorie Actualité ; Calendrier : si une date est définie ; Activité : le
 *  reste »*. Les VALEURS sont celles que le serveur dérive
 *  (`nature_affaire.natures`, transportées par `Ticket.natures`) : l'écran ne
 *  redérive rien. Ce n'est pas une partition — une actualité datée paraît sous
 *  Actualité ET sous Calendrier.
 */
//: Les trois natures, écrites UNE fois : le filtre et la gouttière des cartes
//: (24/09/2026) en dérivent. Leurs teintes vivent dans `styles/normes.css`
//: (`[data-nature=…]`), avec les autres couleurs.
//: « Affaire » et non plus « Activité » (24/09/2026, arbitré à l'écran) : le
//: libellé change, la valeur `activite` reste — liens et serveur inchangés.
//: `abrege` est le mot de la GOUTTIÈRE (#1220, arbitré à l'écran le 24/09) :
//: écrit en entier, « CALENDRIER » dépassait de la bande ou l'élargissait. Le
//: filtre, lui, garde le mot entier — il a la place.
//: `icone` est le pictogramme AU TRAIT de la gouttière (maquette B, 10/10/2026) :
//: l'émoji reste celui du filtre, la carte dessine le sien (`#lib/icones-svg.json`).
export const NATURES = [
	{
		val: 'actualite',
		emoji: '\u{1F4F0}',
		icone: 'newspaper',
		libelle: 'Actualité',
		abrege: 'ACTU.',
	},
	{
		val: 'calendrier',
		emoji: '\u{1F4C5}',
		icone: 'calendar-days',
		libelle: 'Calendrier',
		abrege: 'CAL.',
	},
	{ val: 'activite', emoji: '\u{1F6E0}️', icone: 'wrench', libelle: 'Affaire', abrege: 'AFF.' },
] as const;

export const OPTIONS_FILTRE_NATURE = NATURES.map((n) => ({
	val: n.val,
	label: `${n.emoji} ${n.libelle}`,
}));

/**
 *  La nature qu'une CARTE affiche, dans sa gouttière (24/09/2026, variante 3
 *  choisie à l'écran parmi cinq ; datée depuis la maquette B du 10/10/2026).
 *  Une affaire peut en porter deux (une actualité datée) : l'actualité prime,
 *  puis la date — c'est l'ordre du filtre. Les natures viennent du serveur
 *  (`Ticket.natures`), jamais redérivées.
 */
export function natureDe(t: { natures?: string[] }): (typeof NATURES)[number] {
	return NATURES.find((x) => (t.natures ?? []).includes(x.val)) ?? NATURES[2];
}

/**
 *  Ce que la GOUTTIÈRE d'une affaire montre : sa date (`mis_a_jour_le`, sinon
 *  `cree_le`) et sa nature. Se passe tel quel à `CarteListe`
 *  (`<CarteListe {...gouttiereAffaire(t)}>`) — la carte d'affaire et celle
 *  d'actualité le lisent ici, jamais chacune chez elle. Il remplace le composant
 *  `GouttiereAffaire`, devenu inutile quand le conteneur a porté la gouttière.
 */
export function gouttiereAffaire(t: {
	natures?: string[];
	cree_le: string;
	mis_a_jour_le?: string | null;
}): { quand: string; classe: (typeof NATURES)[number] } {
	return { quand: t.mis_a_jour_le ?? t.cree_le, classe: natureDe(t) };
}

/**
 *  L'attribut qui TEINTE une carte d'après sa nature (`styles/normes.css`). Le
 *  pictogramme et le mot ne passent plus par des attributs rendus en
 *  pseudo-éléments : la gouttière est un composant, rendu par `CarteListe`.
 */
export function attributsNature(t: { natures?: string[] }): Record<string, string> {
	return { 'data-nature': natureDe(t).val };
}
