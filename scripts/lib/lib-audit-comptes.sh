#!/bin/bash
# =============================================================================
#  lib-audit-comptes.sh — S2 : qui peut entrer, et qui est root sans le dire ?
#
#  Module SOURCÉ (mode 100644) par `audit-securite.sh` (audit de sécurité
#  nocturne). Jamais exécuté par un cron.
#  Autotest : bash scripts/lib/lib-audit-comptes.sh --selftest
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  Un nœud compromis se GARDE par un compte : un utilisateur ajouté avec un
#  shell, un second UID 0 sous un autre nom, un mot de passe vidé dans
#  `/etc/shadow`, une entrée dans le groupe `docker` (équivalent root :
#  `docker run -v /:/host`, `lib-sudoers.sh`) ou `sudo`. C20/C21/C24 jugent les
#  règles sudo ; C38, la méthode d'authentification SSH. Rien ne lisait les
#  comptes eux-mêmes — et ces quatre portes se posent en une commande chacune.
#
#  Ce que S2 mesure, par nœud, sur la configuration EFFECTIVE (les fichiers que
#  le système lit, pas une intention) :
#    1. les comptes d'UID 0 : `root` seul ;
#    2. les comptes qui ont un SHELL de connexion : la liste déclarée ci-dessous ;
#    3. les comptes dont le champ de mot de passe est VIDE (connexion sans rien) ;
#    4. les membres des groupes qui VALENT root : la liste déclarée ci-dessous.
#
#  Un écart est un FAIL : aucun de ces quatre états n'a de raison d'apparaître
#  sans décision — et la décision s'écrit ici, dans la liste déclarée.
#  Une lecture vide (shadow sans root) rend INCONNU, jamais CONFORME.
#
#  Fonctions PURES : un texte entre, un verdict sort —
#    CONFORME · ECART:<ce qui diffère> · INCONNU:<pourquoi>
# =============================================================================

#: Les comptes ADMIS avec un shell de connexion : root, et le compte
#: d'exploitation (`SSH_NOEUDS_COMPTE`, `lib-ssh-noeuds.sh`). Tout autre compte
#: humain se déclare ici, avec sa raison.
COMPTES_SHELL_ADMIS="${COMPTES_SHELL_ADMIS:-root ptressard}"

#: Les groupes qui valent root, et leurs membres admis — « groupe:membre,membre ».
#: `docker` : le compte d'exploitation déploie par Compose (`docs/restauration-
#: complete.md`, `usermod -aG docker`). `sudo` : le même, par la règle de
#: `lib-sudoers.sh`. Un membre de plus est un root de plus.
GROUPES_ROOT_ADMIS="${GROUPES_ROOT_ADMIS:-docker:ptressard sudo:ptressard}"

#: Les shells qui ne permettent PAS de se connecter (comptes de service).
COMPTES_SHELLS_SANS_CONNEXION="/usr/sbin/nologin /sbin/nologin /bin/false /usr/bin/false /bin/sync /sbin/halt /sbin/shutdown"

# ── Décisions PURES ──────────────────────────────────────────────────────────

#  $1 = contenu de /etc/passwd → les comptes d'UID 0 autres que root (un par ligne)
comptes_uid0() {
    printf '%s\n' "${1:-}" | awk -F: '$3 == 0 && $1 != "root" { print $1 }'
}

#  $1 = contenu de /etc/passwd → les comptes qui ont un shell de connexion
#  et ne sont pas admis (un par ligne)
comptes_shell_hors_liste() {
    local ligne nom shell
    while IFS= read -r ligne; do
        [ -n "$ligne" ] || continue
        nom=${ligne%%:*}; shell=${ligne##*:}
        case " $COMPTES_SHELLS_SANS_CONNEXION " in *" $shell "*) continue ;; esac
        [ -n "$shell" ] || continue
        case " $COMPTES_SHELL_ADMIS " in *" $nom "*) continue ;; esac
        printf '%s\n' "$nom"
    done <<< "${1:-}"
}

#  $1 = contenu de /etc/shadow → les comptes dont le mot de passe est VIDE
comptes_sans_mot_de_passe() {
    printf '%s\n' "${1:-}" | awk -F: '$2 == "" { print $1 }'
}

