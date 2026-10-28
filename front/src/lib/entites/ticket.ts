/**
 * Le TICKET, déclaré une fois — les sections du cadre, ce qu'elles portent, et
 * **chaque divergence entre états avec son motif** (R4).
 *
 * Première entité mise au cadre #430, parce qu'elle en était déjà la plus proche :
 * #425 avait rendu `FormulaireTicket` paramétrable, et c'était le **seul endroit
 * du produit** où chaque écart entre création et édition portait une raison
 * écrite. Elles vivaient en commentaires, donc invisibles à tout contrôle ; elles
 * vivent ici, et `npm run lint:etats` les vérifie.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireTicket.svelte`  — création ET édition (`sectionPresente`)
 *   • `FicheLecture.svelte`      — affichage, via `sectionsDe(TICKET, 'affichage')`
 *   • `EvolForm.svelte`          — évolution *(pas encore : composant partagé par
 *     quatre écrans, il rejoindra le cadre avec #463 — cf. la note en fin de
 *     fichier)*
 *
 * ⚠️ **Rien de spécifique au ticket ne doit s'écrire ailleurs.** Si un écran a
 * besoin de savoir qu'une section du ticket est absente quelque part, il appelle
 * `sectionPresente` — il ne réécrit pas la condition.
 */

import type { EntiteDeclaree } from './types';
import { DIFFUSION_NE_SE_LIT_PAS } from './types';

/**
 * ⚠️ **Plus aucun motif `api` ici, et c'est un événement.** Deux divergences en
 * portaient un, citant #431 : les **photos** fermées en édition, et « Saisi
 * pour » qu'on ne pouvait pas effacer. Un motif `api` est une **dette, jamais un
 * choix** — il tombe le jour où l'API sait faire, et sa disparition est la preuve
 * qu'elle a été payée. Les deux ont été soldées le 18/08/2026.
 *
 * `lint:etats` garde encore un cas vivant, côté publications (#390) : le contrôle
 * du motif `api` n'est donc pas devenu aveugle faute de sujet.
 */

