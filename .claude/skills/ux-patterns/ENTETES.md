# ux-patterns — En-tête de page, mode lu sur l'icône, formulaire de création (§13 à §14)

Annexe de `SKILL.md`, chargée à la demande (#2910) : la règle d'uniformisation, le
registre des arbitrages, le sommaire et la checklist avant commit sont dans `SKILL.md`.
Les numéros de § sont ceux de toujours : un renvoi « §N » se lit au sommaire.

## 13. En-tête de page — `EntetePage.svelte`, une seule écriture

**Ne jamais rendre `<div class="page-header">` à la main.** Le composant porte le
conteneur, le titre (icône + libellé + taille), le retour et la zone d'actions :

```svelte
<EntetePage titre={_pc.titre} icone={_pc.icone || 'newspaper'}>
  {#if $estModerateur}
    <BoutonNouveau ouvert={showForm} libelle={TICKET.libelleNouveau} on:basculer={() => (showForm = true)} />
  {/if}
</EntetePage>
```

🔴 **Le bouton d'ouverture passe par `BoutonNouveau`** — il ne s'écrit plus à la
main (12/09/2026). Il porte le « + », le libellé, et surtout **l'effacement
pendant la saisie** : l'annulation vit à côté d'« Enregistrer », jamais en double
dans l'en-tête (#367, norme du 18/08/2026).

⚠️ **Ce composant a porté la règle INVERSE pendant quatre semaines.** Créé le
16/08 avec la bascule « + … » ⇆ « ✕ Annuler », il n'a pas suivi la révision du
18/08 — que Tickets et Actualités ont appliquée, chacun en la recopiant chez lui.
Trois écritures, dont une périmée, et son en-tête affirmait porter la bonne.
Prestataires, son unique appelant, affichait donc « ✕ Annuler » **même en
édition** — on n'annule pas une création qui n'a pas lieu — jusqu'au signalement
de l'utilisateur. *Une consigne fausse fait lire l'écart comme une décision.*

🔴 **Un onglet d'Admin n'a pas d'en-tête à lui** (« Paramétrage » est partagé) : son
`BoutonNouveau` se pose dans `.actions-onglet` (`composants.css`), sur sa rangée, à
gauche, au-dessus de `ReglagesListe` — jamais à côté de la recherche (arbitrage n° 79).

| Prop | Rôle |
|---|---|
| `titre` | obligatoire |
| `icone` | nom Lucide du catalogue `#lib/icones-svg.json` |
| `retour` | href — affiche `← Retour` **à gauche du titre** |
| `descriptif` | le descriptif **de la page** (`_pc.descriptif`), rendu sous l'en-tête et **au-dessus** des onglets |
| ~~`marge`~~ | **retirée le 17/08/2026** — voir ci-dessous |
| slot par défaut | les actions, **à droite** |

**Disposition, la même partout** : `[retour] titre` à gauche · actions à droite.

Les écrans **sans session** (connexion, inscription, mot de passe, erreur) n'ont pas
d'`EntetePage` : leur en-tête est `EnteteAuthentification` — la marque de la résidence,
son nom en titre, le geste en phrase dessous, comme à la connexion (#2357).

🔴 **Le descriptif de page est une prop, pas une ligne de l'écran** (#1369, 27/09/2026).
Douze écrans écrivaient `<div class="page-subtitle">` à la main ; Résidence le posait
**sous** ses onglets, juste au-dessus du descriptif de l'onglet « Fiche », qui portait le
même texte — la phrase se lisait deux fois. Délégations l'écrivait **en dur** : le texte
administrable ne s'y affichait pas. Une phrase par niveau : la page dit ce qu'elle est
(`EntetePage`), l'onglet ce qu'il montre (`BarreOnglets`), et l'onglet **se tait** quand
il répète mot pour mot la page — comparé sans balisage, les deux étant administrables.
🔒 `lint:entetes` (motif 4, composants compris) · `e2e/descriptif-page.spec.ts`.

⚠️ **Vérifier que l'icône existe** dans `#lib/icones-svg.json` : `Icon` retombe
**silencieusement** sur `help-circle` pour un nom inconnu. `message-square-plus`
n'existe pas et aurait affiché un point d'interrogation sans qu'aucun contrôle ne
le dise (constaté le 15/08/2026). Depuis le 24/09/2026, `npm run lint:icones` le
dit : il a trouvé `database`, affiché en « ? » depuis v2.19.0 (#1045).

**Garde-fou** : `npm run lint:entetes` (job `build-frontend`) refuse un
`class="page-header"` écrit à la main, une redéfinition locale de `.page-header`,
et un `<h1>` portant `font-size` en ligne. Les exceptions sont **nommées avec leur
raison** dans le script, et le contrôle échoue si l'une devient inutile.

**Dette soldée le 17/08/2026 — la marge d'en-tête vaut `1.5rem`, sans exception.**

`marge` existait parce que **six** écrans divergeaient : `0` (FAQ), `.5rem`
(espace CS, prestataires), `.75rem` (délégations, résidence), `1rem` (calendrier),
contre `1.5rem` partout ailleurs. Centraliser les valeurs les avait rendues
explicites **sans les réduire** — la dette était nommée ici, et elle a duré.

Le symptôme se voyait : en passant d'`/actualites` à `/calendrier`, le titre et le
bouton **sautaient** de quelques pixels, alors que les deux pages utilisent le même
composant (#372). Arbitré par l'utilisateur : la valeur du plus grand nombre gagne.

**La prop n'existe plus.** C'est le point important : la laisser en place aurait
invité la septième valeur. Un écran qui aurait vraiment besoin d'autre chose doit
d'abord expliquer pourquoi lui — pas recevoir une prop qui rouvre les six.

⚠️ Le retrait a fait **échouer `lint:entetes`**, dont le cas zéro exige que
`EntetePage` expose ses props connues. C'est voulu : son message dit « le contrat a
changé — mettre ce contrôle à jour ». Un garde-fou qui n'aurait rien dit aurait
laissé passer une prop disparue, et donc laissé le contrôle vérifier un contrat
imaginaire.

> **La leçon, générale** : nommer une divergence ne la corrige pas. Centraliser
> six valeurs dans une prop les rend lisibles et **pérennes**. Tant que le
> mécanisme d'exception existe, l'exception se reproduit.

**Pages de détail** (`tickets/[id]`, `sondages/[id]`) : elles n'ont **pas**
d'en-tête de page — leur `<h1>` est le titre de l'objet. Ne pas les convertir
mécaniquement : ce qu'il faut y mettre est instruit dans #365.

🔴 **Le lien d'une affaire rend SA CARTE, dépliée** (15/10/2026, signalé à l'écran :
*« affichée d'une manière différente du fil d'actualité ou de la page »*).
`/tickets/[id]` rendait une fiche à part — en-tête, boutons d'état, Historique ; il
rend désormais `ListeTickets` sur une liste d'UNE affaire, dépliée d'office, avec
les gestes de la liste (`#lib/affaires-en-liste`, la seule écriture des gestes, que
la page Affaires emploie aussi). Ce qui lui reste propre : le fil de MESSAGES dessous
(les notifications pointent `#msg-…`), et un `<h1 class="sr-only">` — le titre de la
carte est un bouton qui la plie, pas un intitulé. Un objet, un rendu : une fiche qui
se lit autrement que sa carte est une divergence, pas une page de détail.
🔒 `e2e/lien-affaire-depliee.spec.ts`.

**Leur colonne de lecture : `.colonne-lecture`** (`normes.css`, 720 px), posée
sur **chaque** bloc — la carte, le fil de messages —, jamais une largeur écrite
par la page sur la classe d'un composant enfant. C'est ce qui s'était produit : la règle visait `.messages`,
l'extraction de `FilMessagesTicket` l'a rendue morte, et la barre « Répondre »
s'étalait seule jusqu'au bord de l'écran (01/10/2026, signalé à l'écran).
🔒 `e2e/transferts-verses.spec.ts` mesure que le lien direct n'a qu'un bord droit.

## 13 bis. 🔴 LE MODE SE LIT SUR L'ICÔNE QUI L'A OUVERT

**Corrigé le 18/08/2026, le soir même où la règle inverse avait été posée.**
Ce paragraphe disait : *« tout formulaire porte un titre, et c'est lui qui dit
le mode »*. Le diagnostic d'origine était bon — le mode ne se lisait nulle part,
signalé ainsi : *« on ne sait pas si on est en mode édition, en mode suivi »* —
mais le remède était mauvais, et l'écran l'a dit :

> « les titres d'état je ne trouve pas ça beau : je mettrais l'icône concernée
>   en plus gros ou inversée pour supprimer ce pseudo état qui éloigne du titre »

Un titre au-dessus du formulaire ajoute un **second en-tête** sous celui de la
carte : il repousse le contenu et éloigne le formulaire de l'objet auquel il se
rapporte. Le bon endroit pour dire « vous êtes en train de commenter » n'est pas
au-dessus du formulaire, c'est **sur l'icône qui l'a ouvert** — elle est déjà là,
déjà regardée, et son inversion se lit sans être lue.

### La règle

| Où | Ce qui dit le mode |
|---|---|
| formulaire **encadré** (création) | son titre : c'est l'en-tête de SA carte, pas un doublon |
| formulaire **dans la carte d'un objet** | l'icône qui l'a ouvert, **inversée** |

```svelte
<button class="btn-icon" aria-pressed={mode === 'edition'} aria-label="Modifier" title="Modifier" …>
  <IconeAction icone="pencil" />
</button>
```

Le style vit dans `styles/composants.css`, une seule fois : fond plein en couleur primaire,
glyphe blanc, `scale(1.15)`. ⚠️ **Un simple changement de teinte ne suffit pas** :
il ne se distinguerait pas du survol, et l'on ne saurait plus si l'icône est
active ou seulement pointée.

⚠️ **`aria-pressed`, et non une classe.** L'état est alors annoncé par les
lecteurs d'écran en même temps qu'il se voit, aucun écran n'a de classe de plus à
penser — et un bouton bascule doit le porter de toute façon.

⚠️ **Le titre ne disparaît pas, il devient invisible** : `FormulaireCreation` le
passe en `aria-label` sur le groupe. Qui ne voit pas l'icône entend toujours
« Modifier le commentaire » en entrant dans le formulaire.

⚠️ `encadre` garde son autre rôle : à `false`, pas de carte imbriquée — deux
bordures pour un seul objet, c'est la « carte dans la carte » de #425. C'est le
composant qui décide, jamais l'écran.

## 14. Formulaire de création — `FormulaireCreation.svelte`, une boîte dans la page

**Un seul paradigme sur tout le site : la boîte dans la page.** Les actualités
sont le modèle, désigné par l'utilisateur.

```svelte
<EntetePage titre={_pc.titre} icone={_pc.icone} alignerSaisie={showForm}>
  {#if $estModerateur}
    <BoutonNouveau ouvert={showForm} libelle={TICKET.libelleNouveau} on:basculer={() => (showForm = true)} />
  {/if}
</EntetePage>

{#if showForm}
  <FormulaireCreation titre={TICKET.libelleNouveau}>
    <form on:submit|preventDefault={creer}> … </form>
  </FormulaireCreation>
{/if}
```

**Ce qui était faux avant le 15/08/2026** (#367), et que l'utilisateur a dû
signaler **trois fois** :

- **trois paradigmes** pour la même intention — boîte (actualités, sondages),
  modale (calendrier, prestataires, accès & badges, fiche sondage), page dédiée
  (nouveau ticket) ;
- le bouton d'annulation **excentré** : il se posait au bord droit de l'ÉCRAN
  alors que la boîte s'arrête à 720 px ;
- sur le calendrier, **deux** commandes d'annulation — la croix de la modale et
  le bouton d'en-tête, ce dernier sous l'overlay, visible et inutilisable.

### Les trois règles

1. **La commande d'annulation reste dans l'en-tête**, où le bouton d'ouverture
   bascule en « ✕ Annuler ». Ne PAS en ajouter une seconde dans la boîte.

   > ⚠️ **Périmé** : depuis le 18/08/2026, l'annulation vit au pied du formulaire et
   > `BoutonNouveau` s'efface pendant la saisie (§13, arbitrage n° 31) ; l'exemple ci-dessus
   > aussi. Vérifié dans `BoutonNouveau.svelte` le 18/10/2026.

2. **`alignerSaisie={showForm}` sur `EntetePage`** dès qu'un formulaire s'ouvre
   dans la page — sans lui le bouton flotte loin de ce qu'il annule.
3. **Jamais de modale pour un formulaire de CRÉATION.** Les modales restent
   légitimes pour une confirmation, un téléversement ponctuel, la visionneuse —
   — mais **plus pour l'édition** d'un objet : voir §14 bis (06/09/2026).

### 🔴 14 bis. CRÉER ET CORRIGER EMPLOIENT LA MÊME BOÎTE DANS LA PAGE (06/09/2026)

Arbitré à l'écran : *« la boîte d'édition n'est pas standard à l'UX, elle
apparaît dans une fenêtre indépendante au lieu de la fenêtre principale […]
comme le reste du site, avec un UX standard, pas de spécifique. »*

| Geste | Format |
|---|---|
| **Créer** | la **boîte dans la page** — `FormulaireCreation`, §14 ci-dessus |
| **Corriger** un objet existant | **la même boîte**, au même endroit |

Le choix se fait dans **`CadreFormulaire`**, et nulle part ailleurs : huit
formulaires le traversent.

## ⚠️ CE PARAGRAPHE DISAIT L'INVERSE PENDANT SEPT JOURS

Du 30/08 au 06/09/2026, il énonçait : *« la modale est le format standard
d'édition »*, arbitré à l'écran lui aussi, avec un raisonnement qui se tenait —
« une édition interrompt une lecture ; déplier un formulaire au milieu d'une
liste déplace tout ce qui est en dessous ».

🔴 **Ce raisonnement n'a pas été réfuté, il a été tranché autrement** : une boîte
qui flotte par-dessus la page est un **paradigme de plus**, et c'est exactement
ce que #367 avait éliminé pour la création (il y en avait trois). Le produit a
préféré un seul format pour les deux gestes à deux formats bien motivés.

L'argument du décalage de liste, lui, avait **déjà** sa réponse :
`FormulaireCreation` s'amène lui-même à l'écran depuis le 29/08 — c'est
l'édition, dont le geste part d'une carte, qui en a le plus besoin.

⚠️ **Ce que ce second renversement ne remet PAS en cause** : les trois constats
de #367 restent vrais — pas de **double commande** d'annulation, pas de bouton
**excentré**, et surtout pas plusieurs paradigmes pour une même intention. On
revient simplement à « un format pour tout ».

🔒 **Le garde-fou a fait son travail avant de changer de forme.** Le cas zéro de
`lint:formulaires` exigeait de trouver `Modale` dans le `this={…}` de
`CadreFormulaire` : il a **refusé le lot qui appliquait la décision**, au lieu de
passer au vert en mesurant moins. Il vérifie désormais l'inverse — que la boîte
est rendue, et qu'aucune `Modale` ne revient par la porte de derrière.

⚠️ Les modales restent légitimes pour ce qui n'est pas un formulaire d'entité :
confirmation, **saisie qui accompagne un geste**, téléversement ponctuel,
visionneuse, écrans d'administration.

### La saisie qui accompagne un geste — `Saisie.svelte` (tranché le 14/09/2026, #931)

Signaler un contenu au conseil syndical demande un **motif**. Ce motif ne crée
aucun objet qu'on retrouvera dans une liste, et n'en corrige aucun : il
**accompagne un geste**, exactement comme une confirmation — dont il n'est que la
version qui pose une question ouverte au lieu d'une question fermée.

🔴 **Il n'y a donc pas de troisième forme à inventer**, et c'est ce que le ticket
cherchait. `Confirmation.svelte` est déployé seize fois, c'est une fenêtre, et il
répond déjà à *« que fait-on d'une question posée avant un geste ? »*. Les deux
règles qui interdisent la fenêtre — la création s'écrit dans la page (#367), la
correction dans la carte (§14 ter) — parlent l'une et l'autre d'un **objet** :
aucune ne recouvre ce cas. La règle la plus déployée l'emporte, et il n'y avait
qu'à la nommer.

⚠️ **Ce qui ferait basculer de l'autre côté** : si le motif devenait un champ de
l'objet signalé — modifiable, relisible, porté par une fiche — il cesserait
d'accompagner le geste pour devenir une **entité**, et la règle de la carte
reprendrait la main. Ce n'est pas le cas : le motif part au conseil syndical et
ne revient pas à l'écran.

⚠️ **Ouvrir le motif DANS la rangée a été écarté pour une raison mesurée**, pas
par goût : `signaler()` cesserait d'être un appel impératif et demanderait un
état d'ouverture **par ligne**, dans `Reponses` et dans chaque liste qui
l'emploie — c'est exactement l'échafaudage que `confirmer()` a retiré à seize
appels. On ne réintroduit pas pour un geste ce qu'on a supprimé pour seize.

### 🔴 OÙ SE POSE LE CADRE : **là où le geste est connu** (30/08/2026, calendrier)

La question s'est posée au troisième écran, et elle se reposera aux suivants —
elle est donc tranchée ici plutôt qu'à chaque conversion.

| Le composant de formulaire reçoit-il le geste ? | Qui pose le cadre |
|---|---|
| **oui** (`modeEdition` est une de ses propriétés) | **le composant** |
| **non** (il ne connaît que les champs) | **l'écran appelant** |

`FormulaireContrat` écrit l'inverse dans son en-tête — *« mettre le cadre ici
obligerait le composant à connaître le geste »* — et **c'est juste pour lui** :
il ne le reçoit pas. `FormulaireTicket`, si — comme le faisait le formulaire
d'événement de #432, supprimé avec #1092. La règle générale
recouvre donc les deux cas sans en contredire aucun.

⚠️ **Ce qu'il en coûte de choisir l'autre.** Poser le cadre dans la page oblige à
deux branches `{#if}` montant le **même** formulaire avec les mêmes propriétés —
seize pour l'événement, dont quatre liaisons bidirectionnelles que `{...props}`
ne répand pas dans le mode legacy de Svelte 5 (`export let`, `$:`). Deux copies qui divergent au premier champ ajouté, c'est-à-dire
la duplication que l'extraction du composant avait supprimée.

**Dans le mode legacy de Svelte 5** — celui du projet (`svelte ^5`, `export let`,
`$:`) ; ce n'est pas du Svelte 4 —, **la forme d'origine, qui n'écrit le corps
qu'une fois, était :**

```svelte
<svelte:component
	this={modeEdition ? Modale : FormulaireCreation}
	titre={titreCadre}
	{...(modeEdition ? { edition: true } : {})}
	on:fermer={() => dispatch('annule')}
>
```

⚠️ `<svelte:component>` n'est déprécié qu'en **mode runes**. Si le projet y passe,
la forme recommandée est un composant dynamique — `{@const Cadre = modeEdition ?
Modale : FormulaireCreation}` puis `<Cadre … />`. Depuis §14 bis, aucun écran
n'écrit plus ce choix : il vit dans `CadreFormulaire`, seul endroit où il se
tranche.

🔒 **Nommer `Modale` DANS le `this={…}` fait partie du geste** : c'est ce que
`lint:formulaires` lit. Un cadre choisi dans une variable (`const cadre = …`)
compile aussi bien et sort la modale du champ du contrôle.

**Garde-fou** : `npm run lint:formulaires` (job `build-frontend`). Il refuse un
cadre `card largeur-saisie` enveloppant un `<form>`, et toute modale portant un
formulaire **sans se déclarer `edition`**. Il a trouvé **deux écrans que l'audit
manuel avait manqués**.

🔒 **Son périmètre a été étendu le 30/08/2026, et c'était le préalable.** Il ne
lisait que `routes/`, alors que le cadre se pose dans le **composant** dès que
celui-ci connaît le geste : chaque conversion faisait donc sortir la modale de son
champ — *convertir revenait à se désarmer*. Il lit désormais aussi
`lib/components/`, et il reconnaît la modale montée par `<svelte:component>`.

✅ **`prestataires` est traité** : la page a été découpée (2 182 lignes au départ) et
ne porte **plus aucune** `<Modale>`. Ce paragraphe l'annonçait encore comme
« reste à traiter », avec quatre formulaires en modale — deux chiffres et un
constat, tous périmés.

⚠️ Ce qui reste, et qui n'était pas la modale : le périmètre y est une **chaîne**
dans un `<select>` là où `PerimetrePicker` travaille sur un tableau. C'est un
changement de contrat, pas un remplacement de composant — et c'est la seule
partie de ce paragraphe qui était encore vraie.

### 🔴 14 ter. LA CORRECTION S'OUVRE À LA PLACE DE L'OBJET (10/09/2026)

Arbitré à l'écran, en une question : *« la position de la fenêtre d'édition
est-elle standard ? avant à la fin, maintenant au début — le standard n'est-il
pas sur la position courante ? »*

Sur les contrats, la boîte d'édition s'ouvrait d'abord **en bas de page**, puis
**en haut** après une première correction. Les deux sont au mauvais endroit : sur
une liste de vingt éléments, l'un comme l'autre déplacent l'utilisateur loin de
ce qu'il édite. La `cle` de `FormulaireCreation` le ramenait bien à l'écran —
mais à l'écran du **formulaire**, pas à sa place dans la liste.

| Geste | Où la boîte s'ouvre |
|---|---|
| **Créer** | en tête de liste — elle ne corrige rien, elle n'a pas de place à occuper |
| **Corriger** | **dans la carte**, à la place de son CORPS — l'en-tête reste, avec son titre et ses actions |

⚠️ **§14 bis n'est pas remis en cause** : c'est toujours LA MÊME BOÎTE — même
composant, même format. Ce qui change est sa **position**, qui suit désormais
l'objet corrigé. « La même boîte » ne voulait jamais dire « le même endroit du
DOM », et c'est ce raccourci qui a produit les deux erreurs.

🔴 **Trois positions essayées en une journée, dont deux fausses.** La leçon n'est
pas qu'il fallait deviner : c'est qu'une position de formulaire se juge **sur une
liste longue**, jamais sur un écran de trois éléments où tout est visible à la
fois.

🔴 **DÉPLACER un rendu, c'est aussi RETIRER l'ancien** — et ce second geste s'est
oublié le jour même. La correction a déménagé dans la carte le matin ; le bloc de
tête de liste, lui, est resté ouvert sur `contratFormOuvert || editContratId`.
Résultat signalé à l'écran l'après-midi : *« plusieurs contrats sont ouverts en
édition simultanément »* — deux boîtes « Modifier le contrat » à la fois, et la
`cle` de celle du haut qui ramenait la page en haut.

⚠️ **`lint:geste-edition` ne pouvait pas le voir, et c'est l'extraction qui l'a
aveuglé** : sa règle B compte les rendus d'un formulaire **fichier par fichier**,
et le second venait d'être déplacé dans un second fichier. La **règle C** couvre
désormais le cas sans dépendre du découpage : *un identifiant d'édition
(`editXxxId`) ne peut pas à la fois ouvrir un formulaire dans l'écran et être
confié à un composant enfant* — les deux rendus s'affichent alors ensemble.

🔴 **QUATRIÈME position, et la bonne** — désignée par l'utilisateur le 10/09/2026 :
*« l'affaire modifiée passe en premier ! prends exemple sur tickets »*. Remplacer
la carte **entière** effaçait la ligne du contrat, et `FormulaireCreation`
ramenait sa boîte en haut de la fenêtre dès qu'elle n'y tenait pas : l'objet
corrigé quittait sa place dans la liste.

Le motif des tickets ne déplace **rien** : la carte reste, son **en-tête** reste —
titre, tags, date, actions — et seul le **corps** cède la place au formulaire, en
`encadre={false}` pour ne pas poser une carte dans une carte. Le mode se lit sur
le crayon (§13 bis), et **aucune `cle` n'est nécessaire** : rien n'a bougé, il n'y
a rien à ramener à l'écran.

⚠️ **Ce composant existait DEUX fois** — `AnnonceCard` et `CarteActualite`
portent tous deux une prop `formulaireOuvert` et un `<slot name="formulaire" />`
qui font exactement cela, depuis des semaines. Trois positions fausses ont été
essayées sans que je les ouvre : la question « où mettre la boîte ? » avait déjà
sa réponse dans le produit. C'est la **sixième** fois — voir la mémoire
`project_le_composant_existait_deja`. Le réflexe reste le même : chercher la
**notion** (« corriger un objet d'une liste »), jamais le nom de l'écran.

🔒 **Depuis le 02/10/2026 (#1539), ce squelette a UN composant : `CarteModifiable`**
— conteneur, `EnteteCarte`, 🔗 ✏️ 📦 (↩️ aux Archives, #1538), corps qui cède la place à
`FormulaireCreation` (`encadre={false}`), titre inerte pendant la correction.
`CarteContrat` et `CartePrestataire` le recopiaient l'une sur l'autre ; une carte
neuve qui se corrige en place le monte et remplit ses emplacements (`tags`,
`apercu`, `gestes`, `edition`, `detail`). Qui RETIRE sans corriger — le gestionnaire
du site devant un avis (#2075) — se dit par `peutArchiver`, qui ressort par
`peutRestaurer` (absents, ils valent `peutModifier`) ; ce qui se fait de plus aux
Archives (🗑️ d'un avis) va dans `gestes-archive`. ⚠️ `AnnonceCard` et `CarteActualite`
portent encore leur propre `formulaireOuvert` : même notion, pas encore migrée.

🔴 **Et ce n'était toujours pas fini : le formulaire DÉFILAIT.** Troisième
signalement du même symptôme — *« le contrat édité remonte en haut »* — alors que
la carte, elle, ne bougeait plus d'une ligne. Ce n'était pas un déplacement dans
la liste : `FormulaireCreation` appelait `ramener()` **à chaque montage**, sans
condition. Un formulaire ouvert dans la carte d'un objet, en bas de la fenêtre,
dépassait la bande visible de quelques pixels et se faisait ramener en haut de
l'écran — en emportant sa carte.

**La règle, désormais : `cle` ne distingue plus seulement deux objets, elle
DEMANDE le défilement.** Sans `cle`, le composant ne défile jamais.

| Le formulaire s'ouvre… | `cle` | Défile ? |
|---|---|---|
| dans la carte de l'objet corrigé | non | **non** — ce qu'on regarde est déjà là |
| en tête de page, geste juste au-dessus | non | **non** |
| ailleurs que là où l'on a cliqué (liste longue, tableau) | **oui** | oui |

⚠️ **L'intention était écrite dans le fichier même**, à dix lignes de l'appel
fautif : *« un formulaire qui s'ouvre sous les yeux n'a pas à faire sauter la
page »*. Le code ne testait que la **position**, jamais la raison d'être là — et
la position seule ne distingue pas « ouvert loin du geste » de « ouvert un peu
bas ». C'est le motif que ce dépôt connaît le mieux : *la règle est écrite, et
elle n'est pas appliquée*.

🔒 `lint:geste-edition` **règle D** : aucun appel à `ramener()` hors de la garde
`cle !== undefined`. Vérifié sur la version fautive — elle la refuse.

📐 **Ce qui a permis de trancher, après trois corrections à l'aveugle** : le vrai
composant monté dans une **route jetable**, avec soixante cartes et un
`Element.prototype.scrollIntoView` instrumenté. Le raisonnement disait « rien ne
peut bouger » ; le relevé a montré l'appel, à la ligne près. Même leçon qu'un
enroulement flex mal attribué à la compression : une reproduction approximative ne
reproduit rien — monter le vrai composant, avec de vraies données.

### La règle en une phrase — et l'audit qui la fait tenir (10/09/2026, #889)

> **La boîte s'ouvre là où est le geste.**

| Geste | Où la boîte s'ouvre |
|---|---|
| **Créer** depuis un bouton de page | en tête de liste — le geste est là |
| **Créer sous un objet** (« ＋ sous-périmètre ») | **dans cet objet** — le geste y est aussi |
| **Corriger** un objet | **dans sa carte, à la place de son corps** ; l'en-tête reste |
| **Commenter** / faire évoluer | idem (`EvolForm`, déjà conforme) |

⚠️ Le « ＋ » d'un nœud n'est **pas** une entorse à « créer s'ouvre en tête » :
c'est la même règle. Le bouton de la barre ouvre en tête parce qu'il y est.

🔒 **`lint:geste-edition` règle E** : `<Modale edition>` est refusée. Le produit
distinguait déjà, par cette propriété, la fenêtre de **correction** de celle de
**confirmation** ou d'**aperçu** — le contrôle s'appuie sur la distinction qui
existe plutôt que d'en inventer une, et les confirmations restent légitimes.

Les **sept** écrans qui en portent encore une sont déclarés dans le contrôle avec
leur motif et le ticket #889 : la dette est nommée, elle ne peut plus grandir, et
une déclaration qui ne sert plus fait échouer.

⚠️ **Cinq d'entre eux ne sont pas des corrections mais des GESTES** (valider un
compte, terminer un bail, noter un prestataire) ou un **sous-écran** entier. La
règle parle de *corriger* : l'étendre à un geste court est une décision
d'interface qui se prend devant l'écran. Ne pas la trancher dans un fichier —
c'est ce qui a coûté trois MEP le même jour.
