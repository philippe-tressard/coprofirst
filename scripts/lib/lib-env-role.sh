#!/bin/bash
# =============================================================================
#  lib-env-role.sh — Ce que le `.env` doit dire selon le RÔLE du nœud
#
#  Module SOURCÉ, jamais exécuté (hors `--selftest`) : pas de bit x, le job CI
#  « Bits d'exécution versionnés » attend 100644 sur les `lib-*.sh`.
#
#  ── POURQUOI CE MODULE (#1077, 20/09/2026) ──────────────────────────────────
#
#  Deux réglages du `.env` dépendent du rôle, et d'eux seuls :
#
#    | Réglage         | Nœud ACTIF              | Nœud STANDBY            |
#    |-----------------|-------------------------|-------------------------|
#    | `ORIGIN`        | https://5hostachy.fr    | http://<IP du nœud>     |
#    | `COOKIE_SECURE` | ABSENT (défaut = true)  | false                   |
#
#  Le standby s'atteint en HTTP clair sur son IP : un cookie `Secure` n'y
#  repartirait pas. L'actif sert le public par le tunnel, en HTTPS : le drapeau
#  y est obligatoire — et il est obtenu en RETIRANT la ligne, pour que ce soit le
#  défaut de `config.py` (`cookie_secure: bool = True`) qui s'applique, et non
#  une valeur recopiée ici qui pourrait un jour dire le contraire de lui.
#
#  🔴 Cette règle était écrite QUATRE fois, dans trois scripts :
#     `bascule.sh:383` (promotion du peer), `bascule.sh:443-446` (soi-même en
#     standby), `health-watch.sh:294` (failover) et `boot-role-guard.sh:182`
#     (promotion au démarrage). Le commentaire de ce dernier disait, en toutes
#     lettres, « identique à bascule.sh phase 5 et health-watch.sh failover » :
#     la duplication était CONNUE et documentée, jamais supprimée. Un commentaire
#     qui décrit une copie ne l'empêche pas de diverger — il note seulement
#     qu'elle existe.
#
#     Et elle avait déjà coûté : le « gap .env du 15/07 » cité par
#     `boot-role-guard.sh` est précisément le jour où une promotion HORS bascule
#     n'a pas appliqué ces `sed`, et a servi le public avec `ORIGIN` sur une IP
#     locale — site cassé.
#
#  ── LA PARTIE PURE, ET CELLE QUI ÉCRIT ──────────────────────────────────────
#
#  `env_role_transformer` ne touche à rien : elle reçoit le TEXTE du `.env` et
#  rend le texte voulu. C'est elle que `--selftest` éprouve, sans les deux RPi —
#  le motif inauguré par `boot-role-guard.sh --selftest` (15/07/2026).
#  `env_role_appliquer` est la seule à écrire, et elle tient en trois lignes.
#
#  Test : bash lib-env-role.sh --selftest   (aucun effet de bord)
# =============================================================================

#: L'origine publique servie par le nœud actif — une seule écriture.
ENV_ROLE_ORIGINE_PUBLIQUE="https://5hostachy.fr"