export const TICKET: EntiteDeclaree = {
	id: 'ticket',
	libelle: 'Affaire',
	motDeCode: 'ticket',
	//  « Nouvelle affaire », le mot du bouton qui l'ouvre : la boîte disait
	//  « Signaler une affaire » sous un bouton « Nouvelle affaire » (#1329).
	libelleNouveau: 'Nouvelle affaire',
	libelleModifier: "Modifier l'affaire",
	sections: [
		{
			//  🔴 Le TITRE, et lui seul. La catégorie a longtemps partagé cette
			//  section — elle y était même rendue AVANT le titre, si bien que le
			//  premier champ de la première section n'était pas le titre. Arbitré
			//  par l'utilisateur le 18/08/2026 : *« dans Tickets, le titre est en
			//  second, il devrait être en premier ; la catégorie fait partie des
			//  champs spécifiques »*. La catégorie qualifie le ticket comme
			//  « Saisi pour » : elle est en section 2.
			id: 'titre',
			objet: 'Titre',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "Une entrée de l'Historique se rattache au ticket ; elle ne le renomme pas.",
				},
			},
		},
		{
			id: 'nature',
			//  « Actualité » en tête, pleine ligne, puis un filet avant les
			//  catégories de suivi (23/09/2026, variante A arbitrée à l'écran) :
			//  on choisit d'abord entre informer et faire suivre.
			objet: 'Catégorie de l’affaire — elle décide de QUI traite ; « Actualité » en tête',
			titreEcran: 'Catégorie',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						'La catégorie appartient à l’affaire, pas à l’entrée du fil. Une suite ' +
						'raconte ce qui lui arrive, elle ne la reclasse pas.',
				},
			},
		},
		{
			//  ✅ CONSTRUITE le 24/09/2026 (#1097) — « sur quoi », que le décret
			//  n° 2001-477 attend du carnet. Posée par le CONSEIL, jamais demandée au
			//  résident : il voit une flaque, il ne sait pas si c'est la plomberie
			//  ou la toiture. Mêmes extinctions que l'Intervenant, dont elle propose
			//  le prestataire sous contrat ; règles serveur : `utils/intervenant`.
			//  C'est elle qui RANGE une affaire résolue au carnet (sans elle :
			//  « Sans équipement rattaché », jamais exclue — 24/09/2026).
			id: 'equipement',
			objet: 'Équipement concerné — alimente le carnet d’entretien',
			pliee: true,
			inactivePour: {
				actualite:
					'Une actualité informe : personne n’intervient, elle n’a donc ni équipement, ni intervenant.',
				resident:
					'Le conseil syndical désigne l’équipement : on signale ce qu’on voit, pas ce qu’il faut entretenir.',
				horsBati: 'Seulement pour les catégories du bâti — celles au liseré doré.',
			},
		},
		{
			//  🔴 Aucune divergence, et c'est la correction due au cadre. L'édition
			//  CORRIGE — une erreur, un oubli, un complément — et l'état s'y corrige
			//  comme les autres champs. Jusqu'au 17/08/2026 l'édition ne montrait
			//  qu'un badge en lecture, avec une mention « l'état se change depuis le
			//  fil » : le motif invoqué (`trace`) n'existe pas dans le cadre.
			//  La traçabilité, elle, ne tombe pas : c'est le `PATCH` qui a changé —
			//  il écrit désormais une CORRECTION, pas une transition de workflow
			//  (`api/app/routers/tickets/crud.py`).
			//  🔁 Une ACTUALITÉ a désormais un suivi OPTIONNEL (10/10/2026) : la case
			//  du conseil, puis Ouvert · Résolu · Annulé par une Suite. La section n'y
			//  est donc plus éteinte ; facultative, elle s'y plie (`#lib/suivi-actualite`
			//  et `SectionsSpecifiquesTicket`).
			id: 'suivi',
			requis: true,
			objet:
				'Ouvert · En cours · Résolu · Annulé — pour une actualité, optionnel : Ouvert · Résolu · Annulé',
		},
		{
			id: 'quand',
			objet: 'SectionQuand — début, fin et échéance',
			//  🔴 Deux notions distinctes, et cette entité est la seule à porter les
			//  deux : `debut`/`fin` disent QUAND ÇA SE PASSE et alimentent le
			//  calendrier ; `echeance` dit AVANT QUAND C EST ATTENDU et alimente la
			//  relance. Une échéance dans l agenda y mettrait « devis attendu sous
			//  15 jours » entre l AG et la coupure d eau (#1092).
			pliee: true,
			//  🔴 Planifiée par le conseil syndical, et par lui seul (arbitré le
			//  23/09/2026) : le serveur ignore ce qu'un autre y enverrait.
			inactivePour: {
				bug: 'Un bogue se corrige, il ne se planifie pas.',
				resident: 'Le conseil syndical planifie la date.',
			},
		},
		{
			id: 'intervenant',
			objet: 'Prestataire qui intervient',
			pliee: true,
			//  ✅ CONSTRUITE le 23/09/2026 (#1092, lot 5) : les événements du
			//  calendrier, qui portaient leur prestataire, deviennent des affaires.
			//  Présente à la création comme à la correction ; éteinte là où elle
			//  n'a pas de sens — et le serveur efface ce qu'elle portait
			//  (`utils/intervenant`).
			inactivePour: {
				actualite:
					'Une actualité informe : personne n’intervient, elle n’a donc ni équipement, ni intervenant.',
				resident: 'Le conseil syndical désigne l’intervenant.',
				horsBati: 'Seulement pour les catégories du bâti — celles au liseré doré.',
			},
		},
		{
			//  🔴 LA DIVERGENCE A ÉTÉ RETIRÉE LE 19/08/2026, et c'est un revirement.
			//
			//  Elle disait : *« Le périmètre est celui du ticket ; une entrée ne le
			//  redéfinit pas »* — motif `hérité`. C'était juste tant qu'un périmètre
			//  était acquis à l'ouverture. L'usage a réfuté la prémisse (#497) :
			//
			//  > *« le périmètre de la fuite pourrait être précisé et évolue »*
			//
			//  Un ticket se signale avec ce qu'on sait au moment où on le signale,
			//  donc souvent avec le périmètre le plus large. Puis on cherche, et
			//  « bâtiment 2 » devient « bât. 2, 3ᵉ étage, cage B ». Une entrée du fil
			//  PEUT donc déclarer un périmètre — il devient alors celui du ticket.
			//
			//  ⚠️ Le champ reste **facultatif** dans ce seul état : y toucher est un
			//  geste rare et volontaire, et ne rien dire ne change rien. C'est une
			//  nuance que R4 ne sait pas déclarer (elle ne parle que de SECTIONS,
			//  #436) — elle est portée par `EvolForm.avecPerimetre`, dont le nom dit
			//  qu'elle est optionnelle, et par le test `test_evolution_perimetre.py`
			//  qui vérifie qu'une entrée muette laisse le ticket tranquille.
			id: 'perimetre',
			objet: 'PerimetrePicker — de quoi il s’agit',
			requis: true,
			inactivePour: {
				bug: 'Un bogue concerne le site, pas un lieu de la copropriété : le périmètre est verrouillé.',
			},
		},
		{
			id: 'description',
			objet: 'RichEditor — le problème, en détail',
			requis: true,
		},
		{
			//  Les documents sont ouverts à l'édition depuis le cadre :
			//  `fichiers_urls` EST accepté par `TicketUpdate`, et une liste vide
			//  efface sans ambiguïté.
			id: 'pieces_jointes',
			objet: 'FichiersUpload mode mixte — photos et documents',
			//  🔴 PLIÉE, comme toute section facultative (21/09/2026, demandé à
			//  l'écran). Elle était l'exception inverse — « dépliée parce que joindre
			//  une photo est le premier geste sur téléphone ». C'est l'ARBITRAGE qui a
			//  changé, pas la règle : un formulaire aux sections toutes ouvertes
			//  n'est pas lisible au pouce.
			//  ⚠️ `valeurModifiee` la rouvre dès qu'un fichier y est joint : en
			//  édition, un objet qui porte des pièces jointes ne les cache pas.
			pliee: true,
		},
		{
			//  🆕 26/09/2026 (#1342) : les affaires qui parlent de la même chose —
			//  une fuite et la tache qu'elle a faite au plafond du dessous. Le lien
			//  est RÉCIPROQUE et ne révèle rien : une affaire que le lecteur ne peut
			//  pas lire n'apparaît pas pour lui (`api/app/utils/affaires_liees.py`).
			//  Facultative, donc pliée. Ouverte à l'évolution : une Suite AJOUTE un
			//  lien, elle n'en retire aucun — le serveur le tient.
			//  🔒 Le conseil et l'admin seuls relient (arbitré le 30/09/2026) : le
			//  résident voit les liens sur la fiche, il ne les pose ni ne les défait
			//  (`utils/affaires_liees.exiger_conseil`).
			id: 'affaires_liees',
			objet: 'SectionAffairesLiees — numéro et titre de chaque affaire liée',
			pliee: true,
			inactivePour: { resident: 'Le conseil syndical relie les affaires entre elles.' },
		},
		{
			//  ✅ OUVERT à l'édition depuis le 18/08/2026. Il en était absent parce
			//  que `TicketUpdate` ne savait pas EFFACER les `saisi_pour_*` — un
			//  `None` y était indistinguable d'un champ non envoyé, et « En mon
			//  nom » aurait été un choix sans effet, en silence. Le serveur lit
			//  désormais la PRÉSENCE du champ (`model_fields_set`).
			//  🔴 Obligatoire, donc DEPLIEE — et plus d'exception (22/09/2026).
			//
			//  Elle etait pliee, au motif que « en mon nom » est juste dans la
			//  quasi-totalite des cas. Signale a l'ecran le jour de sa livraison :
			//  une section marquee d'une asterisque qui arrive fermee demande de
			//  l'ouvrir pour voir qu'il n'y a rien a y faire, ce qui est exactement
			//  le contraire de ce que l'asterisque annonce.
			//
			//  ⚠️ C'etait la SEULE exception de pliage du cadre. La regle
			//  « obligatoire -> deplie, facultatif -> plie » n'en a plus aucune, et
			//  c'est ce que l'utilisateur a demande : « pour eviter toute exception ».
			id: 'au_nom_de',
			objet: 'Saisi pour — en mon nom · un résident inscrit · une personne extérieure',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						'Au nom de qui l’affaire a été ouverte appartient à l’affaire. Une suite ' +
						'ne la ré-attribue pas — `EvolForm` n’a jamais proposé ce champ.',
				},
			},
			inactivePour: {
				bug: 'Un bogue se signale en son propre nom.',
			},
		},
		{
			id: 'destinataires',
			//  🔴 Une ACTUALITÉ dit à qui elle parle (#1091) ; une affaire suivie non :
			//  elle est lue de tous sauf les locataires, dans son périmètre, et
			//  `destinataire_syndic` / `destinataire_cs` sont des CANAUX (section 9).
			//
			//  🔴 RALLUMÉE pour l'affaire le 25/09/2026 (lot 1 de la pastille de
			//  lecture) : elle répond à « qui d'autre la lit ? » pour les deux
			//  natures, et s'ouvre par « Confidentielle ».
			//
			//  🔴 L'AFFAIRE Y CHOISIT SES PROFILS depuis le 26/09/2026 (#1343) —
			//  *« il n'est toujours pas possible de choisir son destinataire ! c'est
			//  urgent »*. Présélectionnés par sa nature, changés par le conseil à
			//  tout moment, appliqués par `ticket_visible` ; « Résident concerné »
			//  remplace la case pour une affaire.
			requis: true,
			objet:
				'Qui la lit — Confidentielle (actualité) ou Résident concerné (affaire), puis DestinatairePicker, présélectionné par la nature (#1343)',
			inactivePour: {
				resident:
					'Le conseil syndical décide qui la lit. Sur la carte, la pastille de lecture le dit à tous.',
				bug: 'Un bogue va au gestionnaire du site : il n’a pas d’autre lecteur.',
			},
		},
		{
			//  🔴 ELLE EST OUVERTE À L'ÉVOLUTION, et c'est ce que la scission permet
			//  enfin de DÉCLARER (#1095, constaté à l'écran le 05/09/2026 :
			//  *« Options de publications n'apparaît pas sur un commentaire »*).
			//
			//  Les trois notions vivaient dans une seule section : catégorie et
			//  « Saisi pour » sont héritées, les options se corrigent en commentant.
			//  Une section absente pour l'une fermait la porte aux deux autres, et
			//  la nuance ne pouvait s'écrire qu'en COMMENTAIRE — invisible à
			//  `lint:etats`. C'est la limite que #436 décrivait, et elle se referme
			//  ici : chacune est maintenant sa propre section, avec son propre motif.
			//
			//  ⚠️ Déclarée ouverte, elle n'était pourtant PAS RENDUE dans la Suite
			//  d'une affaire jusqu'au 25/09/2026 : `EvolForm` n'ouvrait son créneau
			//  que sur `nature`, héritée ici. Signalé à l'écran — « une affaire peut
			//  devenir urgente » ; le créneau suit désormais toutes ses sections.
			id: 'mise_en_avant',
			//  📌 et 🚨 seulement, pour les deux natures (25/09/2026) : 🛡️ et 🔒
			//  disent qui LIT, ils ouvrent Destinataires et Périmètre.
			objet: 'Épinglage · Urgence',
			pliee: true,
			inactivePour: {
				bug: 'Un bogue va au gestionnaire du site : ni épingle, ni urgence, ni réserve.',
			},
		},
		{
			id: 'diffusion',
			objet: 'CanauxNotification — WhatsApp, syndic, conseil syndical',
			absente: {
				affichage: DIFFUSION_NE_SE_LIT_PAS,
			},
			pliee: true,
			inactivePour: {
				bug: 'Un bogue ne prévient que le gestionnaire du site, et lui seul.',
			},
		},
	],
};

