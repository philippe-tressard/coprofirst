---
name: user-manual
description: "Documentation utilisateur de 5Hostachy — le manuel (docs/manuel-utilisateur.html et sa copie servie) et le README.md — quand une fonctionnalité visible est ajoutée, modifiée ou retirée. À charger : nouvel écran, onglet ou parcours, libellé ou geste qui change, page retirée, navigation modifiée. Pas pour un changement purement technique (migration, refactor, sécurité côté serveur seulement)."
argument-hint: "Describe the feature to document (e.g. 'new fournisseurs page with list and detail')"
---

# Documentation utilisateur — 5Hostachy

**DEUX documents, pas un.** Cette skill couvre `docs/manuel-utilisateur.html`
(copié tel quel vers `front/static/`, qui le sert) **et** `README.md`. Ils sont de
**même rang** : un changement visible se répercute dans les deux quand il touche
les deux.

## Les deux questions à se poser — elles n'ont pas la même réponse

| Document | Répond à | À mettre à jour quand… |
|---|---|---|
| `docs/manuel-utilisateur.html` | **comment on s'en sert** | tout changement visible : écran, libellé, geste, parcours, ce qui apparaît ou disparaît sous les yeux d'un résident ou d'un administrateur |
| `README.md` | **ce que le produit EST** | un module, un écran de premier niveau ou une capacité est **ajouté, retiré ou renommé** · la pile technique change · un document du tableau `docs/` bouge · une commande d'exploitation change |

Un lot peut légitimement ne toucher qu'un seul des deux — mais alors on le **dit**,
on ne l'omet pas en silence. Exemple : supprimer deux cartes redondantes de
l'onglet Maintenance (#299) change le manuel — le geste pour consulter un
historique n'est plus le même — et **pas** le README, dont la ligne « Maintenance
— Tâches automatiques + déclenchement manuel » reste vraie.

> **Pourquoi cette skill porte les deux depuis le 11/08/2026.** Le manuel était
> vérifié par réflexe et le README jamais : la consigne du projet ne nommait que
> le manuel, alors que l'exigence **E3** (documentation à jour) de l'étape 0 bis
> de `mep-precheck` dit « README · manuel · `specs/` » depuis toujours. Deux
> listes ont divergé, et c'est la plus courte qui a été suivie. Signalé par
> l'utilisateur.

## Règle obligatoire

Toute modification UX ou fonctionnalité visible **doit** être documentée dans le
**même commit** que la fonctionnalité. Après modification du manuel, depuis la
racine du dépôt :

```bash
cp docs/manuel-utilisateur.html front/static/manuel-utilisateur.html
```

`docs/` est la source, `front/static/` la copie servie, à l'octet près
(`test_documentation.py` échoue si elles diffèrent).

⚠️ **Ne jamais éditer le manuel avec `sed -i`** : il est versionné en **CRLF**, et
`sed` le réécrit en LF — le diff passe de quelques lignes à plusieurs milliers, et
la relecture devient impossible (vécu le 27/09/2026 en éprouvant un contrôle :
3 432 lignes). Éditer avec l'outil d'édition, ou en Python en lecture et écriture
binaires ; pour éprouver un contrôle, muter une copie. Vérifier après coup :
`git diff --stat`.

## Un nom par objet — celui de l'écran

