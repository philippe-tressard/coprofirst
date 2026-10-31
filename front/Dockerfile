FROM node:26-alpine AS builder

ARG GIT_HASH=dev
ENV VITE_GIT_HASH=$GIT_HASH

WORKDIR /app
# Lockfile COPIÉ + `npm ci` : build DÉTERMINISTE (versions figées par package-lock.json).
# Avant : `COPY package.json` seul + `npm install` re-résolvait les `^` vers les dernières
# versions à chaque build → un build propre cassait (vite-plugin-pwa 1.3.0) alors qu'un cache
# ancien passait. Cause des échecs silencieux de build front (cf. 23/06/2026).
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --legacy-peer-deps

COPY . .
RUN npm run build

FROM node:26-alpine AS runner
#  Le gestionnaire de paquets QUITTE l'image d'exécution (#2377, 31/10/2026) :
#  le npm livré avec Node embarque ses propres undici et brace-expansion, qui
#  portaient six HIGH (Trivy) que `npm audit` ne voit pas — ce n'est pas notre
#  arbre. Le serveur ne fait que `node build` : npm n'y sert qu'à installer, et
#  l'installation a eu lieu dans `builder`. 🔒 `api/tests/test_images_sans_npm.py`.
RUN apk upgrade --no-cache && apk add --no-cache tzdata \
    && rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg /opt/yarn-* \
    && ! sh -c 'command -v npm || command -v npx' && node --version
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json .
COPY --from=builder /app/node_modules ./node_modules
RUN addgroup -S app && adduser -S app -G app
#  🔴 ET ON S'EN SERT (#769, 05/09/2026). L'utilisateur était créé depuis
#  toujours, et le conteneur tournait quand même en root : `USER` manquait.
#  Un compte créé mais jamais endossé ne protège rien — il donne juste l'air.
#
#  Rien à écrire ici : le serveur SSR ne sert que `build/` et `node_modules/`,
#  copiés en lecture. Pas de volume, donc pas de reprise de propriétés à faire.
USER app

EXPOSE 3000
ENV PORT=3000
ENV NODE_ENV=production

CMD ["node", "build"]
