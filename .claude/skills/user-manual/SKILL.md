---
name: user-manual
description: "Update the 5Hostachy user-facing documentation — manuel-utilisateur.html AND README.md — when a feature is added, modified or removed. Use when: adding a new feature visible to users, modifying UI behavior, adding or removing a page, screen or module, updating navigation or workflows. Do NOT use for purely technical changes (migrations, refactor, backend-only security)."
argument-hint: "Describe the feature to document (e.g. 'new fournisseurs page with list and detail')"
---

# Documentation utilisateur — 5Hostachy

**DEUX documents, pas un.** Cette skill couvre `docs/manuel-utilisateur.html`
(synchronisé vers `front/static/`) **et** `README.md`. Ils sont de **même rang** :
un changement visible se répercute dans les deux quand il touche les deux.

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
> le manuel, alors que le point **0e** du pré-check dit « README · manuel ·
> `specs/` » depuis toujours. Deux listes ont divergé, et c'est la plus courte qui
> a été suivie. Signalé par l'utilisateur.

## Règle obligatoire

Toute modification UX ou fonctionnalité visible **doit** être documentée dans le
**même commit** que la fonctionnalité. Après modification du manuel :

```powershell
Copy-Item docs/manuel-utilisateur.html front/static/manuel-utilisateur.html
```

(depuis la racine du dépôt — **un seul chemin**, le même que dans la checklist
ci-dessous ; `api/tests/test_documentation.py` échoue si les deux copies diffèrent)

⚠️ **Ne jamais éditer le manuel avec `sed -i`** : il est versionné en **CRLF**, et
`sed` le réécrit en LF — le diff passe alors de 3 lignes à 5 700, et la
relecture devient impossible. Vérifier après coup : `git diff --stat`.

Ce qui est vérifié **mécaniquement** (`api/tests/test_documentation.py`) : la
synchronisation `docs/` ⇆ `front/static/` et les badges du README (Python, Node,
CI). Le **fond** des deux documents reste à relire — aucun test ne sait dire si
une phrase décrit encore l'application.

## Structure du document

```
docs/manuel-utilisateur.html
├── <head> : CSS variables, styles, responsive
├── <nav class="sidebar"> : Navigation latérale sticky
├── <header class="topbar"> : Titre + lien PDF (aucun badge de version, 23/10/2026)
├── <main class="main">
│   ├── <section class="hero"> : Introduction
│   └── <section class="chapter" id="..." data-section="..."> : Chapitres
└── <footer class="doc-footer"> : Copyright
```

## Ajouter un nouveau chapitre

### 1. Définir la couleur dans `:root`

```css
--c-nouveau: #hexcolor;
```

### 2. Ajouter le lien dans la sidebar

Le point de couleur est un `<span class="dot">` dont la couleur se pose **en ligne**
— il n'existe aucune classe `nav-dot-*` :

```html
<div class="nav-section">
  <a class="nav-item" href="#nouveau">
    <span class="dot" style="background:var(--c-nouveau)"></span>
    Nouveau Chapitre
  </a>
</div>
```

### 3. Ajouter le style de la card (border-top)

```css
.chapter[data-section="nouveau"] .card { border-top: 3px solid var(--c-nouveau); }
```

### 4. Créer la section dans `<main>`

```html
<section class="chapter" id="nouveau" data-section="nouveau">
  <div class="chapter-header">
    <div class="chapter-icon" style="background:#eef6ff; color:var(--c-nouveau)">
      🆕
    </div>
    <div>
      <h2>Titre du chapitre</h2>
      <p>Description courte du chapitre.</p>
    </div>
  </div>

  <div class="card">
    <h3>Sous-section</h3>
    <ul class="steps">
      <li class="step">
        <span class="step-num" style="background:var(--c-nouveau)">1</span>
        <div class="step-content">
          <strong>Titre de l'étape</strong>
          <p>Description détaillée de l'étape.</p>
        </div>
      </li>
      <li class="step">
        <span class="step-num" style="background:var(--c-nouveau)">2</span>
        <div class="step-content">
          <strong>Étape suivante</strong>
          <p>Description.</p>
        </div>
      </li>
    </ul>
  </div>
</section>
```

## Éléments de contenu disponibles

### Card (bloc principal)

```html
<div class="card">
  <h3>Titre de la card</h3>
  <p>Contenu texte...</p>
</div>
```

### Étapes numérotées

```html
<ul class="steps">
  <li class="step">
    <span class="step-num" style="background:var(--c-nouveau)">1</span>
    <div class="step-content">
      <strong>Action à effectuer</strong>
      <p>Explication détaillée.</p>
    </div>
  </li>
</ul>
```

### Captures d'écran — il n'y en a plus

