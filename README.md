<h1 align="center">
  <img src="docs/images/coprofirst.png" alt="CoproFirst" width="160" />
</h1>

<p align="center">
  <em>Application web de gestion de copropriétés — côté résidents et conseil syndical.</em>
</p>

<p align="center">
  <a href="https://github.com/philippe-tressard/coprofirst/actions/workflows/ci.yml"><img src="https://github.com/philippe-tressard/coprofirst/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-AGPL--3.0--or--later-blue.svg" alt="Licence AGPL-3.0-or-later — logiciel libre" /></a>
  <a href="https://api.reuse.software/info/github.com/philippe-tressard/coprofirst"><img src="https://api.reuse.software/badge/github.com/philippe-tressard/coprofirst" alt="REUSE compliant" /></a>
  <img src="https://img.shields.io/badge/python-3.12-3776ab.svg" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/node-22+-339933.svg" alt="Node 22+" />
</p>

---

> **Votre résidence a désormais son appli.**
> Signalez un problème, suivez les travaux, consultez vos documents, commandez un badge ou échangez entre voisins — tout se fait depuis un seul espace, sécurisé et accessible 24 h/24.

**Deux noms, deux choses.** Le logiciel s'appelle **CoproFirst** ; « 5Hostachy » est la résidence pour laquelle il est né, et le nom que ce dépôt a porté jusqu'au 09/10/2026 (les anciennes adresses redirigent ici). Rien dans le code ne nomme la résidence : son nom, son adresse et ses textes légaux se règlent dans l'administration, et l'application installée sur un téléphone porte le nom de **la résidence qui la sert**. Le pied de chaque page renvoie au code source de la version en service. **Depuis la version 3.0.0, CoproFirst est multi-copropriété** : une même installation sert plusieurs copropriétés, chacune dans sa base, ses fichiers et ses textes légaux, étanches entre elles. L'architecture : [`specs/architecture/multi-coproprietes.md`](specs/architecture/multi-coproprietes.md).

## Fonctionnalités

