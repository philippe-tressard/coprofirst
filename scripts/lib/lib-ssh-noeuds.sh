#!/bin/bash
# =============================================================================
#  lib-ssh-noeuds.sh — La connexion SSH d'un nœud à l'autre (module à sourcer)
#
#  POURQUOI ce module existe (#1598, audit du 02/10/2026) :
#    La commande `ssh -i /root/.ssh/id_ed25519_bascule … StrictHostKeyChecking=no`
#    était recopiée dans CINQ scripts : bascule.sh, boot-role-guard.sh,
#    check-reliability.sh, health-watch.sh et noyau-standby.sh. Et l'option
#    recopiée était la mauvaise : la clé dédiée authentifie le CLIENT, jamais le
#    serveur. Avec `no`, un hôte qui prend l'IP du pair sur le réseau local
#    reçoit la connexion à chaque fois — et, pour `bascule.sh`, les octets de la
#    base répliquée et l'ordre de démarrer la production.
#
#  LA DÉCISION : `StrictHostKeyChecking=yes` + un `known_hosts` DÉDIÉ.
#    - `no`         accepte un hôte usurpé à CHAQUE connexion ;
#    - `accept-new` ne l'accepte qu'au premier contact — mais ce premier contact
#                   a lieu quand le fichier est vide, c'est-à-dire après une
#                   réinstallation, la nuit, pendant une bascule que personne ne
#                   regarde : la confiance se donne alors à qui répond ;
#    - `yes`        n'accepte que la clé épinglée. Deux hôtes fixes : épingler
#                   coûte UNE commande par nœud, une fois (`ssh_noeud_diagnostic`
#                   la donne), et un fichier absent ÉCHOUE au lieu de faire
#                   confiance. C'est le seul des trois qui échoue en se fermant.
#
#  POURQUOI le fichier vit dans /root/.ssh et pas dans le dépôt :
#    /opt/5hostachy appartient au compte de déploiement et `auto-deploy.sh` le
#    réécrit toutes les 5 minutes. Une ancre de confiance que ce compte peut
#    réécrire lui donnerait la main sur ce que root croit parler
#    (`standards/03` §8 bis). Le fichier est à root, à côté de la clé qu'il
#    complète, et `GlobalKnownHostsFile=/dev/null` en fait la SEULE référence.
#
#  Usage :
#    source /opt/5hostachy/scripts/lib/lib-ssh-noeuds.sh
#    SSH_CMD=$(ssh_noeud_cmd 10)            # délai de connexion, en secondes
#    $SSH_CMD ptressard@"$PEER_IP" "…" || log "… $(ssh_noeud_diagnostic "$PEER_IP")"
#
#  Test : bash lib-ssh-noeuds.sh --selftest   (aucun effet de bord hors mktemp)
# =============================================================================

#  Les deux chemins de la relation de confiance. La clé est celle de
#  `~/.claude/CLAUDE.md` §4 — ne pas la remplacer.
SSH_NOEUDS_CLE=/root/.ssh/id_ed25519_bascule
SSH_NOEUDS_KNOWN_HOSTS=/root/.ssh/known_hosts_bascule

# ── La commande, écrite UNE fois ─────────────────────────────────────────────
#  Rendue sous forme de chaîne : les appelants l'emploient nue (`$SSH_CMD hôte
#  cmd`) ou la passent à `rsync -e` (lib-volumes.sh). Aucun espace ni guillemet
#  dans les chemins : le découpage en mots du shell reste sûr.
ssh_noeud_cmd() { # [délai de connexion, défaut 10]
  echo "ssh -i $SSH_NOEUDS_CLE -o BatchMode=yes -o ConnectTimeout=${1:-10}" \
       "-o StrictHostKeyChecking=yes -o UserKnownHostsFile=$SSH_NOEUDS_KNOWN_HOSTS" \
       "-o GlobalKnownHostsFile=/dev/null"
}

# ── Un outil lancé À LA MAIN qui parle au pair : root, ou rien ───────────────
#  La clé ci-dessus n'est lisible que par root. Les points d'entrée (cron root,
#  unité systemd) le sont d'office ; un outil d'exploitation lancé par une
#  personne ne l'est que sous `sudo`. Lancé en ptressard, il ne pouvait pas
#  joindre le pair, lisait sa base « illisible » et refusait — sans dire
#  pourquoi (`reconstruire-replique.sh`, essai du 09/10/2026, #1781). Il le dit
#  désormais, AVANT le moindre geste. 🔒 `test_ssh_cmd_pose.py`.
ssh_noeud_exiger_root() { # $1 = le script appelant ($0)
  [ "$(id -u)" -eq 0 ] && return 0
  echo "La clé inter-nœuds ($SSH_NOEUDS_CLE) n'est lisible que par root — à lancer avec sudo : sudo bash $1" >&2
  exit 1
}

# ── La clé d'hôte de cette IP est-elle épinglée ? ────────────────────────────
#  → ok | absent (fichier manquant ou vide) | non-epingle | inconnu
#  `ssh-keygen -F` et non un grep : il lit les entrées HACHÉES (HashKnownHosts,
#  le défaut de Debian) et ne confond pas 192.168.1.22 avec 192.168.1.222.
#  Sans ssh-keygen, on ne sait pas : INCONNU, jamais ok (`standards/04` §1).
ssh_noeud_confiance() { # fichier ip
  [ -s "$1" ] || { echo absent; return 0; }
  command -v ssh-keygen >/dev/null 2>&1 || { echo inconnu; return 0; }
  if ssh-keygen -F "$2" -f "$1" >/dev/null 2>&1; then echo ok; else echo non-epingle; fi
}