Elles ont été **retirées le 02/09/2026** (#1038) : `docs/img/` n'existe plus, et une
capture périme au premier changement d'écran sans que personne s'en aperçoive. Le
manuel **décrit** les écrans ; il ne les montre pas. Aucun gabarit `capture-*` n'est
à écrire — ces classes n'existent pas dans le manuel.

### Callouts (info, tip, warning, danger)

```html
<div class="callout info">
  <strong>ℹ️ Information</strong>
  <p>Texte informatif.</p>
</div>

<div class="callout tip">
  <strong>💡 Astuce</strong>
  <p>Conseil utile.</p>
</div>

<div class="callout warning">
  <strong>⚠️ Attention</strong>
  <p>Point de vigilance.</p>
</div>

<div class="callout danger">
  <strong>🚫 Important</strong>
  <p>Risque ou interdiction.</p>
</div>
```

### Étiquettes — « pour vous » et accès

Il n'y a pas de composant « badge de statut » : le manuel emploie deux étiquettes,
dans la table des sections d'une affaire et dans la fiche d'un écran.

```html
<span class="pour-vous pour-vous-obligatoire">Obligatoire</span>   <!-- ou -facultatif, -conseil -->
<ul class="ecran-profils">
  <li><span class="profil">Chacun</span> n’y voit que ce que son profil lui ouvre…</li>
</ul>
```

### Montrer une pastille du site — la VRAIE, jamais un mot (27/09/2026)

Arbitré à l'écran : le manuel nommait « la pastille bleue » en texte brut, et le
survoler ne montrait rien. Une pastille se montre telle que le site la rend —
`<span class="pastille-lecture-ex" data-lecture="…" title="…">` avec l'icône SVG
du catalogue (`#lib/icones-svg.json`) — et sa phrase au survol n'est **jamais
écrite à la main** : `npm run lint:manuel-pastilles` la recalcule avec `#lib/lecture`
et refuse tout écart. Un nouveau cas s'ajoute dans `CAS` du contrôle.

⚠️ Pour éprouver un contrôle sur le manuel, **ne jamais le muter par `sed -i`** :
il réécrit le CRLF en LF (vécu le 27/09/2026, 3 432 lignes de diff). Muter en
octets, ou sur une copie.

### Accordéon

Le détail qui ne sert qu'à qui le cherche se range dans un `<details>` — la forme
employée par les fiches d'écran du manuel :

```html
<details class="ecran-detail">
  <summary>En savoir plus</summary>
  <div class="ecran-detail-corps">
    <ul><li>Détail…</li></ul>
  </div>
</details>
```

(`details.faq-item` est défini dans la feuille de style, mais aucun chapitre ne
l'emploie aujourd'hui : préférer `ecran-detail`, déjà éprouvé.)

## Couleurs des sections existantes

| Section | Variable CSS | Couleur | Emoji |
|---------|-------------|---------|-------|
| Connexion | `--c-login` | `#7c3aed` | 🔐 |
| Mes lots | `--c-lot` | `#0284c7` | 🏠 |
| Tickets | `--c-ticket` | `#ea580c` | 🎫 |
| Actualités | `--c-news` | `#059669` | 📰 |
| Calendrier | `--c-cal` | `#4f46e5` | 📅 |
| Badges | `--c-badges` | `#dc2626` | 🔴 |
| FAQ | `--c-faq` | `#0f766e` | ❓ |
| Résidence | `--c-residence` | `#0f766e` | 🏢 |
| Annuaire | `--c-annuaire` | `#0369a1` | 📇 |
| Profil | `--c-profil` | `#6d28d9` | 👤 |
| Prestataires | `--c-presta` | `#b45309` | 🔧 |
| ~~Délégation~~ | `--c-delegation` | `#d97706` | 🤝 |

⚠️ **La ligne « Délégation » est barrée** : la variable de couleur existe, mais
aucune `data-section="delegation"` n'est rendue — le manuel n'a pas de chapitre de
délégation. Une table de sections qui annonce une section absente fait chercher un
écran qui n'existe pas (#1051).

## Checklist

- [ ] Chapitre ajouté/modifié dans `docs/manuel-utilisateur.html`
- [ ] Couleur CSS ajoutée si nouveau chapitre
- [ ] Lien sidebar ajouté si nouveau chapitre
- [ ] Style `.chapter[data-section="..."] .card` ajouté si nouveau chapitre
- [ ] Étapes numérotées pour les workflows
- [ ] Callouts pour les points importants
- [ ] Synchronisé : `Copy-Item docs/manuel-utilisateur.html front/static/manuel-utilisateur.html`
- [ ] Inclus dans le même commit que la fonctionnalité
