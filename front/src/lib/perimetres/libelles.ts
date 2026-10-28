/**
 * Comment un périmètre S'ÉCRIT — séparateurs, qualification par le parent, tri
 * par l'arbre, et la table des icônes proposées en administration.
 *
 * Séparé d'`arbre.ts` le 10/09/2026, quand `perimetres.ts` a franchi les 500
 * lignes en accueillant `perimetresNiveau1`. La césure n'est pas arbitraire :
 * c'est **exactement celle du serveur** (`app/utils/perimetres/{arbre,libelles}.py`),
 * et deux découpes différentes des deux côtés d'une même notion auraient rendu
 * la comparaison front ⇆ API plus difficile qu'elle ne l'est déjà — les deux
 * règles de libellé sont tenues par une seule chaîne attendue en CI.
 *
 * ⚠️ Le paquet réexporte tout : `#lib/perimetres` continue de servir, et aucun
 * import du dépôt n'a changé.
 */
import { PREFIXE_BATIMENT, carte, cle, normaliser, type Perimetre } from './arbre';

/** Sépare deux éléments de même niveau : « Bât. 1 · Parking ». */
export const SEPARATEUR_ELEMENT = ' · ';

/**
 * Borne un GROUPE de plusieurs espaces partageant le même parent :
 * « Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès » (27/08/2026,
 * signalé à l'écran).
 *
 * Sans lui, le « · » qui sépare les deux espaces du bâtiment 4 se lit comme celui
 * qui introduit AFUL, et « AFUL › Voie d'accès » paraît être un troisième espace
 * du bâtiment. Il n'apparaît QUE là où le « · » deviendrait ambigu — c'est-à-dire
 * dès qu'un des deux groupes voisins compte plusieurs éléments. Deux groupes d'un
 * seul élément portent chacun leur chemin complet et se lisent sans lui :
 * « Bât. 3 › Toit · Bât. 4 › Toit » ne change pas.
 */
export const SEPARATEUR_GROUPE = ' — ';

/**
 * Un nœud d'ORGANISATION : une racine qui ne se cible pas (« Bâtiments »).
 *
 * Il ne qualifie pas ses enfants — « Bâtiments › Bât. 4 » n'apprend rien et allonge
 * tout. Même définition que dans `PerimetrePicker.svelte` (`estGroupeRacine`), et
 * les deux doivent le rester : ce qui fait une pastille de premier niveau à la
 * saisie est exactement ce qui ne se préfixe pas à la lecture.
 */
function estGroupeRacine(n: Perimetre | undefined): boolean {
	return !!n && n.parent === null && !n.selectionnable;
}

/**
 * Le parent qui doit précéder ce nœud dans son libellé, ou `undefined`.
 *
 * 🔴 **La qualification ne s'arrête PLUS aux bâtiments** (27/08/2026, signalé à
 * l'écran). La version précédente exigeait `parent.batiment_id != null`, en
 * s'appuyant sur ceci, qui était écrit juste au-dessus d'elle : *« les enfants du
 * parking, des espaces verts ou des locaux techniques portent déjà des libellés
 * distincts (Places, Chaufferie…) : les préfixer allongerait sans lever
 * d'ambiguïté »*.
 *
 * C'était vrai **du seed, et de lui seul**. Rien n'impose la même discipline aux
 * nœuds créés depuis `/admin/patrimoine` : une « Voie d'accès » ajoutée sous AFUL
 * s'affichait nue sur le fil, sur la carte de ticket et dans la relance syndic —
 * alors que le sélecteur, lui, écrivait bien « AFUL › Voie d'accès ». Le même objet
 * avait donc deux écritures contradictoires selon l'écran, ce que le cadre
 * d'interface interdit ; et devant cet écart c'est la LECTURE qui avait tort, elle
 * perdait une information que la saisie affichait déjà.
 *
 * La condition porte donc sur ce que le parent EST — une cible, ou un simple
 * regroupement — et non sur ce qu'il contient.
 */
function parentQualifiant(n: Perimetre): Perimetre | undefined {
	const parent = n.parent ? carte[cle(n.parent)] : undefined;
	return parent && !estGroupeRacine(parent) ? parent : undefined;
}

