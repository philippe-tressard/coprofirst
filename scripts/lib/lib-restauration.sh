#!/bin/bash
# =============================================================================
#  lib-restauration.sh — Repartir de la COPIE HORS SITE : les gestes, une fois
#  (module à sourcer, #1921)
#
#  POURQUOI ce module existe :
#    Les deux nœuds perdus (sinistre, rançongiciel, `docker volume rm` sur les
#    deux), il n'y a ni pair ni primaire à copier : la résidence renaît de
#    l'archive que `scripts/poste/export-hors-site.sh` a tirée sur le poste. Aucun
#    geste de ce chemin n'était écrit sous PostgreSQL, et un geste qu'on n'écrit
#    qu'au jour du sinistre ne s'est jamais exécuté.
#
#    Les gestes vivent ICI, et deux appelants les emploient À L'IDENTIQUE :
#      - `restaurer-copie-hors-site.sh`         — le vrai, sur le nœud qui renaît ;
#      - `restaurer-copie-hors-site.sh --banc`  — l'ÉPREUVE, sur des ressources
#        jetables. Un banc qui rejouerait sa propre copie des gestes éprouverait
#        autre chose que la procédure (banc-volumes.sh, même raison).
#    Ce qui les distingue est le LANCEUR — le conteneur de l'image de l'API dans
#    lequel chaque geste s'exécute —, que l'appelant définit :
#      lancer_base     : en `app`, `DATABASE_URL` dans l'environnement, le
#                        dossier de l'export monté sur /restauration (lecture seule) ;
#      lancer_fichiers : en root, le volume des fichiers sur /app/uploads,
#                        l'archive montée sur /restauration/archive.tar.gz.
#
#  L'archive est celle de `utils/backup.py` sous PostgreSQL :
#    base-export.tar.gz   l'export vérifié (format neutre, `export_copropriete`) ;
#    uploads/…            les fichiers téléversés.
#  Une archive de l'époque SQLite (`app.db`) n'est PAS prise en charge : la
#  résidence est servie par PostgreSQL depuis le 10/10/2026 (DI-7).
#
#  Ce que ce module NE fait PAS : le `.env` (il se reconstruit à la main, depuis
#  `.env.example` et le gestionnaire de mots de passe), l'état WhatsApp (absent
#  des sauvegardes : on ré-appaire), le registre des installations (#1972).
#
#  Test : bash lib-restauration.sh --selftest   (aucun effet de bord)
# =============================================================================

#: Le membre de l'archive qui porte la base — écrit par `backup.NOM_EXPORT_BASE`.
RESTAURATION_EXPORT=base-export.tar.gz

# ── PURE : que contient l'archive ? ───────────────────────────────────────────
#  stdin : la liste des membres (`tar -tzf`) → postgresql | sqlite | illisible
nature_archive() {
    local membres
    membres=$(cat)
    if grep -qx "$RESTAURATION_EXPORT" <<< "$membres"; then echo postgresql
    elif grep -qx "app.db" <<< "$membres"; then echo sqlite
    else echo illisible; fi
}

# ── PURE : peut-on faire renaître la résidence de cette archive, ICI ? ────────
#  $1 nature de l'archive (postgresql|sqlite|illisible)
#  $2 le pair sert-il en LAN (oui|non) — `/api/health` à 200
#  $3 profil postgresql (oui|non) · $4 moteur de l'application (postgresql|…)
#  $5 conteneurs applicatifs ici (nombre) · $6 volume de base ici (oui|non)
#  $7 `.active` nomme ce nœud (oui|non) · $8 crons d'exploitation posés (oui|non)
#  → RESTAURER | REFUS:<raison>
decider_restauration() {
    case "$1" in
        postgresql) ;;
        sqlite) echo "REFUS:archive de l'époque SQLite (app.db) — cette procédure ne restaure que l'export vérifié"; return ;;
        *) echo "REFUS:archive illisible ou sans $RESTAURATION_EXPORT"; return ;;
    esac
    [ "$2" = non ] || { echo "REFUS:le pair SERT encore — un seul nœud est perdu : docs/restauration-complete.md, étapes 6 à 9"; return; }
    [ "$3" = oui ] || { echo "REFUS:PostgreSQL n'est pas activé (COMPOSE_PROFILES) dans .env"; return; }
    [ "$4" = postgresql ] || { echo "REFUS:DATABASE_URL ne désigne pas PostgreSQL dans .env"; return; }
    [ "$5" = 0 ] || { echo "REFUS:l'application tourne déjà ici ($5 conteneur(s))"; return; }
    [ "$6" = non ] || { echo "REFUS:un volume de base existe déjà ici — ce nœud n'est pas neuf, rien n'est écrasé"; return; }
    [ "$7" = oui ] || { echo "REFUS:.active doit nommer CE nœud — c'est lui qui va servir"; return; }
    [ "$8" = non ] || { echo "REFUS:crons d'exploitation déjà posés — auto-deploy démarrerait l'application sur une base vide : les poser APRÈS (étape 11)"; return; }
    echo RESTAURER
}

# ── PURE : le banc peut-il tourner ici ? ──────────────────────────────────────
#  $1 nature de l'archive · $2 conteneurs applicatifs ici (nombre)
#  → EPROUVER | REFUS:<raison>
decider_banc() {
    [ "$1" = postgresql ] || { echo "REFUS:archive sans $RESTAURATION_EXPORT ($1)"; return; }
    [ "$2" = 0 ] || { echo "REFUS:des conteneurs hostachy tournent ici — le banc ne s'exécute que sur le STANDBY"; return; }
    echo EPROUVER
}

