FROM node:22-alpine
# Node 22 (#1380, 27/09/2026) : ce conteneur tournait sur Node 20, en fin de vie
# depuis le 30/04/2026 — cinq mois sans correctif pour celui qui tient la
# session WhatsApp. 22 est une LTS, et la MÊME que le front : une seule image de
# base à rafraîchir sur le daemon. Pas 25 (PR Dependabot #1290) : une version
# impaire n'est jamais LTS, sa fin de vie arrive en quelques mois.

RUN apk add --no-cache git tzdata

WORKDIR /app

# `npm ci` et le lockfile (#1050, 25/09/2026) : `npm install` résolvait les
# plages `^` au moment du build — deux nœuds construits à deux dates pouvaient
# embarquer deux Baileys différents, sans que rien ne le dise. C'est le défaut
# corrigé le 23/06/2026 sur `front/Dockerfile`, resté ici.
# ⚠️ `libsignal` est une dépendance git (verrouillée en `git+ssh`) : npm la
# récupère en HTTPS sans clé SSH — vérifié par `npm ci` sans clé avant la PR.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY index.js arret.js accuses.js ./

VOLUME /app/auth_state

EXPOSE 8090

CMD ["node", "index.js"]
