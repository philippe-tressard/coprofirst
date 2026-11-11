/**
 * **« Saisi pour »** — au nom de qui une entrée est ouverte, côté écran.
 *
 * ## Pourquoi ce module (15/09/2026)
 *
 * La notion vivait dans le seul circuit des tickets. Son extension aux
 * **actualités** et aux **événements**, demandée à l'écran, aurait recopié deux
 * fois chacune de ses trois règles :
 *
 * 1. **quel mode** un objet déjà enregistré rouvre (`modeDepuis`) ;
 * 2. **ce qui part** vers l'API selon le mode (`lotSaisiPour`) ;
 * 3. quelles valeurs le formulaire remet à zéro.
 *
 * Aucune n'est évidente, et la deuxième est franchement contre-intuitive.
 *
 * ## ⚠️ Les trois champs partent TOUJOURS, y compris à `null`
 *
 * C'est leur **présence** dans la charge utile qui dit au serveur d'écrire
 * (`model_fields_set` côté Python, cf. `api/app/utils/saisi_pour.py`), et c'est
 * ce qui permet de revenir à « En mon nom » : sans elles, un `null` serait
 * indistinguable d'un champ non transmis, et le choix resterait sans effet — en
 * silence.
 *
 * ⚠️ Et le mode décide **lesquels** valent quelque chose : revenir d'« une
 * personne extérieure » à « un résident inscrit » doit effacer le nom saisi,
 * sinon un ancien destinataire survivrait à la personne qui le remplace.
 *
 * ## Le pendant serveur
 *
 * `api/app/utils/saisi_pour.py` — même notion, mêmes trois champs, et le mixin
 * dont héritent `Ticket`, `Publication` et `Evenement`. Les contextes de build
 * étant `./api` et `./front`, le partage d'un fichier est impossible (mémoire
 * `project_partage_front_api_impossible`) : ce sont deux écritures assumées
 * d'une même règle, et c'est le serveur qui tranche.
 */

/** En son nom, pour un résident inscrit, ou pour une personne extérieure. */
export type ModeSaisiPour = 'moi' | 'resident' | 'exterieur';

/** Ce qu'un objet déjà enregistré porte de « Saisi pour ». */
export interface PorteSaisiPour {
	saisi_pour_user_id?: number | null;
	saisi_pour_nom?: string | null;
	saisi_pour_email?: string | null;
}

/**
 * Le mode qu'un objet ROUVRE à l'édition.
 *
 * 🔴 L'ordre des deux tests n'est pas indifférent : un résident inscrit peut
 * avoir laissé un nom d'une saisie antérieure, et c'est l'identifiant qui fait
 * foi. L'inverse rouvrirait « personne extérieure » sur un ticket rattaché à un
 * compte.
 *
 * ⚠️ Rouvrir sur « En mon nom » par défaut effacerait le « Saisi pour » au
 * premier enregistrement — c'est pour cela que cette fonction existe plutôt
 * qu'un `'moi'` initial.
 */
export function modeDepuis(objet: PorteSaisiPour | null | undefined): ModeSaisiPour {
	if (objet?.saisi_pour_user_id) return 'resident';
	if (objet?.saisi_pour_nom) return 'exterieur';
	return 'moi';
}

/**
 * Ce qui part vers l'API — les **trois** champs, toujours.
 *
 * ⚠️ Ne jamais filtrer ce que cette fonction rend, ni l'étaler
 * conditionnellement : c'est la présence des trois clés qui permet d'effacer.
 */
export function lotSaisiPour(
	mode: ModeSaisiPour,
	userId: number | null,
	nom: string,
	email: string,
): Required<PorteSaisiPour> {
	return {
		saisi_pour_user_id: mode === 'resident' ? userId : null,
		saisi_pour_nom: mode === 'exterieur' ? nom.trim() || null : null,
		saisi_pour_email: mode === 'exterieur' ? email.trim() || null : null,
	};
}

/**
 * Les trois champs d'un formulaire, repris d'un objet existant ou vides.
 *
 * ⚠️ **Les trois sont toujours présents**, y compris pour une création : c'est
 * ce qui garantit qu'ils partiront vers l'API (`lotSaisiPour` en fait autant à
 * l'envoi), et donc qu'un retour à « En mon nom » soit enregistré.
 *
 * ⚠️ `saisi_pour_user_id` vaut `null` et non `''` — c'est un identifiant, et un
 * `''` envoyé à un champ entier serait refusé par le serveur.
 */
export function champsSaisiPour(
	objet: PorteSaisiPour | Record<string, unknown> | null | undefined,
): {
	saisi_pour_user_id: number | null;
	saisi_pour_nom: string;
	saisi_pour_email: string;
} {
	const o = (objet ?? {}) as PorteSaisiPour;
	return {
		saisi_pour_user_id: o.saisi_pour_user_id ?? null,
		saisi_pour_nom: o.saisi_pour_nom ?? '',
		saisi_pour_email: o.saisi_pour_email ?? '',
	};
}

/** Une personne proposable dans le sélecteur « pour un résident inscrit ». */
export interface ResidentProposable {
	id: number;
	/** « Prénom NOM » rendu par le serveur (`UserRead.nom_affiche`, #2633). */
	nom_affiche: string;
	email: string;
}

