#!/bin/bash
# =============================================================================
#  lib-audit-persistance.sh — S3 : les points de PERSISTANCE du système ont-ils
#  changé depuis la dernière lecture acceptée ?
#
#  Module SOURCÉ (mode 100644) par `audit-securite.sh` (audit de sécurité
#  nocturne). Jamais exécuté par un cron.
#  Autotest : bash scripts/lib/lib-audit-persistance.sh --selftest
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  Un attaquant qui a pris pied se donne un RETOUR : un cron, une unité ou un
#  minuteur systemd, une clé dans `authorized_keys`, une règle sudo, une
#  bibliothèque dans `ld.so.preload`, un script dans `profile.d`, un dépôt apt
#  ou une clé de confiance apt. Ces emplacements sont peu nombreux, connus, et
#  ne changent presque jamais sur un nœud en service — sauf par une décision.
#  C18/C22 lisent les crontabs, C24 la règle sudo du dépôt : chacun UN
#  emplacement. Les autres n'étaient lus par personne.
#
#  La méthode est celle d'un AIDE sans AIDE : un RELEVÉ (empreinte de chaque
#  fichier, cible de chaque lien) comparé à une RÉFÉRENCE acceptée par un humain.
#  Tout écart se nomme — ajouté, retiré, modifié — et se classe :
#    - CHAUD : un emplacement qui donne la main (cron, systemd, clés, sudo,
#      comptes, préchargement, apt). Un écart est un FAIL : il se lit la nuit
#      même, et s'accepte APRÈS lecture (`audit-securite.sh --accepter`) ;
#    - TIÈDE : la configuration que les mises à jour retouchent (sshd, pam,
#      fail2ban, ufw, apt.conf.d, firmware). Un écart est un WARN, dans le
#      digest quotidien ; son état EFFECTIF est jugé par ailleurs (S5, C38).
#
#  La référence vit HORS de l'arbre déployé, chez root (`AUDIT_SECURITE_DIR`,
#  mode 700) : une référence que le compte de déploiement pourrait réécrire
#  dirait ce qu'on lui fait dire (`standards/03` §8 bis, même règle que la clé
#  d'hôte épinglée de `lib-ssh-noeuds.sh`).
#
#  🔴 Une référence ABSENTE rend INCONNU, jamais CONFORME : la première nuit
#  après l'installation, S3 dit « référence à poser » et donne la commande.
#  Elle se pose à la main, après avoir lu le relevé — pas par l'audit lui-même,
#  qui accepterait alors l'état qu'il doit juger.
#
#  Fonctions PURES, sauf `persistance_relever` (lit le disque) et
#  `persistance_accepter` (écrit la référence), isolées plus bas.
# =============================================================================

#: Les emplacements CHAUDS — qui donnent la main. Un glob est admis (étendu par
#: le shell à la lecture). `/etc/shadow` : son EMPREINTE seule entre dans le
#: relevé, jamais son contenu.
PERSISTANCE_CHAUDS="${PERSISTANCE_CHAUDS:-/etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly /etc/crontab /var/spool/cron/crontabs /etc/systemd/system /etc/rc.local /etc/ld.so.preload /etc/profile.d /etc/bash.bashrc /etc/sudoers /etc/sudoers.d /root/.ssh/authorized_keys /home/*/.ssh/authorized_keys /etc/passwd /etc/group /etc/shadow /etc/docker/daemon.json /etc/hosts /etc/apt/sources.list /etc/apt/sources.list.d}"
#: Les emplacements TIÈDES — la configuration, que les mises à jour retouchent.
PERSISTANCE_TIEDES="${PERSISTANCE_TIEDES:-/etc/ssh/sshd_config /etc/ssh/sshd_config.d /etc/pam.d /etc/security /etc/fail2ban /etc/ufw/user.rules /etc/ufw/user6.rules /etc/apt/apt.conf.d /etc/apt/trusted.gpg.d /etc/apt/keyrings /usr/share/keyrings /boot/firmware/config.txt /boot/firmware/cmdline.txt}"

#: Les liens d'activation qui suivent le RÔLE du nœud, « <lien>=<cible attendue> ».
#: La bascule et le failover activent l'unité sur l'actif et la désactivent sur le
#: standby (`lib-failover.sh`) : sa présence change à chaque bascule nocturne, et
#: S3 criait au loup sur les deux nœuds le lendemain (01/11/2026, rpi1 « + »,
#: rpi2 « - »). Le lien à SA cible attendue sort donc du relevé comparé ; vers une
#: autre cible, il reste un écart CHAUD. L'activation selon le rôle est jugée par
#: `check-reliability.sh` (`cf_enabled` : activée chez l'actif, coupée chez le
#: standby), jamais ici.
PERSISTANCE_SELON_ROLE="${PERSISTANCE_SELON_ROLE:-/etc/systemd/system/multi-user.target.wants/cloudflared.service=/etc/systemd/system/cloudflared.service}"

