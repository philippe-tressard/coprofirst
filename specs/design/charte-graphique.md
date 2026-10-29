# Charte graphique

> Charte inspirée de l'identité de Croissy-sur-Seine : la Seine, les espaces verts, l'architecture résidentielle bourgeoise et le cadre de vie calme et qualitatif de la ville.

---

## Palette de couleurs

### Couleurs principales

| Nom             | Hexadécimal | RVB               | Usage                                        |
|-----------------|-------------|-------------------|----------------------------------------------|
| Bleu Seine      | `#1E3A5F`   | rgb(30, 58, 95)   | Couleur primaire — CTA, en-têtes, navigation |
| Vert Parc       | `#3D6B4F`   | rgb(61, 107, 79)  | Couleur secondaire — badges, succès, nature  |
| Or Croissy      | `#C9983A`   | rgb(201, 152, 58) | Accent — highlights, icônes actives, hover   |
| Pierre de taille| `#F2EFE9`   | rgb(242, 239, 233)| Fond principal — pages, arrière-plans clairs |
| Blanc Surface   | `#FFFFFF`   | rgb(255, 255, 255)| Cartes, modales, surfaces élevées            |

### Couleurs de texte

| Nom              | Hexadécimal | Usage                                 |
|------------------|-------------|---------------------------------------|
| Texte principal  | `#1A1A2E`   | Corps de texte, titres                |
| Texte secondaire | `#5A6070`   | Sous-titres, labels, placeholders     |
| Texte inversé    | `#F2EFE9`   | Texte sur fonds sombres               |

### Couleurs fonctionnelles

| Nom      | Hexadécimal | Usage                            |
|----------|-------------|----------------------------------|
| Succès   | `#2E7D52`   | Confirmation, validation         |
| Avertissement | `#B07D1E` | Alertes modérées, prudence    |
| Erreur   | `#C0392B`   | Erreurs, actions destructrices   |
| Info     | `#2563A6`   | Informations neutres             |

### Mode sombre (dark mode)

| Nom             | Hexadécimal | Usage                            |
|-----------------|-------------|----------------------------------|
| Fond sombre     | `#0D1B2A`   | Arrière-plan principal           |
| Surface sombre  | `#162236`   | Cartes, panneaux                 |
| Bord sombre     | `#2A3F5A`   | Séparateurs, bordures            |
| Texte clair     | `#E8E6E1`   | Corps de texte en mode sombre    |