# ---------------------------------------------------------------------------
#  env_role_transformer <texte du .env> <actif|standby> [ip du nœud]
#
#  Rend sur la sortie standard le `.env` tel qu'il doit être pour ce rôle.
#  PURE : ni lecture, ni écriture, ni réseau. Idempotente.
# ---------------------------------------------------------------------------
env_role_transformer() {
  local texte=$1 role=$2 ip=${3:-}
  local origine

  case "$role" in
    actif)   origine="$ENV_ROLE_ORIGINE_PUBLIQUE" ;;
    standby)
      [ -n "$ip" ] || { echo "env_role_transformer: IP requise pour standby" >&2; return 2; }
      origine="http://$ip"
      ;;
    *) echo "env_role_transformer: rôle inconnu « $role »" >&2; return 2 ;;
  esac

  #  ORIGIN : remplacée si elle existe, ajoutée sinon. Le `.env` d'un nœud neuf
  #  vient de `.env.example`, qui la porte — mais un `.env` restauré à la main
  #  peut l'avoir perdue, et un site sans ORIGIN refuse les envois de formulaire.
  local sortie
  sortie=$(printf '%s' "$texte" | sed "s|^ORIGIN=.*|ORIGIN=${origine}|")
  if ! grep -q '^ORIGIN=' <<<"$sortie"; then
    sortie=$(printf '%s\nORIGIN=%s' "$sortie" "$origine")
  fi

  #  COOKIE_SECURE : RETIRÉE pour l'actif (le défaut de config.py vaut `true`),
  #  posée à `false` pour le standby. On retire d'abord dans les deux cas, ce
  #  qui rend la fonction idempotente quelle que soit la valeur déjà présente.
  sortie=$(printf '%s' "$sortie" | sed '/^COOKIE_SECURE=/d')
  if [ "$role" = "standby" ]; then
    sortie=$(printf '%s\nCOOKIE_SECURE=false' "$sortie")
  fi

  printf '%s\n' "$sortie"
}

# ---------------------------------------------------------------------------
#  env_role_appliquer <chemin du .env> <actif|standby> [ip]
#
#  La seule fonction qui écrit. L'écriture passe par un fichier temporaire du
#  même répertoire puis `mv` : une coupure de courant pendant une bascule ne
#  doit pas laisser un `.env` tronqué, qui empêcherait la stack de démarrer.
# ---------------------------------------------------------------------------
env_role_appliquer() {
  local fichier=$1 role=$2 ip=${3:-} tmp
  [ -f "$fichier" ] || { echo "env_role_appliquer: $fichier introuvable" >&2; return 1; }
  tmp="${fichier}.tmp.$$"
  env_role_transformer "$(cat "$fichier")" "$role" "$ip" > "$tmp" || { rm -f "$tmp"; return 2; }
  #  🔴 Le MODE *et* le PROPRIETAIRE, et le second manquait (#1138).
  #
  #  `>` CREE le fichier temporaire : il prend le proprietaire du processus,
  #  et `mv` le conserve. Lance en root depuis `bascule.sh`, ce module rendait
  #  donc le `.env` a root:root — silencieusement. Le 22/09/2026, le standby a
  #  perdu d'un coup son build ET son canal d'alerte, qui lit le SMTP dans ce
  #  meme fichier : aveugle et muet pendant 70 minutes (#1135).
  #
  #  ⚠️ `--reference` plutot qu'un nom en dur : celui-ci serait faux le jour
  #  ou l'installation change d'utilisateur, et personne ne le relirait.
  #
  #  ⚠️ L'echec est TOLERE, et c'est voulu : sans privileges, `chown` refuse —
  #  mais le fichier appartient alors deja au bon utilisateur, puisque c'est lui
  #  qui ecrit. Faire echouer la bascule sur ce cas casserait `MaJ-Hostachy.sh`,
  #  qui appelle ce module sans sudo. Ce qui surveille l'etat reel est C28.
  chmod --reference="$fichier" "$tmp" 2>/dev/null || chmod 600 "$tmp"
  chown --reference="$fichier" "$tmp" 2>/dev/null || true
  mv "$tmp" "$fichier"
}

