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

#  Le serveur de base peut démarrer après l'API : on l'attend, et on s'arrête
#  s'il ne répond pas — jamais de migration sur une base qu'on n'a pas pu lire
#  (`app/utils/attendre_base`, #1759). Affecté AVANT d'être affiché, pour que
#  `set -e` compte l'échec.
JOIGNABLE=$(python -m app.utils.attendre_base)
echo "==> Base : $JOIGNABLE"

#  Une base EN AVANCE sur ce code (retour à l'image précédente, #1756) : son
#  `alembic upgrade head` échouerait sur une révision qu'il ne connaît pas, et
#  `set -e` arrêterait le conteneur en boucle. Les migrations étant compatibles
#  d'une version à l'autre (#1757), ce code sait servir cette base : on démarre
#  sans migrer, et on le DIT. Lecture impossible → « inconnu » → on migre.
ETAT_BASE=$(python -m app.utils.revision_base 2>/dev/null || echo inconnu)
if [ "$ETAT_BASE" = "en_avance" ]; then
    echo "==> ⚠ Base EN AVANCE sur ce code (retour à une version précédente) — migrations ignorées."
else
    #  Une base NEUVE reçoit le schéma courant d'un coup, marqué à la tête
    #  (#1747, spec §4.3). Une base qui a des tables n'est pas touchée.
    #  Affecté AVANT d'être affiché : sous `set -e`, un échec dans `$(…)` passé à
    #  `echo` serait ignoré, et le conteneur démarrerait sur une base sans schéma.
    SCHEMA_INITIAL=$(python -m app.utils.schema_initial)
    echo "==> Schéma initial d'une base neuve : $SCHEMA_INITIAL"
    #  « inconnu » : la base n'a pas pu être lue. La migrer quand même marquerait
    #  une base peut-être vide sans lui poser de schéma — on s'arrête, Docker relance.
    if [ "$SCHEMA_INITIAL" = "inconnu" ]; then
        echo "==> ✗ Base illisible au moment de poser le schéma — arrêt, sans migrer."
        exit 1
    fi
    echo "==> Lancement des migrations Alembic... (utilisateur : $(id -un))"
    alembic upgrade head
fi

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
