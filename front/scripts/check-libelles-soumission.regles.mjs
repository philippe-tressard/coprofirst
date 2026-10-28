/**
 *  Les EXCEPTIONS de `check-libelles-soumission.mjs` — chacune avec sa raison.
 *
 *  🔴 Séparées du script le 07/09/2026 : la détection (lui) et ce qu'elle
 *  tolère (ici) ne doivent pas grossir dans le même fichier. C'est ce qui l'a
 *  fait passer au-dessus de son propre plafond de modularité.
 *
 *  ⚠️ Cette table BOUGE à chaque écran repris ; la détection, presque jamais.
 *  Deux rythmes différents, deux fichiers — le pattern de
 *  `check-styles-nus.regles.mjs`, pour la même raison exactement.
 */
/**
 * Fichiers dispensés, avec leur raison.
 *
 * Une tolérance sans raison devient un dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une cesse de servir — c'est-à-dire dès que le fichier
 * qu'elle protège devient conforme (règle posée en #374, reprise de
 * `check-pages.mjs`). Une exception qui dort laisserait repasser une vraie
 * divergence dans ce fichier sans que personne l'ait décidé.
 */
export const EXCEPTIONS = {
	//  🔴 Deux DÉCLARATIONS au choix, pas un formulaire (29/09/2026, #779) : le
	//  résident dit « je suis un nouvel arrivant » ou « je suis déjà résident ».
	//  Chaque bouton EST la réponse ; « Enregistrer » ne dirait plus laquelle.
	//  Le bloc vivait dans `profil/+page.svelte`, hors de la portée du contrôle :
	//  c'est son extraction en composant qui l'y a fait entrer.
	'lib/components/DemarcheArrivant.svelte':
		'deux boutons qui sont chacun une réponse (« nouvel arrivant » / « déjà résident ») : le verbe générique effacerait le choix',
	//  🔴 Transmettre une affaire par courriel (#1357) : rien n'est ENREGISTRÉ,
	//  un courriel PART. « Enregistrer » y mentirait sur le geste — même raison
	//  que les confirmations ci-dessous, qui nomment ce qu'elles font.
	//  🔴 Questions au règlement (03/10/2026) : rien n'est saisi pour être
	//  ENREGISTRÉ. « Poser la question » envoie une demande facturée à
	//  l'assistant, « Charger ce texte » remplace le texte interrogé — deux
	//  gestes que le verbe générique ne dirait pas, même raison que le courriel.
	'lib/components/OngletReglement.svelte':
		'« Poser la question » interroge l’assistant (facturé) : il n’enregistre pas une saisie',
	//  🔴 Concilier une fusion refusée (27/10/2026) : le premier temps de la fusion
	//  CHOISIT, il n'enregistre rien — « Continuer » mène à la fusion elle-même, dont
	//  le formulaire (`FusionAffaires`) garde le verbe commun. Un « Enregistrer » ici
	//  ferait croire que la conciliation est déjà décidée côté serveur.
	'lib/components/reporting/EtapeConciliationFusion.svelte':
		'étape de choix avant la fusion : « Continuer » n’enregistre rien, la fusion qui suit a son « Enregistrer »',
	'lib/components/PartageCourriel.svelte':
		'le bouton envoie un courriel et n’enregistre rien : « Envoyer » nomme le geste',
	//  🔴 `PiedFormulaire` rend `{enCours ? libelleEnCours : libelle}` — des
	//  VARIABLES, pas des chaînes. Le contrôle B lit le balisage : il ne peut rien
	//  y voir, et il l'a dit honnêtement (« aucun libellé lisible — contrôle
	//  impossible »).
	//
	//  ⚠️ Ce n'est PAS une dérogation à la règle, c'est un DÉPLACEMENT de
	//  l'endroit où elle se vérifie : `check-pied-formulaire.mjs` lit les valeurs
	//  par défaut de ces props et refuse qu'un appelant en passe d'autres. Le
	//  verbe générique est donc mieux tenu qu'avant — il l'était par dix-neuf
	//  copies d'accord entre elles, il l'est maintenant par une déclaration.
	'lib/components/PiedFormulaire.svelte':
		'le libellé y est une PROP : la règle se vérifie sur ses défauts, dans ' +
		'check-pied-formulaire.mjs, pas sur son balisage',
	//  🔴 Une CONFIRMATION n'est pas une soumission de formulaire, et son verbe
	//  ne doit surtout pas être générique : « Enregistrer » sur une boîte qui
	//  supprime définitivement serait un piège. Le libellé y nomme le GESTE —
	//  « Supprimer », « Archiver » — et c'est ce qui rend la boîte sûre.
	//
	//  ⚠️ L'exception porte sur le VERBE (contrôle B), pas sur l'ordre des
	//  boutons : « Annuler » y vient bien avant l'action, comme partout ailleurs
	//  (contrôle C), et c'est délibérément la même main.
	'lib/components/Confirmation.svelte':
		'boîte de confirmation : le verbe nomme le geste (« Supprimer »), il ne peut pas être générique',
	//  🔴 Même famille que `Confirmation`, et même raison (12/09/2026) : une
	//  SAISIE impérative n'est pas une soumission de formulaire. Son verbe nomme
	//  ce que le texte va faire — « Signaler » —, et « Enregistrer » y serait
	//  faux : rien n'est enregistré, un signalement part au conseil syndical.
	//  ⚠️ Comme pour `Confirmation`, l'exception porte sur le VERBE seul : « Annuler »
	//  vient bien avant l'action, la même main que partout ailleurs.
	'lib/components/Saisie.svelte':
		'saisie impérative : le verbe nomme le geste (« Signaler »), il ne peut pas être générique',
	//  🔀 Même famille encore (05/10/2026, #1704) : la question posée À LA CLÔTURE.
	//  Son verbe nomme le geste — « Clore sans fusionner », « Clore et fusionner (n) » —
	//  et rien n'y est « enregistré » : la boîte répond à l'appelant, qui clôt.
	'lib/components/DialogueFusion.svelte':
		'question à la clôture : le verbe nomme le geste (« Clore et fusionner »), il ne peut pas être générique',
	//  ── Hors périmètre par la RÈGLE elle-même (§9 quinquies bis) ────────────
	//  Ce ne sont pas des créations d'objet, et leur verbe métier est le bon.
	'lib/components/FormulaireCreation.svelte':
		"c'est le cadre (titre + boîte), pas un formulaire — chaque écran écrit son " +
		'propre bouton dans son <form>',
	'lib/components/ChangementMotDePasse.svelte':
		'changement de mot de passe — hors périmètre explicite de la règle',
	'routes/auth/connexion/+page.svelte': "écran d'authentification — « Se connecter »",
	'routes/auth/inscription/+page.svelte': "écran d'authentification — « Créer mon compte »",
	'routes/auth/mot-de-passe-oublie/+page.svelte':
		"écran d'authentification — « Envoyer le lien » ne crée aucun objet",
	'lib/components/AiguillageCopropriete.svelte':
		"écran d'authentification de l'hôte commun (#1894) — « Continuer » n'enregistre rien, il renvoie à l'adresse de la copropriété",
	'routes/auth/verifier-email/+page.svelte':
		"écran d'authentification — « Renvoyer » relance un e-mail déjà parti",
	//  🔴 Arbitré à l'écran le 18/08/2026 : « Créer et envoyer au CS me semble
	//  bizarre : ça doit être plutôt Générer une affiche ». Cet écran ne crée pas un
	//  objet qu'on retrouvera dans une liste — il FABRIQUE un document à imprimer,
	//  et depuis le même jour il n'envoie plus rien. Même famille que les imports,
	//  déjà hors périmètre de la règle.
	'lib/components/FormulaireAnnonceHall.svelte':
		'affiche de hall — « Générer une affiche » : on produit un document, on ne ' +
		"crée pas un objet (et l'écran n'envoie plus d'e-mail depuis le 18/08/2026)",

	//  ── RESTE À TRAITER — révélé par l'élargissement de portée (#416) ───────
	//  Ces écarts sont réels et connus. Ils ne sont PAS corrigés dans #416, dont
	//  le périmètre est `EvolForm` : les corriger au passage aurait mélangé deux
	//  lots dans le même diff. Chaque ligne dit ce qu'on lit à l'écran ; l'entrée
	//  disparaît d'elle-même quand l'écran est repris, sinon ce contrôle échoue
	//  en réclamant sa suppression.
	'routes/(app)/profil/+page.svelte':
		'« Envoyer la demande » / « Envoi… » (l. ~451) et « Je suis un nouvel arrivant » ' +
		'/ « Envoi… » (l. ~526)',
	//  ⚠️ L'exception de `tickets/[id]` disait « c'est une seconde écriture
	//  d'`EvolForm`, à fusionner avant d'aligner le verbe ». La fusion a eu lieu le
	//  17/08/2026 (#431) : le formulaire de réponse écrit à la main a disparu, le
	//  geste n'a plus qu'un libellé, et le contrôle a REFUSÉ la tolérance dès
	//  qu'elle est devenue inutile.
};