/**
 * ⚠️ **Ce que cette déclaration ne gouverne PAS encore, et pourquoi.**
 *
 * L'état `evolution` est déclaré ici, mais `EvolForm.svelte` ne le consomme pas :
 * ce composant sert **cinq écrans** — tickets, fiche de ticket, actualités,
 * espace CS, et le **calendrier** depuis le 18/08/2026 (`HistoriqueEvenement`) —
 * et l'y brancher changerait les quatre autres avant qu'on les ait regardés.
 * C'est très exactement ce que R5 interdit : *l'enrichissement se propose sur UN
 * écran, se fait constater, puis se généralise*.
 *
 * ⚠️ Le compte était resté à « quatre » après l'arrivée du cinquième : un nombre
 * écrit dans un commentaire ne se met pas à jour tout seul, et c'est précisément
 * ce nombre qui justifie de ne pas brancher.
 *
 * ✅ **La divergence que cette note décrivait est SOLDÉE.** Elle disait qu'`EvolForm`
 * savait rendre les pièces jointes « unifiées » (`separatePhotosAndDocs = false`),
 * fusionnant les sections 7 et 8, et que les actualités et l'espace CS s'en
 * servaient. Le mode a disparu le **18/08/2026**, quand son dernier appelant l'a
 * quitté — mais la note, elle, est restée, et a été **recopiée telle quelle dans
 * `evenement.ts`** le lendemain. Une affirmation périmée ne dort pas : elle se
 * propage au fichier suivant.
 *
 * Ce qui subsiste réellement : `EvolForm` n'est gouverné par aucune déclaration,
 * il sert **cinq** écrans, et l'intitulé de sa description bascule
 * « Commentaire » / « Contenu » là où **R3** demande le même libellé partout.
 * C'est **#463** — et non plus #433, fermé le 18/08 après constat en production.
 */