/**
 * Ce qu'un objet déjà enregistré sait de son propriétaire : **le nom AFFICHÉ**.
 *
 * ## 🔴 Servi par l'API depuis #2508
 *
 * « À qui cet objet appartient » — la personne « saisie pour » s'il y en a une,
 * le rédacteur sinon (#1104) — se composait ici (`nomProprietaire`). L'app iOS
 * devait le recomposer à son tour : le serveur le sert (`nom_proprietaire`,
 * `schemas_affaire_servie`), et les deux clients le LISENT. La règle est écrite
 * une fois, côté serveur ; `npm run lint:regles-partagees` refuse son retour ici.
 *
 * ⚠️ C'est le défaut que ce module portait depuis sa naissance : sa propre
 * en-tête signalait que `CarteTicket` composait `proprietaire_nom ?? auteur_nom`
 * à la main — la remarque est restée, l'expression aussi, et les cartes ont
 * continué d'afficher le rédacteur pendant six jours. `npm run
 * lint:nom-proprietaire` refuse toujours un `auteur_nom` affiché à sa place.
 */
export interface PorteProprietaire {
	nom_proprietaire?: string | null;
}

/**
 * **À QUI part la copie** — le nom écrit dans « Envoyer une copie à … ».
 *
 * ## 🔴 Pourquoi cette fonction (15/09/2026)
 *
 * Signalé à l'écran :
 *
 * > « Quand on change "Saisi pour" avec une personne ayant un email, ça change
 * >   envoyer une copie à X »
 *
 * C'est le comportement **voulu** — arbitré le 12/09 : *« pour un ticket dont
 * le "Saisi pour" possède un résident inscrit ou une personne extérieure, ce
 * dernier se substitue à l'auteur »*. La copie va au PROPRIÉTAIRE, pas à celui
 * qui tape.
 *
 * ⚠️ Mais les écrans ne le disaient pas tous. `CarteTicket` et
 * `FilMessagesTicket` composaient `proprietaire_nom ?? auteur_nom` — deux fois
 * la même expression —, tandis que **les formulaires passaient `auteur_nom`
 * seul**. La même case annonçait donc deux noms différents selon l'écran, et
 * celui du formulaire était le mauvais.
 *
 * 🔴 **Et ce paragraphe, écrit à l'imparfait, décrivait un défaut encore
 * PRÉSENT** — pendant six jours (#1104). Ce lot n'avait corrigé que la moitié
 * qui l'intéressait, la copie ; les cartes ont continué d'afficher
 * `auteur_nom` brut, trois lignes sous un appel à `nomCopie`. Une remarque au
 * passé sur un défaut présent est pire qu'un silence : elle donne l'impression
 * que quelqu'un s'en est occupé. Le nom affiché est désormais servi
 * (`nom_proprietaire`), et `npm run lint:nom-proprietaire` refuse la récidive.
 *
 * 🔴 Et en CRÉATION, aucun des deux ne convenait : rien n'est encore
 * enregistré, mais le rédacteur vient de désigner quelqu'un. La case doit dire
 * **ce qui partira**, pas ce qui était là — sinon elle promet un destinataire
 * et en sert un autre. C'est exactement ce que l'arbitrage du 31/08 reprochait
 * à « Envoyer une copie à l'auteur » : un libellé qui ne dit pas à qui l'on
 * écrit.
 *
 * @param objet L'objet enregistré, s'il existe.
 * @param saisie Le « Saisi pour » en cours de saisie, s'il y en a un. Il
 *   l'emporte : c'est lui qui sera enregistré au prochain clic.
 * @returns Le nom, ou `''` — jamais `undefined`. `CanauxNotification` retombe
 *   alors sur « l'auteur », jamais sur rien.
 */
export function nomCopie(
	objet: PorteProprietaire | null | undefined,
	saisie?: {
		mode: ModeSaisiPour;
		userId: number | null;
		nom: string;
		residents: ResidentProposable[];
	},
): string {
	if (saisie?.mode === 'exterieur' && saisie.nom.trim()) return saisie.nom.trim();
	if (saisie?.mode === 'resident' && saisie.userId != null) {
		const p = saisie.residents.find((r) => r.id === saisie.userId);
		//  ⚠️ Sans le résident sous la main (liste pas encore chargée), on retombe
		//  sur l'enregistré plutôt que d'afficher un nom vide : une case muette
		//  redeviendrait « Envoyer une copie à l'auteur », c'est-à-dire l'ambiguïté
		//  que le libellé nommé existe pour lever.
		if (p) return p.nom_affiche;
	}
	//  🔴 Le repli n'est PAS réécrit ici : le serveur le compose, une fois
	//  (`nom_proprietaire`, #2508). Cette fonction ne répond qu'à la saisie en cours.
	return objet?.nom_proprietaire ?? '';
}

/**
 * **L'état de saisie**, comme un objet — et non quatre variables parallèles.
 *
 * 🔴 Les quatre se déclaraient, se liaient et se passaient séparément dans
 * chaque formulaire : quatre `let`, quatre `bind:`, quatre arguments. Trois
 * écrans × huit lignes, pour UNE notion. Et deux de ces trois fichiers étaient
 * au plafond de modularité, si bien que la notion ne pouvait plus s'étendre.
 *
 * ⚠️ Les quatre champs changent **ensemble** — c'est déjà vrai côté serveur, où
 * ils voyagent groupés. Un objet le dit ; quatre variables laissent croire
 * qu'on peut en toucher une seule.
 */
export interface SaisieSaisiPour {
	mode: ModeSaisiPour;
	userId: number | null;
	nom: string;
	email: string;
}

/** L'état de saisie d'un objet existant — ou vierge. */
export function saisieDepuis(objet: PorteSaisiPour | null | undefined): SaisieSaisiPour {
	const c = champsSaisiPour(objet);
	return {
		mode: modeDepuis(objet),
		userId: c.saisi_pour_user_id,
		nom: c.saisi_pour_nom,
		email: c.saisi_pour_email,
	};
}

/** Ce qui part vers l'API, depuis l'état de saisie. */
export function lotDepuisSaisie(s: SaisieSaisiPour): Required<PorteSaisiPour> {
	return lotSaisiPour(s.mode, s.userId, s.nom, s.email);
}