#: Où vit la référence, chez root (créé en 700 par `persistance_accepter`).
AUDIT_SECURITE_DIR="${AUDIT_SECURITE_DIR:-/var/lib/hostachy/audit-securite}"
PERSISTANCE_REFERENCE="${PERSISTANCE_REFERENCE:-$AUDIT_SECURITE_DIR/persistance.releve}"

# ── Décisions PURES ──────────────────────────────────────────────────────────

#  $1 = un chemin → chaud | tiede | autre (un chemin hors des deux listes)
persistance_classe() {
    local c=${1:-} e
    for e in $PERSISTANCE_CHAUDS; do
        # shellcheck disable=SC2254  # le glob de la liste doit rester un motif
        case "$c" in $e|$e/*) echo chaud; return 0 ;; esac
    done
    for e in $PERSISTANCE_TIEDES; do
        # shellcheck disable=SC2254
        case "$c" in $e|$e/*) echo tiede; return 0 ;; esac
    done
    echo autre
}

#  $1 = un relevé → le même, sans les liens de PERSISTANCE_SELON_ROLE qui pointent
#  vers leur cible attendue (un lien vers une autre cible y reste).
persistance_sans_role() {
    local releve=${1:-} entree
    for entree in $PERSISTANCE_SELON_ROLE; do
        releve=$(printf '%s\n' "$releve" | grep -vxF "L:${entree#*=}  ${entree%%=*}" || true)
    done
    printf '%s\n' "$releve"
}

#  $1 = la référence · $2 = le relevé courant (lignes « <empreinte>  <chemin> »)
#  → une ligne par écart : « + chemin » (ajouté), « - chemin » (retiré),
#    « ~ chemin » (modifié) ; rien si identiques.
persistance_comparer() {
    local ref cur
    ref=$(persistance_sans_role "${1:-}" | awk 'NF >= 2 { e=$1; $1=""; sub(/^ +/, ""); print $0 "\t" e }' | sort)
    cur=$(persistance_sans_role "${2:-}" | awk 'NF >= 2 { e=$1; $1=""; sub(/^ +/, ""); print $0 "\t" e }' | sort)
    #  join sur le chemin : présent d'un seul côté, ou empreinte différente.
    join -t $'\t' -a1 -a2 -e MANQUE -o '0,1.2,2.2' <(printf '%s\n' "$ref") <(printf '%s\n' "$cur") \
        | awk -F'\t' '$2 == "MANQUE" { print "+ " $1; next }
                      $3 == "MANQUE" { print "- " $1; next }
                      $2 != $3       { print "~ " $1 }'
}

#  $1 = la référence · $2 = le relevé → CONFORME | FAIL:<chauds> | WARN:<tièdes> | INCONNU:…
#  Les chauds priment : un FAIL nomme aussi les tièdes, après.
persistance_verdict() {
    local ref=${1:-} cur=${2:-} ecarts ligne chauds="" tiedes=""
    [ -n "$ref" ] || { echo "INCONNU:référence absente — lire le relevé, puis l'accepter"; return 0; }
    [ -n "$cur" ] || { echo "INCONNU:relevé vide (root requis)"; return 0; }
    ecarts=$(persistance_comparer "$ref" "$cur")
    [ -n "$ecarts" ] || { echo CONFORME; return 0; }
    while IFS= read -r ligne; do
        [ -n "$ligne" ] || continue
        case "$(persistance_classe "${ligne:2}")" in
            tiede) tiedes="$tiedes${tiedes:+ }$ligne" ;;
            *)     chauds="$chauds${chauds:+ }$ligne" ;;
        esac
    done <<< "$ecarts"
    if [ -n "$chauds" ]; then echo "FAIL:$chauds${tiedes:+ · tièdes : $tiedes}"
    else echo "WARN:$tiedes"; fi
}

#  Le nombre d'écarts d'un verdict (pour la ligne de constat).
persistance_compte() { printf '%s' "${1:-}" | grep -o '[-+~] /' | grep -c .; }

# ── Le relevé (effet de bord : lit le disque, en root) ───────────────────────
#  Une ligne par fichier (« <sha256>  <chemin> ») et par lien (« L:<cible>  <chemin> ») ;
#  les répertoires sont parcourus, un glob étendu. Un chemin absent ne produit rien :
#  son apparition sera un « + ». Rien n'est écrit.
persistance_relever() {
    local e chemins=() f
    # shellcheck disable=SC2086  # les listes sont des globs, étendus exprès
    for e in $PERSISTANCE_CHAUDS $PERSISTANCE_TIEDES; do
        for f in $e; do [ -e "$f" ] || [ -L "$f" ] && chemins+=("$f"); done
    done
    [ "${#chemins[@]}" -gt 0 ] || return 0
    find "${chemins[@]}" \( -type f -o -type l \) -print0 2>/dev/null | sort -z | while IFS= read -r -d '' f; do
        if [ -L "$f" ]; then printf 'L:%s  %s\n' "$(readlink "$f")" "$f"
        #  `sed` : sous MSYS, sha256sum marque le mode binaire (« <empreinte> *chemin ») ;
        #  on normalise à la forme de coreutils (« <empreinte>  chemin »).
        else sha256sum -- "$f" 2>/dev/null | sed 's/^\([0-9a-f]\{64\}\) \*/\1  /'; fi
    done
}

