<!-- GÉNÉRÉ par `python scripts/ci/licences_tierces.py --ecrire` — ne pas éditer. -->

# Licences tierces

Inventaire des dépendances de `front/`, `whatsapp-bridge/` et `api/` et de leurs
licences (`standards/14` §6.3), puis des fichiers repris d'un projet tiers. La CI
le régénère et échoue s'il diffère : un paquet qui entre ou qui change de licence
se relit ici. La politique — liste blanche, exceptions et leurs motifs — vit dans
`scripts/ci/licences_politique.py`.

> ⚠️ Ce document constate, il ne tranche rien de juridique. Les exceptions
> ci-dessous sont des questions posées par écrit ; leur statut dit lesquelles
> restent à valider par l'auteur — aucune depuis le passage du projet à
> l'AGPL-3.0-or-later (08/10/2026, #1726), dont l'analyse a été validée.

## Exceptions déclarées

| Source | Paquets | Licence | Motif | Statut |
|---|---|---|---|---|
| whatsapp-bridge | `libsignal` | `GPL-3.0` | Protocole de chiffrement Signal, tiré par `baileys` (seule bibliothèque WhatsApp Web maintenue de l'écosystème Node), non substituable. Copyleft fort. Il s'exécute dans le bridge, conteneur distinct de l'API et du front, avec lesquels il ne communique que par HTTP. | compatible avec l'AGPL-3.0-or-later (la GPLv3 et l'AGPLv3 se combinent l'une avec l'autre (§13 de chacune) ; programme distinct, joint par HTTP) — analyse du 08/10/2026, validée par l'auteur |
| whatsapp-bridge | `@img/sharp-libvips-*`, `@img/sharp-win32-*`, `@img/sharp-wasm32` | `LGPL-3.0-or-later`<br>`Apache-2.0 AND LGPL-3.0-or-later`<br>`Apache-2.0 AND LGPL-3.0-or-later AND MIT` | Binaires de libvips embarqués par `sharp`, dépendance pair de `baileys` (traitement d'images). Copyleft faible ; une seule variante de plateforme est installée dans l'image (Linux musl). Même conteneur que libsignal. | compatible avec l'AGPL-3.0-or-later (la LGPL-3.0-or-later l'est par construction) — analyse du 08/10/2026, validée par l'auteur |
| front | `caniuse-lite` | `CC-BY-4.0` | Table de compatibilité des navigateurs lue par `browserslist` au moment de la construction (devDependencies). Licence de données, qui demande l'attribution. | compatible avec l'AGPL-3.0-or-later (la CC-BY-4.0 est compatible avec la GPLv3 ; outil de construction, non distribué ; attribution portée par cet inventaire) — analyse du 08/10/2026, validée par l'auteur |
| front | `lightningcss`, `lightningcss-*` | `MPL-2.0` | Minifieur CSS de Vite 8 (#2205), dépendance directe de `vite` : il n'est pas substituable sans quitter la chaîne de construction. Copyleft faible au niveau du fichier ; utilisé sans modification. Les binaires de plateforme (un par système) sont des paquets optionnels, dont un seul est installé. | compatible avec l'AGPL-3.0-or-later (la MPL-2.0 admet la GPL et l'AGPL comme « Secondary Licenses » ; outil de construction, présent dans node_modules de l'image sans être modifié) — analyse du 08/10/2026, validée par l'auteur |
| api | `psycopg`, `psycopg-binary` | `LGPL-3.0-only` | Pilote PostgreSQL (DI-7, #1759 ; tests depuis P2-5, #1747), employé tel quel par SQLAlchemy. Copyleft faible ; les roues binaires embarquent libpq (licence PostgreSQL) et ses dépendances. Seul pilote qui rend une clé violée en `IntegrityError` — pg8000, sous BSD, ne le faisait pas. | compatible avec l'AGPL-3.0-or-later (la LGPL-3.0 permet l'usage d'une bibliothèque par une œuvre sous GPLv3 ou AGPLv3 (§4 et §5 de la LGPL), qui la distribue avec sa licence et son source) — analyse du 08/10/2026, validée par l'auteur |
| api | `certifi` | `MPL-2.0` | Magasin de certificats racine (tiré par httpx). Copyleft faible au niveau du fichier ; utilisé sans modification. | compatible avec l'AGPL-3.0-or-later (la MPL-2.0 admet la GPL et l'AGPL comme « Secondary Licenses ») — analyse du 08/10/2026, validée par l'auteur |
| api | `pyphen` | `GPL-2.0-or-later \| LGPL-2.0-or-later \| MPL-1.1 (classifieurs multiples)` | Césure des mots, tirée par WeasyPrint (documents PDF). Le paquet se dit « GPL 2.0+/LGPL 2.1+/MPL 1.1 tri-license » (fichier LICENSE installé) ; ses dictionnaires viennent de LibreOffice sous GPL, LGPL et/ou MPL. | compatible avec l'AGPL-3.0-or-later (par son option GPL-2.0-or-later ou LGPL-2.1-or-later) — analyse du 08/10/2026, validée par l'auteur |
| api | `dkimpy` | `BSD-like` | Vérification DKIM des réponses par courriel. Les métadonnées disent « BSD-like » ; le fichier LICENSE installé porte le texte de la licence zlib, qui est permissive. | métadonnées imprécises — le texte installé est celui de la licence zlib |

## Fichiers repris d'un projet tiers

| Contenu | Licences | Fichiers | Origine et remarques |
|---|---|---|---|
| Lucide | ISC AND MIT | `front/src/lib/icones-svg.json`<br>`api/app/utils/icones-svg.json`<br>`docs/manuel-utilisateur.html`<br>`front/static/manuel-utilisateur.html`<br>`infra/cloudflare-worker.js` | https://lucide.dev — tracés recopiés à la main, aucune dépendance npm. ISC pour Lucide ; MIT pour les icônes dérivées de Feather (Cole Bemis), dont la licence de Lucide donne la liste — `calendar`, `clock`, `lock`, `search`, `trash-2`… en font partie. |
| Simple Icons — logo WhatsApp | CC0-1.0 | `front/src/lib/icones-svg.json`<br>`api/app/utils/icones-svg.json` | https://simpleicons.org — tracé de l'icône `whatsapp`. Le TRACÉ est versé au domaine public (CC0-1.0), mais CC0 ne cède aucun droit de marque : le logo reste une marque de son titulaire. Son usage pour désigner le canal WhatsApp de la résidence est À VALIDER par l'auteur. |

Icônes de `front/src/lib/icones-svg.json` qui ne viennent pas de Lucide — `stairs` : absente de Lucide — présumée dessinée pour le projet, à confirmer par l'auteur; `whatsapp` : Simple Icons.

## Dépendances — `front` (569 paquets)

| Paquet | Licence | Déclaré | Admise |
|---|---|---|---|
| `@apideck/better-ajv-errors` | `MIT` | devDependencies | oui |
| `@babel/code-frame` | `MIT` | devDependencies | oui |
| `@babel/compat-data` | `MIT` | devDependencies | oui |
| `@babel/core` | `MIT` | devDependencies | oui |
| `@babel/generator` | `MIT` | devDependencies | oui |
| `@babel/helper-annotate-as-pure` | `MIT` | devDependencies | oui |
| `@babel/helper-compilation-targets` | `MIT` | devDependencies | oui |
| `@babel/helper-create-class-features-plugin` | `MIT` | devDependencies | oui |
| `@babel/helper-create-regexp-features-plugin` | `MIT` | devDependencies | oui |
| `@babel/helper-define-polyfill-provider` | `MIT` | devDependencies | oui |
| `@babel/helper-globals` | `MIT` | devDependencies | oui |
| `@babel/helper-member-expression-to-functions` | `MIT` | devDependencies | oui |
| `@babel/helper-module-imports` | `MIT` | devDependencies | oui |
| `@babel/helper-module-transforms` | `MIT` | devDependencies | oui |
| `@babel/helper-optimise-call-expression` | `MIT` | devDependencies | oui |
| `@babel/helper-plugin-utils` | `MIT` | devDependencies | oui |
| `@babel/helper-remap-async-to-generator` | `MIT` | devDependencies | oui |
| `@babel/helper-replace-supers` | `MIT` | devDependencies | oui |
| `@babel/helper-skip-transparent-expression-wrappers` | `MIT` | devDependencies | oui |
| `@babel/helper-string-parser` | `MIT` | devDependencies | oui |
| `@babel/helper-validator-identifier` | `MIT` | devDependencies | oui |
| `@babel/helper-validator-option` | `MIT` | devDependencies | oui |
| `@babel/helper-wrap-function` | `MIT` | devDependencies | oui |
| `@babel/helpers` | `MIT` | devDependencies | oui |
| `@babel/parser` | `MIT` | devDependencies | oui |
| `@babel/plugin-bugfix-firefox-class-in-computed-class-key` | `MIT` | devDependencies | oui |
| `@babel/plugin-bugfix-safari-class-field-initializer-scope` | `MIT` | devDependencies | oui |
| `@babel/plugin-bugfix-safari-id-destructuring-collision-in-function-expression` | `MIT` | devDependencies | oui |
| `@babel/plugin-bugfix-safari-rest-destructuring-rhs-array` | `MIT` | devDependencies | oui |
| `@babel/plugin-bugfix-v8-spread-parameters-in-optional-chaining` | `MIT` | devDependencies | oui |
| `@babel/plugin-bugfix-v8-static-class-fields-redefine-readonly` | `MIT` | devDependencies | oui |
| `@babel/plugin-proposal-private-property-in-object` | `MIT` | devDependencies | oui |
| `@babel/plugin-syntax-import-assertions` | `MIT` | devDependencies | oui |
| `@babel/plugin-syntax-import-attributes` | `MIT` | devDependencies | oui |
| `@babel/plugin-syntax-unicode-sets-regex` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-arrow-functions` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-async-generator-functions` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-async-to-generator` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-block-scoped-functions` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-block-scoping` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-class-properties` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-class-static-block` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-classes` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-computed-properties` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-destructuring` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-dotall-regex` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-duplicate-keys` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-duplicate-named-capturing-groups-regex` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-dynamic-import` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-explicit-resource-management` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-exponentiation-operator` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-export-namespace-from` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-for-of` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-function-name` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-json-strings` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-literals` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-logical-assignment-operators` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-member-expression-literals` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-modules-amd` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-modules-commonjs` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-modules-systemjs` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-modules-umd` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-named-capturing-groups-regex` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-new-target` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-nullish-coalescing-operator` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-numeric-separator` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-object-rest-spread` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-object-super` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-optional-catch-binding` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-optional-chaining` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-parameters` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-private-methods` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-private-property-in-object` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-property-literals` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-regenerator` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-regexp-modifiers` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-reserved-words` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-shorthand-properties` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-spread` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-sticky-regex` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-template-literals` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-typeof-symbol` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-unicode-escapes` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-unicode-property-regex` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-unicode-regex` | `MIT` | devDependencies | oui |
| `@babel/plugin-transform-unicode-sets-regex` | `MIT` | devDependencies | oui |
| `@babel/preset-env` | `MIT` | devDependencies | oui |
| `@babel/preset-modules` | `MIT` | devDependencies | oui |
| `@babel/runtime` | `MIT` | devDependencies | oui |
| `@babel/template` | `MIT` | devDependencies | oui |
| `@babel/traverse` | `MIT` | devDependencies | oui |
| `@babel/types` | `MIT` | devDependencies | oui |
| `@cacheable/memory` | `MIT` | devDependencies | oui |
| `@cacheable/utils` | `MIT` | devDependencies | oui |
| `@esbuild/aix-ppc64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/android-arm` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/android-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/android-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/darwin-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/darwin-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/freebsd-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/freebsd-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-arm` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-ia32` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-loong64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-mips64el` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-ppc64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-riscv64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-s390x` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/linux-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/netbsd-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/netbsd-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/openbsd-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/openbsd-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/openharmony-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/sunos-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/win32-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/win32-ia32` | `MIT` | devDependencies (optionnel) | oui |
| `@esbuild/win32-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@eslint-community/eslint-utils` | `MIT` | devDependencies | oui |
| `@eslint-community/regexpp` | `MIT` | devDependencies | oui |
| `@eslint/config-array` | `Apache-2.0` | devDependencies | oui |
| `@eslint/config-helpers` | `Apache-2.0` | devDependencies | oui |
| `@eslint/core` | `Apache-2.0` | devDependencies | oui |
| `@eslint/js` | `MIT` | devDependencies | oui |
| `@eslint/object-schema` | `Apache-2.0` | devDependencies | oui |
| `@eslint/plugin-kit` | `Apache-2.0` | devDependencies | oui |
| `@humanfs/core` | `Apache-2.0` | devDependencies | oui |
| `@humanfs/node` | `Apache-2.0` | devDependencies | oui |
| `@humanfs/types` | `Apache-2.0` | devDependencies | oui |
| `@humanwhocodes/module-importer` | `Apache-2.0` | devDependencies | oui |
| `@humanwhocodes/retry` | `Apache-2.0` | devDependencies | oui |
| `@isaacs/nonrecursive-glob-match` | `BlueOak-1.0.0` | devDependencies | oui |
| `@jridgewell/gen-mapping` | `MIT` | devDependencies | oui |
| `@jridgewell/remapping` | `MIT` | devDependencies | oui |
| `@jridgewell/resolve-uri` | `MIT` | devDependencies | oui |
| `@jridgewell/source-map` | `MIT` | devDependencies | oui |
| `@jridgewell/sourcemap-codec` | `MIT` | devDependencies | oui |
| `@jridgewell/trace-mapping` | `MIT` | devDependencies | oui |
| `@keyv/bigmap` | `MIT` | devDependencies | oui |
| `@keyv/serialize` | `MIT` | devDependencies | oui |
| `@napi-rs/lzma-linux-x64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@oxc-project/types` | `MIT` | devDependencies | oui |
| `@playwright/test` | `Apache-2.0` | devDependencies | oui |
| `@polka/url` | `MIT` | devDependencies | oui |
| `@rolldown/binding-android-arm-eabi` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-android-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-darwin-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-darwin-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-freebsd-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-linux-arm-gnueabihf` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-linux-arm64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-linux-arm64-musl` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-linux-ppc64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-linux-s390x-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-linux-x64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-linux-x64-musl` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-openharmony-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-win32-arm64-msvc` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/binding-win32-x64-msvc` | `MIT` | devDependencies (optionnel) | oui |
| `@rolldown/pluginutils` | `MIT` | devDependencies | oui |
| `@rollup/plugin-babel` | `MIT` | devDependencies | oui |
| `@rollup/plugin-node-resolve` | `MIT` | devDependencies | oui |
| `@rollup/plugin-replace` | `MIT` | devDependencies | oui |
| `@rollup/plugin-terser` | `MIT` | devDependencies | oui |
| `@rollup/pluginutils` | `MIT` | devDependencies | oui |
| `@rollup/rollup-android-arm-eabi` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-android-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-darwin-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-darwin-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-freebsd-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-freebsd-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-arm-gnueabihf` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-arm-musleabihf` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-arm64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-arm64-musl` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-loong64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-loong64-musl` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-ppc64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-ppc64-musl` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-riscv64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-riscv64-musl` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-s390x-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-x64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-linux-x64-musl` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-openbsd-x64` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-openharmony-arm64` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-win32-arm64-msvc` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-win32-ia32-msvc` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-win32-x64-gnu` | `MIT` | devDependencies (optionnel) | oui |
| `@rollup/rollup-win32-x64-msvc` | `MIT` | devDependencies (optionnel) | oui |
| `@standard-schema/spec` | `MIT` | devDependencies | oui |
| `@sveltejs/acorn-typescript` | `MIT` | devDependencies | oui |
| `@sveltejs/adapter-node` | `MIT` | devDependencies | oui |
| `@sveltejs/kit` | `MIT` | devDependencies | oui |
| `@sveltejs/load-config` | `MIT` | devDependencies | oui |
| `@sveltejs/vite-plugin-svelte` | `MIT` | devDependencies | oui |
| `@tiptap/core` | `MIT` | dependencies | oui |
| `@tiptap/extension-blockquote` | `MIT` | dependencies | oui |
| `@tiptap/extension-bold` | `MIT` | dependencies | oui |
| `@tiptap/extension-bullet-list` | `MIT` | dependencies | oui |
| `@tiptap/extension-code` | `MIT` | dependencies | oui |
| `@tiptap/extension-code-block` | `MIT` | dependencies | oui |
| `@tiptap/extension-document` | `MIT` | dependencies | oui |
| `@tiptap/extension-dropcursor` | `MIT` | dependencies | oui |
| `@tiptap/extension-gapcursor` | `MIT` | dependencies | oui |
| `@tiptap/extension-hard-break` | `MIT` | dependencies | oui |
| `@tiptap/extension-heading` | `MIT` | dependencies | oui |
| `@tiptap/extension-horizontal-rule` | `MIT` | dependencies | oui |
| `@tiptap/extension-italic` | `MIT` | dependencies | oui |
| `@tiptap/extension-link` | `MIT` | dependencies | oui |
| `@tiptap/extension-list` | `MIT` | dependencies | oui |
| `@tiptap/extension-list-item` | `MIT` | dependencies | oui |
| `@tiptap/extension-list-keymap` | `MIT` | dependencies | oui |
| `@tiptap/extension-ordered-list` | `MIT` | dependencies | oui |
| `@tiptap/extension-paragraph` | `MIT` | dependencies | oui |
| `@tiptap/extension-placeholder` | `MIT` | dependencies | oui |
| `@tiptap/extension-strike` | `MIT` | dependencies | oui |
| `@tiptap/extension-text` | `MIT` | dependencies | oui |
| `@tiptap/extension-underline` | `MIT` | dependencies | oui |
| `@tiptap/extensions` | `MIT` | dependencies | oui |
| `@tiptap/pm` | `MIT` | dependencies | oui |
| `@tiptap/starter-kit` | `MIT` | dependencies | oui |
| `@trickfilm400/rollup-plugin-off-main-thread` | `Apache-2.0` | devDependencies | oui |
| `@types/esrecurse` | `MIT` | devDependencies | oui |
| `@types/estree` | `MIT` | devDependencies | oui |
| `@types/json-schema` | `MIT` | devDependencies | oui |
| `@types/node` | `MIT` | devDependencies | oui |
| `@types/resolve` | `MIT` | devDependencies | oui |
| `@types/trusted-types` | `MIT` | dependencies | oui |
| `@typescript-eslint/eslint-plugin` | `MIT` | devDependencies | oui |
| `@typescript-eslint/parser` | `MIT` | devDependencies | oui |
| `@typescript-eslint/project-service` | `MIT` | devDependencies | oui |
| `@typescript-eslint/scope-manager` | `MIT` | devDependencies | oui |
| `@typescript-eslint/tsconfig-utils` | `MIT` | devDependencies | oui |
| `@typescript-eslint/type-utils` | `MIT` | devDependencies | oui |
| `@typescript-eslint/types` | `MIT` | devDependencies | oui |
| `@typescript-eslint/typescript-estree` | `MIT` | devDependencies | oui |
| `@typescript-eslint/utils` | `MIT` | devDependencies | oui |
| `@typescript-eslint/visitor-keys` | `MIT` | devDependencies | oui |
| `acorn` | `MIT` | devDependencies | oui |
| `acorn-jsx` | `MIT` | devDependencies | oui |
| `ajv` | `MIT` | devDependencies | oui |
| `aria-query` | `Apache-2.0` | devDependencies | oui |
| `array-buffer-byte-length` | `MIT` | devDependencies | oui |
| `arraybuffer.prototype.slice` | `MIT` | devDependencies | oui |
| `async` | `MIT` | devDependencies | oui |
| `async-function` | `MIT` | devDependencies | oui |
| `at-least-node` | `ISC` | devDependencies | oui |
| `available-typed-arrays` | `MIT` | devDependencies | oui |
| `axobject-query` | `Apache-2.0` | devDependencies | oui |
| `babel-plugin-polyfill-corejs2` | `MIT` | devDependencies | oui |
| `babel-plugin-polyfill-corejs3` | `MIT` | devDependencies | oui |
| `babel-plugin-polyfill-regenerator` | `MIT` | devDependencies | oui |
| `balanced-match` | `MIT` | devDependencies | oui |
| `baseline-browser-mapping` | `Apache-2.0` | devDependencies | oui |
| `brace-expansion` | `MIT` | devDependencies | oui |
| `browserslist` | `MIT` | devDependencies | oui |
| `buffer-from` | `MIT` | devDependencies | oui |
| `cacheable` | `MIT` | devDependencies | oui |
| `call-bind` | `MIT` | devDependencies | oui |
| `call-bind-apply-helpers` | `MIT` | devDependencies | oui |
| `call-bound` | `MIT` | devDependencies | oui |
| `caniuse-lite` | `CC-BY-4.0` | devDependencies | **exception** |
| `chokidar` | `MIT` | devDependencies | oui |
| `clsx` | `MIT` | devDependencies | oui |
| `commander` | `MIT` | devDependencies | oui |
| `common-tags` | `MIT` | devDependencies | oui |
| `convert-source-map` | `MIT` | devDependencies | oui |
| `cookie` | `MIT` | devDependencies | oui |
| `core-js-compat` | `MIT` | devDependencies | oui |
| `cross-spawn` | `MIT` | devDependencies | oui |
| `crypto-random-string` | `MIT` | devDependencies | oui |
| `cssesc` | `MIT` | devDependencies | oui |
| `data-view-buffer` | `MIT` | devDependencies | oui |
| `data-view-byte-length` | `MIT` | devDependencies | oui |
| `data-view-byte-offset` | `MIT` | devDependencies | oui |
| `debug` | `MIT` | devDependencies | oui |
| `deep-is` | `MIT` | devDependencies | oui |
| `deepmerge` | `MIT` | devDependencies | oui |
| `define-data-property` | `MIT` | devDependencies | oui |
| `define-properties` | `MIT` | devDependencies | oui |
| `detect-libc` | `Apache-2.0` | devDependencies | oui |
| `devalue` | `MIT` | devDependencies | oui |
| `dompurify` | `(MPL-2.0 OR Apache-2.0)` | dependencies | oui |
| `dunder-proto` | `MIT` | devDependencies | oui |
| `ejs` | `Apache-2.0` | devDependencies | oui |
| `electron-to-chromium` | `ISC` | devDependencies | oui |
| `es-abstract` | `MIT` | devDependencies | oui |
| `es-abstract-get` | `MIT` | devDependencies | oui |
| `es-define-property` | `MIT` | devDependencies | oui |
| `es-errors` | `MIT` | devDependencies | oui |
| `es-object-atoms` | `MIT` | devDependencies | oui |
| `es-set-tostringtag` | `MIT` | devDependencies | oui |
| `es-to-primitive` | `MIT` | devDependencies | oui |
| `esbuild` | `MIT` | devDependencies | oui |
| `escalade` | `MIT` | devDependencies | oui |
| `escape-string-regexp` | `MIT` | devDependencies | oui |
| `eslint` | `MIT` | devDependencies | oui |
| `eslint-plugin-svelte` | `MIT` | devDependencies | oui |
| `eslint-scope` | `BSD-2-Clause` | devDependencies | oui |
| `eslint-visitor-keys` | `Apache-2.0` | devDependencies | oui |
| `esm-env` | `MIT` | devDependencies | oui |
| `espree` | `BSD-2-Clause` | devDependencies | oui |
| `esquery` | `BSD-3-Clause` | devDependencies | oui |
| `esrap` | `MIT` | devDependencies | oui |
| `esrecurse` | `BSD-2-Clause` | devDependencies | oui |
| `estraverse` | `BSD-2-Clause` | devDependencies | oui |
| `estree-walker` | `MIT` | devDependencies | oui |
| `esutils` | `BSD-2-Clause` | devDependencies | oui |
| `eta` | `MIT` | devDependencies | oui |
| `fast-deep-equal` | `MIT` | devDependencies | oui |
| `fast-json-stable-stringify` | `MIT` | devDependencies | oui |
| `fast-levenshtein` | `MIT` | devDependencies | oui |
| `fast-uri` | `BSD-3-Clause` | devDependencies | oui |
| `fdir` | `MIT` | devDependencies | oui |
| `file-entry-cache` | `MIT` | devDependencies | oui |
| `filelist` | `Apache-2.0` | devDependencies | oui |
| `find-up` | `MIT` | devDependencies | oui |
| `flat-cache` | `MIT` | devDependencies | oui |
| `flatted` | `ISC` | devDependencies | oui |
| `for-each` | `MIT` | devDependencies | oui |
| `fs-extra` | `MIT` | devDependencies | oui |
| `fsevents` | `MIT` | devDependencies (optionnel) | oui |
| `function-bind` | `MIT` | devDependencies | oui |
| `function.prototype.name` | `MIT` | devDependencies | oui |
| `functions-have-names` | `MIT` | devDependencies | oui |
| `generator-function` | `MIT` | devDependencies | oui |
| `gensync` | `MIT` | devDependencies | oui |
| `get-intrinsic` | `MIT` | devDependencies | oui |
| `get-own-enumerable-property-symbols` | `ISC` | devDependencies | oui |
| `get-proto` | `MIT` | devDependencies | oui |
| `get-symbol-description` | `MIT` | devDependencies | oui |
| `glob` | `BlueOak-1.0.0` | devDependencies | oui |
| `glob-parent` | `ISC` | devDependencies | oui |
| `globals` | `MIT` | devDependencies | oui |
| `globalthis` | `MIT` | devDependencies | oui |
| `gopd` | `MIT` | devDependencies | oui |
| `graceful-fs` | `ISC` | devDependencies | oui |
| `has-bigints` | `MIT` | devDependencies | oui |
| `has-property-descriptors` | `MIT` | devDependencies | oui |
| `has-proto` | `MIT` | devDependencies | oui |
| `has-symbols` | `MIT` | devDependencies | oui |
| `has-tostringtag` | `MIT` | devDependencies | oui |
| `hashery` | `MIT` | devDependencies | oui |
| `hasown` | `MIT` | devDependencies | oui |
| `hookified` | `MIT` | devDependencies | oui |
| `idb` | `ISC` | devDependencies | oui |
| `ignore` | `MIT` | devDependencies | oui |
| `imurmurhash` | `MIT` | devDependencies | oui |
| `internal-slot` | `MIT` | devDependencies | oui |
| `is-array-buffer` | `MIT` | devDependencies | oui |
| `is-async-function` | `MIT` | devDependencies | oui |
| `is-bigint` | `MIT` | devDependencies | oui |
| `is-boolean-object` | `MIT` | devDependencies | oui |
| `is-callable` | `MIT` | devDependencies | oui |
| `is-core-module` | `MIT` | devDependencies | oui |
| `is-data-view` | `MIT` | devDependencies | oui |
| `is-date-object` | `MIT` | devDependencies | oui |
| `is-document.all` | `MIT` | devDependencies | oui |
| `is-extglob` | `MIT` | devDependencies | oui |
| `is-finalizationregistry` | `MIT` | devDependencies | oui |
| `is-generator-function` | `MIT` | devDependencies | oui |
| `is-glob` | `MIT` | devDependencies | oui |
| `is-map` | `MIT` | devDependencies | oui |
| `is-module` | `MIT` | devDependencies | oui |
| `is-negative-zero` | `MIT` | devDependencies | oui |
| `is-number-object` | `MIT` | devDependencies | oui |
| `is-obj` | `MIT` | devDependencies | oui |
| `is-reference` | `MIT` | devDependencies | oui |
| `is-regex` | `MIT` | devDependencies | oui |
| `is-regexp` | `MIT` | devDependencies | oui |
| `is-set` | `MIT` | devDependencies | oui |
| `is-shared-array-buffer` | `MIT` | devDependencies | oui |
| `is-stream` | `MIT` | devDependencies | oui |
| `is-string` | `MIT` | devDependencies | oui |
| `is-symbol` | `MIT` | devDependencies | oui |
| `is-typed-array` | `MIT` | devDependencies | oui |
| `is-weakmap` | `MIT` | devDependencies | oui |
| `is-weakref` | `MIT` | devDependencies | oui |
| `is-weakset` | `MIT` | devDependencies | oui |
| `isarray` | `MIT` | devDependencies | oui |
| `isexe` | `ISC` | devDependencies | oui |
| `jake` | `Apache-2.0` | devDependencies | oui |
| `js-tokens` | `MIT` | devDependencies | oui |
| `jsesc` | `MIT` | devDependencies | oui |
| `json-schema-traverse` | `MIT` | devDependencies | oui |
| `json-stable-stringify-without-jsonify` | `MIT` | devDependencies | oui |
| `json5` | `MIT` | devDependencies | oui |
| `jsonfile` | `MIT` | devDependencies | oui |
| `jsonpointer` | `MIT` | devDependencies | oui |
| `keyv` | `MIT` | devDependencies | oui |
| `known-css-properties` | `MIT` | devDependencies | oui |
| `leven` | `MIT` | devDependencies | oui |
| `levn` | `MIT` | devDependencies | oui |
| `lightningcss` | `MPL-2.0` | devDependencies | **exception** |
| `lightningcss-android-arm64` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-darwin-arm64` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-darwin-x64` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-freebsd-x64` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-linux-arm-gnueabihf` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-linux-arm64-gnu` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-linux-arm64-musl` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-linux-x64-gnu` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-linux-x64-musl` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-win32-arm64-msvc` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lightningcss-win32-x64-msvc` | `MPL-2.0` | devDependencies (optionnel) | **exception** |
| `lilconfig` | `MIT` | devDependencies | oui |
| `linkifyjs` | `MIT` | dependencies | oui |
| `locate-character` | `MIT` | devDependencies | oui |
| `locate-path` | `MIT` | devDependencies | oui |
| `lodash.debounce` | `MIT` | devDependencies | oui |
| `lru-cache` | `BlueOak-1.0.0` | devDependencies | oui |
| `lru-cache` | `ISC` | devDependencies | oui |
| `magic-string` | `MIT` | devDependencies | oui |
| `marked` | `MIT` | dependencies | oui |
| `math-intrinsics` | `MIT` | devDependencies | oui |
| `minimatch` | `BlueOak-1.0.0` | devDependencies | oui |
| `minipass` | `BlueOak-1.0.0` | devDependencies | oui |
| `mri` | `MIT` | devDependencies | oui |
| `mrmime` | `MIT` | devDependencies | oui |
| `ms` | `MIT` | devDependencies | oui |
| `nanoid` | `MIT` | devDependencies | oui |
| `natural-compare` | `MIT` | devDependencies | oui |
| `node-releases` | `MIT` | devDependencies | oui |
| `object-inspect` | `MIT` | devDependencies | oui |
| `object-keys` | `MIT` | devDependencies | oui |
| `object.assign` | `MIT` | devDependencies | oui |
| `obug` | `MIT` | devDependencies | oui |
| `optionator` | `MIT` | devDependencies | oui |
| `orderedmap` | `MIT` | dependencies | oui |
| `own-keys` | `MIT` | devDependencies | oui |
| `p-limit` | `MIT` | devDependencies | oui |
| `p-locate` | `MIT` | devDependencies | oui |
| `path-exists` | `MIT` | devDependencies | oui |
| `path-key` | `MIT` | devDependencies | oui |
| `path-parse` | `MIT` | devDependencies | oui |
| `path-scurry` | `BlueOak-1.0.0` | devDependencies | oui |
| `picocolors` | `ISC` | devDependencies | oui |
| `picomatch` | `MIT` | devDependencies | oui |
| `playwright` | `Apache-2.0` | devDependencies | oui |
| `playwright-core` | `Apache-2.0` | devDependencies | oui |
| `possible-typed-array-names` | `MIT` | devDependencies | oui |
| `postcss` | `MIT` | devDependencies | oui |
| `postcss-load-config` | `MIT` | devDependencies | oui |
| `postcss-safe-parser` | `MIT` | devDependencies | oui |
| `postcss-scss` | `MIT` | devDependencies | oui |
| `postcss-selector-parser` | `MIT` | devDependencies | oui |
| `prelude-ls` | `MIT` | devDependencies | oui |
| `prettier` | `MIT` | devDependencies | oui |
| `prettier-plugin-svelte` | `MIT` | devDependencies | oui |
| `pretty-bytes` | `MIT` | devDependencies | oui |
| `prosemirror-changeset` | `MIT` | dependencies | oui |
| `prosemirror-commands` | `MIT` | dependencies | oui |
| `prosemirror-dropcursor` | `MIT` | dependencies | oui |
| `prosemirror-gapcursor` | `MIT` | dependencies | oui |
| `prosemirror-history` | `MIT` | dependencies | oui |
| `prosemirror-inputrules` | `MIT` | dependencies | oui |
| `prosemirror-keymap` | `MIT` | dependencies | oui |
| `prosemirror-model` | `MIT` | dependencies | oui |
| `prosemirror-schema-list` | `MIT` | dependencies | oui |
| `prosemirror-state` | `MIT` | dependencies | oui |
| `prosemirror-tables` | `MIT` | dependencies | oui |
| `prosemirror-transform` | `MIT` | dependencies | oui |
| `prosemirror-view` | `MIT` | dependencies | oui |
| `punycode` | `MIT` | devDependencies | oui |
| `qified` | `MIT` | devDependencies | oui |
| `qrcode-generator` | `MIT` | dependencies | oui |
| `readdirp` | `MIT` | devDependencies | oui |
| `reflect.getprototypeof` | `MIT` | devDependencies | oui |
| `regenerate` | `MIT` | devDependencies | oui |
| `regenerate-unicode-properties` | `MIT` | devDependencies | oui |
| `regexp.prototype.flags` | `MIT` | devDependencies | oui |
| `regexpu-core` | `MIT` | devDependencies | oui |
| `regjsgen` | `MIT` | devDependencies | oui |
| `regjsparser` | `BSD-2-Clause` | devDependencies | oui |
| `require-from-string` | `MIT` | devDependencies | oui |
| `resolve` | `MIT` | devDependencies | oui |
| `rolldown` | `MIT` | devDependencies | oui |
| `rollup` | `MIT` | devDependencies | oui |
| `rope-sequence` | `MIT` | dependencies | oui |
| `sade` | `MIT` | devDependencies | oui |
| `safe-array-concat` | `MIT` | devDependencies | oui |
| `safe-push-apply` | `MIT` | devDependencies | oui |
| `safe-regex-test` | `MIT` | devDependencies | oui |
| `semver` | `ISC` | devDependencies | oui |
| `serialize-javascript` | `BSD-3-Clause` | devDependencies | oui |
| `set-function-length` | `MIT` | devDependencies | oui |
| `set-function-name` | `MIT` | devDependencies | oui |
| `set-proto` | `MIT` | devDependencies | oui |
| `shebang-command` | `MIT` | devDependencies | oui |
| `shebang-regex` | `MIT` | devDependencies | oui |
| `side-channel` | `MIT` | devDependencies | oui |
| `side-channel-list` | `MIT` | devDependencies | oui |
| `side-channel-map` | `MIT` | devDependencies | oui |
| `side-channel-weakmap` | `MIT` | devDependencies | oui |
| `sirv` | `MIT` | devDependencies | oui |
| `smob` | `MIT` | devDependencies | oui |
| `source-map` | `BSD-3-Clause` | devDependencies | oui |
| `source-map-js` | `BSD-3-Clause` | devDependencies | oui |
| `source-map-support` | `MIT` | devDependencies | oui |
| `stop-iteration-iterator` | `MIT` | devDependencies | oui |
| `string.prototype.matchall` | `MIT` | devDependencies | oui |
| `string.prototype.trim` | `MIT` | devDependencies | oui |
| `string.prototype.trimend` | `MIT` | devDependencies | oui |
| `string.prototype.trimstart` | `MIT` | devDependencies | oui |
| `stringify-object` | `BSD-2-Clause` | devDependencies | oui |
| `strip-comments` | `MIT` | devDependencies | oui |
| `supports-preserve-symlinks-flag` | `MIT` | devDependencies | oui |
| `svelte` | `MIT` | devDependencies | oui |
| `svelte-check` | `MIT` | devDependencies | oui |
| `svelte-eslint-parser` | `MIT` | devDependencies | oui |
| `temp-dir` | `MIT` | devDependencies | oui |
| `tempy` | `MIT` | devDependencies | oui |
| `terser` | `BSD-2-Clause` | devDependencies | oui |
| `tinyglobby` | `MIT` | devDependencies | oui |
| `totalist` | `MIT` | devDependencies | oui |
| `ts-api-utils` | `MIT` | devDependencies | oui |
| `type-check` | `MIT` | devDependencies | oui |
| `type-fest` | `(MIT OR CC0-1.0)` | devDependencies | oui |
| `typed-array-buffer` | `MIT` | devDependencies | oui |
| `typed-array-byte-length` | `MIT` | devDependencies | oui |
| `typed-array-byte-offset` | `MIT` | devDependencies | oui |
| `typed-array-length` | `MIT` | devDependencies | oui |
| `typescript` | `Apache-2.0` | devDependencies | oui |
| `typescript-eslint` | `MIT` | devDependencies | oui |
| `unbox-primitive` | `MIT` | devDependencies | oui |
| `undici-types` | `MIT` | devDependencies | oui |
| `unicode-canonical-property-names-ecmascript` | `MIT` | devDependencies | oui |
| `unicode-match-property-ecmascript` | `MIT` | devDependencies | oui |
| `unicode-match-property-value-ecmascript` | `MIT` | devDependencies | oui |
| `unicode-property-aliases-ecmascript` | `MIT` | devDependencies | oui |
| `unique-string` | `MIT` | devDependencies | oui |
| `universalify` | `MIT` | devDependencies | oui |
| `upath` | `MIT` | devDependencies | oui |
| `update-browserslist-db` | `MIT` | devDependencies | oui |
| `uri-js` | `BSD-2-Clause` | devDependencies | oui |
| `util-deprecate` | `MIT` | devDependencies | oui |
| `vite` | `MIT` | devDependencies | oui |
| `vite-plugin-pwa` | `MIT` | devDependencies | oui |
| `vitefu` | `MIT` | devDependencies | oui |
| `w3c-keyname` | `MIT` | dependencies | oui |
| `which` | `ISC` | devDependencies | oui |
| `which-boxed-primitive` | `MIT` | devDependencies | oui |
| `which-builtin-type` | `MIT` | devDependencies | oui |
| `which-collection` | `MIT` | devDependencies | oui |
| `which-typed-array` | `MIT` | devDependencies | oui |
| `word-wrap` | `MIT` | devDependencies | oui |
| `workbox-background-sync` | `MIT` | devDependencies | oui |
| `workbox-broadcast-update` | `MIT` | devDependencies | oui |
| `workbox-build` | `MIT` | devDependencies | oui |
| `workbox-cacheable-response` | `MIT` | devDependencies | oui |
| `workbox-core` | `MIT` | dependencies | oui |
| `workbox-expiration` | `MIT` | devDependencies | oui |
| `workbox-google-analytics` | `MIT` | devDependencies | oui |
| `workbox-navigation-preload` | `MIT` | devDependencies | oui |
| `workbox-precaching` | `MIT` | devDependencies | oui |
| `workbox-range-requests` | `MIT` | devDependencies | oui |
| `workbox-recipes` | `MIT` | devDependencies | oui |
| `workbox-routing` | `MIT` | devDependencies | oui |
| `workbox-strategies` | `MIT` | devDependencies | oui |
| `workbox-streams` | `MIT` | devDependencies | oui |
| `workbox-sw` | `MIT` | devDependencies | oui |
| `workbox-window` | `MIT` | dependencies | oui |
| `yallist` | `ISC` | devDependencies | oui |
| `yaml` | `ISC` | devDependencies | oui |
| `yocto-queue` | `MIT` | devDependencies | oui |
| `zimmerframe` | `MIT` | devDependencies | oui |

## Dépendances — `whatsapp-bridge` (190 paquets)

| Paquet | Licence | Déclaré | Admise |
|---|---|---|---|
| `@borewit/text-codec` | `MIT` | dependencies | oui |
| `@cacheable/memory` | `MIT` | dependencies | oui |
| `@cacheable/node-cache` | `MIT` | dependencies | oui |
| `@cacheable/utils` | `MIT` | dependencies | oui |
| `@emnapi/runtime` | `MIT` | dependencies (optionnel) | oui |
| `@hapi/boom` | `BSD-3-Clause` | dependencies | oui |
| `@hapi/hoek` | `BSD-3-Clause` | dependencies | oui |
| `@img/colour` | `MIT` | dependencies | oui |
| `@img/sharp-darwin-arm64` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-darwin-x64` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-freebsd-wasm32` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-libvips-darwin-arm64` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-darwin-x64` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-linux-arm` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-linux-arm64` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-linux-ppc64` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-linux-riscv64` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-linux-s390x` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-linux-x64` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-linuxmusl-arm64` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-libvips-linuxmusl-x64` | `LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-linux-arm` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-linux-arm64` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-linux-ppc64` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-linux-riscv64` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-linux-s390x` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-linux-x64` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-linuxmusl-arm64` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-linuxmusl-x64` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-wasm32` | `Apache-2.0 AND LGPL-3.0-or-later AND MIT` | dependencies (optionnel) | **exception** |
| `@img/sharp-webcontainers-wasm32` | `Apache-2.0` | dependencies (optionnel) | oui |
| `@img/sharp-win32-arm64` | `Apache-2.0 AND LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-win32-ia32` | `Apache-2.0 AND LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@img/sharp-win32-x64` | `Apache-2.0 AND LGPL-3.0-or-later` | dependencies (optionnel) | **exception** |
| `@keyv/bigmap` | `MIT` | dependencies | oui |
| `@keyv/serialize` | `MIT` | dependencies | oui |
| `@pinojs/redact` | `MIT` | dependencies | oui |
| `@protobufjs/aspromise` | `BSD-3-Clause` | dependencies | oui |
| `@protobufjs/base64` | `BSD-3-Clause` | dependencies | oui |
| `@protobufjs/codegen` | `BSD-3-Clause` | dependencies | oui |
| `@protobufjs/eventemitter` | `BSD-3-Clause` | dependencies | oui |
| `@protobufjs/fetch` | `BSD-3-Clause` | dependencies | oui |
| `@protobufjs/float` | `BSD-3-Clause` | dependencies | oui |
| `@protobufjs/path` | `BSD-3-Clause` | dependencies | oui |
| `@protobufjs/pool` | `BSD-3-Clause` | dependencies | oui |
| `@protobufjs/utf8` | `BSD-3-Clause` | dependencies | oui |
| `@tokenizer/inflate` | `MIT` | dependencies | oui |
| `@tokenizer/token` | `MIT` | dependencies | oui |
| `@types/node` | `MIT` | dependencies | oui |
| `accepts` | `MIT` | dependencies | oui |
| `agent-base` | `MIT` | dependencies | oui |
| `ansi-regex` | `MIT` | dependencies | oui |
| `ansi-styles` | `MIT` | dependencies | oui |
| `async-mutex` | `MIT` | dependencies | oui |
| `asynckit` | `MIT` | dependencies | oui |
| `atomic-sleep` | `MIT` | dependencies | oui |
| `axios` | `MIT` | dependencies | oui |
| `baileys` | `MIT` | dependencies | oui |
| `body-parser` | `MIT` | dependencies | oui |
| `bytes` | `MIT` | dependencies | oui |
| `cacheable` | `MIT` | dependencies | oui |
| `call-bind-apply-helpers` | `MIT` | dependencies | oui |
| `call-bound` | `MIT` | dependencies | oui |
| `camelcase` | `MIT` | dependencies | oui |
| `cliui` | `ISC` | dependencies | oui |
| `color-convert` | `MIT` | dependencies | oui |
| `color-name` | `MIT` | dependencies | oui |
| `combined-stream` | `MIT` | dependencies | oui |
| `content-disposition` | `MIT` | dependencies | oui |
| `content-type` | `MIT` | dependencies | oui |
| `cookie` | `MIT` | dependencies | oui |
| `cookie-signature` | `MIT` | dependencies | oui |
| `curve25519-js` | `MIT` | dependencies | oui |
| `debug` | `MIT` | dependencies | oui |
| `decamelize` | `MIT` | dependencies | oui |
| `delayed-stream` | `MIT` | dependencies | oui |
| `depd` | `MIT` | dependencies | oui |
| `detect-libc` | `Apache-2.0` | dependencies | oui |
| `dijkstrajs` | `MIT` | dependencies | oui |
| `dunder-proto` | `MIT` | dependencies | oui |
| `ee-first` | `MIT` | dependencies | oui |
| `emoji-regex` | `MIT` | dependencies | oui |
| `encodeurl` | `MIT` | dependencies | oui |
| `es-define-property` | `MIT` | dependencies | oui |
| `es-errors` | `MIT` | dependencies | oui |
| `es-object-atoms` | `MIT` | dependencies | oui |
| `es-set-tostringtag` | `MIT` | dependencies | oui |
| `escape-html` | `MIT` | dependencies | oui |
| `etag` | `MIT` | dependencies | oui |
| `express` | `MIT` | dependencies | oui |
| `file-type` | `MIT` | dependencies | oui |
| `finalhandler` | `MIT` | dependencies | oui |
| `find-up` | `MIT` | dependencies | oui |
| `follow-redirects` | `MIT` | dependencies | oui |
| `form-data` | `MIT` | dependencies | oui |
| `forwarded` | `MIT` | dependencies | oui |
| `fresh` | `MIT` | dependencies | oui |
| `function-bind` | `MIT` | dependencies | oui |
| `get-caller-file` | `ISC` | dependencies | oui |
| `get-intrinsic` | `MIT` | dependencies | oui |
| `get-proto` | `MIT` | dependencies | oui |
| `gopd` | `MIT` | dependencies | oui |
| `has-symbols` | `MIT` | dependencies | oui |
| `has-tostringtag` | `MIT` | dependencies | oui |
| `hashery` | `MIT` | dependencies | oui |
| `hasown` | `MIT` | dependencies | oui |
| `hookified` | `MIT` | dependencies | oui |
| `http-errors` | `MIT` | dependencies | oui |
| `https-proxy-agent` | `MIT` | dependencies | oui |
| `iconv-lite` | `MIT` | dependencies | oui |
| `ieee754` | `BSD-3-Clause` | dependencies | oui |
| `inherits` | `ISC` | dependencies | oui |
| `ipaddr.js` | `MIT` | dependencies | oui |
| `is-fullwidth-code-point` | `MIT` | dependencies | oui |
| `is-promise` | `MIT` | dependencies | oui |
| `keyv` | `MIT` | dependencies | oui |
| `libsignal` | `GPL-3.0` | dependencies | **exception** |
| `locate-path` | `MIT` | dependencies | oui |
| `long` | `Apache-2.0` | dependencies | oui |
| `math-intrinsics` | `MIT` | dependencies | oui |
| `media-typer` | `MIT` | dependencies | oui |
| `merge-descriptors` | `MIT` | dependencies | oui |
| `mime-db` | `MIT` | dependencies | oui |
| `mime-types` | `MIT` | dependencies | oui |
| `ms` | `MIT` | dependencies | oui |
| `music-metadata` | `MIT` | dependencies | oui |
| `negotiator` | `MIT` | dependencies | oui |
| `object-inspect` | `MIT` | dependencies | oui |
| `on-exit-leak-free` | `MIT` | dependencies | oui |
| `on-finished` | `MIT` | dependencies | oui |
| `once` | `ISC` | dependencies | oui |
| `p-limit` | `MIT` | dependencies | oui |
| `p-locate` | `MIT` | dependencies | oui |
| `p-try` | `MIT` | dependencies | oui |
| `parseurl` | `MIT` | dependencies | oui |
| `path-exists` | `MIT` | dependencies | oui |
| `path-to-regexp` | `MIT` | dependencies | oui |
| `pino` | `MIT` | dependencies | oui |
| `pino-abstract-transport` | `MIT` | dependencies | oui |
| `pino-std-serializers` | `MIT` | dependencies | oui |
| `pngjs` | `MIT` | dependencies | oui |
| `process-warning` | `MIT` | dependencies | oui |
| `protobufjs` | `BSD-3-Clause` | dependencies | oui |
| `proxy-addr` | `MIT` | dependencies | oui |
| `proxy-from-env` | `MIT` | dependencies | oui |
| `qified` | `MIT` | dependencies | oui |
| `qrcode` | `MIT` | dependencies | oui |
| `qs` | `BSD-3-Clause` | dependencies | oui |
| `quick-format-unescaped` | `MIT` | dependencies | oui |
| `range-parser` | `MIT` | dependencies | oui |
| `raw-body` | `MIT` | dependencies | oui |
| `real-require` | `MIT` | dependencies | oui |
| `require-directory` | `MIT` | dependencies | oui |
| `require-main-filename` | `ISC` | dependencies | oui |
| `router` | `MIT` | dependencies | oui |
| `safe-stable-stringify` | `MIT` | dependencies | oui |
| `safer-buffer` | `MIT` | dependencies | oui |
| `semver` | `ISC` | dependencies | oui |
| `send` | `MIT` | dependencies | oui |
| `serve-static` | `MIT` | dependencies | oui |
| `set-blocking` | `ISC` | dependencies | oui |
| `setprototypeof` | `ISC` | dependencies | oui |
| `sharp` | `Apache-2.0` | dependencies | oui |
| `side-channel` | `MIT` | dependencies | oui |
| `side-channel-list` | `MIT` | dependencies | oui |
| `side-channel-map` | `MIT` | dependencies | oui |
| `side-channel-weakmap` | `MIT` | dependencies | oui |
| `sonic-boom` | `MIT` | dependencies | oui |
| `split2` | `ISC` | dependencies | oui |
| `statuses` | `MIT` | dependencies | oui |
| `string-width` | `MIT` | dependencies | oui |
| `strip-ansi` | `MIT` | dependencies | oui |
| `strtok3` | `MIT` | dependencies | oui |
| `thread-stream` | `MIT` | dependencies | oui |
| `toidentifier` | `MIT` | dependencies | oui |
| `token-types` | `MIT` | dependencies | oui |
| `tslib` | `0BSD` | dependencies | oui |
| `type-is` | `MIT` | dependencies | oui |
| `uint8array-extras` | `MIT` | dependencies | oui |
| `undici-types` | `MIT` | dependencies | oui |
| `unpipe` | `MIT` | dependencies | oui |
| `vary` | `MIT` | dependencies | oui |
| `which-module` | `ISC` | dependencies | oui |
| `win-guid` | `MIT` | dependencies | oui |
| `wrap-ansi` | `MIT` | dependencies | oui |
| `wrappy` | `ISC` | dependencies | oui |
| `ws` | `MIT` | dependencies | oui |
| `y18n` | `ISC` | dependencies | oui |
| `yargs` | `MIT` | dependencies | oui |
| `yargs-parser` | `ISC` | dependencies | oui |

## Dépendances — `api` (29 dépendances directes)

Seules les dépendances **directes** de l'API sont figées ici : les transitives ne sont pas épinglées dans `api/requirements.txt`, et leur métadonnée de licence changerait ce document sans que le dépôt bouge. Elles sont jugées par la liste blanche à chaque passage de la CI, comme les directes.

| Paquet | Licence | Déclaré | Admise |
|---|---|---|---|
| `alembic` | `MIT` | directe | oui |
| `apscheduler` | `MIT` | directe | oui |
| `bcrypt` | `Apache-2.0` | directe | oui |
| `cryptography` | `Apache-2.0 OR BSD-3-Clause` | directe | oui |
| `dkimpy` | `BSD-like` | directe | **exception** |
| `dnspython` | `ISC` | directe | oui |
| `email-validator` | `Unlicense` | directe | oui |
| `fastapi` | `MIT` | directe | oui |
| `fastapi-mail` | `MIT` | directe | oui |
| `httpx` | `BSD-3-Clause` | directe | oui |
| `jinja2` | `BSD` | directe | oui |
| `markupsafe` | `BSD-3-Clause` | directe | oui |
| `nh3` | `MIT` | directe | oui |
| `openpyxl` | `MIT` | directe | oui |
| `passlib` | `BSD` | directe | oui |
| `pillow` | `MIT-CMU` | directe | oui |
| `psycopg` | `LGPL-3.0-only` | directe | **exception** |
| `pydantic` | `MIT` | directe | oui |
| `pydantic-settings` | `MIT` | directe | oui |
| `pyjwt` | `MIT` | directe | oui |
| `pypdf` | `BSD-3-Clause` | directe | oui |
| `python-dotenv` | `BSD-3-Clause` | directe | oui |
| `python-multipart` | `Apache-2.0` | directe | oui |
| `qrcode` | `BSD` | directe | oui |
| `slowapi` | `MIT` | directe | oui |
| `sqlalchemy` | `MIT` | directe | oui |
| `sqlmodel` | `MIT` | directe | oui |
| `uvicorn` | `BSD-3-Clause` | directe | oui |
| `weasyprint` | `BSD` | directe | oui |