# ---------------------------------------------------------------------------
#  C28. verdict_env_lisible <proprietaire> <groupe> <mode> <utilisateur du cron>
#         [<groupes de cet utilisateur>]
#
#  « Ce que lit `auto-deploy` est-il lisible par qui le fait tourner ? »
#
#  🔴 Aucun des controles C1 a C27 ne posait cette question, et c'est
#  pourtant d'elle que dependent le deploiement du standby ET le canal d'alerte
#  — tous deux lisent le `.env`. Le 22/09/2026, les deux sont tombes ensemble, et
#  le second a empeche de savoir que le premier etait tombe.
#
#  PURE : trois chaines en entree, un mot en sortie. Elle s'eprouve sans les deux
#  RPi, et sans avoir a rendre un fichier illisible pour voir ce qui arrive.
#
#  Verdicts :
#    OK         lisible par l'utilisateur du cron
#    ILLISIBLE  ne l'est pas — c'est le cas vecu (root:root en 600)
#    EXPOSE     lisible, mais de TOUT LE MONDE : un secret en clair. Deux
#               verdicts distincts, parce que repondre OK cacherait un defaut de
#               securite derriere une question de disponibilite.
#    INCONNU    une entree manque : on n'a rien constate (`standards/04` §1)
# ---------------------------------------------------------------------------
verdict_env_lisible() {
  local prop=$1 groupe=$2 mode=$3 utilisateur=$4 groupes=${5:-}

  #  🔴 CAS ZERO. Ne pas pouvoir relever les droits est exactement l'etat
  #  que ce controle doit reveler : le dire INCONNU, jamais OK.
  [ -n "$prop" ] && [ -n "$mode" ] && [ -n "$utilisateur" ] || { echo INCONNU; return; }
  case "$mode" in
    [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) : ;;
    *) echo INCONNU; return ;;
  esac

  #  Les trois derniers chiffres, quel que soit le bit collant en tete.
  local u g o
  u=${mode: -3:1}; g=${mode: -2:1}; o=${mode: -1:1}

  #  Lisible de tous : la disponibilite est acquise, la confidentialite non.
  #  Ce verdict passe AVANT les autres — un `.env` world-readable est a
  #  signaler meme quand le proprietaire est le bon.
  case "$o" in 4|5|6|7) echo EXPOSE; return ;; esac

  #  Le proprietaire lit-il ? C'est le cas nominal.
  if [ "$prop" = "$utilisateur" ]; then
    case "$u" in 4|5|6|7) echo OK; return ;; esac
    echo ILLISIBLE; return
  fi

  #  Sinon, le groupe — a condition que l'utilisateur en fasse partie. Sans la
  #  liste de ses groupes, on se contente du groupe primaire du fichier.
  case "$g" in
    4|5|6|7)
      if [ "$groupe" = "$utilisateur" ] || grep -q " $groupe " <<<" $groupes "; then
        echo OK; return
      fi
      ;;
  esac
  echo ILLISIBLE
}

# ---------------------------------------------------------------------------
#  Self-test — le contrat du module, exécuté par le job CI `test-scripts`.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
#  C29. verdict_env_cles <cles du noeud A> <cles du noeud B>
#
#  PURE. Deux listes de NOMS de cles, separes par des espaces — jamais les
#  valeurs : ce controle ne doit rien faire circuler de secret.
#  Rend OK, INCONNU, ou « ECART <cles de A seul>|<cles de B seul> ».
# ---------------------------------------------------------------------------
verdict_env_cles() {
  [ -n "${1// /}" ] && [ -n "${2// /}" ] || { echo INCONNU; return; }
  #  Chaque jeu passe par la regle qui ECRIT le `.env` selon le role : ce qui
  #  en depend (ORIGIN, COOKIE_SECURE) se normalise tout seul, sans liste
  #  recopiee ici. On prend le role « actif » pour les deux : seule compte
  #  l egalite, et c est le seul role qui ne demande pas d IP.
  _env_cles_normalisees() {
    local k texte=""
    for k in $1; do texte+="$k="$'\n'; done
    env_role_transformer "$texte" actif | cut -d= -f1 | grep -E '^[A-Za-z_][A-Za-z0-9_]*$' | sort -u
  }
  local a b seul_a seul_b
  a=$(_env_cles_normalisees "$1"); b=$(_env_cles_normalisees "$2")
  seul_a=$(comm -23 <(echo "$a") <(echo "$b") | paste -sd, -)
  seul_b=$(comm -13 <(echo "$a") <(echo "$b") | paste -sd, -)
  if [ -z "$seul_a$seul_b" ]; then echo OK; else echo "ECART $seul_a|$seul_b"; fi
}

