FROM node:26-alpine
# Node 26 (#1413, 29/10/2026) : LTS active depuis le 28/10/2026, la MÊME que le
# front — une seule image de base à rafraîchir sur le daemon. Avant : Node 22
# (#1380), lui-même venu de Node 20, en fin de vie depuis le 30/04/2026. Jamais
# une version impaire (PR Dependabot #1290) : elle n'est jamais LTS, sa fin de
# vie arrive en quelques mois.

RUN apk upgrade --no-cache && apk add --no-cache git tzdata

WORKDIR /app

# `npm ci` et le lockfile (#1050, 25/09/2026) : `npm install` résolvait les
# plages `^` au moment du build — deux nœuds construits à deux dates pouvaient
# embarquer deux Baileys différents, sans que rien ne le dise. C'est le défaut
# corrigé le 23/06/2026 sur `front/Dockerfile`, resté ici.
# ⚠️ `libsignal` est une dépendance git (verrouillée en `git+ssh`) : npm la
# récupère en HTTPS sans clé SSH — vérifié par `npm ci` sans clé avant la PR.
#  Puis le gestionnaire de paquets QUITTE l'image (#2377, 31/10/2026), dans la
#  même couche : le npm livré avec Node embarque ses propres undici et
#  brace-expansion, qui portaient six HIGH (Trivy) que `npm audit` ne voit pas.
#  Le bridge ne fait que `node index.js`. 🔒 `api/tests/test_images_sans_npm.py`.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev \
    && rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg /opt/yarn-* \
    && ! sh -c 'command -v npm || command -v npx' && node --version

COPY index.js arret.js accuses.js ./

VOLUME /app/auth_state

EXPOSE 8090

CMD ["node", "index.js"]
