#!/bin/sh
set -e

#  🔴 ON NE RESTE PAS ROOT (#769, 05/09/2026).
#
#  Le conteneur démarrait — et servait — en root. Un défaut d'exécution donnait
#  alors root sur le volume de données : le confinement Docker ne sépare rien
#  quand le processus est root.
#
#  ⚠️ POURQUOI LA BASCULE EST ICI ET PAS UN `USER` DANS LE DOCKERFILE : les trois
#  volumes sont déjà écrits par root sur les deux nœuds. Un conteneur qui
#  démarrerait directement en `app` ne pourrait plus y écrire — l'API tomberait
#  au premier déploiement, sur les deux nœuds, et la seule issue serait un
#  `chown` manuel en production. Ce script garde donc root le temps de reprendre
#  les propriétés, PUIS se relance en `app`.
#
#  `setpriv` vient de l'image de base (`util-linux`) : aucune dépendance ajoutée.
if [ "$(id -u)" = "0" ]; then
    echo "==> Reprise des propriétés des volumes (app:app)..."
    chown -R app:app /app/data /app/uploads /backups
    echo "==> Bascule vers l'utilisateur applicatif..."
    exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

#  CHAQUE base de l'installation est attendue, puis migrée — ou reçoit le schéma
#  courant si elle est neuve (`app/utils/preparer_bases`, #2053). La décision vit
#  là, écrite une fois pour les deux installations :
#    - propre à une copropriété (5Hostachy) : `DATABASE_URL` seule, comme avant —
#      illisible, ou en échec de migration → code 1, `set -e` arrête, Docker relance ;
#      EN AVANCE sur ce code (retour arrière, #1756) → migrations ignorées, et dit ;
#    - commune : une base par copropriété déclarée ; l'échec de l'une ne bloque pas
#      les autres, sa ligne le dit et l'API la refuse (503 pour son seul hôte).
#  Affecté AVANT d'être affiché : sous `set -e`, un échec dans `$(…)` passé à
#  `echo` serait ignoré, et le conteneur démarrerait sur une base sans schéma.
echo "==> Préparation des bases... (utilisateur : $(id -un))"
BASES=$(python -m app.utils.preparer_bases)
echo "$BASES" | sed 's/^/==> /'

#  Le REGISTRE DES INSTALLATIONS (référence seule, spec §4.11) : sa base `plateforme`
#  est une AUTRE base, migrée par sa propre chaîne. Jamais sous `set -e` : un
#  registre en panne ne doit pas arrêter la résidence — le verdict se dit, et ses
#  routes répondent 503 (`app/registre/migrer.py`). « eteint » partout ailleurs.
REGISTRE=$(python -m app.registre.migrer 2>/dev/null | tail -n 1) || REGISTRE="echec: lancement"
echo "==> Registre des installations : ${REGISTRE:-echec: verdict vide}"

echo "==> Démarrage de l'API..."
#  --no-access-log (#1300, 25/09/2026) : pas une ligne par requête avec l'adresse
#  du client — une donnée personnelle dès que l'API lira l'adresse réelle. Les
#  erreurs restent journalisées (uvicorn.error). 🔒 tests/test_journal_acces.py
#  --proxy-headers (#1300) : l'adresse du visiteur, transmise par Caddy — le
#  réseau Docker, et lui seul, est de confiance. Même réseau que
#  `trusted_proxies` du Caddyfile. 🔒 tests/test_adresse_client.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --proxy-headers --forwarded-allow-ips=172.16.0.0/12