# ── Ce que dit un appelant quand la connexion échoue ─────────────────────────
#  Vide si la clé est épinglée (la panne est ailleurs : réseau, nœud figé).
#  Sinon, la commande exacte à lancer une fois — un échec qui ne dit pas comment
#  en sortir finit contourné par `StrictHostKeyChecking=no`.
ssh_noeud_diagnostic() { # ip [fichier, défaut SSH_NOEUDS_KNOWN_HOSTS]
  local ip="$1" f="${2:-$SSH_NOEUDS_KNOWN_HOSTS}" v
  v=$(ssh_noeud_confiance "$f" "$ip")
  case "$v" in
    ok) return 0 ;;
    inconnu) echo "(confiance INCONNUE : ssh-keygen introuvable pour lire $f)" ;;
    *) echo "(clé d'hôte de $ip non épinglée — $f ${v/non-epingle/sans $ip}." \
            "Une fois, en root sur CE nœud : ssh-keyscan -t ed25519 $ip > $f ;" \
            "puis comparer ssh-keygen -lf $f à l'empreinte lue SUR $ip" \
            "(ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub) — docs/restauration-complete.md, étape 7)" ;;
  esac
}

# ── Self-test ────────────────────────────────────────────────────────────────
#  Garde `BASH_SOURCE` : sourcé par un script appelé avec `--selftest`, ce bloc
#  ne doit pas sortir à sa place (cf. lib-role.sh).
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  st=0
  t() { # description attendu obtenu
    if [ "$3" = "$2" ]; then echo "PASS  $1"; else echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; fi
  }
  contient() { case "$3" in *"$2"*) echo "PASS  $1" ;; *) echo "FAIL  $1  [$2] absent de [$3]"; st=1 ;; esac; }
  echo "== self-test lib-ssh-noeuds =="
  cmd=$(ssh_noeud_cmd 8)
  contient "la clé dédiée, inchangée"         "-i /root/.ssh/id_ed25519_bascule" "$cmd"
  contient "BatchMode : jamais d'invite"       "-o BatchMode=yes" "$cmd"
  contient "le délai demandé"                  "-o ConnectTimeout=8" "$cmd"
  contient "délai par défaut : 10 s"           "-o ConnectTimeout=10" "$(ssh_noeud_cmd)"
  contient "confiance explicite"               "-o StrictHostKeyChecking=yes" "$cmd"
  contient "known_hosts dédié"                 "-o UserKnownHostsFile=/root/.ssh/known_hosts_bascule" "$cmd"
  contient "seule référence"                   "-o GlobalKnownHostsFile=/dev/null" "$cmd"
  case "$cmd" in *"=no"*|*accept-new*) echo "FAIL  la commande ne fait confiance à personne d'office"; st=1 ;;
                 *) echo "PASS  la commande ne fait confiance à personne d'office" ;; esac

  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
  t "fichier absent → absent"                  absent "$(ssh_noeud_confiance "$tmp/rien" 10.0.0.2)"
  : > "$tmp/vide"
  t "fichier vide → absent (cas zéro)"         absent "$(ssh_noeud_confiance "$tmp/vide" 10.0.0.2)"
  if command -v ssh-keygen >/dev/null 2>&1; then
    ssh-keygen -q -t ed25519 -N '' -C test -f "$tmp/k" >/dev/null
    echo "10.0.0.2 $(cut -d' ' -f1,2 "$tmp/k.pub")" > "$tmp/kh"
    t "IP épinglée → ok"                       ok "$(ssh_noeud_confiance "$tmp/kh" 10.0.0.2)"
    t "autre IP → non-epingle"                 non-epingle "$(ssh_noeud_confiance "$tmp/kh" 10.0.0.3)"
    t "préfixe d'IP → non-epingle"             non-epingle "$(ssh_noeud_confiance "$tmp/kh" 10.0.0.)"
    cp "$tmp/kh" "$tmp/hache"; ssh-keygen -q -H -f "$tmp/hache" >/dev/null 2>&1
    t "entrée hachée (défaut Debian) → ok"     ok "$(ssh_noeud_confiance "$tmp/hache" 10.0.0.2)"
    t "épinglée : diagnostic muet"             "" "$(ssh_noeud_diagnostic 10.0.0.2 "$tmp/kh")"
    contient "non épinglée : la commande"      "ssh-keyscan -t ed25519 10.0.0.3 > $tmp/kh" "$(ssh_noeud_diagnostic 10.0.0.3 "$tmp/kh")"
    contient "non épinglée : la cause"         "$tmp/kh sans 10.0.0.3" "$(ssh_noeud_diagnostic 10.0.0.3 "$tmp/kh")"
  else
    echo "INCONNU  ssh-keygen absent : les cas d'épinglage ne sont pas joués"; st=2
  fi
  contient "absent : la cause"                 "$tmp/rien absent" "$(ssh_noeud_diagnostic 10.0.0.2 "$tmp/rien")"
  contient "absent : la vérification"          "/etc/ssh/ssh_host_ed25519_key.pub" "$(ssh_noeud_diagnostic 10.0.0.2 "$tmp/rien")"
  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS (code $st) =="
  exit $st
fi
