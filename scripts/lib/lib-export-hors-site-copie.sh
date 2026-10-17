#!/bin/bash
# =============================================================================
#  lib-export-hors-site-copie.sh — les GESTES de la copie hors site (module à sourcer)
#
#  POURQUOI ce module existe (14/10/2026, #1896) :
#    La copie hors site a reçu une seconde série : les archives du REGISTRE des
#    installations (base `plateforme`, #1892). `export-hors-site.sh` était à 469
#    lignes ; y ajouter cette passe le faisait franchir le plafond de 500.
#
#    ⚠️ Deux gestes, à dire séparément :
#    - MODULARITÉ : `transferer_archive` et la relecture d'un export quittent le
#      script pour ce module — un déplacement, pas une factorisation ;
#    - FACTORISATION : ils servent désormais aux DEUX séries. La relecture était
#      écrite pour la résidence seule ; la recopier pour le registre aurait fait
#      deux contrôles d'intégrité qui divergent au premier changement de format.
#
#  Ce module fait du réseau et du disque — c'est ce qui le sépare de
#  `lib-export-hors-site.sh`, qui ne porte QUE des décisions pures. Il s'appuie
#  sur ce que l'appelant a posé : `SSH_CMD`, `LIRE`, `EXPORT_SSH_USER`,
#  `EXPORT_DEST`, `EXPORT_KEEP`, `log`, et les fonctions du module pur.
#
#  Usage :   source "$(dirname "$0")/../lib/lib-export-hors-site-copie.sh"
# =============================================================================

# ── Transférer UNE archive, sans jamais laisser de fichier tronqué ──────────
# 🔴 Écrite une fois (05/09/2026) : le rattrapage recopiait ce geste. La
# subtilité qui compte — le nom définitif n'apparaît QU'APRÈS un transfert
# complet, sinon une rotation prendrait un fichier tronqué pour une sauvegarde.
# Le chemin distant est RELATIF au volume (`nom` ou `plateforme/nom`) ; il a été
# validé par `nom_valide` avant d'arriver ici.
# `$4`/`$5` : la lecture d'un AUTRE volume — celui des fichiers pour les archives
# d'affaires (#2014) ; par défaut, celui des sauvegardes.
transferer_archive() { # $1=ip $2=relatif $3=destination [$4=lecture $5=montage] → 0 si complète
  local ip="$1" relatif="$2" dest="$3" lire="${4:-$LIRE}" montage="${5:-/b}"
  if $SSH_CMD "$EXPORT_SSH_USER@$ip" "$lire cat '$montage/$relatif'" > "$dest.partiel" 2>/dev/null; then
    mv -f "$dest.partiel" "$dest"
    return 0
  fi
  rm -f "$dest.partiel"
  return 1
}

# ── Relire un EXPORT vérifié : chaque table compte-t-elle ses lignes ? ──────
# L'export est celui de `app.utils.export_copropriete` : un manifeste et une
# table par fichier `.jsonl`. La résidence le range DANS son archive
# (`base-export.tar.gz`), le registre en fait son archive même. On le relit ici
# sans rien du projet : Python seul, présent sur le poste. Rend le verdict de
# `verdict_export_base` — « inconnue » si aucun Python ne l'a lu.
# 🔒 `test_sauvegarde_base_serveur.py` exécute ce code Python sur un export
# réellement produit : il le cherche entre les deux balises PYTHON ci-dessous.
relire_export() { # $1=chemin local de l'export → ok | « écarts : … » | inconnue
  local chemin="$1" resume="" py
  command -v cygpath >/dev/null 2>&1 && chemin=$(cygpath -w "$chemin")
  for py in python3 python py; do
    command -v "$py" >/dev/null 2>&1 || continue
    resume=$("$py" - "$chemin" 2>/dev/null <<'PYTHON'
import json, sys, tarfile
with tarfile.open(sys.argv[1]) as archive:
    manifeste = json.load(archive.extractfile("manifeste.json"))
    for table, info in manifeste["tables"].items():
        membre = archive.extractfile(f"tables/{table}.jsonl")
        lues = sum(1 for ligne in membre if ligne.strip()) if membre else -1
        print(table, lues, info["lignes"])
PYTHON
)
    break
  done
  verdict_export_base "$resume"
}

