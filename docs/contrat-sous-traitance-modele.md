# Contrat de sous-traitance — modèle (RGPD, article 28)

> ⚠️ **PROJET, À FAIRE RELIRE.** Ce modèle n'est pas un avis juridique. Il a été
> rédigé pour qu'une installation CoproFirst qui sert plusieurs syndicats de
> copropriétaires dispose d'une base de discussion, et il doit être relu par un
> juriste avant toute signature (#2065). Les passages entre crochets `[…]` se
> complètent ; les notes « **À vérifier** » signalent un point que la rédaction
> n'a pas pu trancher seule.

**Pourquoi ce contrat.** Dès qu'une installation sert un syndicat de
copropriétaires, ce syndicat est **responsable du traitement** des données de sa
copropriété, et l'exploitant de l'installation — l'**opérateur** — traite ces
données pour son compte : il est son **sous-traitant**. L'article 28 du règlement
(UE) 2016/679 (RGPD) impose qu'un contrat écrit les lie, et en fixe le contenu
minimal (art. 28.3). Les textes légaux publiés par chaque copropriété y renvoient
(`[[operateur]]`, politique de confidentialité, point 1).

---

## Entre les soussignés

**Le syndicat des copropriétaires de la résidence [nom de la résidence]**, dont
l'immeuble est situé [adresse], immatriculé au registre national des copropriétés
sous le numéro [numéro], représenté par son syndic, [nom du syndic], [adresse du
syndic], dûment habilité à cet effet,

ci-après « **le responsable du traitement** » ;

> **À vérifier** : l'habilitation du syndic à conclure ce contrat — acte
> d'administration courante, ou décision de l'assemblée générale (loi n° 65-557 du
> 10 juillet 1965, art. 18, 24 et 25), notamment s'il est conclu à titre onéreux.

**Et [nom ou raison sociale de l'opérateur]**, [forme juridique, numéro
d'immatriculation le cas échéant], dont le siège ou l'adresse est [adresse],
joignable à [adresse de contact],

ci-après « **le sous-traitant** ».

---

## Article 1 — Objet

Le présent contrat fixe les conditions dans lesquelles le sous-traitant traite,
pour le compte du responsable du traitement, les données à caractère personnel
nécessaires au fonctionnement de l'application de la copropriété, servie par le
logiciel libre CoproFirst (AGPL-3.0-or-later) sur l'installation qu'il exploite.

Il complète le service convenu entre les parties [référence de la convention de
service, ou « à titre gratuit »] ; en cas de contradiction sur la protection des
données, le présent contrat prévaut.

## Article 2 — Description du traitement

Le traitement confié est décrit en **annexe 1** : nature des opérations,
finalités, catégories de données et de personnes concernées, durée.

Le sous-traitant ne traite les données que pour ces finalités.

## Article 3 — Obligations du sous-traitant

Le sous-traitant s'engage à :

1. **Instructions documentées** — ne traiter les données que sur instruction
   documentée du responsable du traitement (art. 28.3.a), y compris pour un
   transfert hors de l'Union européenne. Le paramétrage de l'application par
   l'administrateur de la copropriété — services activés, textes publiés, comptes
   validés — vaut instruction. Si une instruction lui paraît contraire au RGPD, il
   en informe immédiatement le responsable du traitement.
2. **Confidentialité** — veiller à ce que les personnes autorisées à traiter les
   données s'engagent à la confidentialité ou soient soumises à une obligation
   légale de confidentialité (art. 28.3.b).
3. **Sécurité** — mettre en œuvre les mesures techniques et organisationnelles de
   l'article 32, décrites en **annexe 2**, et les tenir à jour.
4. **Accès limité** — n'accéder au contenu des données que lorsqu'une opération du
   service l'exige : sauvegarde, restauration, mise à jour, diagnostic d'un
   incident, ou demande du responsable du traitement. La supervision technique de
   l'installation ne lit aucune donnée de résident.
5. **Sous-traitance ultérieure** — ne recourir à un autre sous-traitant qu'avec
   l'autorisation écrite du responsable du traitement (art. 28.2). Celui-ci
   autorise par le présent contrat ceux listés en **annexe 3**. Le sous-traitant
   l'informe de tout ajout ou remplacement envisagé au moins [trente] jours à
   l'avance ; le responsable du traitement peut s'y opposer, et à défaut d'accord,
   résilier sans frais. Il impose au sous-traitant ultérieur les mêmes obligations
   (art. 28.4).
6. **Droits des personnes** — aider le responsable du traitement à répondre aux
   demandes d'exercice des droits (accès, rectification, effacement, limitation,
   portabilité, opposition — art. 15 à 22), et lui transmettre sans délai toute
   demande qui lui parviendrait directement, sans y répondre lui-même (art. 28.3.e).
7. **Violation de données** — notifier au responsable du traitement toute violation
   de données à caractère personnel dans les meilleurs délais et au plus tard
   [48 heures] après en avoir pris connaissance, avec les informations de l'article
   33.3 dont il dispose, pour permettre au responsable de notifier la CNIL dans les
   72 heures (art. 33) et, le cas échéant, les personnes (art. 34).

   > **À vérifier** : le délai contractuel (le RGPD dit « dans les meilleurs
   > délais » pour le sous-traitant, art. 33.2).

8. **Assistance** — aider le responsable du traitement à garantir le respect des
   articles 32 à 36 : sécurité, violation, analyse d'impact et consultation
   préalable, compte tenu de la nature du traitement (art. 28.3.f).
9. **Fin du contrat** — au choix du responsable du traitement, lui **restituer**
   les données puis les **supprimer**, y compris des sauvegardes au terme de leur
   rotation, au plus tard [trois] mois après la fin du contrat, sauf obligation
   légale de conservation (art. 28.3.g). La restitution se fait par l'**export
   vérifié** de la copropriété (Administration › Maintenance › Export vérifié :
   une archive au format ouvert, une table par fichier avec son empreinte, et les
   fichiers déposés), dont l'importabilité est prouvée dans une base jetable.
10. **Information et audit** — mettre à la disposition du responsable du traitement
    les informations nécessaires pour démontrer le respect du présent article, et
    permettre des audits, y compris des inspections, menés par lui ou par un
    auditeur qu'il mandate, avec un préavis de [trente] jours (art. 28.3.h). Le
    code source du logiciel étant public, l'audit porte sur l'exploitation.
11. **Registre** — tenir le registre des catégories d'activités de traitement
    effectuées pour le compte du responsable du traitement (art. 30.2).

## Article 4 — Obligations du responsable du traitement

Le responsable du traitement :

1. définit les finalités et les moyens essentiels du traitement, et documente ses
   instructions ;
2. informe les personnes concernées — notamment par les mentions légales et la
   politique de confidentialité de l'application, qu'il relit et valide à la mise
   en service (Administration › Pages légales) ;
3. tient son propre registre des activités de traitement (art. 30.1) ;
4. répond aux demandes d'exercice des droits, avec l'aide du sous-traitant ;
5. décide seul des **services tiers** de l'application qu'il active — diffusion sur
   une messagerie instantanée, assistant de rédaction, envoi et réception des
   courriels — et de leurs fournisseurs, lorsqu'il les configure lui-même.

   > **À vérifier** : la qualification de ces fournisseurs. Configurés par la
   > copropriété avec ses propres comptes, ils paraissent être ses sous-traitants
   > directs, et non des sous-traitants ultérieurs de l'opérateur ; fournis par
   > l'opérateur, ils relèvent de l'annexe 3.

## Article 5 — Localisation des données et transferts

Les données sont hébergées dans l'Union européenne, chez l'hébergeur de l'annexe 3.
Aucun transfert hors de l'Union européenne n'a lieu sans l'accord écrit préalable
du responsable du traitement et l'une des garanties du chapitre V du RGPD.

Un intermédiaire technique qui relaie les connexions (nom de domaine, réseau de
diffusion) est nommé en annexe 3, avec le pays d'où il opère.

## Article 6 — Durée, résiliation

Le présent contrat prend effet à sa signature et dure autant que le service. Il
prend fin avec lui, ou par résiliation de l'une des parties moyennant un préavis
de [trois] mois, sans préjudice de l'article 3.9 — la restitution et la
suppression des données —, qui survit à la fin du contrat.

## Article 7 — Responsabilité

Chaque partie répond des manquements qui lui sont imputables, dans les conditions
de l'article 82 du RGPD. [Plafond ou exclusion éventuels — **à vérifier**.]

## Article 8 — Droit applicable

Le présent contrat est soumis au droit français. [Juridiction compétente.]

Fait à [lieu], le [date], en deux exemplaires.

| Pour le responsable du traitement | Pour le sous-traitant |
|---|---|
| [nom du syndic], syndic | [nom], [qualité] |

---

## Annexe 1 — Description du traitement

| Rubrique | Contenu |
|---|---|
| Nature des opérations | hébergement de l'application et de sa base, sauvegarde et restauration, mise à jour du logiciel, supervision technique, diagnostic d'incident, restitution et suppression en fin de contrat |
| Finalités | faire fonctionner l'application de la copropriété : gestion des affaires et de l'entretien, communication entre résidents, conseil syndical et syndic, documents de la copropriété, accès et badges, telles que décrites dans la politique de confidentialité de la copropriété |
| Catégories de personnes | copropriétaires (occupants et bailleurs), locataires et occupants, membres du conseil syndical, membres du syndic, aidants et mandataires, prestataires et leurs contacts, auteurs de courriels reçus par l'application |
| Catégories de données | identité et coordonnées ; lots, bâtiments, tantièmes ; badges et télécommandes rattachés aux lots ; contenus déposés (affaires, messages, documents, photos sans métadonnées de prise de vue) ; données de connexion et journal de sécurité (identifiant de compte, sans adresse) ; mesure d'audience interne, refusable |
| Données sensibles | aucune n'est collectée à dessein. Un contenu libre déposé par un résident peut en contenir : le responsable du traitement en fixe la règle d'usage |
| Durée | celle du contrat ; les durées de conservation de chaque donnée sont celles de la politique de confidentialité de la copropriété |

## Annexe 2 — Mesures de sécurité (art. 32)

Mesures portées par le logiciel, vérifiables dans son code source public :

- **Cloisonnement par copropriété** : une base de données et un secret de
  signature propres à chaque copropriété ; une requête est rattachée à sa
  copropriété dès son entrée, par le nom d'hôte, et un essai automatique vérifie
  qu'aucune réponse servie pour l'une ne porte les données d'une autre.
- **Authentification** : mots de passe hachés (bcrypt) ; session en cookies
  `HttpOnly`, `Secure`, `SameSite=Strict` ; jetons de session et liens à usage
  unique stockés par leur seule empreinte ; limitation du nombre de tentatives ;
  sessions fermées au changement de mot de passe.
- **Droits** : chaque route de l'application vérifie le rôle et l'appartenance
  (lot, auteur) ; la supervision de l'opérateur n'expose aucune donnée de résident.
- **Fichiers** : types et tailles contrôlés au dépôt, signature du fichier
  vérifiée, métadonnées de prise de vue retirées des photos.
- **Journaux** : journal de sécurité des gestes sensibles, sans adresse, mot de
  passe ni jeton.
- **Sauvegarde** : sauvegarde vérifiée avant chaque mise à jour, retour arrière
  automatique si l'application ne répond plus ; export vérifié par réimport.

Mesures propres à l'exploitation, **à compléter par l'opérateur** :

- chiffrement des connexions (TLS) : [certificat, fournisseur] ;
- fréquence des sauvegardes, durée de leur rotation, copie hors de la machine :
  [à compléter] ;
- accès d'administration au serveur : [clés, personnes autorisées] ;
- mises à jour du système : [politique] ;
- procédure en cas de violation : [contact, délai].

## Annexe 3 — Sous-traitants ultérieurs autorisés

| Sous-traitant | Prestation | Pays des données |
|---|---|---|
| [hébergeur] | hébergement du serveur et de ses disques | [pays] |
| [intermédiaire technique, le cas échéant] | nom de domaine, acheminement des connexions | [pays, garanties du chapitre V s'il opère hors UE] |
| [service d'envoi de courriels, s'il est fourni par l'opérateur] | acheminement des notifications | [pays] |

## Annexe 4 — Contacts

| Rôle | Responsable du traitement | Sous-traitant |
|---|---|---|
| Contact pour les données personnelles | [adresse publiée dans les textes légaux] | [adresse] |
| Notification d'une violation | [adresse, téléphone] | [adresse, téléphone] |