/**
 * Le libellé ABRÉGÉ (« Bât. 3 »), employé en position de préfixe : le long
 * (« Bâtiment 3 ») allongerait un badge déjà à deux niveaux.
 */
function court(n: Perimetre): string {
	return n.libelle_court || n.libelle;
}

/**
 * Le chemin d'`ordre` de la racine jusqu'au nœud — sa position dans l'arbre.
 *
 * ⚠️ `ordre` n'est unique qu'entre FRÈRES : le seed donne 0 à « Copropriété
 * entière » comme au premier bâtiment. Trier sur ce seul entier mélangerait les
 * niveaux. Le chemin, lui, se compare terme à terme comme un numéro de chapitre :
 * `[10]` < `[10,0]` < `[20]`. Un parent précède ses enfants, et deux enfants d'un
 * même parent restent **contigus** — ce dont le regroupement de `perimetreLabel`
 * dépend entièrement.
 *
 * La remontée est bornée par `vus` : une boucle dans l'arbre ne doit pas figer
 * l'interface (même garde-fou que `batimentsCibles`).
 */
function cheminOrdre(n: Perimetre): number[] {
	const chemin: number[] = [];
	const vus = new Set<string>();
	let courant: Perimetre | undefined = n;
	while (courant && !vus.has(cle(courant.code))) {
		chemin.unshift(courant.ordre ?? 0);
		vus.add(cle(courant.code));
		courant = courant.parent ? carte[cle(courant.parent)] : undefined;
	}
	return chemin;
}

/** `-1` pour la position absente : un parent passe avant ses enfants. */
function comparerChemins(a: number[], b: number[]): number {
	for (let i = 0; i < Math.max(a.length, b.length); i++) {
		const x = a[i] ?? -1;
		const y = b[i] ?? -1;
		if (x !== y) return x - y;
	}
	return 0;
}

/**
 * Libellé d'un périmètre isolé. Ne rend jamais un code brut à l'écran.
 *
 * 🔴 **Un espace est QUALIFIÉ par son parent** — « Bât. 3 › Toit », « AFUL › Voie
 * d'accès », « Parking › Portail d'accès ». Le gabarit pose les mêmes neuf espaces
 * sous chaque bâtiment, si bien qu'un ticket ciblant les toits de deux bâtiments
 * affichait « Toit · Toit · Bâtiment 3 » (18/08/2026) ; et un espace créé sous un
 * nœud transverse s'affichait nu (27/08/2026). Le détail de la règle et de son
 * élargissement est dans `parentQualifiant`.
 *
 * C'est la même écriture que le résumé des pastilles du sélecteur — un objet se lit
 * partout de la même façon (R3).
 */
export function perimetreLabelUn(code: string): string {
	const n = carte[cle(code)];
	if (n) {
		const parent = parentQualifiant(n);
		return parent ? `${court(parent)} › ${n.libelle}` : n.libelle;
	}
	//  Repli d'affichage, identique à celui du serveur : un contenu peut citer un
	//  nœud supprimé depuis, et l'arborescence peut n'être pas encore chargée.
	//  Ce n'est PAS une source de vérité — la convention `bat:N` est posée par le
	//  seed, l'arbre reste seul juge.
	if (code && cle(code).startsWith(PREFIXE_BATIMENT)) {
		return `Bât. ${code.slice(PREFIXE_BATIMENT.length)}`;
	}
	return code;
}

