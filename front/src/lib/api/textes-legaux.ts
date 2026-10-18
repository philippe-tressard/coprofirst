//  Les TEXTES LÉGAUX d'une copropriété (#2065) : ce que l'administration édite —
//  la source, ses champs et leurs valeurs — et le constat « à relire ». Les appels
//  vivent dans `config` (`administration.ts`) ; leurs types ont quitté ce fichier
//  quand il a franchi le plafond de 500 lignes, à l'assemblage de la v2.178.0.

/**  Un champ des textes légaux et sa valeur pour LA copropriété servie (#2065) :
 *   `null`, il se rend « À RENSEIGNER », et `ou` dit où le renseigner. */
export interface ChampTexteLegal {
	nom: string;
	libelle: string;
	ou: string;
	valeur: string | null;
}

/**  Le constat d'un texte légal : relu tel qu'il est enregistré, et complet. */
export interface EtatTexteLegal {
	cle: string;
	titre: string;
	/** « relue » ou « relues » : l'accord du titre, déclaré par le serveur. */
	participe_relu: string;
	relu: boolean;
	relu_le: string | null;
	complet: boolean;
	manques: string[];
	a_relire: boolean;
}

export interface ConstatTextesLegaux {
	a_relire: boolean;
	textes: EtatTexteLegal[];
}

/**  `GET /config/textes-legaux` — la SOURCE que l'administration édite (champs
 *   compris, jamais remplis), leurs valeurs et le constat. */
export interface TextesLegauxSource {
	textes: Record<string, string>;
	champs: ChampTexteLegal[];
	contact: string;
	etat: ConstatTextesLegaux;
}