Ces quatre valeurs sont le socle de la palette sombre complète — 85 jetons,
arbitrée sur maquette le 29/10/2026 (#2174, variante « bleu nuit ») — qui vit
dans `front/src/styles/palette-sombre.css`, et nulle part ailleurs. Elle
s'applique sous `<html data-theme="dark">` ; le choix Auto / Clair / Sombre
offert aux utilisateurs arrive avec le lot S5.

---

## Typographie

### Familles de polices

| Rôle       | Police                          | Source              | Justification                                                          |
|------------|---------------------------------|---------------------|------------------------------------------------------------------------|
| Titres     | **Georgia** *(+ Palatino)*      | Système natif       | Serif conçu pour l'écran, disponible sur Windows/macOS/Linux, sans CDN |
| Corps / UI | **Segoe UI** *(+ system-ui)*    | Système natif       | Sans-serif humaniste, natif Windows/macOS/Android, lisibilité optimale |
| Monospace  | **Consolas** *(+ Courier New)*  | Système natif       | Présent nativement sur Windows/macOS, excellent rendu à l'écran        |

### Échelle typographique

| Usage        | Police           | Taille desktop (rem) | Taille mobile (rem) | Graisse | Interligne |
|--------------|------------------|----------------------|---------------------|---------|------------|
| Titre H1     | Georgia          | 2.5 rem              | 1.75 rem            | 700     | 1.2        |
| Titre H2     | Georgia          | 1.875 rem            | 1.375 rem           | 600     | 1.25       |
| Titre H3     | Georgia          | 1.375 rem            | 1.125 rem           | 600     | 1.3        |
| Sous-titre   | Segoe UI         | 1.125 rem            | 1 rem               | 500     | 1.4        |
| Corps texte  | Segoe UI         | 1 rem (16 px)        | 0.875 rem (14 px)   | 400     | 1.6        |
| Légende      | Segoe UI         | 0.875 rem            | 0.8 rem             | 400     | 1.5        |
| Label / Chip | Segoe UI         | 0.75 rem             | 0.75 rem            | 500     | 1.4        |

> **Mobile** : `font-size: 14px` appliqué sur `:root` en dessous de 768 px (via media query dans `app.css`), ce qui réduit proportionnellement toute l'échelle.

### Règles typographiques

- Pas de texte en dessous de 12 px pour l'accessibilité (WCAG 2.2).
- Contraste texte/fond ≥ 4.5:1 (normal) et ≥ 3:1 (grand texte).
- Éviter les lignes de texte dépassant 75 caractères (lisibilité optimale).
- Les titres utilisent exclusivement Georgia (serif système) ; l'UI (boutons, champs, menus) utilise Segoe UI / system-ui.

---

## Iconographie

### Principe général

Les icônes d'action de l'interface (boutons dans les tableaux, listes et formulaires) utilisent des **emojis Unicode natifs** — aucune bibliothèque SVG externe n'est requise pour cet usage. Ce choix garantit zéro dépendance, un rendu immédiat et une compatibilité universelle.

Pour des icônes illustratives ou décoratives (feature icons, illustrations), [Lucide Icons](https://lucide.dev/) reste la référence (trait outline 1.5 px, tailles 16/20/24/32 px).

### Classes CSS globales — boutons icône (`app.css`)

Cinq classes sont définies globalement dans `front/src/app.css` :

| Classe | Couleur repos | Hover | Usage sémantique |
|---|---|---|---|
| `.btn-icon` | texte courant | fond gris `#f3f4f6` | Action neutre |
| `.btn-icon-edit` | texte courant | fond gris `#f3f4f6` | Modification / édition |
| `.btn-icon-danger` | texte courant | fond rouge `#fee2e2`, texte `--color-danger` | Action destructrice irréversible |
| `.btn-icon-warn` | ambre `#d97706` | fond ambre `#fef3c7` | Action réversible / avertissement |
| `.btn-icon-success` | `--color-success` | fond vert `#e6f4ee` | Action positive / activation |

Toutes partagent : `background: transparent; border: none; cursor: pointer; font-size: .9rem; padding: .25rem; border-radius: var(--radius); line-height: 1;`

### Icônes d'action standardisées

| Action | Icône | Classe | Notes |
|---|---|---|---|
| Modifier | ✏️ | `.btn-icon-edit` | Ouvre un formulaire d'édition |
| Supprimer | 🗑️ | `.btn-icon-danger` | Action destructrice irréversible |
| Ignorer / Écarter | ⊘ | `.btn-icon-warn` | Écarte une ligne sans la supprimer (réversible) |
| Remettre en attente | ↩️ | `.btn-icon-success` | Remet une ligne ignorée en statut "en attente" |
| Stopper | ⏹️ | `.btn-icon-warn` | Clôture un sondage ou processus en cours |
| Masquer | 🙈 | `.btn-icon-warn` | Bascule visible → caché |
| Afficher | 👁️ | `.btn-icon-edit` | Bascule caché → visible |
| Interdire | 🔒 | `.btn-icon-warn` | Bascule autorisé → interdit |
| Autoriser | 🔓 | `.btn-icon-success` | Bascule interdit → autorisé |

> **Règle de cohérence :** les paires d'icônes à bascule doivent être visuellement opposées (🙈/👁️, 🔒/🔓) pour signifier clairement l'état courant et l'action disponible.

### Icônes de contexte (badges inline)

| Concept | Icône | Classe badge | Exemple |
|---|---|---|---|
| Lieu physique (adresse) | 📍 | — (texte inline) | `📍 66 route de Sartrouville – Bâtiment 4` |
| Périmètre logique (zone) | 🔹 | `.badge-gray` ou `.badge-blue` | `🔹 Parking` · `🔹 Bât. 1` |

> **Règle :** ne jamais utiliser `📍` pour un périmètre. `📍` = lieu géographique, `🔹` = périmètre / zone de la résidence.

### Accessibilité des boutons icône

Tout bouton ne contenant qu'une icône (sans libellé textuel visible) **doit** porter :
- `aria-label="[Action] [complément contextuel]"` — lu par les lecteurs d'écran
- `title="[Action]"` — infobulle au survol

Exemple :
```svelte
<button class="btn-icon-danger" aria-label="Supprimer cette actualité" title="Supprimer"
  on:click={() => supprimer(item.id)}>🗑️</button>
```

### Convention d'encodage des emojis (OBLIGATOIRE)

Les caractères Unicode hors BMP (U+10000+, ex : 🔹🛠️🏠📰🗑️) sont encodés sur 4 octets UTF-8 et se corrompent systématiquement en U+FFFD lors des éditions par certains outils. Pour éviter ce problème, **tous les emojis non-BMP sont encodés en escape sequences ASCII-safe** :

| Contexte | Format | Exemple |
|---|---|---|
| JS / Svelte `<script>` / `.ts` | `\u{HEX}` (ES6 escape) | `'\u{1F6E0}️ Panne'` |
| Template Svelte (partie HTML) | `&#xHEX;` (entité HTML) | `&#x1F539; Parking` |
| Fichier `.html` (manuel, static) | `&#xHEX;` (entité HTML) | `&#x1F3E0;` |

> **Emojis BMP** (U+0000–U+FFFF, ex : ✏️ ❓ ⚠️ ✅) peuvent rester en littéral car encodés sur ≤3 octets, sans risque de corruption.

**Outils à la racine du projet :**
- `fix_emoji_encoding.py` — conversion automatique de tous les non-BMP
- `check_emoji.py` — vérification (exit 1 si non-BMP ou U+FFFD détecté)

### Icônes interdites

- Images bitmap (PNG/JPG) pour les icônes d'action.
- Caractères typographiques détournés (×, ✗, ✕) comme icônes de suppression — utiliser 🗑️ ou ⊘ selon la sémantique.
- **Emojis non-BMP en littéral dans les fichiers sources** — utiliser les escape sequences ci-dessus.

---

## Espacement et grille

- **Unité de base :** 4 px (grille au pas de 4).
- **Espacements courants :** 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px.
- **Rayons de bordure (border-radius) :**
  - Petits éléments (chips, badges) : 4 px
  - Boutons, champs : 8 px
  - Cartes : 12 px
  - Modales / panels : 16 px
- **Ombres :**
  - Légère : `0 1px 3px rgba(30,58,95,0.10)`
  - Carte : `0 4px 12px rgba(30,58,95,0.12)`
  - Modale : `0 8px 32px rgba(30,58,95,0.18)`

---

## Composants UI — directives

| Composant   | Primaire                              | État hover / actif                 |
|-------------|---------------------------------------|------------------------------------|
| Bouton CTA  | Fond `#1E3A5F`, texte blanc, r=8px    | Fond `#16304F`, ombre légère       |
| Bouton secondaire | Bordure `#1E3A5F`, texte `#1E3A5F` | Fond `#EEF2F7`                |
| Lien        | Couleur `#1E3A5F`, souligné au hover  | `#C9983A`                          |
| Badge succès | Fond `#E6F4EE`, texte `#2E7D52`      | —                                  |
| Badge alerte | Fond `#FDF3E0`, texte `#B07D1E`      | —                                  |
| Badge erreur | Fond `#FDEDEC`, texte `#C0392B`      | —                                  |

### Pattern : Pill buttons (sélection multiple ou exclusive)

**Quand l'utiliser** : chaque fois qu'un champ de formulaire propose un choix exclusif ou multiple parmi un petit ensemble d'options bien identifiées (périmètre, type, localisation, filtre…). À préférer aux `<select>`, `radio`, ou checkboxes en colonne lorsque les options sont ≤ 8 et les libellés courts.

**Comportement :**
- Sélection exclusive (1 seul actif) : cliquer sur un pill désactive l'ancien et active le nouveau.
- Sélection multiple (toggle) : cliquer active / désactive le pill ; si aucun n'est sélectionné, revenir à l'option par défaut.

**CSS de référence (variables du design system) :**
```css
.perimetre-pills {
  display: flex;
  flex-wrap: wrap;
  gap: .4rem;
  margin-top: .4rem;
}
.pill {
  padding: .3rem .85rem;
  border-radius: 999px;
  border: 1.5px solid var(--color-border);
  background: var(--color-bg);
  font-size: .85rem;
  cursor: pointer;
  transition: background .15s, border-color .15s, color .15s;
  white-space: nowrap;
  line-height: 1.6;
}
.pill:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.pill-active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
```

**Exemple Svelte — sélection multiple avec retour à "Copropriété entière" :**
```svelte
<div class="perimetre-pills">
  <button type="button" class="pill" class:pill-active={formPerimetre === 'résidence'}
    on:click={() => { formPerimetre = 'résidence'; formLieux = new Set(); }}>
    🏘️ Copropriété entière
  </button>
  {#each [['bat:1','Bât. 1'],['bat:2','Bât. 2'],['bat:3','Bât. 3'],['bat:4','Bât. 4'],['parking','Parking'],['cave','Cave']] as [val, lbl]}
    <button type="button" class="pill" class:pill-active={formLieux.has(val)}
      on:click={() => {
        if (formLieux.has(val)) { formLieux.delete(val); } else { formLieux.add(val); }
        formLieux = formLieux;
        formPerimetre = formLieux.size > 0 ? 'specifique' : 'résidence';
      }}>
      {lbl}
    </button>
  {/each}
</div>
```

**Règles :**
- `white-space: nowrap` obligatoire — aucun libellé ne doit couper en deux lignes.
- Sur mobile, le `flex-wrap` permet le passage à la ligne entre pills, jamais à l'intérieur.
- Un pill actif porte toujours `class:pill-active`, jamais un style inline.
- Le label du champ doit suivre la règle générale : obligatoire → suivi de ` *`.

---

### Pattern : Carte expansible au clic (expand-on-click)

**Quand l'utiliser** : liste de résumés cliquables où l'utilisateur peut lire le détail sans quitter la page — actualités, événements, demandes, FAQ, notifications… À préférer à une navigation vers une page dédiée quand le contenu détaillé est court et que le contexte de liste doit rester visible.

**Comportement :**
- État replié : en-tête (titre + métadonnée courte) + indicateur "▼ Détails" / "▼ Lire la suite".
- Clic sur la carte → expansion in-place, bordure colorée (`var(--color-primary)`), indicateur "▲ Réduire".
- Second clic → repli.
- Plusieurs cartes peuvent être ouvertes simultanément (Set indépendant par type de contenu).
- Les actions secondaires dans le détail (ex. "Voir le calendrier") portent `on:click|stopPropagation` pour ne pas déclencher le toggle.

**État JS (Svelte) :**
```typescript
let expandedItems = new Set<number>();
function toggleItem(id: number) {
  if (expandedItems.has(id)) expandedItems.delete(id);
  else expandedItems.add(id);
  expandedItems = expandedItems; // trigger reactivity
}
```

**Template Svelte :**
```svelte
{#each items as item}
  <div
    class="item-card card"
    class:expanded={expandedItems.has(item.id)}
    role="button"
    tabindex="0"
    on:click={() => toggleItem(item.id)}
    on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleItem(item.id)}
  >
    <!-- En-tête toujours visible -->
    <div class="item-header">
      <strong class="item-titre">{item.titre}</strong>
      <small class="item-meta">{formatDate(item.date)}</small>
    </div>

    <!-- Détail conditionnel -->
    {#if expandedItems.has(item.id)}
      <div class="item-detail">
        <!-- contenu détaillé, liens secondaires avec stopPropagation -->
        <a href="/page#item-{item.id}" on:click|stopPropagation>Voir la page complète</a>
      </div>
    {/if}

    <span class="item-toggle">{expandedItems.has(item.id) ? '▲ Réduire' : '▼ Détails'}</span>
  </div>
{/each}
```

**CSS de référence :**
```css
.item-card {
  margin-bottom: .5rem;
  border-left: 3px solid var(--color-border);
  cursor: pointer;
  transition: border-color .12s;
}
.item-card:hover  { border-color: var(--color-primary); }
.item-card.expanded { border-color: var(--color-primary); }
.item-header { display: flex; justify-content: space-between; align-items: baseline; gap: .5rem; }
.item-titre  { font-size: .95rem; font-weight: 600; }
.item-meta   { font-size: .8rem; color: var(--color-text-muted); white-space: nowrap; }
.item-detail { margin-top: .5rem; font-size: .85rem; color: var(--color-text-muted);
               display: flex; flex-direction: column; gap: .2rem; }
.item-toggle { font-size: .75rem; color: var(--color-primary); display: block; margin-top: .3rem; }
```

**Règles :**
- Nommer le Set selon le type de contenu : `expandedPubs`, `expandedEvs`, `expandedTickets`…
- Le `role="button"` + `tabindex="0"` + handler `keydown` sont obligatoires pour l'accessibilité clavier (WCAG 2.2).
- Ne jamais utiliser `<a>` comme conteneur principal du toggle — utiliser `<div role="button">` pour éviter les conflits de navigation.
- Les liens internes dans le détail utilisent toujours `on:click|stopPropagation`.
- **Date de publication** : toujours afficher un libellé textuel. Format uniforme : `Publié le DD/MM/YYYY` ou `Mise à jour le DD/MM/YYYY` si le champ `mis_a_jour_le` est renseigné. Ne jamais afficher une date brute sans contexte (`10/03/2026` seul est interdit).
- **Footer d'une carte expansée** : le bouton d'action (« Voir l'actualité », « Voir le calendrier »…) et la date sont placés sur la même ligne dans un conteneur `display:flex; align-items:center; gap:.75rem`. Le bouton est à gauche, la date (`<small class="pub-date">`) à droite.
- **Implémenté dans** : `tableau-de-bord/+page.svelte` (actualités récentes, événements récents).

---

## Logotype

- **Le logo est celui de la RÉSIDENCE** : il se téléverse dans *Admin › Paramétrage site* (PNG ou JPEG, carré, 512 px), et le site en dérive le menu, l'écran de connexion, l'onglet, l'icône de l'application installée, les documents et les courriels (#1728). Sans logo, le logo neutre de CoproFirst : trois immeubles en Bleu Seine, une fenêtre allumée et la ligne de sol en Or Croissy, sur une tuile blanche arrondie — lisible sur les en-têtes bleu marine des documents. Son dessin vit dans `front/static/favicon.svg` (copie `api/app/utils/logo-neutre.svg`), et ses rendus PNG en dérivent (#1774). Ces fichiers ne sont **pas** sous l'AGPL : licence d'usage propre, `LICENSES/LicenseRef-CoproFirst-Logo.txt`, déclarée dans `REUSE.toml` (`MARQUE.md` §5).
- **Celui de 5Hostachy** (08/10/2026) : un immeuble au trait bleu marine sur fond blanc, une fenêtre et le sol dorés — sobre et institutionnel.
- **Nom affiché :** « 5Hostachy » ou « Résidence du Parc »
- **Déclinaisons à produire :**
  - Logo couleur fond clair (`.svg`, `.png` @1x / @2x / @3x)
  - Logo couleur fond sombre (`.svg`, `.png` @1x / @2x / @3x)
  - Favicon (`.ico`, 16×16, 32×32, `.svg`)
  - Icône PWA (192×192 px, 512×512 px)
- **Zone de protection :** espace libre ≥ hauteur de la lettre « H » du logotype sur chaque côté.
- **Usages interdits :** déformation, rotation, changement de couleurs hors palette, ajout d'effets (ombre portée, dégradé).

---

## Accessibilité et contrastes

| Combinaison                          | Ratio    | WCAG AA | WCAG AAA |
|--------------------------------------|----------|---------|----------|
| Texte `#1A1A2E` sur `#F2EFE9`        | ≥ 12:1   | ✅       | ✅        |
| Texte `#1A1A2E` sur `#FFFFFF`        | ≥ 14:1   | ✅       | ✅        |
| Texte blanc sur `#1E3A5F`            | ≥ 8.5:1  | ✅       | ✅        |
| Texte blanc sur `#3D6B4F`            | ≥ 5.5:1  | ✅       | ✅        |
| Texte `#1A1A2E` sur `#C9983A`        | ≈ 4.6:1  | ✅       | ❌        |
| Texte `#5A6070` sur `#F2EFE9`        | ≈ 5.2:1  | ✅       | ❌        |

> Vérification outillée recommandée : [Colour Contrast Analyser](https://www.tpgi.com/color-contrast-checker/) ou extension axe DevTools.

---

## Références d'inspiration

- Identité visuelle de Croissy-sur-Seine : blanche, verte, institutionnelle.
- Seine-et-Yvelines : sobriété, qualité résidentielle.
- Applications de gestion d'immeuble de référence : Matera, Syndic.fr — épurées, rassurantes.
- Mouvement design : Material Design 3 (tokens, accessibilité) et French Government Design System (DSFR) pour l'aspect institutionnel.

---

## Conventions UI (implémentées)

### Champs de formulaire

| Règle | Implémentation |
|-------|---------------|
| Champ **obligatoire** | Label suivi de ` *` (ex : `Nom *`) |
| Champ **facultatif** | Label seul, sans mention (ex : `Téléphone`) |
| Ne jamais écrire "(optionnel)" | Tout ce qui n'a pas `*` est implicitement optionnel |

```svelte
<label for="nom">Nom *</label>
<label for="tel">Téléphone</label>
```

### Texte enrichi (WYSIWYG)

Tous les champs de saisie longue (contenus, descriptions, réponses, notes) **autres qu'un titre monoligne** utilisent le composant `<RichEditor>` basé sur TipTap.

- **Saisie** : composant `src/lib/components/RichEditor.svelte`
- **Stockage** : HTML (`<p>`, `<ul>`, `<strong>`…)
- **Affichage** : `{@html valeur}` enveloppé dans `<div class="rich-content">`

Champs concernés : Contenu/Actualités, Réponse/FAQ, Description/Tickets, Description/Calendrier, Description/Sondages, Notes/Prestataires, Notes/Baux, Motif/demandes.

### Ordre des boutons dans les formulaires

Règle universelle (DSFR, Material Design, macOS HIG) :

```
[ Annuler ]   [ Action principale ]
 secondaire        primaire
```

- Le bouton **Annuler / secondaire** est toujours **à gauche**.
- L'**action principale** (Enregistrer, Envoyer, Valider…) est **à droite**.
- Le groupe est aligné **à droite** du formulaire via `.form-actions`.
- Dans les **modales**, même règle : `[Annuler]` en premier, action destructrice ou de validation à droite.

```html
<div class="form-actions">
  <button type="button" class="btn btn-outline" on:click={annuler}>Annuler</button>
  <button type="submit" class="btn btn-primary">Enregistrer</button>
</div>
```

```css
/* app.css */
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: .5rem;
  margin-top: .75rem;
}
```

> **Exception** : les boutons bascule en en-tête de section (`showForm = !showForm`) affichent « Annuler » ou « + Ajouter » selon l'état — ce sont des toggles, pas des actions de formulaire, ils restent à leur position dans le header.