- **Tableau de bord** — la page d'accueil&nbsp;: les **consignes** du conseil syndical, ce qui est **📌 épinglé**, le **kanban** des dossiers en cours (les colonnes de l'onglet Kanban d'Affaires, reprises en brique), puis le **fil** de ce qui s'est passé — et ses archives
- **Affaires / Demandes** — Signalements avec suivi par le conseil syndical. Une **actualité qui dérape devient une affaire** d'un clic (🎯 *Transformer en affaire*) : c'est la **même** affaire qui change de catégorie — titre, description, pièces jointes, périmètre et **adresse** restent, **rien n'est à ressaisir**. Les **actualités** elles-mêmes vivent dans cette vue, sous le filtre **Actualité · Calendrier · Affaire** — et le suivi en trois pastilles : Ouvert · En cours · Résolu : la page Actualités n'existe plus, et ses anciens liens mènent à la bonne fiche. Une actualité peut porter un **suivi optionnel** — Ouvert, Résolu ou Annulé, choisi dès l'ouverture, corrigé en modification, et dont une suite trace l'avancée — que **seul le conseil syndical** active : un repère, sans kanban ni relance ; « Annulé » la range aussitôt aux archives, « Résolu » trente jours après. Une **recherche libre** remplace le filtre par catégorie et cherche **partout** — numéro, titre, description, catégorie, lieu, personnes, prestataire, équipement, **suites, messages et pièces jointes** — sans tenir compte des accents ni des majuscules : chaque carte dit *où* le mot a été trouvé (passage surligné), les Archives s'y ajoutent sur demande, et rien n'est cherché dans ce que le lecteur ne peut pas lire. Les **catégories** de signalement — chacune choisie parce qu'elle change *qui traite*, certaines posées par le **conseil syndical seul** — et celles qu'un résident peut choisir se lisent au chapitre [« Ouvrir une affaire »](docs/manuel-utilisateur.html#affaire) du manuel, qui est confronté au code ; le README ne les recopie plus (#1540). Les dossiers longs du conseil — diagnostic, sondage, devis, chantier — entrent au **kanban** d'Affaires. Pour une catégorie du bâti, le conseil désigne l'**intervenant** et l'**équipement** concerné — et, si l'intervenant a des contrats en cours, s'il agit **sous contrat** (lequel : la fréquence est alors celle du contrat, et seule sa prochaine visite avance à la clôture) ou **hors contrat**. L'**urgence n'est pas une catégorie** mais une case à cocher : une panne peut être urgente, une nuisance aussi. **Qui la lit** se voit sur chaque carte : une **pastille bleue** (« Copropriétaires », « Résidents », « CS »…, un cadenas si le périmètre est réservé) résume la règle d'accès du serveur, et la phrase complète s'ouvre au toucher ; le conseil syndical choisit ses **Destinataires** — présélectionnés selon la catégorie, modifiables à la création, en correction ou depuis une suite, et appliqués par le serveur — ou la rend **confidentielle** (« Résident concerné » sur une affaire). Les droits valent pour l'**affaire entière** : qui la lit en lit toutes les suites, et une suite qui change les destinataires les change pour tout le fil — en l'écrivant dans le fil. Le **conseil syndical** lie une affaire **à d'autres** (section *Affaires liées*, à la création, en correction ou depuis une suite) : chacune s'y reconnaît à son **titre**, le lien vaut dans les deux sens, et une affaire que le lecteur ne peut pas lire n'y apparaît pas. **À la clôture**, le conseil peut **fusionner** les affaires liées encore ouvertes qui portent le même besoin sur le même périmètre : celle qu'il clôt les absorbe — suites, messages, documents et courriels à leur date, chaque description devenue une suite d'ouverture —, elles sont closes en même temps, et la synthèse de clôture les couvre toutes ; une affaire lue par moins de monde ne s'absorbe pas, ses suites fuiraient. Un membre du conseil **transfère à l'adresse des affaires** un fil reçu dans sa messagerie : chaque message cité devient une suite, datée et signée de son auteur, dans l'affaire que désigne son numéro « TK-… » — ou celle d'un transfert précédent du même fil —, sinon dans une **affaire neuve** (Étude & travaux, conseil syndical seul, au nom de l'auteur du premier message) ; un message déjà versé n'est jamais doublé, et un transfert versé par erreur **s'annule, se déplace vers une autre affaire ou en devient une nouvelle**, d'un geste depuis l'affaire **Toute affaire close** — résolue ou annulée, quelle que soit sa catégorie, à la validation d'un point CS / Syndic comme ailleurs — reçoit une demi-heure plus tard sa **synthèse** : une suite 🧾 à **cinq graphiques** (chiffres clés, frise du temps par étape, chronologie, comparaison à la moyenne des affaires de même catégorie sur l'exercice comptable, rythme des suites par semaine) calculés en **jours ouvrés** et figés — plus, **pour le conseil seul**, un bloc *La récidive* quand au moins deux autres affaires résolues ont porté sur le même équipement et le même périmètre en 24 mois —, puis un récit, ses difficultés et une amélioration suggérée, rédigés par l'assistant IA ; en **brouillon** pour le conseil syndical — avisé par courriel avec le gestionnaire du site —, qui la **modifie, la relance avec une consigne, la recommence ou la valide** ; validée, elle est lue de tous ceux qui lisent l'affaire et versée au carnet quand l'affaire en est
- **Calendrier** — n'est plus une page depuis le 23/09/2026 : ce qui porte une date paraît sous le filtre **Calendrier** d'Affaires, le **kanban** est l'onglet **Kanban** d'Affaires (colonnes AG · CS · Syndic · Prestataire · Terminé, et Annulé — masquée à l'accueil seulement ; la table est `front/src/lib/kanban.ts`), et `/calendrier` redirige. Les événements d'hier sont devenus des affaires : une coupure ou une assemblée, une **actualité datée** ; une maintenance, une affaire **🧰 Entretien**, avec son **intervenant** et sa **récurrence** ; des travaux suivis, une **Étude & travaux**. La section **Quand** (début, fin) est planifiée par le conseil syndical seul. Déplacer une carte au kanban inscrit l'avancée au fil de l'affaire, sans prévenir personne
- **Documents** — GED avec catégories et accès par profil (résidents, propriétaires, CS)
- **Carnet d'entretien** — l'histoire du bâti, obligatoire depuis le décret n° 2001-477 : ce qui a été entretenu, réparé et contrôlé, rangé **par équipement** ; la ligne d'une affaire dont la synthèse a été validée se déplie sur elle. C'est une **vue**, pas une saisie — elle se constitue à partir des contrats d'entretien, des entretiens terminés et des affaires résolues du bâti, sans rien ressaisir — chaque intervention y dit si elle a eu lieu *sous contrat n° …* ou *hors contrat*. Chacun n'y voit **que les affaires qu'il peut lire** : le carnet, les affaires et le kanban appliquent la même règle. Onglet de *Résidence*, réservé aux copropriétaires, au conseil syndical et à l'administration ; son filtre par **périmètre** suit l'arborescence administrée. Le conseil syndical y trouve en plus un **bilan de l'exercice** comptable — un argument chiffré pour l'AG : par catégorie, la durée moyenne et le temps par étape du kanban en jours ouvrés, les relances au syndic et son délai de réaction, les intervenants les plus lents — recalculé sur toutes les affaires du carnet closes. L'usage est décrit dans le manuel
- **Mes lots & accès** — une seule page pour ce qu'on possède et ce qui l'ouvre, en quatre onglets : **Mes lots** (appartement, cave, parkings, diagnostics), **Mes badges d'accès (Vigik)**, **Télécommandes de parking** et — pour un copropriétaire bailleur — **Gestion locative** (baux, locataires, inventaire de remise, documents, et leurs archives). On y demande un accès au syndic, ou on y déclare un badge déjà détenu — les deux gestes sont décrits dans le manuel. Un bailleur confie ses accès à son locataire pour la durée du bail, et les récupère à sa sortie ; un locataire dont le propriétaire n'a pas de compte dit lui-même ce qu'il loue — appartement, cave, parking —, d'après le fichier des lots du syndic, et en reçoit les badges
- **FAQ** — Questions fréquentes filtrées par profil utilisateur
- **Communauté** — Boîte à idées, sondages, petites annonces et **avis sur l'application** — **réservée aux résidents**&nbsp;: ni le syndic, ni un mandataire, ni un aidant n'y ont accès, sauf à l'onglet **Avis**, ouvert au syndic et au mandataire. Un **avis** par compte : une note de 1 à 5 étoiles (une remarque est demandée sous 3), un titre, une description et, à partir de 4 étoiles, l'**accord explicite** de l'auteur (Oui ou Non, sans réponse par défaut) pour être lu de tous et paraître sur le site de présentation — sans cet accord, l'avis ne se lit que de son auteur et du conseil syndical ; le gestionnaire du site y répond, retient les avis consentis et les **exporte** en JSON (prénom et initiale du nom, rôle) pour coprofirst.fr. L'**Annuaire** est une page à part, et il ne liste que le conseil syndical et le syndic. Fil de réponses entre voisins (réponses du conseil syndical mises en avant) et notifications au créateur. Un sondage se cible comme une actualité : périmètre pris dans l'arborescence, et destinataires pris dans la liste commune (résidents, copropriétaires, copropriétaires occupants, bailleurs, locataires, conseil syndical). Une **petite annonce** porte elle aussi un périmètre — la résidence entière, un bâtiment, le parking, les caves — et se **corrige** après dépôt (titre, prix, catégorie, description) sans qu'il faille la supprimer et la redéposer, ce qui effaçait les réponses des voisins
- **Prestataires & Contrats** — Gestion des prestataires et contrats d'entretien. La **catégorie** d'un prestataire dit son **métier** (Maintenance & dépannage, Travaux, Réglementaire, Études & expertise, Gestion) ; « **sous contrat** » n'en est plus une — une même entreprise entretient sous contrat et dépanne hors contrat : c'est une pastille **déduite de ses contrats actifs**, et un filtre. L'annuaire se filtre en **deux lignes** — catégorie, puis contrat et une **recherche libre** (nom, catégorie, équipement, coordonnées, contacts, sans accents ni majuscules) qui remplace le filtre par équipement. Avec la **prochaine échéance de visite** de chaque contrat (en retard, à venir, sans échéance) et la **notation** de l'intervenant. La fiche dépliée chiffre, pour le conseil syndical, les **affaires closes** où l'entreprise était l'intervenant désigné : nombre, temps moyen *Chez le prestataire* et durée totale en jours ouvrés, relances, et leur évolution par exercice comptable. Une intervention datée se suit dans **Affaires** (filtre Calendrier, catégorie Entretien), une demande au syndic par un **affaire**. Deux contrats sont **désignés** depuis la fiche de copropriété — l'**assurance** et le **mandat de syndic** — qui y affiche alors l'organisation, les dates, le numéro et le document signé. Le cabinet est un prestataire ; ses **membres** restent dans l'annuaire, d'où partent les e-mails. Une **synthèse de contrat** se propose d'un clic sur ✨ : l'assistant IA lit **tous** les documents joints — l'initial, ses avenants, les conditions générales — et rend un résumé au format du carnet d'entretien, ouvert en correction, jamais enregistré sans relecture, et précédé d'un encart qui dit quel modèle l'a rédigé, quand et sur quels fichiers ; les clauses auxquelles elle renvoie sont **jointes en extraits** en fin de synthèse. Le même assistant **retravaille une description** (affaires, actualités, calendrier, sondages, idées, annonces, commentaires) sur demande du conseil syndical : proposition sous le champ, « Appliquer » ou « Ignorer », et un ✨ discret à côté de l'auteur d'un texte assisté
- **Annonces de hall** — Production d'une **affiche PDF** aux couleurs de la résidence pour les panneaux d'affichage, au **plus petit format qui accueille le texte** (A4 à A7, trait de découpe en dessous de l'A4). Elle se rédige directement ou se **pré-remplit depuis une actualité ou une affaire** (titre, contenu, périmètre, photos) — et **réciproquement** : une actualité se pré-remplit depuis une annonce de hall déjà produite, le conseil composant souvent l'affiche d'abord. Sa **diffusion** se choisit case par case comme partout ailleurs — groupe WhatsApp, syndic, conseil syndical, copie à soi —, toutes décochées d'origine : le conseil syndical du périmètre et le syndic reçoivent le PDF en pièce jointe, le groupe WhatsApp un lien vers l'actualité d'origine. Historique consultable, archivable, avec renvoi possible
- **Reporting CS** — onglet de l'Espace CS. Sa première vue, **Suivi des affaires**, liste les **affaires en cours** (ni résolues, ni annulées, ni archivées, ni entretien périodique), la plus ancienne en tête — âge, date d'ouverture, titre, périmètre, résumé, catégorie —, sous leur **nombre**, celles de plus de 90 jours et deux **répartitions croisées**, par catégorie (découpée par bâtiment) et par bâtiment (découpée par catégorie) ; l'assistant IA rédige sur demande le **résumé de chaque affaire** en une ou deux phrases, tiré de toute sa matière (sans aucun nom), et le rapport s'**exporte en PDF**, rendu par le serveur aux couleurs de la résidence. Son second mode, **Relancer le syndic**, compose la relance groupée sur la même liste : affaires sans avancée cochées d'office, relances déjà envoyées, aperçu du courriel. Pendant une réunion avec le syndic, un **point CS / Syndic** s'y ouvre — quand, où, présents du conseil et du syndic, invités — pour prendre le **compte rendu en direct**, affaire par affaire (brouillon automatique, « CS et présents », **état à la validation** — « Chez le syndic » d'office, « À l'AG » gardé —, l'affaire suivante dépliée en haut de l'écran après chaque enregistrement), sur une liste figée à l'ouverture et avec l'**état de suivi** et **qui la lit** de chaque affaire — avec, au Suivi affaires, une affaire **« Points annexes CS & Syndic »** créée d'office et la possibilité d'**ouvrir une affaire en séance** —, lu au fur et à mesure en compte rendu global : le point, les affaires abordées, les non traitées ; le **PDF du point** à tout instant (« Exporter en PDF ») ; terminé, il part aux présents pour **validation** (lien personnel, « Je valide » ou commentaire, validation d'office à 7 jours, **révisions** « Modifié en révision N », **dérogation** de l'administrateur pour un présent qui a donné son accord) ; validé, il pose l'état décidé de chaque affaire, son **PDF** — le point et ses validations, les répartitions en couleur, chaque affaire abordée avec son résumé et son compte rendu — est rangé et **envoyé aux présents, tout le conseil en copie**, rejoint chaque affaire abordée, s'annonce une fois au fil du conseil et du syndic, et se retrouve dans l'**historique des comptes rendus**. Les **affaires liées** s'y rassemblent dans le tri et se **fusionnent** d'un geste — l'assistant propose le titre et la description, la plus ancienne absorbe les autres et reste ouverte, la fusion est citée au point — ou s'écartent (« Ne pas fusionner », plus proposé à la clôture). Un troisième mode, **Suivi entretiens périodiques**, montre le bilan des visites de l'année et les entretiens non clos. Les autres vues : prestataires, renouvellements
- **Courriels affaires** — onglet de l'Espace CS : chaque message reçu à l'adresse des affaires (réponses du syndic, fils transférés par le conseil), une **pliure par message** avec son verdict — ajouté au fil, transmis au conseil, refusé, ignoré — et **pourquoi**, jamais le texte (90 jours). Un transfert refusé pour un numéro d'affaire mal tapé propose le bon. Le conseil lit le nom de l'expéditeur, l'administrateur son adresse ; le nombre de lignes (20 par défaut) est un paramètre de Paramétrage › SMTP
- **Questions au règlement** — onglet de Ma résidence : le conseil syndical — et les **copropriétaires**, quand l'administration le leur ouvre (jamais les locataires, mandataires ni le syndic) — pose une question (« ai-je le droit de… ? ») et l'assistant IA répond **en juriste**, d'après les fichiers **Markdown** du règlement que **l'administration seule** joint sur la même page, par les pièces jointes standard, et que l'assistant lit bout à bout (versionnés, jamais publiés ni versés au dépôt) — verdict, réponse argumentée, **extraits cités mot pour mot**, réserves. Les autres lisent un lien vers le règlement publié dans la Fiche. Chaque extrait est **recherché dans le texte par le site** : retrouvé, il porte son acte et sa page, lus dans la transcription ; sinon il est signalé ⚠️. Les questions restent dans un historique — chacun n'y lit que les siennes, le conseil toutes ; l'administration peut l'élaguer —, et une réponse **relue** peut rejoindre la FAQ, sans auteur, par le conseil. Avis indicatif, qui ne se substitue pas aux actes authentiques
- **Administration** — rangée **par niveau en six groupes** (Personnes, Imports, Copropriété, Services, Présentation, Exploitation), les onglets du groupe choisi en seconde rangée ; **Pages légales** paramétrées par l'identité de la copropriété (syndicat responsable, syndic, opérateur sous-traitant, hébergeur), avec un constat **« à relire »** mesuré texte par texte et le geste qui le lève ; **Services de la copropriété** sur un seul écran (assistant IA, diffusion WhatsApp, réponses par courriel : état, ce qu'on perd en coupant, interrupteur ; l'envoi des courriels y figure sans interrupteur, il porte ceux de sécurité), paramétrage du site (le **nom de la résidence**, repris par la connexion, le menu, les courriels et l'application installée, et son **logo** — PNG ou JPEG téléversé, qui remplace partout le logo neutre de CoproFirst : menu, onglet, application installée, documents imprimables, courriels), comptes (dont la **purge automatique des comptes inactifs** : deux ans sans connexion, un avertissement par courriel, la suppression trente jours plus tard — jamais un compte d'administration), SMTP (envoi, relève des réponses par courriel et nombre de messages affichés dans l'onglet **Courriels** de l'Espace CS), WhatsApp, **assistant IA** (un bloc commun — fournisseur, clé, adresse, délai — et un bloc par usage — modèle, effort de raisonnement, prompt modifiable, plafond, activation, test — : synthèse de contrat, rédaction d'une description, **mise en forme automatique des réponses du syndic reçues par courriel**, le texte reçu restant consultable, **synthèse automatique d'une affaire close**, livrée désactivée, **question au règlement de copropriété**, livrée désactivée et fermée aux copropriétaires — une case l'ouvre, et **synthèse des affaires en cours** du Reporting CS, **fusion d'affaires liées** (titre et description proposés) ; la clé n'est jamais renvoyée par l'API). Chaque usage a ses **limites d'appels** — par mois, et par heure et par personne ; atteintes, l'appel est refusé avant l'envoi —, le coût de son **premier essai** avec le modèle et l'effort enregistrés, qui en chiffre l'estimation du mois, et son **tarif**, qui chiffre la consommation — trois prix en dollars — envoyés, produits, lus en cache —, qu'un ✨ à côté du modèle cherche dans la grille publiée par le fournisseur (usage *Tarif d'un modèle*) et enregistre
- **Périmètres** — arborescence de la copropriété (bâtiments et leurs espaces, parking, AFUL, espaces verts, cheminements, locaux techniques) servant à localiser affaires, actualités, **sondages** et annonces. Sa **pastille prend la couleur de son bâtiment** : « Ascenseur » du bâtiment 1 porte la teinte du bâtiment 1, partout où elle s'affiche — on lit *où ça se passe* sans lire le libellé. Sur une affaire, il n'est pas figé à l'ouverture : une entrée du fil de suivi peut le **préciser** à mesure qu'on cherche, et l'historique garde la trace du resserrement. Entièrement éditable depuis l'administration, sans déploiement. Le périmètre dit *de quoi* il s'agit, pas *qui peut lire* — sauf sur une actualité **🔒 Réservée au périmètre sélectionné**, où il redevient restrictif (lecture réservée au périmètre visé, affiche de hall alors impossible) — et sur une affaire suivie, qui l'est d'office
- **WhatsApp** — Notifications automatiques programmées vers le groupe de la résidence. ⚠️ Le pont passe par un client non officiel (Baileys) : WhatsApp peut déconnecter ou **bloquer le numéro** appairé ; le contrôle quotidien distingue ce cas d'une coupure ordinaire, et le courriel reste le canal de repli (conduite à tenir : `.claude/skills/infra-rpi`)
- **Maintenance** — Le **rôle de l'installation** en tête (*Référence*, qui suit `main` ; *Réplique*,
  qui suit `replica` ; *Inconnu* s'il n'est pas déclaré), avec sa version et, si le service
  *Vérification de la version* est activé, son écart à la branche suivie. Dessous, l'**inscription au registre** de la référence (contact de l'administrateur, conditions acceptées, bail signé renouvelé chaque nuit, rapport nocturne fait de nombres seulement ; l'état — limitée, active, suspendue — n'est encore que constaté, **sauf les services** : une réplique n'allume que ceux que la référence lui accorde). L'**export vérifié** de la base (format neutre, empreinte
  par table, réimporté dans une base jetable pour prouver qu'elle se restaure ; archive
  complète dans le volume des sauvegardes). Tâches automatiques (purge tokens, archivage, logs, **images de base des
  conteneurs re-tirées chaque semaine**) + déclenchement manuel ; les **contrôles de fiabilité**
  des deux nœuds (dont les **mises à jour système**) avec leurs constats en cours — chacun
  une fois, sous le nœud qu'il concerne — et l'heure du dernier contrôle ; la
  **consommation de l'assistant IA** (jetons, appels, coût estimé, jauge des plafonds) ;
  et le **contrôle de santé quotidien** (base, WhatsApp, sauvegardes, copie hors site, disque,
  modèles d'e-mail, **tâches planifiées manquantes ou en échec**, archives d'affaires non copiées) relançable à la demande depuis
  l'écran ; la **conservation des affaires** : à l'échéance (2, 5 ou 10 exercices selon la
  catégorie), et seulement si le service est activé, une affaire close perd ses pièces jointes —
  archivées, sommaire sans nom, copiées sur le PC par la sauvegarde hors site puis retirées du
  serveur — et ses auteurs, et garde son texte ; cocher le service ajoute à la politique de confidentialité la phrase qui l'annonce (`specs/architecture/conservation-affaires.md`)
- **Installations** — sur la **référence** seulement, pour l'**opérateur** : le **registre des installations** CoproFirst inscrites. Une carte par installation (état, version, contrat accepté, services accordés, **alertes** — muette, mise à jour revenue en arrière, sauvegarde, disque, certificat, retard de version, clone, deux références ; les trois graves partent aussi par courriel à l'opérateur), et, dépliée, les **décisions** — valider, suspendre, rétablir, résilier, chacune motivée et inscrite au **journal** —, les **services accordés**, le contact de l'administrateur d'installation, le dernier rapport nocturne et le **contrat accepté**, archivé sous l'identifiant. Le **canal** suivi, la **vague** de déploiement (pilote, générale, tardive) et l'**épinglage** — retour à une version compris — fixent la **version cible** du bail, la seule que la mise à jour nocturne d'une réplique installe ; sans bail valide, aucune mise à jour automatique. Une décision part dans le bail au prochain renouvellement : la référence ne pousse jamais
- **Liens partageables** — Chaque onglet et sous-onglet a son **adresse propre** (`/annonces`, `/idees`, `/tickets/kanban`, `/mon-lot/location/archives`…) : l'adresse du navigateur suit ce qu'on regarde, elle se copie et s'envoie. Chaque publication porte une icône 🔗 qui copie **son** lien — annonce, actualité, affaire, idée, sondage, question de FAQ, document, rapport de diagnostic, contrat, prestataire. Le lien n'ouvre aucun droit : le destinataire doit être connecté et ne voit que ce qui le concerne. Les anciennes adresses (`?onglet=…`) restent servies, en redirection permanente
- **Installation commune** — une même installation peut servir **plusieurs copropriétés**, chacune dans sa base, déclarées dans un fichier (`COPROPRIETES_FICHIER`). Chacune est jointe par son domaine propre ou par une **adresse dérivée** de son code postal et de son nom (`75015-les-tilleuls.<hôte commun>`) ; l'hôte commun ne sert aucune donnée : son écran de connexion **aiguille** — code postal + nom, correspondance exacte, sans liste, tentatives limitées — puis redirige, et un ancien alias renvoie à l'adresse actuelle. Livré en deux lots, complet depuis la v2.179.0 et stable en v3.0.0 : le second (#2053) prépare chaque base au démarrage, sert les fichiers de chaque copropriété par l'API et outille la création d'une copropriété — [`deploiement/standard/commune/LISEZMOI.md`](deploiement/standard/commune/LISEZMOI.md). Une installation propre à une copropriété, comme 5Hostachy, n'en voit rien
- **Démonstration publique** — une installation lancée avec `MODE_DEMO=oui` montre le site sur une résidence **fictive** : on s'y connecte par le formulaire, sous l'un de **trois comptes publiés** (copropriétaire membre du conseil, copropriétaire, locataire) partagés entre les visiteurs, sans en créer, un bandeau le dit sur chaque écran, **rien ne part** (ni courriel, ni WhatsApp, ni appel à l'IA — l'historique note ce qui serait parti), les réglages qui feraient sortir quelque chose se lisent sans s'enregistrer, les pages ne s'indexent pas, et la base repart de son jeu de données chaque nuit (`deploiement/demo/`). Spécification : `specs/architecture/mode-demo.md`

## Manuel utilisateur

Le **manuel utilisateur** décrit chaque écran : ce qu'il contient, les gestes
qu'il permet et qui peut le voir — [docs/manuel-utilisateur.html](docs/manuel-utilisateur.html).
L'application le sert aussi elle-même, à l'adresse `/manuel-utilisateur.html`.

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) · SQLModel · PostgreSQL 17, répliqué en continu vers le second nœud · Alembic |
| Frontend | [SvelteKit](https://kit.svelte.dev/) · TypeScript · Vite · PWA (installable ; écrans précachés, contenus toujours en ligne) |
| Reverse proxy | [Caddy](https://caddyserver.com/) |
| Messaging | WhatsApp Bridge (Baileys) |
| Déploiement | Docker Compose · Raspberry Pi 5 |
| Tests | pytest (API) · [Playwright](https://playwright.dev/) (navigateur, bureau et mobile) · des contrôles `lint:*` sur la source (la liste : `front/package.json`) |
| CDN / Tunnel | Cloudflare Tunnel + Worker (maintenance page) |

```
coprofirst/
├── api/               # Backend FastAPI
│   ├── app/           # Code applicatif (routers, models, utils)
│   └── alembic/       # Migrations de base de données
├── front/             # Frontend SvelteKit
│   ├── src/routes/    # Pages de l'application
│   └── e2e/           # Tests de navigateur (Playwright)
├── whatsapp-bridge/   # Bridge WhatsApp (Node.js)
├── scripts/           # Tous les scripts
│   ├── exploitation/  # Lancés par cron/systemd sur les RPi (bascule, failover…)
│   ├── lib/           # Modules sourcés par les précédents
│   ├── poste/         # Développeur et CI (pré-check, rejeu CI, export hors site)
│   └── installation/  # Durcissement système et sudo, tunnel — la réinstallation
│                      # d'un nœud se suit pas à pas (docs/restauration-complete.md)
├── infra/             # Code déployé ailleurs (worker Cloudflare)
├── specs/             # Spécification d'origine — historique, le manuel fait foi
├── docs/              # Documentation déploiement & ops
├── boot-role-guard.sh # RELAIS PERMANENT vers scripts/exploitation/ : l'unité
│                      #   systemd désigne CE chemin absolu, et rien dans un
│                      #   déploiement ne la met à jour. Il reste donc.
└── docker-compose.yml
```

## Démarrage rapide

### Prérequis

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose v2+
- Git

### Installation

```bash
git clone https://github.com/philippe-tressard/coprofirst.git
cd coprofirst

# Configurer l'environnement
cp .env.example .env
# Éditer .env : SECRET_KEY (min 32 chars), WHATSAPP_API_KEY (min 16 chars) et ORIGIN.
# WHATSAPP_API_KEY est OBLIGATOIRE — sans elle, docker compose refuse de démarrer.

# Lancer
docker compose up --build -d
```

L'application est accessible sur `http://localhost`.

> 📦 **Images publiées.** Chaque version reçoit un tag `vX.Y.Z` et des images
> signées (amd64 et arm64) : `ghcr.io/philippe-tressard/coprofirst-api`, `-front`,
> `-caddy` et `-whatsapp-bridge`, étiquetées par version (et chaque commit de `main`
> par `sha-<commit>`). Vérifier une image :
> `gh attestation verify oci://ghcr.io/philippe-tressard/coprofirst-api:<version> --owner philippe-tressard`.
> Les versions choisies pour les autres installations sont **promues** sur la branche
> `replica`, avec leurs notes de version (onglet *Releases*) : après 7 jours sur la
> référence, ou sans attendre pour un correctif urgent.
> **Installer sans construire** : [`deploiement/standard/LISEZMOI.md`](deploiement/standard/LISEZMOI.md)
> — chaque version promue joint son archive de déploiement à ses notes de version.

Au premier lancement, deux comptes sont créés avec un **mot de passe aléatoire** affiché dans les logs : l'**administrateur** de la copropriété (`admin@localhost`) et l'**opérateur** de l'installation (`operateur@localhost`, administrateur aussi — supervision, santé, inscription au registre). Séparés pour confier le premier sans livrer le second.

```bash
docker compose logs api | grep -A5 "ADMIN INITIAL"
```

> **Changez immédiatement les mots de passe** après la première connexion.

### Développement local (sans Docker)

```bash
# Backend
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (autre terminal)
cd front && npm install && npm run dev

# Tests de navigateur (le serveur de dev démarre tout seul)
cd front && npx playwright install chromium && npm run e2e
```

> Les tests Playwright rendent les écrans **publics en vrai** et les écrans
> **authentifiés sur une API simulée** : ils éprouvent le comportement de
> l'interface (clavier, responsivité, rendu), pas le serveur — droits, filtres et
> forme réelle des réponses restent l'affaire de `api/tests/`.
> `front/e2e/README.md` dit ce que l'API simulée prouve, et ce qu'elle ne prouve pas.

## Configuration

Toute la configuration se fait via le fichier `.env` (voir [.env.example](.env.example)). Le tableau ci-dessous n'en retient que l'essentiel : le gabarit fait foi, et `api/tests/test_env_exemple_coherent.py` vérifie en CI qu'il démarre la stack et que chacune de ses clés est lue par quelqu'un.

| Variable | Description | Défaut |
|---|---|---|
| `SECRET_KEY` | Clé JWT — **obligatoire**, min 32 caractères | *(rejeté si non défini)* |
| `ORIGIN` | URL complète du site | `https://example.com` |
| `COOKIE_SECURE` | `true` en prod HTTPS, `false` en dev HTTP | `true` |
| `MAIL_ENABLED` | Activer les notifications email | `false` |
| `WHATSAPP_API_KEY` | Clé du bridge WhatsApp — **obligatoire**, min 16 caractères ; lue par l'API et par le bridge, seule source | *(refusée si absente, d'exemple ou trop courte)* |
| `ENABLE_API_DOCS` | Exposer `/docs` et `/redoc` | `false` |

## Documentation

| Document | Description |
|---|---|
| [specs/](specs/) | Spécification **d'origine**, fonctionnelle et technique — **historique** : le site a évolué depuis (écrans fusionnés ou retirés), le **manuel utilisateur** ci-dessous fait foi |
| [docs/deploy-rpi5-auto.md](docs/deploy-rpi5-auto.md) | Renvois : où se lit le déploiement automatique (`auto-deploy.sh`, `infra/points-entree/`) — plus une procédure |
| [docs/restauration-complete.md](docs/restauration-complete.md) | Réinstaller un nœud de zéro (il rejoint la paire comme standby) ; les deux perdus, la résidence renaît de la copie hors site |
| [docs/redondance-rpi5.md](docs/redondance-rpi5.md) | Architecture de redondance : réplique PostgreSQL en continu, bascule, failover |
| [docs/cloudflare-worker-maintenance.md](docs/cloudflare-worker-maintenance.md) | Page de maintenance Cloudflare |
| [docs/icones-menu.md](docs/icones-menu.md) | Renvois : où se lisent les icônes du menu (`pages.ts`, `pages-roles.ts`) — plus un inventaire |
| [docs/manuel-utilisateur.html](docs/manuel-utilisateur.html) | **Manuel utilisateur** — ce que chaque écran contient et qui peut le voir |
| [docs/contrat-sous-traitance-modele.md](docs/contrat-sous-traitance-modele.md) | **Contrat de sous-traitance** (RGPD art. 28) entre un syndicat de copropriétaires et l'opérateur de l'installation qui le sert — modèle, projet à faire relire (#2065) |
| [api/app/registre/conditions/v1.md](api/app/registre/conditions/v1.md) | **Conditions d'inscription** d'une installation au registre de la référence — un contrat d'engagements réciproques, archivé pour chaque installation ; projet à faire relire (#1876) |
| [deploiement/standard/commune/LISEZMOI.md](deploiement/standard/commune/LISEZMOI.md) | **Installation commune** à plusieurs copropriétés : adresses dérivées, aiguillage, déclaration des copropriétés, nom de domaine générique |
| [docs/licences-tierces.md](docs/licences-tierces.md) | Inventaire **généré** des licences tierces — dépendances, exceptions déclarées, fichiers repris (vérifié en CI) |
| [docs/carte-reglages.md](docs/carte-reglages.md) | Carte **générée** des réglages — qui règle quoi (administrateur, conseil syndical, opérateur, exploitant du serveur), où, et où la valeur vit ; l'accès de chaque notion est confronté à la route en CI (#2061) |

## Sécurité

- JWT avec cookies HttpOnly / Secure / SameSite=strict
- Hachage bcrypt des mots de passe
- **Autorisation centralisée** — toutes les règles dans `api/app/auth/deps.py`, chaque endpoint en dépend, les rares exceptions publiques sont énumérées et justifiées (vérifié en CI)
- **Exposition publique en liste blanche** — ce qui est lisible sans authentification est énuméré, jamais déduit par exclusion
- Rate limiting sur les endpoints d'authentification (slowapi)
- Validation Pydantic / SQLModel sur toutes les entrées
- En-têtes de sécurité — HSTS, `X-Frame-Options`, `X-Content-Type-Options` et `Referrer-Policy` servis par **Caddy**&nbsp;; la **politique de sécurité du contenu** (CSP) est émise par **SvelteKit** (`svelte.config.js`), qui seul connaît le condensat de ses scripts en ligne
- Sanitisation HTML côté client (DOMPurify)
- Protection path traversal sur les uploads
- **Vulnérabilités des dépendances vérifiées en CI, des DEUX côtés** — `npm audit` sur tout l'arbre (`devDependencies` comprises : elles servent le site) et `pip-audit` sur `api/requirements.txt`. Même mécanique de part et d'autre : exceptions **nominatives**, chacune avec son motif d'atteignabilité, sa condition de levée et sa date de revue — et une exception devenue inutile fait **échouer** le contrôle, pour forcer son retrait (`front/audit-exceptions.json`, `api/audit-exceptions.json`)
- **Le lock ne ment pas sur ses versions** — vérifié en CI : `npm audit` lit le champ `version` du lock, donc une version fausse le rend aveugle sans rien dire

Voir [SECURITY.md](SECURITY.md) pour la politique de signalement de vulnérabilités.

## Contribuer

Les contributions sont les bienvenues ! Voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

**[AGPL-3.0-or-later](LICENSE)** — GNU Affero General Public License, version 3
ou ultérieure. © Philippe TRESSARD, 2024-2026.

CoproFirst est un **logiciel libre** : chacun peut l'utiliser, l'étudier, le
modifier et le redistribuer, y compris à titre commercial — à condition de
publier ses modifications sous la même licence, **y compris** quand il le fait
fonctionner comme service en ligne (AGPL §13). Aucune condition additionnelle.

Les versions publiées jusqu'à la 2.115.0 restent sous leur licence d'origine ;
l'historique du changement et les mentions de copyright sont dans
[`NOTICE.md`](NOTICE.md). La licence ne cède aucun droit sur les noms, et le logo
n'est pas sous l'AGPL ([sa licence](LICENSES/LicenseRef-CoproFirst-Logo.txt)) :
leur usage suit [`MARQUE.md`](MARQUE.md) — CoproFirst est une demande de marque
déposée à l'INPI (n° 5307183, 09/10/2026).

Les composants tiers gardent leur propre licence : [`NOTICE.md`](NOTICE.md) §6
les nomme, dont `libsignal` (GPL-3.0) dans le service de messagerie — tous
compatibles avec l'AGPL-3.0-or-later, analyse validée par l'auteur.