/**
 * Périmètres → libellé affichable, **trié puis regroupé par parent**.
 * Ex : ['bat:1','parking'] → 'Bât. 1 · Parking'
 *
 * Accepte les DEUX formes que porte réellement le produit : le tableau
 * `perimetre_cible` (publications, tickets) et la chaîne `perimetre` des
 * événements. Le calendrier réimplémentait la fonction pour cette seule raison,
 * avec une table recopiée à l'identique — une correction faite ici ne l'atteignait
 * pas (#316).
 *
 * 🔴 **L'ordre affiché ne suit plus l'ordre des clics** (27/08/2026, signalé à
 * l'écran). Les codes sont stockés dans l'ordre où l'utilisateur a touché les
 * pastilles (`PerimetrePicker`, `value = [...s]`), et personne ne les triait
 * ensuite : deux espaces d'un même bâtiment se retrouvaient séparés par un
 * périmètre étranger, et le bâtiment répété —
 *
 *     Bât. 4 › Logement · Voie d'accès · Bât. 4 › Jardin Bâtiment
 *
 * On trie par la position dans l'arbre, on fusionne les éléments contigus qui
 * partagent un parent qualifiant, et on rend :
 *
 *     Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès
 *
 * Les codes INCONNUS de l'arbre (nœud supprimé depuis, arborescence pas encore
 * chargée) sont conservés — un contenu ne perd pas son badge — mais rangés à la
 * fin, dans leur ordre d'origine : ils n'ont pas de position dans un arbre où ils
 * ne figurent plus.
 *
 * Le `trim()` de `normaliser` n'est pas cosmétique : sur `'bat:1, parking'`, une
 * clé avec espace de tête ne correspond à rien et ressortirait brute à l'écran.
 */
export function perimetreLabel(items: string[] | string | null | undefined): string {
	const codes = normaliser(items);
	const connus = codes.map((c) => carte[cle(c)]).filter(Boolean);
	const inconnus = codes.filter((c) => !carte[cle(c)]);
	connus.sort((a, b) => comparerChemins(cheminOrdre(a), cheminOrdre(b)));

	//  Un « groupe » = des éléments CONTIGUS partageant le même parent qualifiant.
	//  Contigus suffit : le tri par chemin garantit qu'aucun nœud étranger ne peut
	//  s'intercaler entre deux enfants d'un même parent.
	const groupes: { parent?: Perimetre; libelles: string[] }[] = [];
	for (const n of connus) {
		const parent = parentQualifiant(n);
		const dernier = groupes[groupes.length - 1];
		if (dernier && parent && dernier.parent === parent) dernier.libelles.push(n.libelle);
		else groupes.push({ parent, libelles: [n.libelle] });
	}
	for (const c of inconnus) groupes.push({ parent: undefined, libelles: [perimetreLabelUn(c)] });

	return groupes
		.map((g, i) => {
			const corps = g.libelles.join(SEPARATEUR_ELEMENT);
			const rendu = g.parent ? `${court(g.parent)} › ${corps}` : corps;
			if (i === 0) return rendu;
			//  Le séparateur fort UNIQUEMENT là où le « · » deviendrait ambigu :
			//  dès que l'un des deux groupes voisins en contient déjà un.
			const ambigu = groupes[i - 1].libelles.length > 1 || g.libelles.length > 1;
			return (ambigu ? SEPARATEUR_GROUPE : SEPARATEUR_ELEMENT) + rendu;
		})
		.join('');
}

export const ICONES_PERIMETRE: { nom: string; libelle: string }[] = [
	{ nom: 'building-2', libelle: 'Bâtiment' },
	{ nom: 'home', libelle: 'Copropriété' },
	{ nom: 'door-closed', libelle: 'Hall, porte' },
	{ nom: 'stairs', libelle: 'Escalier' },
	{ nom: 'layers', libelle: 'Paliers, étages' },
	{ nom: 'arrow-up-down', libelle: 'Ascenseur' },
	{ nom: 'box', libelle: 'Cave, stockage' },
	{ nom: 'car', libelle: 'Parking' },
	{ nom: 'square-parking', libelle: 'Parking public' },
	{ nom: 'trees', libelle: 'Espaces verts' },
	{ nom: 'sprout', libelle: 'Jardin' },
	{ nom: 'footprints', libelle: 'Cheminement' },
	{ nom: 'lightbulb', libelle: 'Éclairage' },
	{ nom: 'zap', libelle: 'Électricité' },
	{ nom: 'droplet', libelle: 'Eau' },
	{ nom: 'flame', libelle: 'Chauffage' },
	{ nom: 'warehouse', libelle: 'Local technique' },
	{ nom: 'wrench', libelle: 'Entretien' },
	{ nom: 'settings', libelle: 'Divers technique' },
];