# ── L'acceptation (effet de bord : écrit la référence, en root) ──────────────
#  $1 = le relevé à accepter. La référence est à root, lisible de lui seul.
persistance_accepter() {
    [ -n "${1:-}" ] || { echo "relevé vide : rien à accepter" >&2; return 1; }
    mkdir -p -m 700 "$AUDIT_SECURITE_DIR" && chmod 700 "$AUDIT_SECURITE_DIR" || return 1
    printf '%s\n' "$1" > "$PERSISTANCE_REFERENCE.tmp" && chmod 600 "$PERSISTANCE_REFERENCE.tmp" \
        && mv -f "$PERSISTANCE_REFERENCE.tmp" "$PERSISTANCE_REFERENCE"
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
audit_persistance_selftest() {
    local st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    echo "== self-test lib-audit-persistance (S3) =="
    local R="aaa  /etc/crontab
bbb  /etc/sudoers.d/5hostachy
ccc  /home/ptressard/.ssh/authorized_keys
ddd  /etc/fail2ban/jail.d/5hostachy.conf
L:/lib/systemd/system/docker.service  /etc/systemd/system/multi-user.target.wants/docker.service"
    t "identiques" CONFORME "$(persistance_verdict "$R" "$R")"
    t "aucun écart → rien" "" "$(persistance_comparer "$R" "$R")"
    t "une clé SSH ajoutée (fichier modifié) → FAIL" "FAIL:~ /home/ptressard/.ssh/authorized_keys" \
      "$(persistance_verdict "$R" "${R/ccc/cc2}")"
    t "un cron.d ajouté → FAIL" "FAIL:+ /etc/cron.d/retour" \
      "$(persistance_verdict "$R" "$R
eee  /etc/cron.d/retour")"
    t "un lien systemd qui change de cible → FAIL" "FAIL:~ /etc/systemd/system/multi-user.target.wants/docker.service" \
      "$(persistance_verdict "$R" "${R/L:\/lib\/systemd/L:\/tmp\/x}")"
    t "une règle sudo retirée → FAIL" "FAIL:- /etc/sudoers.d/5hostachy" \
      "$(persistance_verdict "$R" "$(grep -v sudoers <<< "$R")")"
    t "fail2ban retouché par une mise à jour → WARN" "WARN:~ /etc/fail2ban/jail.d/5hostachy.conf" \
      "$(persistance_verdict "$R" "${R/ddd/dd2}")"
    t "chaud ET tiède : FAIL, les tièdes après" \
      "FAIL:+ /etc/ld.so.preload · tièdes : ~ /etc/fail2ban/jail.d/5hostachy.conf" \
      "$(persistance_verdict "$R" "${R/ddd/dd2}
fff  /etc/ld.so.preload")"
    t "un chemin hors des listes est jugé chaud (pas d'angle mort)" "FAIL:+ /opt/inconnu" \
      "$(persistance_verdict "$R" "$R
ggg  /opt/inconnu")"
    t "classe : authorized_keys d'un compte (glob)" chaud "$(persistance_classe /home/x/.ssh/authorized_keys)"
    t "classe : un fichier sous sshd_config.d" tiede "$(persistance_classe /etc/ssh/sshd_config.d/01-x.conf)"
    t "classe : /etc/shadow" chaud "$(persistance_classe /etc/shadow)"
    t "classe : /etc/shadowx n'est pas /etc/shadow" autre "$(persistance_classe /etc/shadowx)"
    t "compte des écarts" 3 "$(persistance_compte "FAIL:+ /a ~ /b · tièdes : - /c")"
    #  LE CAS ZÉRO : sans référence ou sans relevé, jamais CONFORME.
    t "référence absente" INCONNU "$(persistance_verdict "" "$R" | cut -d: -f1)"
    t "relevé vide" INCONNU "$(persistance_verdict "$R" "" | cut -d: -f1)"
    t "les deux vides" INCONNU "$(persistance_verdict "" "" | cut -d: -f1)"
    #  Le lien du tunnel suit le rôle (bascule nocturne) : présent ou absent, ce
    #  n'est pas un écart ; vers une autre cible, c'en est un (01/11/2026).
    local LT="L:/etc/systemd/system/cloudflared.service  /etc/systemd/system/multi-user.target.wants/cloudflared.service"
    t "tunnel activé par la bascule (absent de la référence) → CONFORME" CONFORME \
      "$(persistance_verdict "$R" "$R
$LT")"
    t "tunnel coupé par la bascule (absent du relevé) → CONFORME" CONFORME \
      "$(persistance_verdict "$R
$LT" "$R")"
    t "lien du tunnel vers une AUTRE cible → FAIL" \
      "FAIL:+ /etc/systemd/system/multi-user.target.wants/cloudflared.service" \
      "$(persistance_verdict "$R" "$R
L:/tmp/faux.service  /etc/systemd/system/multi-user.target.wants/cloudflared.service")"
    t "un autre lien d'activation reste jugé → FAIL" "FAIL:+ /etc/systemd/system/multi-user.target.wants/retour.service" \
      "$(persistance_verdict "$R" "$R
L:/etc/systemd/system/retour.service  /etc/systemd/system/multi-user.target.wants/retour.service")"
    t "un chemin avec espace survit à la comparaison" "~ /etc/cron.d/a b" \
      "$(persistance_comparer "x  /etc/cron.d/a b" "y  /etc/cron.d/a b")"

    #  Le relevé RÉEL, sur une arborescence jetable, et l'acceptation.
    #  ⚠️ Un lien symbolique et un mode 700 ne se posent pas sur tout poste
    #  (MSYS sous Windows) : ces cas se disent SAUT, jamais PASS — la CI (Linux)
    #  les joue (`standards/05` §13).
    local d; d=$(mktemp -d)
    mkdir -p "$d/cron.d" "$d/sshd.d" "$d/home/u/.ssh" "$d/ref"
    echo a > "$d/cron.d/un"; echo k > "$d/home/u/.ssh/authorized_keys"; echo s > "$d/sshd.d/01.conf"
    local liens=oui modes=oui
    ln -s /nulle/part "$d/cron.d/lien" 2>/dev/null || liens=non
    mkdir -p "$d/sonde" && chmod 700 "$d/sonde" 2>/dev/null && [ "$(stat -c %a "$d/sonde")" = 700 ] || modes=non
    local releve verdict L="$d/cron.d $d/home/*/.ssh/authorized_keys" T="$d/sshd.d"
    releve=$(PERSISTANCE_CHAUDS="$L $d/absent" PERSISTANCE_TIEDES="$T" persistance_relever)
    if [ "$liens" = oui ]; then
        t "relevé : 4 entrées (3 fichiers, 1 lien), l'absent ignoré" 4 "$(grep -c . <<< "$releve")"
        t "relevé : le lien porte sa cible" 1 "$(grep -c "^L:/nulle/part  $d/cron.d/lien$" <<< "$releve")"
    else
        echo "SAUT  relevé des liens symboliques : ce poste ne sait pas en poser (la CI le mesure)"
        t "relevé : 3 fichiers, l'absent ignoré" 3 "$(grep -c . <<< "$releve")"
    fi
    t "relevé : empreinte puis chemin, sans marque de mode binaire" 3       "$(grep -c "^[0-9a-f]\{64\}  $d/" <<< "$releve")"
    if [ "$modes" = oui ]; then
        t "acceptation : référence écrite en 600 dans un dossier 700" "600 700"           "$(AUDIT_SECURITE_DIR="$d/ref/a" PERSISTANCE_REFERENCE="$d/ref/a/p" persistance_accepter "$releve"              && stat -c '%a' "$d/ref/a/p" | tr -d '
' && printf ' ' && stat -c '%a' "$d/ref/a")"
    else
        echo "SAUT  acceptation en 600/700 : ce poste ne pose pas les modes (la CI le mesure)"
    fi
    t "acceptation d'un relevé vide refusée" 1 "$(AUDIT_SECURITE_DIR="$d/ref/b" persistance_accepter "" 2>/dev/null; echo $?)"
    echo k2 >> "$d/home/u/.ssh/authorized_keys"; echo s2 > "$d/sshd.d/01.conf"
    verdict=$(PERSISTANCE_CHAUDS="$L" PERSISTANCE_TIEDES="$T"         persistance_verdict "$releve" "$(PERSISTANCE_CHAUDS="$L" PERSISTANCE_TIEDES="$T" persistance_relever)")
    t "relevé réel : clé ajoutée (FAIL) et sshd retouché (tiède)"       "FAIL:~ $d/home/u/.ssh/authorized_keys · tièdes : ~ $d/sshd.d/01.conf" "$verdict"
    rm -rf "$d"
    [ "$st" -eq 0 ] && echo "lib-audit-persistance : tous les cas passent."
    return "$st"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    audit_persistance_selftest; exit $?
fi
