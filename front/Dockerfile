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
RUN apk add --no-cache tzdata
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
