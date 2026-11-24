# ux-patterns — L'ordre des sections, les sections communes, la soumission (§9 sexies à §9 quinquies)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

### 9 sexies. L'ORDRE des champs est imposé — il ne se discute pas par écran

| # | Section | Qui l'écrit |
|---|---|---|
| 1 | **Titre** | l'écran |
| 2 | **Champs spécifiques** à la page | l'écran |
| 3 | **Options de publication** — si l'objet en a | `ChampsCommuns` |
| 4 | **Workflow** — si l'objet en a un | `ChampsCommuns` (contenu par `slot`) |
| 5 | **Périmètre** | `ChampsCommuns` |
| 6 | **Destinataires** | `ChampsCommuns` |
| 7 | **Description** | `ChampsCommuns` |
| 8 | **Photos** | `ChampsCommuns` |
| 9 | **Documents** | `ChampsCommuns` |
| 10 | **Diffusion** | `ChampsCommuns` |

> ⚠️ **Périmé** : cette table date d'avant le 21/09/2026 (#1095 a scindé, ajouté et
> déplacé des sections). L'ordre se lit dans `SECTIONS_ORDRE`, et nulle part ici —
> arbitrage n° 53.

🔴 **Révisé le 12/09/2026, et surtout CONTRÔLÉ depuis.** « Options de
publication » n'avait aucun rang : chaque écran la posait où il voulait, et
l'utilisateur a vu la divergence — entre Actualité et Tickets d'une part, et
dans le calendrier d'autre part, où « Épingler dans le fil » vivait carrément
dans la **Diffusion**, avec son propre glyphe, alors que
`#lib/options-publication` porte la notion.

⚠️ **Les deux écarts avaient la même cause** : cette table existait et rien ne
la faisait respecter. Elle est désormais tenue par deux mécanismes, pas par la
bonne volonté :

* `ChampsCommuns` rend les sections **3 à 10** — l'écran ne décide plus de leur
  rang, seulement de leur PRÉSENCE (`avecOptions`, `avecWorkflow`…) ;
