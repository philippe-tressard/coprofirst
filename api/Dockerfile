FROM python:3.12-slim

WORKDIR /app

# Le commit de l'image, lu par Administration › Maintenance (« Installation »,
# #1761) pour le comparer à la branche suivie. Posé par la CI (images.yml) et
# par `construire_images` ; `dev` hors de ces deux chemins.
ARG GIT_HASH=dev
ENV GIT_HASH=$GIT_HASH

# Dépendances système
# libpango/libcairo/libharfbuzz(+subset) + polices : rendu PDF WeasyPrint
# (fiche arrivant, annonces de hall). Aucune compilation : install rapide sur ARM64.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    libfontconfig1 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Code source
COPY . .

#  🔴 UN UTILISATEUR APPLICATIF, PAS ROOT (#769, 05/09/2026).
#
#  Le conteneur tournait en root : un défaut d'exécution (rendu PDF, dépendance
#  compromise, désérialisation) donnait root SUR LE VOLUME DE DONNÉES. Le
#  confinement Docker ne sépare rien quand le processus est root.
#
#  ⚠️ `USER app` n'est PAS posé ici, et c'est délibéré : les trois volumes sont
#  déjà écrits par root sur les deux nœuds, et un conteneur non-root ne pourrait
#  plus y écrire — l'API tomberait au premier déploiement. `start.sh`
#  garde donc root le temps de reprendre les propriétés, puis LAISSE root
#  (`setpriv`, présent dans l'image de base). La migration se fait ainsi toute
#  seule, sur les deux nœuds, sans geste manuel sur une base en production.
RUN useradd --system --uid 10001 --shell /usr/sbin/nologin app

#  Un cache INSCRIPTIBLE pour Fontconfig (#1066). `useradd --system` ne crée pas
#  de répertoire personnel, et `setpriv` garde HOME=/root, illisible pour `app` :
#  WeasyPrint écrivait donc « Fontconfig error: No writable cache directories »
#  quinze fois à chaque démarrage. Une variable d'environnement de l'image, et
#  non de `start.sh` : l'enfant `spawn` du rendu PDF (`utils/pdf_rendu.py`)
#  hérite de l'environnement, pas des gestes du script qui l'a lancé.
ENV XDG_CACHE_HOME=/app/.cache
RUN mkdir -p /app/.cache && chown app:app /app/.cache

# Répertoires de données
RUN mkdir -p /app/data /app/uploads /backups     && chown -R app:app /app/data /app/uploads /backups

# Script de démarrage (migrations + uvicorn)
RUN chmod +x /app/start.sh

# Migrations + démarrage
CMD ["/app/start.sh"]