#  $1 = sortie de `getent group <groupes>` (« docker:x:999:a,b » par ligne)
#  → « groupe:membre » pour chaque membre NON admis (un par ligne)
groupes_membres_hors_liste() {
    local ligne groupe membres m admis decl
    while IFS= read -r ligne; do
        [ -n "$ligne" ] || continue
        groupe=${ligne%%:*}; membres=${ligne##*:}
        admis=""
        for decl in $GROUPES_ROOT_ADMIS; do
            [ "${decl%%:*}" = "$groupe" ] && admis=${decl#*:}
        done
        local IFS=,
        for m in $membres; do
            [ -n "$m" ] || continue
            case ",$admis," in *",$m,"*) continue ;; esac
            printf '%s:%s\n' "$groupe" "$m"
        done
        unset IFS
    done <<< "${1:-}"
}

#  $1 = /etc/passwd · $2 = /etc/shadow · $3 = `getent group` des groupes root
#  → CONFORME | ECART:… | INCONNU:…
comptes_verdict() {
    local passwd=${1:-} shadow=${2:-} groupes=${3:-} ecarts="" v
    [ -n "$passwd" ] || { echo "INCONNU:/etc/passwd illisible"; return 0; }
    [ -n "$shadow" ] || { echo "INCONNU:/etc/shadow illisible (root requis)"; return 0; }
    grep -q '^root:' <<< "$shadow" || { echo "INCONNU:/etc/shadow sans ligne root — lecture tronquée"; return 0; }
    [ -n "$groupes" ] || { echo "INCONNU:groupes root illisibles (getent muet)"; return 0; }
    v=$(comptes_uid0 "$passwd" | paste -sd, -);                [ -z "$v" ] || ecarts="$ecarts uid0=[$v]"
    v=$(comptes_shell_hors_liste "$passwd" | paste -sd, -);    [ -z "$v" ] || ecarts="$ecarts shell=[$v]"
    v=$(comptes_sans_mot_de_passe "$shadow" | paste -sd, -);   [ -z "$v" ] || ecarts="$ecarts sans-mot-de-passe=[$v]"
    v=$(groupes_membres_hors_liste "$groupes" | paste -sd, -); [ -z "$v" ] || ecarts="$ecarts groupes=[$v]"
    if [ -n "$ecarts" ]; then echo "ECART:${ecarts# }"; else echo CONFORME; fi
}

# ── Les lectures (effets de bord : lecture seule) ────────────────────────────
comptes_lire_passwd() { cat /etc/passwd 2>/dev/null; }
comptes_lire_shadow() { cat /etc/shadow 2>/dev/null; }
comptes_lire_groupes() {
    local g noms=""
    for g in $GROUPES_ROOT_ADMIS; do noms="$noms ${g%%:*}"; done
    # shellcheck disable=SC2086  # liste de groupes, coupée exprès
    getent group $noms 2>/dev/null
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
audit_comptes_selftest() {
    local st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    echo "== self-test lib-audit-comptes (S2) =="
    local P="root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
ptressard:x:1000:1000::/home/ptressard:/bin/bash
postfix:x:104:110::/var/spool/postfix:/usr/sbin/nologin"
    local S="root:\$y\$j9T\$abc:19000:0:99999:7:::
daemon:*:19000:0:99999:7:::
ptressard:\$y\$j9T\$def:19000:0:99999:7:::"
    local G="docker:x:999:ptressard
sudo:x:27:ptressard"
    t "les deux nœuds tels qu'attendus" CONFORME "$(comptes_verdict "$P" "$S" "$G")"
    t "un second UID 0 (« toor ») — dit deux fois, c'est voulu" "ECART:uid0=[toor] shell=[toor]" \
      "$(comptes_verdict "$P
toor:x:0:0::/root:/bin/sh" "$S" "$G")"
    t "un UID 0 sans shell reste un UID 0" "ECART:uid0=[toor]" \
      "$(comptes_verdict "$P
toor:x:0:0::/root:/usr/sbin/nologin" "$S" "$G")"
    t "un compte avec shell, non déclaré" "ECART:shell=[support]" \
      "$(comptes_verdict "$P
support:x:1001:1001::/home/support:/bin/bash" "$S" "$G")"
    t "un shell zsh compte aussi" "ECART:shell=[dev]" \
      "$(comptes_verdict "$P
dev:x:1002:1002::/home/dev:/usr/bin/zsh" "$S" "$G")"
    t "un service en nologin ne compte pas" CONFORME \
      "$(comptes_verdict "$P
_apt:x:42:65534::/nonexistent:/usr/sbin/nologin" "$S" "$G")"
    t "mot de passe vidé" "ECART:sans-mot-de-passe=[ptressard]" \
      "$(comptes_verdict "$P" "${S/ptressard:\$y\$j9T\$def/ptressard:}" "$G")"
    t "un compte verrouillé (!) n'est pas vide" CONFORME \
      "$(comptes_verdict "$P" "$S
postfix:!:19000:0:99999:7:::" "$G")"
    t "un membre de plus dans docker" "ECART:groupes=[docker:www-data]" \
      "$(comptes_verdict "$P" "$S" "docker:x:999:ptressard,www-data
sudo:x:27:ptressard")"
    t "un membre dans sudo, groupe docker vide" "ECART:groupes=[sudo:intrus]" \
      "$(comptes_verdict "$P" "$S" "docker:x:999:
sudo:x:27:ptressard,intrus")"
    t "deux écarts, dans l'ordre" "ECART:uid0=[toor] groupes=[sudo:toor]" \
      "$(comptes_verdict "$P
toor:x:0:0::/root:/usr/sbin/nologin" "$S" "docker:x:999:ptressard
sudo:x:27:toor,ptressard")"
    #  LE CAS ZÉRO : rien de lu ne dit jamais « conforme ».
    t "passwd vide" INCONNU "$(comptes_verdict "" "$S" "$G" | cut -d: -f1)"
    t "shadow illisible (pas root)" INCONNU "$(comptes_verdict "$P" "" "$G" | cut -d: -f1)"
    t "shadow tronqué, sans root" INCONNU "$(comptes_verdict "$P" "daemon:*:1:::::" "$G" | cut -d: -f1)"
    t "getent muet" INCONNU "$(comptes_verdict "$P" "$S" "" | cut -d: -f1)"
    t "la lecture des groupes demande ceux de la liste" "docker sudo" \
      "$(getent() { shift; echo "$*"; }; comptes_lire_groupes | sed 's/^ //'; unset -f getent)"
    [ "$st" -eq 0 ] && echo "lib-audit-comptes : tous les cas passent."
    return "$st"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    audit_comptes_selftest; exit $?
fi
