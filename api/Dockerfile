#  ── Étape « heif » : pillow-heif compilé contre la libheif de Debian (#2389) ──
#
#  🔴 LES ROUES PyPI DE `pillow-heif` NE DOIVENT JAMAIS ENTRER DANS L'IMAGE. Elles
#  embarquent libx265, l'ENCODEUR HEVC, sous GPLv2 (`LICENSES_bundled.txt`), et
#  l'image est distribuée publiquement sur ghcr.io. Le site ne fait que DÉCODER :
#  libheif (LGPL-3.0+) et son greffon libde265 (LGPL-3.0+) y suffisent. Le module
#  se compile donc ici, contre la libheif de Debian, et seule la roue produite
#  passe à l'image ; compilateur et en-têtes restent dans cette étape.
#  `--no-install-recommends` n'est pas une économie : `libheif1` RECOMMANDE
#  `libheif-plugin-x265`. La version vient de `requirements.txt`, seule source.
#  🔒 `scripts/ci/licences_image.py` (règles du Dockerfile) et
#  `scripts/verifier_heif.py` (l'image construite, ci-dessous).
FROM python:3.15-slim AS heif
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libheif-dev \
    pkgconf \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN version=$(grep -oE '^pillow-heif==[0-9.]+' requirements.txt) \
    && pip wheel --no-binary pillow-heif --no-deps --wheel-dir /roues "$version"

FROM python:3.15-slim

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
    libheif1 \
    libheif-plugin-libde265 \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
#  pillow-heif d'abord, depuis la roue compilée ci-dessus ; `PIP_NO_BINARY` interdit
#  ensuite toute roue PyPI de ce paquet : une version désalignée tenterait une
#  compilation, sans compilateur, et la construction échouerait — jamais en silence.
COPY --from=heif /roues /roues
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --no-deps /roues/*.whl \
    && PIP_NO_BINARY=pillow-heif pip install -r requirements.txt \
    && rm -rf /roues

# Code source
COPY . .

#  🔒 L'image construite, pas le Dockerfile : aucun x265, le module lié à la
#  libheif du système, le décodage d'une vraie photo HEIC (#2389).
RUN python -I scripts/verifier_heif.py tests/donnees/photo.heic

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
