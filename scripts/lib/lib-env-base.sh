#!/bin/bash
# =============================================================================
#  lib-env-base.sh — Une ligne du `.env` des DEUX nœuds : `DATABASE_URL` (la base
#  servie, DI-7c, #1782) et `CLE_SIGNATURE_BAUX` (R2, #1878) — module à sourcer
#
#  Un AJUSTEMENT du `.env`, jamais sa régénération : une seule ligne change, et
#  l'ancienne valeur peut y rester en commentaire, datée (`# RETOUR_SQLITE=`).
#  Deux scripts s'en servent dans les deux sens — `basculer-donnees.sh` (SQLite →
#  PostgreSQL) et `retour-sqlite.sh` (l'inverse) — : la réécriture s'écrit ICI.
#
#  🔴 L'URL d'une base serveur porte son mot de passe : elle ne passe jamais par
#  une ligne de commande (lisible par `ps`). `awk` la lit dans l'environnement,
#  le `.env` du pair voyage par l'entrée standard de SSH, et y est réécrit en 600.
#
#  Test : bash lib-env-base.sh --selftest   (aucun effet de bord)
# =============================================================================

# ── PURE : le texte d'un `.env`, UNE de ses lignes réécrite ──────────────────
#  $1 texte · $2 clé · $3 valeur · $4 ligne qui la précède (commentaire, vide
#  sinon) · $5 motif (ERE) des lignes à retirer (vide sinon)
#  Une seule ligne `clé=` ; la ligne qui la précède, une fois ; les lignes du motif
#  partent. Généralisée le 13/10/2026 pour la clé des baux (R2 #1878) : même
#  transport, même secret qui ne passe jamais par une ligne de commande.
reecrire_cle_env() {
    printf '%s\n' "$1" | CLE_ENV="$2" VALEUR_ENV="$3" LIGNE_AVANT="$4" A_RETIRER="$5" awk '
        BEGIN { cle = ENVIRON["CLE_ENV"] "="; val = ENVIRON["VALEUR_ENV"]
                avant = ENVIRON["LIGNE_AVANT"]; retirer = ENVIRON["A_RETIRER"] }
        retirer != "" && $0 ~ retirer { next }
        index($0, cle) == 1 { if (!fait) { if (avant != "") print avant; print cle val; fait = 1 }; next }
        { print }
        END { if (!fait) { if (avant != "") print avant; print cle val } }'
}

#  Le `.env` de ce dépôt ($REPO) — ses droits restent les siens (réécrit en place).
#  $1 clé · $2 valeur · [$3 ligne avant] · [$4 motif à retirer]
ecrire_cle_env_local() {
    local t
    t=$(reecrire_cle_env "$(cat "$REPO/.env")" "$1" "$2" "${3:-}" "${4:-}") && printf '%s\n' "$t" > "$REPO/.env"
}

#  Le `.env` du pair ($SSH_CMD, $PEER_IP) — lu et réécrit par l'entrée standard.
ecrire_cle_env_pair() {
    local t
    t=$($SSH_CMD ptressard@"$PEER_IP" "cat /opt/5hostachy/.env") || return 1
    printf '%s\n' "$(reecrire_cle_env "$t" "$1" "$2" "${3:-}" "${4:-}")" \
        | $SSH_CMD ptressard@"$PEER_IP" "umask 077 && cat > /opt/5hostachy/.env.tmp && chmod 600 /opt/5hostachy/.env.tmp && mv /opt/5hostachy/.env.tmp /opt/5hostachy/.env"
}

#  La clé $1 a-t-elle une valeur dans le `.env` du pair ? → oui | non (code ≠ 0 :
#  pair injoignable — l'appelant décide, une absence n'est pas une réponse).
cle_env_pair_presente() {
    local n
    n=$($SSH_CMD ptressard@"$PEER_IP" "grep -c '^$1=.' /opt/5hostachy/.env") ; [ -n "$n" ] || return 1
    [ "$n" -gt 0 ] && echo oui || echo non
}

# ── DATABASE_URL : la base servie (DI-7c) ─────────────────────────────────────
#  La ligne de retour (`# RETOUR_SQLITE=…`) précède la nouvelle URL ; une
#  ancienne ligne de retour part toujours.
MOTIF_RETOUR_SQLITE='^# RETOUR_SQLITE='
reecrire_database_url() { reecrire_cle_env "$1" DATABASE_URL "$2" "$3" "$MOTIF_RETOUR_SQLITE"; }
ecrire_database_url_local() { ecrire_cle_env_local DATABASE_URL "$1" "$2" "$MOTIF_RETOUR_SQLITE"; }
ecrire_database_url_pair() { ecrire_cle_env_pair DATABASE_URL "$1" "$2" "$MOTIF_RETOUR_SQLITE"; }

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { [ "$3" = "$2" ] && echo "PASS  $1 → $3" || { echo "FAIL  $1  attendu=$2 obtenu=$3"; st=1; }; }
    compte() { printf '%s\n' "$1" | grep -cE "$2"; }
    env_av=$'A=1\nDATABASE_URL=sqlite:////app/data/app.db\nB=2'
    apres=$(reecrire_database_url "$env_av" "postgresql+psycopg://u:p@postgres:5432/b" "# RETOUR_SQLITE=sqlite:////app/data/app.db (bascule du 2026-10-09)")
    t "une seule ligne DATABASE_URL"        1 "$(compte "$apres" '^DATABASE_URL=')"
    t "elle désigne PostgreSQL"             1 "$(compte "$apres" '^DATABASE_URL=postgresql\+psycopg://')"
    t "la ligne de retour est posée"        1 "$(compte "$apres" '^# RETOUR_SQLITE=sqlite:')"
    t "les autres clés restent"             2 "$(compte "$apres" '^(A=1|B=2)$')"
    retour=$(reecrire_database_url "$apres" "sqlite:////app/data/app.db" "")
    t "retour : la ligne de retour part"    0 "$(compte "$retour" '^# RETOUR_SQLITE=')"
    t "retour : SQLite de nouveau"          1 "$(compte "$retour" '^DATABASE_URL=sqlite:')"
    t "un .env sans DATABASE_URL la reçoit" 1 "$(compte "$(reecrire_database_url 'A=1' 'sqlite://x' '')" '^DATABASE_URL=')"
    t "un mot de passe à caractères spéciaux passe intact" 1 \
      "$(compte "$(reecrire_database_url "$env_av" 'postgresql://u:a&b/c\d@h/b' '')" '^DATABASE_URL=postgresql://u:a&b/c\\d@h/b$')"
    cle=$(reecrire_cle_env "$env_av" CLE_SIGNATURE_BAUX "abc+/=" "")
    t "une clé neuve s'ajoute"              1 "$(compte "$cle" '^CLE_SIGNATURE_BAUX=abc\+/=$')"
    t "et ne touche pas DATABASE_URL"       1 "$(compte "$cle" '^DATABASE_URL=sqlite:')"
    t "une clé présente se réécrit, une fois" 1       "$(compte "$(reecrire_cle_env "$cle" CLE_SIGNATURE_BAUX "xyz" "")" '^CLE_SIGNATURE_BAUX=')"
    [ "$st" -eq 0 ] && echo "lib-env-base : tous les cas passent."
    exit "$st"
fi