#  Les lignes C29 de check-reliability. Depend de ok/warn de l appelant.
#  $1 noeud local, $2 pair, $3 cles locales, $4 cles du pair, $5 code SSH du pair.
env_cles_verdicts() {
  [ "${5:-1}" -eq 0 ] || return 0
  local v d
  v=$(verdict_env_cles "$3" "$4")
  case "$v" in
    OK) ok "Cles du .env identiques sur les 2 noeuds (hors ORIGIN et COOKIE_SECURE, qui suivent le role)" ;;
    ECART*)
      d=${v#ECART }
      local a=${d%%|*} b=${d#*|}
      warn "Cles du .env DIVERGENTES : sur $1 seul : ${a:-aucune} · sur $2 seul : ${b:-aucune} (comparer les deux /opt/5hostachy/.env)" ;;
    *) warn "Cles du .env non relevees sur l un des noeuds : la comparaison n a pas eu lieu, son silence ne prouve rien" ;;
  esac
}

_env_role_selftest() {
  local echecs=0 obtenu

  _cas() {
    local titre=$1 attendu=$2 obtenu=$3
    if [ "$attendu" = "$obtenu" ]; then
      echo "  ✓ $titre"
    else
      echo "  ✗ $titre"
      echo "      attendu : $(printf '%s' "$attendu" | tr '\n' '|')"
      echo "      obtenu  : $(printf '%s' "$obtenu" | tr '\n' '|')"
      echecs=$((echecs + 1))
    fi
  }

  echo "lib-env-role.sh --selftest"

  #  1. Actif : origine publique, et COOKIE_SECURE RETIRÉE (pas mise à true —
  #     une valeur recopiée ici pourrait un jour contredire config.py).
  obtenu=$(env_role_transformer "$(printf 'A=1\nORIGIN=http://192.168.1.222\nCOOKIE_SECURE=false\nB=2')" actif)
  _cas "actif : origine publique, COOKIE_SECURE retirée" \
       "$(printf 'A=1\nORIGIN=https://5hostachy.fr\nB=2')" "$obtenu"

  #  2. Standby : origine sur son IP, COOKIE_SECURE=false.
  obtenu=$(env_role_transformer "$(printf 'A=1\nORIGIN=https://5hostachy.fr\nB=2')" standby 192.168.1.223)
  _cas "standby : origine locale, COOKIE_SECURE=false" \
       "$(printf 'A=1\nORIGIN=http://192.168.1.223\nB=2\nCOOKIE_SECURE=false')" "$obtenu"

  #  3. Idempotence : rejouer une bascule interrompue ne doit rien empiler.
  obtenu=$(env_role_transformer "$(env_role_transformer "$(printf 'ORIGIN=x')" standby 192.168.1.223)" standby 192.168.1.223)
  _cas "standby appliqué deux fois : une seule ligne COOKIE_SECURE" \
       "$(printf 'ORIGIN=http://192.168.1.223\nCOOKIE_SECURE=false')" "$obtenu"

  #  4. Le cas ZÉRO du passage standby → actif : la ligne doit DISPARAÎTRE, pas
  #     être laissée à `false`. C'est la faute que ce module existe pour rendre
  #     impossible — elle servirait le public sans drapeau `Secure`.
  obtenu=$(env_role_transformer "$(env_role_transformer "$(printf 'ORIGIN=x')" standby 192.168.1.222)" actif)
  _cas "standby → actif : plus aucune ligne COOKIE_SECURE" \
       "$(printf 'ORIGIN=https://5hostachy.fr')" "$obtenu"

  #  5. `.env` restauré sans ORIGIN : elle est AJOUTÉE, pas silencieusement
  #     absente — un site sans ORIGIN refuse les envois de formulaire.
  obtenu=$(env_role_transformer "$(printf 'A=1')" actif)
  _cas "ORIGIN absente : ajoutée" "$(printf 'A=1\nORIGIN=https://5hostachy.fr')" "$obtenu"

  #  6. Une valeur inattendue ne passe pas pour un succès.
  if env_role_transformer "ORIGIN=x" cuisinier >/dev/null 2>&1; then
    echo "  ✗ rôle inconnu accepté"; echecs=$((echecs + 1))
  else
    echo "  ✓ rôle inconnu refusé"
  fi
  if env_role_transformer "ORIGIN=x" standby >/dev/null 2>&1; then
    echo "  ✗ standby sans IP accepté"; echecs=$((echecs + 1))
  else
    echo "  ✓ standby sans IP refusé"
  fi

  #  🔴 L'ECRITURE preserve le proprietaire et le mode (#1138).
  #
  #  ⚠️ Hors root, ce cas passe trivialement : on ne peut pas changer le
  #  proprietaire d'un fichier qu'on vient de creer. Il n'est donc PAS la preuve
  #  du correctif — C28 l'est, en mesurant l'etat reel sur le noeud. Il est le
  #  filet qui attrape la regression le jour ou la bascule, elle, tourne en root :
  #  retirer le `chown --reference` le ferait echouer la, et nulle part ailleurs.
  #  Le dire ici evite qu'on le lise un jour comme une garantie qu'il ne donne pas.
  #  ⚠️ Le fichier d'épreuve ne s'appelle PAS `.env`, et c'est volontaire :
  #  `test_env_exemple_coherent.py` refuse toute redirection vers un `.env` dans
  #  un script versionné — il traque les installeurs qui régénèrent la
  #  configuration au lieu de s'en remettre au dépôt. Déclarer une exception pour
  #  un fichier temporaire affaiblirait ce contrôle-là pour rien : la fonction
  #  éprouvée se moque du nom qu'on lui donne.
  local tmpdir cible avant apres
  tmpdir=$(mktemp -d)
  cible="$tmpdir/env-sous-epreuve"
  printf 'ORIGIN=x
' > "$cible"
  chmod 640 "$cible"
  avant=$(stat -c '%U:%G:%a' "$cible" 2>/dev/null || echo INDISPONIBLE)
  env_role_appliquer "$cible" standby 192.168.1.223 >/dev/null
  apres=$(stat -c '%U:%G:%a' "$cible" 2>/dev/null || echo INDISPONIBLE)
  _cas "ecriture : proprietaire et mode inchanges" "$avant" "$apres"
  _cas "ecriture : le contenu est bien celui du role"        "ORIGIN=http://192.168.1.223" "$(grep '^ORIGIN=' "$cible")"
  rm -rf "$tmpdir"

  # ── C28. Ce que lit auto-deploy est-il lisible par qui le fait tourner ? ──
  #
  #  🔴 Le 22/09/2026, le `.env` du standby est passe root:root a la bascule
  #  de 02:03 : plus aucun build possible, ET plus aucune alerte — elle cherche
  #  le SMTP dans ce meme fichier. Aveugle et muet pendant 70 minutes (#1135).
  #
  #  Aucun des C1 a C27 ne posait la question. Elle est pure : un proprietaire,
  #  un mode, un utilisateur — donc eprouvable sans les deux RPi.
  _cas "C28 : proprietaire = utilisateur du cron" OK        "$(verdict_env_lisible ptressard ptressard 600 ptressard)"
  #  🔴 LE CAS VECU, celui qui a tout arrete.
  _cas "C28 : root:root en 600, cron en ptressard" ILLISIBLE        "$(verdict_env_lisible root root 600 ptressard)"
  #  Le groupe suffit, si le mode l'accorde.
  _cas "C28 : root:ptressard en 640" OK        "$(verdict_env_lisible root ptressard 640 ptressard)"
  _cas "C28 : root:ptressard en 600 — le groupe ne lit pas" ILLISIBLE        "$(verdict_env_lisible root ptressard 600 ptressard)"
  #  ⚠️ Lisible de TOUS, c'est lisible — et c'est un secret expose. Deux
  #  verdicts distincts : repondre OK cacherait un defaut de securite derriere
  #  une question de disponibilite.
  _cas "C28 : 644 — lisible, mais expose" EXPOSE        "$(verdict_env_lisible root root 644 ptressard)"
  #  🔴 CAS ZERO. Ne pas pouvoir lire les droits est exactement l'etat que
  #  ce controle doit reveler : INCONNU, jamais OK (`standards/04` §1).
  _cas "C28 : proprietaire non releve" INCONNU "$(verdict_env_lisible '' '' '' ptressard)"
  _cas "C28 : utilisateur du cron inconnu" INCONNU        "$(verdict_env_lisible root root 600 '')"
  _cas "C28 : mode illisible" INCONNU "$(verdict_env_lisible root root '' ptressard)"

  # ── C29. Les deux `.env` portent-ils les memes CLES ? (#1109) ─────────────
  #
  #  🔴 LE CAS VECU le 21/09/2026 : rpi1 portait WHATSAPP_DB_PASSWORD, que rpi2
  #  n avait pas — et aucun controle ne comparait la configuration dont depend
  #  le demarrage de la pile. Quatrieme divergence rpi1/rpi2 du depot.
  _cas "C29 : une cle presente sur un seul noeud" "ECART WHATSAPP_DB_PASSWORD|"        "$(verdict_env_cles 'A ORIGIN SECRET_KEY WHATSAPP_DB_PASSWORD' 'A ORIGIN SECRET_KEY')"
  _cas "C29 : l ecart est dit dans les deux sens" "ECART B|C"        "$(verdict_env_cles 'A B ORIGIN' 'A C ORIGIN')"
  #  ⚠️ L ECART LEGITIME : COOKIE_SECURE est retiree chez l actif et posee chez
  #  le standby, ORIGIN ajoutee si elle manque. La liste n est pas recopiee :
  #  les deux jeux passent par `env_role_transformer`, la regle qui les ecrit.
  _cas "C29 : COOKIE_SECURE sur le seul standby n est pas un ecart" OK        "$(verdict_env_cles 'A COOKIE_SECURE ORIGIN SECRET_KEY' 'A ORIGIN SECRET_KEY')"
  _cas "C29 : ORIGIN absente d un cote n est pas un ecart (elle est posee)" OK        "$(verdict_env_cles 'A SECRET_KEY' 'A ORIGIN SECRET_KEY')"
  _cas "C29 : l ordre ne compte pas" OK "$(verdict_env_cles 'B A' 'A B')"
  #  CAS ZERO : un `.env` non lu n a pas « les memes cles » que l autre.
  _cas "C29 : jeu de cles vide d un cote" INCONNU "$(verdict_env_cles 'A B' '')"
  _cas "C29 : les deux vides" INCONNU "$(verdict_env_cles '' '')"

  if [ "$echecs" -eq 0 ]; then
    echo "✓ lib-env-role : tous les cas passent."
    return 0
  fi
  echo "✗ lib-env-role : $echecs cas en échec."
  return 1
}

#  🔴 « SOURCE, jamais execute » n etait pas GARDE, et c est ce qui a failli
#  passer inapercu (22/09/2026).
#
#  Ce bloc ne regardait que `$1`. Or un module source herite des arguments de
#  son appelant : des que `check-reliability.sh` a source ce fichier, un
#  `check-reliability.sh --selftest` declenchait CE self-test, puis son
#  `exit $?` — le script sortait avec 0 sans avoir joue `verdicts_selftest` ni
#  `points_entree_selftest`. Un faux vert dans le contrat du job CI lui-meme.
#
#  La garde demande donc si ce fichier est EXECUTE, pas seulement s il voit
#  l argument. Tout module de la liste `for _mod` de `check-reliability.sh`
#  doit la porter : `lib-modules-sources.sh --selftest` le verifie.
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  _env_role_selftest
  exit $?
fi