* 🔒 `npm run lint:ordre-sections` refuse une section de rang inférieur écrite
  après une supérieure, dans **tout** `.svelte` du dépôt. Vérifié échouant sur
  le défaut, et son lecteur de balise l'est aussi : un `=>` dans les props
  coupait la lecture, et le contrôle passait au vert sur ce qu'il devait refuser.
  Depuis le 27/09/2026 (#1329), il classe aussi les intitulés **propres à un
  objet** (« Code », « Type », « État ») : ils se lisent dans le `titreEcran`
  de l'entité que le fichier importe. Un formulaire qui n'importe pas sa
  déclaration reste donc à moitié invisible — **déclarer l'entité, c'est ce qui
  la fait contrôler**.
* 🔒 `npm run lint:pliage-transmis` (22/09/2026) tient l'autre bout du même
  fil : un composant qui **porte** une section du cadre — `SectionsPiecesJointes`,
  `ChampSaisiPour`, `SectionWorkflow` — doit **transmettre** son pliage. Sans
  prop `pliable`, la table a beau dire `pliee: true`, la section s'ouvre.
  Signalé deux fois à l'écran avant qu'un contrôle le voie : corriger la table
  ne suffit pas si le porteur ne la lit pas.

⚠️ Un épinglage ne se met JAMAIS dans la Diffusion, même quand il en dépend. Le
calendrier avait un motif réel — un événement absent du fil ne peut pas y être
épinglé — mais **une dépendance n'est pas un rang** : elle se dit
(`epingleInterdit`, qui désactive la case *et écrit pourquoi*), elle ne déplace
pas la section.

**Workflow et Diffusion sont deux notions distinctes**, et les confondre est
l'erreur qui a fait poser la question :

| | Workflow | Diffusion |
|---|---|---|
| Répond à | *où en est cet objet ?* | *qui le voit, et où ?* |
| Contient | Ouvert / En cours / Résolu (ticket), Suivi Kanban (événement, prestation) | affichage au fil, épinglage, WhatsApp, syndic, conseil syndical, Publié / Brouillon |
| Se place | **avant** le Périmètre — c'est un champ spécifique de l'objet | **en fin**, après les documents |

🔴 **Le KANBAN du calendrier EST un workflow** (18/08/2026). Ses six colonnes —
AG · CS · Syndic · Prestataire · Terminé · Annulé — répondent exactement à *« où
en est cet objet ? »*. La section s'appelle donc **Workflow**, et non « Suivi
Kanban » : ce dernier nommait l'écran où on le voit, pas la notion. **Aucun
second champ d'état n'a été créé** — deux notions de suivi sur le même objet se
contredisent au premier écart, et rien ne dirait laquelle fait foi.

Corollaire : **un changement de colonne est une transition tracée**, avec son
avant et son après dans l'Historique ; toute autre modification reste une
correction. Le calendrier était le dernier écran du site à faire avancer un suivi
en silence.

🔴 **Ce qu'une entrée d'Historique ENVOIE parle d'ELLE** (18/08/2026). Rouvrir
la Diffusion sur un suivi ne suffit pas : il faut recâbler ce qui part. Le lot
de la veille avait ouvert la section et laissé l'appel existant — le groupe
WhatsApp recevait donc la description de l'ÉVÉNEMENT à chaque commentaire, le
même texte indéfiniment, et l'e-mail attachait les pièces de l'événement au
lieu de celles de l'entrée.

⚠️ **C'est le défaut typique de l'ajout d'un canal à une entité existante** :
on reprend l'appel qui marche, et l'appel qui marche parle de l'objet porteur.
Rien ne lève, rien ne manque dans les journaux — le message part, il est
simplement faux. Trois questions à se poser, dans cet ordre :

1. **le contenu** — texte de l'entrée, pas de l'objet ;
2. **les pièces** — celles de l'entrée, avec repli sur l'objet si elle n'en a
   pas (même règle que `flux/tickets.py`) ;
3. **le renvoi** — un commentaire se lit hors contexte : le message porte un
   lien vers l'objet, sinon le lecteur ne sait pas sur quoi il porte.

🔴 **Et le FIL doit apprendre la nouvelle table.** Le fil est une douzaine de
rubriques indépendantes ; rien n'oblige une table neuve à s'y déclarer.
Le fil des événements (`flux/evenements.py`, supprimé avec #1092) ne lisait que `Evenement` et datait donc ses cartes de
l'annonce — une affaire qui avançait aujourd'hui restait noyée dans les
vieilles lignes. **Le fil date du dernier fait, jamais du premier.**

⚠️ Ajouter un TYPE pour la mise à jour aurait été le réflexe (c'est ce que font
les tickets, avec trois types). **Ne pas le faire ici** : le front teste
`type === 'evenement'` à six endroits — libellé, couleur, fond, lien, urgence,
et le filtre du tableau de bord qui **masque les AG** à qui n'y a pas droit. Un
type neuf serait passé à côté des six, et une AG commentée serait devenue
visible de tous, en silence. **C'est la donnée qui porte la différence** :
`evol_contenu` présent ⇒ la carte rend le bloc de suivi.

### 9 septies. Les sections communes ne se réécrivent plus : `ChampsCommuns.svelte`

**L'ordre ci-dessus a un point d'héritage depuis le 16/08/2026.** Périmètre,
Destinataires, Description, Pièces jointes et Diffusion sont rendus par UN
composant, qui porte leur ordre, leurs intitulés et leurs séparations
(`SectionFormulaire`). Un écran déclare ce qu'il a, jamais où le mettre :

```svelte
<ChampsCommuns
  idPrefixe="ticket"
  avecPerimetre bind:perimetre={perimetreCible}
  avecDescription descriptionRequise bind:description
  avecPhotos bind:photos={photosUrls}
  avecDocuments bind:documents={fichiersUrls}
  avecDiffusion bind:whatsapp bind:syndic bind:cs bind:auteur
>
  {#snippet creneauDiffusion()}…options propres à l'écran…{/snippet}
</ChampsCommuns>
```

Les sections **1 à 3** (Titre, champs spécifiques, Workflow) restent dans l'écran :
lui seul sait ce qu'elles portent.

🔴 **Une Description se rend par `SectionDescription`**, assistant IA et marque ✨
compris — jamais un `RichEditor` posé sous un intitulé « Description ». L'annonce
de hall le faisait, sous « Message » : seule Description du site privée de
l'assistant (#1089). 🔒 `npm run lint:description-unique` ; deux écarts LÉGITIMES y
sont déclarés — le descriptif d'une page du menu, et le contrat, qui garde sa
synthèse IA seule (arbitré, #1240).

#### Une section à UN seul champ ne répète pas son nom

Première livraison, l'écran affichait :

```
PÉRIMÈTRE
Périmètre *                            [Copropriété entière]
```

Le nom deux fois, en deux typographies — signalé par l'utilisateur, capture à
l'appui, **le jour même de la mise en production**. La cause est mécanique :
`PerimetrePicker`, `DestinatairePicker` et `FichiersUpload` portent chacun leur
intitulé (c'est justement leur point d'héritage, §9 quater), et la section en
ajoutait un second.

**Règle** : quand une section ne contient qu'un champ, le **titre de section EST
le libellé**. Il porte l'astérisque (`requis`) et le badge d'état (`badge`) ; le
champ reçoit `titre=""` et n'écrit plus rien.

```
PÉRIMÈTRE *                            [Copropriété entière]
```

Les sections à **plusieurs** champs (Détails, Clôture, Diffusion) gardent leur
titre de groupe **et** les libellés de leurs champs : ce n'est pas une redite,
c'est une hiérarchie.

🔴 **La section 1 aussi** (23/09/2026, signalé à l'écran : *« normalise les
titres des sections »*). Sept formulaires l'ouvraient par un `<label>` de champ
sous une `SectionFormulaire` sans titre : TITRE prenait le style d'un libellé
(0,875 rem, graisse 500), CATÉGORIE juste dessous celui d'une section (0,72 rem,
gras). Elle vit dans **`SectionTitre`** (« Titre », ou « Nom », « Question »),
et `npm run lint:section-nommee` refuse une section nommée par son champ.

**Hiérarchie** (arbitrée le même jour) : dans une section à plusieurs champs, le
libellé d'un champ se lit **un cran sous** le titre de section — même corps et
mêmes capitales, graisse moyenne, couleur atténuée (`champs.css`,
`.section-formulaire .field > label`). Il était plus GRAND que son titre de
section, et la hiérarchie se lisait à l'envers. Hors section (connexion,
réglages), le libellé est le seul repère et garde sa taille.

⚠️ **Le titre de section est un vrai libellé, donc il s'associe.** `SectionFormulaire`
rend un `<label for>` quand la section porte un contrôle **labelable** (`<select>`,
`<input>`) — prop `pour` —, et un `<h4 id>` sinon, l'appelant reliant son groupe par
`aria-labelledby` (prop `idTitre`). Les pastilles et l'éditeur riche ne sont PAS
labelables : un `for` posé dessus n'associe rien, **et le fait en silence**. C'est
d'ailleurs ce qui existait avant — `Périmètre *` était un `<div>`, donc un groupe de
boutons sans nom pour un lecteur d'écran.

Corollaire appliqué au passage : le `(max N)` a quitté l'intitulé des pièces
jointes. Le compteur `0/N` sous le bouton le dit déjà, et il le dit mieux — il se
met à jour. Les types acceptés sont en aide grise à côté du compteur, déduits
d'`ACCEPT_DOCUMENTS` et non récités.

**Why.** L'ordre était écrit, `SectionFormulaire` savait séparer — et les six
formulaires recomposaient quand même la suite à la main. L'utilisateur l'a
signalé ainsi : *« Les objets ont l'air d'être dupliqués, pas instanciés, car ils
diffèrent selon les pages. »* Relevé avant correction :

| Notion | Ce qui divergeait |
|---|---|
| Description | « Description » / « Description * » / « Notes » ; hauteur 60, 80, 90, 100 ou 120 px |
| Documents | `FichiersUpload` sur tickets et calendrier, `<input type="file">` **nu** sur actualités et prestations |
| Diffusion | aucune section nommée sur **4 écrans sur 6** |
| Ordre | Périmètre au milieu de la grille des champs spécifiques (prestations) ; Kanban rangé dans la diffusion (calendrier) ; « Saisi pour » **après** les pièces jointes (tickets) |

Aucune n'était voulue : ce sont les six recopies qui les produisent. La seule
façon de ne pas les voir revenir est qu'un seul endroit les écrive.

⚠️ **Une rubrique dont le parent n'existe pas encore** (documents d'actualité,
fichiers de prestation : leur endpoint réclame l'identifiant) passe par le mode
**différé** de `FichiersUpload` — `differes` + `bind:fichiersDifferes`.
L'écran téléverse après création. Ne PAS retomber sur un `<input type="file">`
nu : c'est ce qui produisait la deuxième apparence.

### 9 octies. Jamais de sélecteur d'ÉLÉMENT nu dans un composant

`input`, `textarea`, `select`, `button`, `label` seuls, dans un `<style>` de page
ou de composant : **interdit**, et refusé par `npm run lint:styles`.

**Why.** `sondages/+page.svelte` portait `input, textarea { width: 100% }`. Le
sélecteur visait les champs de saisie et atteignait **toutes les cases à cocher
de la page** : chacune s'étirait sur la largeur du formulaire et repoussait son
libellé à l'autre bout. L'utilisateur l'a signalé sur **deux écrans distincts**
(« Nouveau sondage » et « Déposer une annonce »), sans lien apparent entre eux —
c'était une seule ligne. Quatre composants annulaient déjà ce genre de règle case
par case avec un `style="width:auto"` recopié : le signe qu'on soignait le
symptôme.

Qualifier le sélecteur (`.case input[type="checkbox"]`) ou porter la règle dans
`styles/composants.css`, où elle est globale et assumée.

### 9 quinquies bis. Le bouton de soumission dit **« Enregistrer »**, partout

Verbe **générique**, sur tous les formulaires de création. Arbitré par
l'utilisateur le 17/08/2026 (#396), après un relevé de sept formulaires portant
**six** libellés — « Publier » / « Enregistrer brouillon », « Envoyer la demande »,
« Créer le sondage », « Publier l'annonce », « Soumettre », « Enregistrer » — plus
« Soumettre la demande » sur accès & badges, que le relevé du ticket avait manqué.

Aucun n'était faux ; l'ensemble n'avait pas de logique.

| | |
|---|---|
| au repos | `Enregistrer` |
| pendant l'envoi | `Enregistrement…` |

L'état d'attente est **inclus dans la règle** : il divergeait pareillement
(« Envoi… », « Création… », « Sauvegarde… », et même « … » tout court). C'est le
même libellé, vu pendant la seconde où l'utilisateur se demande si son geste a été
pris.

⚠️ **Le mode brouillon ne se dit plus dans le bouton.** L'actualité affichait
« Enregistrer brouillon » ou « Publier » selon la case cochée — or cette case est
déjà visible dans la section Diffusion, juste au-dessus. Le bouton la répétait.

**Hors périmètre, et volontairement** : les écrans d'authentification
(« Se connecter », « Créer mon compte »), les imports (« Importer ») et le
changement de mot de passe. Ce ne sont pas des créations d'objet.

**Garde-fou** : `npm run lint:soumission` (job `build-frontend`), sur les
composants `Formulaire*.svelte`. Les exceptions sont nommées avec leur raison et
le contrôle échoue si l'une devient inutile.

### 9 quinquies. Le bouton de soumission est **à droite**, via `.form-actions`

`.form-actions` (`styles/composants.css`) porte `justify-content: flex-end`. Un bouton posé nu dans
un `<form>` se cale à **gauche** et détonne : c'était le cas des sondages (« Créer
le sondage », « Publier l'annonce », « Soumettre » d'une idée), seuls de tout le
site, jusqu'au 16/08/2026. Ne jamais écrire un bouton de soumission hors de
`.form-actions`.

> ⚠️ **Question de nommage ouverte** (posée le 16/08/2026, non tranchée) : unifier
> **Libellé → Titre** et **Notes / Contenu → Description** ? C'est une décision
> fonctionnelle qui touche les libellés vus par les résidents, pas un renommage
> de classe.