# ── Geste 1 : sortir l'export de l'archive ────────────────────────────────────
#  $1 archive · $2 dossier (créé par l'appelant). Lisible par l'utilisateur
#  `app` du conteneur, qui n'est pas celui qui l'a extrait.
restauration_extraire_export() {
    tar -xzf "$1" -C "$2" "$RESTAURATION_EXPORT" || return 1
    chmod 755 "$2" && chmod 644 "$2/$RESTAURATION_EXPORT"
}

# ── Geste 2 : poser le schéma courant, puis IMPORTER en vérifiant ─────────────
#  Les gestes de `basculer-donnees.sh` (étapes 4 et 5), dans le même ordre : le
#  schéma marqué à la tête d'abord, sinon l'import créerait des tables qu'Alembic
#  ne connaîtrait pas. L'import relit la base et refuse un écart d'empreinte —
#  sa transaction est alors annulée, la base reste au schéma seul.
restauration_poser_base() {
    local schema
    schema=$(lancer_base python -m app.utils.schema_initial 2>/dev/null | tail -1)
    [ "$schema" = posee ] || { echo "schéma initial : « $schema » (attendu « posee » — la base n'est pas vide ?)"; return 1; }
    lancer_base python -m app.utils.export_copropriete importer \
        "/restauration/$RESTAURATION_EXPORT" env:DATABASE_URL
}

#  Python de l'image de l'API (3.12) : `filter="data"` refuse un membre qui
#  sortirait du dossier (`../`, lien absolu) — l'archive vient d'un disque que l'on
#  n'a pas sous les yeux. Puis l'inventaire : chaque fichier de l'archive est dans
#  le volume, à sa taille, et rien d'autre n'y est.
# shellcheck disable=SC2016
RESTAURATION_PY_FICHIERS='
import os, sys, tarfile
RACINE = "/app/uploads"
with tarfile.open("/restauration/archive.tar.gz") as t:
    membres = [m for m in t.getmembers() if m.name == "uploads" or m.name.startswith("uploads/")]
    t.extractall("/app", members=membres, filter="data")
attendu = sorted((m.name[len("uploads/"):], m.size) for m in membres if m.isfile())
vu = sorted(
    (os.path.relpath(os.path.join(r, f), RACINE), os.path.getsize(os.path.join(r, f)))
    for r, _, fs in os.walk(RACINE) for f in fs
)
if attendu != vu:
    manquants = sorted(set(attendu) - set(vu))[:5]
    en_trop = sorted(set(vu) - set(attendu))[:5]
    print(f"ECART manquants={manquants} en_trop={en_trop}")
    sys.exit(1)
print(f"FICHIERS {len(vu)}")
'

# ── Geste 3 : installer les fichiers téléversés dans leur volume ──────────────
#  → « FICHIERS <n> » sur la sortie, code 1 sur un écart. Les propriétés sont
#  reprises par `api/start.sh` au démarrage (`chown -R app:app /app/uploads`).
restauration_installer_fichiers() {
    lancer_fichiers python -c "$RESTAURATION_PY_FICHIERS"
}

# ── Self-test (aucun effet de bord) ───────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); r=${r%%:*}
          [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    n() { local r; r=$(printf '%b' "$2" | nature_archive)
          [ "$r" = "$3" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$3 obtenu=$r"; st=1; }; }
    n "archive PostgreSQL"                  "base-export.tar.gz\nuploads/\nuploads/a.jpg\n" postgresql
    n "archive SQLite"                      "app.db\nuploads/\n"                             sqlite
    n "archive vide (cas zéro)"             ""                                              illisible
    n "nom voisin, pas l'export"            "x/base-export.tar.gz\n"                         illisible
    t "tout est prêt"                       RESTAURER decider_restauration postgresql non oui postgresql 0 non oui non
    t "archive SQLite"                      REFUS     decider_restauration sqlite     non oui postgresql 0 non oui non
    t "archive illisible"                   REFUS     decider_restauration illisible  non oui postgresql 0 non oui non
    t "le pair sert : un seul nœud perdu"   REFUS     decider_restauration postgresql oui oui postgresql 0 non oui non
    t "pair non mesuré"                     REFUS     decider_restauration postgresql inconnu oui postgresql 0 non oui non
    t "profil éteint"                       REFUS     decider_restauration postgresql non non postgresql 0 non oui non
    t "application sous SQLite"             REFUS     decider_restauration postgresql non oui sqlite     0 non oui non
    t "application qui tourne"              REFUS     decider_restauration postgresql non oui postgresql 2 non oui non
    t "volume de base présent"              REFUS     decider_restauration postgresql non oui postgresql 0 oui oui non
    t ".active nomme l'autre"               REFUS     decider_restauration postgresql non oui postgresql 0 non non non
    t "crons déjà posés"                    REFUS     decider_restauration postgresql non oui postgresql 0 non oui oui
    t "banc sur le standby"                 EPROUVER  decider_banc postgresql 0
    t "banc sur l'actif"                    REFUS     decider_banc postgresql 3
    t "banc, archive SQLite"                REFUS     decider_banc sqlite 0
    [ "$st" -eq 0 ] && echo "lib-restauration : tous les cas passent."
    exit "$st"
fi