Le manuel et le README nomment un écran, un onglet ou un bouton **comme l'écran le
montre** : les pages et leurs onglets dans `front/src/lib/pages.ts` et
`front/src/lib/pages-roles.ts`, un bouton dans son composant. Jamais un nom d'avant
un renommage, jamais un synonyme (#2971).

- **Un onglet d'Admin** s'écrit `Admin › Groupe › Onglet` — « Admin › Services ›
  Courriel », « Admin › Copropriété › Identité » —, ou `Admin › Onglet` quand le
  groupe n'aide pas. L'entrée **Admin** du menu ouvre la page *Paramétrage* : c'est
  « Admin » qui s'écrit dans un chemin. 🔒
  `test_chaque_chemin_d_admin_ecrit_nomme_un_onglet_que_le_front_range`
  (`api/tests/test_carte_reglages.py`) refuse un chemin dont le groupe ou l'onglet
  n'est pas rangé par `pages-roles.ts` — dans le manuel, le README, `docs/`,
  `deploiement/`, `.env.example` et `api/app`.
- **Un mot à deux sens** se déclare là où il sert. « Bailleur » : le profil est
  le *copropriétaire bailleur*, qui loue son lot ; dans le choix des destinataires,
  « Bailleurs » désigne ceux qui louent par délégation (agence, gestionnaire).
- **Renommer un onglet de l'interface** n'est pas un geste de documentation : les
  apps lisent `front/tables-clients.json`. Le manuel suit l'écran, pas l'inverse.

## La structure du manuel

```
docs/manuel-utilisateur.html
├── <head> : feuille de style (variables, gabarits, responsive)
├── <nav class="sidebar"> : la marge — logo de la résidence, liens vers
│     #intro #apropos #express #par-profil #ecrans #affaire #icones #aide
├── <header class="topbar"> : titre et lien vers le PDF (aucun numéro de version)
├── <main class="main">
│   ├── <section class="hero" id="intro">
│   ├── <section class="apropos" id="apropos"> : à quoi sert le site, pour qui
│   ├── <section class="quick-start" id="express"> : commencer, et le mini
│   │     sommaire par profil (#par-profil)
│   ├── <section class="chapter" id="ecrans"> : « Le menu, écran par écran » —
│   │     les deux maquettes du menu, puis une FICHE par écran (ci-dessous)
│   ├── <section class="chapter" id="affaire" data-section="tickets"> :
│   │     « Ouvrir une affaire » — catégories, pastille de lecture, sections du
│   │     formulaire, fusion, synthèse
│   ├── <section class="chapter" id="icones" data-section="tickets"> :
│   │     « Les icônes d'une carte »
│   ├── l'aide (#aide), « Un logiciel libre », l'application mobile
└── <footer class="doc-footer">
```

**Trois chapitres, pas un par écran.** Les écrans ne sont plus des chapitres
colorés (#651, 02/09/2026) : chacun est une fiche du chapitre `#ecrans`. Un écran
qui apparaît s'ajoute en fiche, jamais en chapitre. Les règles CSS
`.chapter[data-section="…"]` des anciens chapitres qui traînent dans la feuille de
style sont mortes : ne pas s'en servir de modèle.

### La fiche d'un écran — `ecran-card`

```html
<div class="ecran-card" data-page="/prestataires" data-acces="cs">
  <span class="ecran-icone" aria-hidden="true"><svg …/></span>
  <h3>Prestataires</h3>
  <p>Ce que l'écran permet, en une ou deux phrases.</p>
  <span class="ecran-acces ecran-acces-cs">Conseil syndical</span>
  <ul class="ecran-profils">
    <li data-onglet="kanban" data-reserve="nonLocataire"><span class="profil">Locataire</span> …</li>
  </ul>
  <details class="ecran-detail" name="en-savoir-plus">
    <summary>En savoir plus</summary>
    <div class="ecran-detail-corps"><ul><li><strong>Un geste</strong> — …</li></ul></div>
  </details>
</div>
```

| Attribut | Ce qu'il porte | Qui le lit |
|---|---|---|
| `data-page` | la route de l'entrée du menu (`href` de `pages.ts` / `pages-roles.ts`) ; `profil` pour Mon profil, sans route | `lint:manuel-menus` : une fiche par route, ni plus ni moins |
| `data-acces` | le public de l'entrée : `tous`, `cs`, `admin`, `resident`, `cs-ou-aidant` — collé à `data-page` | `lint:manuel-menus` : le public que `Nav.svelte` applique (`PUBLIC_ATTENDU`) |
| `data-onglet` + `data-reserve` | un onglet réservé : son `id` et la valeur `reserve:` de `pages.ts`, sur le `<li>` de `ecran-profils` | `lint:manuel-profils` : chaque onglet réservé est annoncé ; une réserve que la page applique elle-même se déclare dans `RESERVES_ECRITES_DANS_LA_PAGE` |

La classe `ecran-acces-<public>` colore l'étiquette ; elle suit `data-acces`.
Le détail d'un onglet se range dans `ecran-detail`, une puce par geste : son nom à
l'écran en gras, puis ce qu'il fait.

### Les autres structures lues par une machine

| Structure | Où | Qui la lit |
|---|---|---|
| `.maq-duo` : deux `<figure class="maq">`, des `maq-item`, le bouton `maq-burger` dessiné et sa `maq-explication` | `#ecrans`, les maquettes du menu | `lint:manuel-menus` : même nombre d'entrées dans les deux, dans l'ordre par défaut du code |
| `data-section-affaire` + `data-resident` (`obligatoire`, `facultatif`, `conseil`) | `#affaire`, la table des sections | `lint:manuel-profils` : l'ordre de `SECTIONS_ORDRE`, « conseil » là où `TICKET` éteint la section pour un résident ; le `<h3>` qui la précède dit leur nombre juste |
| `data-categorie` | `#affaire`, les catégories qu'un résident choisit | `lint:manuel-profils` : celles de `CATEGORIES_TICKET` sans `reserveCS` |
| `data-geste` | `#icones`, chaque icône d'une rangée d'actions | `lint:manuel-profils` : chaque `aria-label` d'`ActionsTicket` et `ActionsActualite` est documenté |
| `pastille-lecture-ex` + `data-lecture` + `title` | `#affaire`, la pastille de lecture | `test_manuel_pastilles_lecture.py` : la phrase au survol est recalculée par la règle servie, jamais écrite à la main ; un cas neuf s'ajoute dans `CAS` |
| `data-nom-residence` | l'en-tête de la marge et le pied de page | `front/e2e/manuel-nom-residence.spec.ts` : le nom servi remplace le texte |
| `<div class="sidebar-logo">` | la marge | `test_documentation.py` : le logo est `/api/config/logo.png`, jamais un dessin |

## Ce qui est vérifié mécaniquement — et ce qui ne l'est pas

| Contrôle | Ce qu'il refuse |
|---|---|
| `npm run lint:manuel-menus` | une route du menu sans fiche, une fiche sans route, un public faux, deux maquettes qui divergent ou ne suivent pas l'ordre par défaut |
| `npm run lint:manuel-profils` | un onglet réservé non annoncé, la table des sections ou des catégories qui diverge du code, une icône de carte non documentée — **et** un README qui énumère trois catégories ou plus, ou les compte (#1540) |
| `npm run lint:manuels` | un balisage mal formé, dans `docs/` comme dans `front/static/` |
| `npm run lint:manuel-volume` | un manuel, une section ou une carte d'écran au-dessus de son plafond de mots (`check-manuel-volume.regles.mjs`, qui ne fait que baisser : un texte qui maigrit baisse son plafond dans le même lot), une carte neuve sans plafond — arbitrage du 07/09/2026, #3008. Ajouter une phrase à une carte, c'est en retirer une autre |
| `npm run lint:pictogrammes` | 🚨 dans le manuel : l'urgence se dit ⚡ |
| `test_documentation.py` | les deux copies qui diffèrent, un numéro de version du manuel, un logo dessiné, les badges du README (Python, Node, CI) qui ne suivent plus l'image ni la CI |
| `test_manuel_ne_recopie_rien.py` | une valeur dont le code est la source : taille de fichier, nombre de pièces jointes, extensions, délai en jours, énumération de catégories |
| `test_liens_api_du_manuel.py` | un lien `/api/…` vers une route qui n'est pas montée |
| `test_manuel_pastilles_lecture.py` | une pastille dont la phrase n'est plus celle du site |
| `test_vocabulaire_affaire.py` | « ticket » là où l'écran dit « affaire » (README et manuel compris) |
| `test_carte_reglages.py` | un chemin `Admin › …` vers un onglet que `pages-roles.ts` ne range pas |
| `front/e2e/liens-manuel.spec.ts` | un lien interne du manuel vers une page qui ne répond pas |

Tous lisent des **attributs** ou des **formes précises**, jamais la prose : un
contrôle qui crie sur du texte légitime finit désarmé. Le **fond** — une phrase
décrit-elle encore l'écran ? — n'est vérifié par rien : il se relit, écran ouvert.

## Ce que le manuel n'écrit pas

- **Aucune valeur que le code tient** : ni taille, ni nombre, ni délai, ni liste
  de types ou de catégories (`test_manuel_ne_recopie_rien.py`). Il dit *où* le
  lecteur la trouve.
- **Aucune énumération recopiée d'une table** : les onglets d'un groupe d'Admin,
  les sources d'un import, les catégories. Une liste écrite à la main diverge au
  premier onglet ajouté (#2920) ; si elle est indispensable, elle passe par un
  attribut que `lint:manuel-profils` (ou un contrôle frère) confronte au code.
- **Aucune capture d'écran** : retirées le 02/09/2026 (#1038) — une capture périme
  au premier changement d'écran sans que personne s'en aperçoive.
- **Aucune pastille écrite en mots** : une pastille se montre telle que le site la
  rend (`pastille-lecture-ex` avec l'icône du catalogue `#lib/icones-svg.json`),
  sa phrase au survol calculée par le test (arbitré le 27/09/2026).

## Éléments de contenu

```html
<div class="callout info"><strong>ℹ️ Information</strong><p>…</p></div>
<!-- aussi : callout tip (💡), callout warning (⚠️), callout danger (🚫) -->

<ul class="steps">
  <li class="step"><span class="step-num" style="background:var(--c-ticket)">1</span>
    <div class="step-content"><strong>Action</strong><p>Explication.</p></div></li>
</ul>

<span class="pour-vous pour-vous-obligatoire">Obligatoire</span>  <!-- ou -facultatif, -conseil -->
```

Le détail qui ne sert qu'à qui le cherche se range dans `details.ecran-detail`
(`details.faq-item` existe dans la feuille de style, aucun chapitre ne l'emploie).

## Le README

- Une puce par entrée du menu et par capacité de premier niveau, sous son nom à
  l'écran ; le détail va au manuel.
- Jamais d'énumération ni de compte des catégories d'affaire : il renvoie au
  chapitre « Ouvrir une affaire » (`lint:manuel-profils`, #1540).
- L'installation locale s'écrit **une fois**, dans « Démarrage rapide » ;
  `CONTRIBUTING.md` y renvoie.

## Checklist

- [ ] Fiche `ecran-card` ajoutée ou modifiée — `data-page`, `data-acces`, et un
      `data-onglet` / `data-reserve` par onglet réservé
- [ ] Le geste décrit sous son nom à l'écran (`pages.ts`, `pages-roles.ts`, le composant)
- [ ] Aucune valeur ni liste recopiée du code
- [ ] README : la puce du module, si un module est ajouté, retiré ou renommé
- [ ] Copié : `cp docs/manuel-utilisateur.html front/static/manuel-utilisateur.html`
- [ ] `cd front && npm run lint:manuel-menus && npm run lint:manuel-profils && npm run lint:manuels`
- [ ] `cd api && pytest tests/test_documentation.py tests/test_manuel_ne_recopie_rien.py tests/test_liens_api_du_manuel.py tests/test_carte_reglages.py -q`
- [ ] `git diff --stat` : aucun fichier réécrit en entier
- [ ] Inclus dans le même commit que la fonctionnalité