# ── La série du REGISTRE des installations (#1896) ──────────────────────────
# Chez la référence, `registre/sauvegarde.py` range chaque nuit une archive
# vérifiée de la base `plateforme` dans `<volume>/plateforme/`. Sans cette passe,
# le registre — et les contrats acceptés qu'il archive (R0) — n'avait aucune
# copie hors des deux RPi.
#
# ⚠️ Elle ne fait JAMAIS échouer l'export : le rapport de l'export appartient à la
# COPROPRIÉTÉ, et le registre ne la regarde pas (§4.11, règle 7). Le verdict part
# dans ses propres champs du rapport, que lit le contrôle de la PLATEFORME
# (`registre/sauvegarde.probleme_copie_hors_site`) pour prévenir l'opérateur.
#
# Pose PLATEFORME_ARCHIVE (nom copié, vide si aucun) et PLATEFORME_INTEGRITE :
# « ok », un motif d'échec, ou « sans objet » quand le nœud n'en porte aucune —
# une installation qui n'est pas la référence. Juger si l'absence est un défaut
# n'est pas le rôle du poste : le contrôle de la plateforme sait si le registre
# est allumé.
copier_plateforme() { # $1=ip du nœud source
  local ip="$1" liste nom dest local_ sha_src sha_dst octets empreintes verdict n
  PLATEFORME_ARCHIVE=""
  PLATEFORME_INTEGRITE="sans objet"
  #  `|| true` DANS le conteneur : un dossier absent est un constat (« sans
  #  objet »). L'accès au volume, lui, a déjà été établi par l'appelant.
  if ! liste=$($SSH_CMD "$EXPORT_SSH_USER@$ip" \
      "$LIRE sh -c 'ls -1 /b/$DOSSIER_PLATEFORME 2>/dev/null || true'" 2>/dev/null); then
    PLATEFORME_INTEGRITE="inconnue : lecture du dossier $DOSSIER_PLATEFORME impossible"
    log "  ! Registre : lecture impossible — copie INCONNUE."
    return 0
  fi
  nom=""
  for n in $(printf '%s\n' "$liste" | tr -d '\r'); do
    nom_valide "$n" "$PREFIXE_PLATEFORME" && nom="$n"   # `ls` trie : la dernière est la plus récente
  done
  if [ -z "$nom" ]; then
    log "  Registre : aucune archive sur ce nœud — sans objet (pas la référence)."
    return 0
  fi
  PLATEFORME_ARCHIVE="$nom"
  dest="$EXPORT_DEST/$DOSSIER_PLATEFORME"
  local_="$dest/$nom"
  mkdir -p "$dest" || { PLATEFORME_INTEGRITE="destination inaccessible"; return 0; }

  sha_src=$($SSH_CMD "$EXPORT_SSH_USER@$ip" "$LIRE sha256sum '/b/$DOSSIER_PLATEFORME/$nom'" 2>/dev/null | awk '{print $1}')
  if ! { [ -f "$local_" ] && [ "$(sha256sum "$local_" | awk '{print $1}')" = "$sha_src" ]; }; then
    if ! transferer_archive "$ip" "$DOSSIER_PLATEFORME/$nom" "$local_"; then
      PLATEFORME_INTEGRITE="transfert interrompu"
      log "  ! Registre : transfert de $nom interrompu."
      return 0
    fi
  fi
  octets=$(stat -c%s "$local_" 2>/dev/null || echo 0)
  sha_dst=$(sha256sum "$local_" 2>/dev/null | awk '{print $1}')
  empreintes="non"; [ -n "$sha_src" ] && [ "$sha_src" = "$sha_dst" ] && empreintes="oui"
  #  L'archive du registre EST l'export : la même relecture, la même règle de
  #  verdict que la résidence — « ok » ou rien.
  verdict=$(verdict_archive "$octets" "$empreintes" oui "$(relire_export "$local_")")
  if [ "${verdict%%|*}" != "succes" ]; then
    PLATEFORME_INTEGRITE="${verdict#*|}"
    mv -f "$local_" "$local_.invalide" 2>/dev/null || true
    log "  ! Registre : $nom écartée — ${verdict#*|}"
    return 0
  fi
  PLATEFORME_INTEGRITE="ok"
  while IFS= read -r n; do
    [ -n "$n" ] && rm -f "$dest/$n"
  done < <(ls -1 "$dest"/"$PREFIXE_PLATEFORME"*.tar.gz 2>/dev/null | xargs -r -n1 basename | sort | archives_a_supprimer "$EXPORT_KEEP")
  log "  Registre : $nom copiée et vérifiée ($octets octets)."
}

# ── Les archives d'affaires échues (#2014, lot L3) ──────────────────────────
# L'API les range dans le volume des FICHIERS, sous `$DOSSIER_AFFAIRES`. Le poste
# les tire TOUTES — aucune rotation : c'est l'archive hors ligne de la
# conservation, arbitrée le 16/10/2026 — dans `$EXPORT_DEST/archives-affaires/`,
# rangée à part des sauvegardes tournantes.
#
# ⚠️ Comme le registre, cette passe ne fait JAMAIS échouer l'export. Une archive
# qu'on n'a pas su copier n'est simplement pas accusée : le serveur la garde, et
# son contrôle d'âge (`conservation_copie.archives_en_retard`) le dit au-delà de
# 30 jours.
#
# Pose AFFAIRES_COPIEES (lignes « nom empreinte » des copies VÉRIFIÉES, présentes
# sur le PC et toujours annoncées par le serveur) et AFFAIRES_RESUME.
LIRE_FICHIERS="docker run --rm -v 5hostachy_uploads:/u:ro alpine"
copier_archives_affaires() { # $1=ip du nœud source
  local ip="$1" liste n dest local_ sha_src sha_dst neuves=0 echecs=0 copiees
  AFFAIRES_COPIEES=""
  AFFAIRES_RESUME="aucune archive"
  if ! liste=$($SSH_CMD "$EXPORT_SSH_USER@$ip" \
      "$LIRE_FICHIERS sh -c 'ls -1 /u/$DOSSIER_AFFAIRES 2>/dev/null || true'" 2>/dev/null); then
    AFFAIRES_RESUME="INCONNU : lecture du volume des fichiers impossible"
    log "  ! Archives d'affaires : lecture impossible — copie INCONNUE."
    return 0
  fi
  dest="$EXPORT_DEST/archives-affaires"
  for n in $(printf '%s\n' "$liste" | tr -d '\r'); do
    nom_archive_affaires_valide "$n" || continue
    mkdir -p "$dest" || { AFFAIRES_RESUME="destination inaccessible"; return 0; }
    local_="$dest/$n"
    sha_src=$($SSH_CMD "$EXPORT_SSH_USER@$ip" \
      "$LIRE_FICHIERS sha256sum '/u/$DOSSIER_AFFAIRES/$n'" 2>/dev/null | awk '{print $1}')
    if ! { [ -f "$local_" ] && [ "$(sha256sum "$local_" | awk '{print $1}')" = "$sha_src" ]; }; then
      if ! transferer_archive "$ip" "$DOSSIER_AFFAIRES/$n" "$local_" "$LIRE_FICHIERS" /u; then
        echecs=$((echecs + 1))
        log "  ! Archive d'affaires $n : transfert interrompu."
        continue
      fi
      neuves=$((neuves + 1))
    fi
    sha_dst=$(sha256sum "$local_" 2>/dev/null | awk '{print $1}')
    if [ -z "$sha_src" ] || [ "$sha_src" != "$sha_dst" ]; then
      mv -f "$local_" "$local_.invalide" 2>/dev/null || true
      echecs=$((echecs + 1))
      log "  ! Archive d'affaires $n : empreinte différente — écartée."
      continue
    fi
    AFFAIRES_COPIEES="$AFFAIRES_COPIEES$n $sha_dst"$'\n'
  done
  copiees=$(printf '%s' "$AFFAIRES_COPIEES" | grep -c . || true)
  AFFAIRES_RESUME="$copiees copiée(s), dont $neuves nouvelle(s), $echecs en échec"
  log "  Archives d'affaires : $AFFAIRES_RESUME — aucune rotation."
}

# L'accusé : le serveur note « copiée le » chaque archive dont il reconnaît
# l'empreinte, et retirera sa copie 30 jours plus tard. Corps par l'entrée
# standard, comme `rapport_envoyer` (#1964).
accuser_archives_affaires() { # $1=url de base $2=clé
  local http
  [ -n "$AFFAIRES_COPIEES" ] || return 0
  http=$(printf '%s' "$AFFAIRES_COPIEES" | charge_accuse_affaires \
    | curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
        -X POST "$1/api/admin/maintenance/archives-affaires/copiees" \
        -H "Content-Type: application/json" -H "x-maintenance-key: $2" \
        --data-binary @- 2>/dev/null) || http="000"
  if [ "$http" = "200" ]; then
    log "  → Copie des archives d'affaires accusée (HTTP $http)"
  else
    log "  ⚠ Accusé des archives d'affaires non enregistré (HTTP $http) — le serveur les garde."
  fi
}
