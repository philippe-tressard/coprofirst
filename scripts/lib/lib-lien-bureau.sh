#!/bin/bash
# =============================================================================
#  lib-lien-bureau.sh — le lien du Bureau qui lance la copie hors site vise-t-il
#  encore le lanceur du dépôt ? (#2708)
#
#  Module SOURCÉ (mode 100644) par `scripts/poste/verifier-points-entree.sh`, donc
#  par le point 17 du pré-check. Son self-test passe par celui de ce script
#  (`verifier-points-entree.sh --selftest`, job `test-scripts`).
#
#  ## Le défaut
#
#  La copie hors site des sauvegardes n'est pas planifiée : Philippe la lance par
#  un lien du Bureau vers `scripts/poste/export-hors-site.command` du CLONE
#  PRINCIPAL (skill `infra-rpi`). Le point 17 ne comparait que les crons et l'unité
#  systemd des nœuds : un lanceur déplacé ou renommé cassait le lien sans que rien
#  ne le dise. C'est #377 (15/08/2026, raccourci Windows cassé par le rangement de
#  #350, trouvé à la main onze heures plus tard), fermé sans que le contrôle soit
#  écrit. Le seul filet restait l'alerte d'ancienneté de la copie : sept jours.
#
#  ## La règle
#
#  Le lien doit résoudre vers le lanceur du clone principal, et ce lanceur exister.
#  Un worktree ne compte pas : retiré après son lot (P12), il casserait le lien.
#  Lien absent ou illisible → INCONNU, jamais OK (un poste Windows a un raccourci
#  `.lnk`, que ce contrôle ne lit pas). Il n'écrit rien.
# =============================================================================

#  Le lien, une fois. Surchargeable pour le self-test de bout en bout.
LIEN_BUREAU_HORS_SITE="${LIEN_BUREAU_HORS_SITE:-$HOME/Desktop/Sauvegarde hors site 5Hostachy.command}"
#  Le lanceur, relatif à la racine d'un clone.
LANCEUR_HORS_SITE="scripts/poste/export-hors-site.command"

#  PURE. $1 lien présent (oui|non) · $2 cible résolue (vide : illisible)
#  · $3 cible présente (oui|non) · $4 cible attendue (vide : clone principal inconnu)
#  → `VERDICT|détail`, VERDICT ∈ OK | ECART | INCONNU
verdict_lien_bureau() {
  local present="$1" cible="$2" cible_presente="$3" attendue="$4"
  if [ "$present" != oui ]; then echo "INCONNU|lien du Bureau absent ou illisible"; return; fi
  if [ -z "$cible" ] || [ -z "$attendue" ]; then echo "INCONNU|cible du lien non résolue"; return; fi
  if [ "$cible" != "$attendue" ]; then echo "ECART|lien du Bureau vers $cible, attendu $attendue"; return; fi
  if [ "$cible_presente" != oui ]; then echo "ECART|lien du Bureau cassé : $cible absent"; return; fi
  echo "OK|lien du Bureau vers le lanceur du clone principal"
}

#  IMPURE — lit le disque. $1 racine d'un clone ou d'un worktree du dépôt.
#  Le clone principal se lit par le répertoire git COMMUN : d'un worktree, c'est
#  celui du clone qui l'a créé.
lien_bureau_releve() {
  local racine="$1" commun principal="" cible="" present=non cible_presente=non
  commun=$(git -C "$racine" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
  [ -n "$commun" ] && principal=$(cd "$commun/.." 2>/dev/null && pwd -P)
  if [ -L "$LIEN_BUREAU_HORS_SITE" ] || [ -e "$LIEN_BUREAU_HORS_SITE" ]; then
    present=oui
    #  `-m`, pas `-f` : un lien vers un worktree RETIRÉ (le cas de P12) n'a plus de
    #  dossier parent, `-f` ne rendait rien et le contrôle disait INCONNU au lieu de
    #  l'écart (trouvé par le self-test de bout en bout).
    cible=$(readlink -m "$LIEN_BUREAU_HORS_SITE" 2>/dev/null)
    [ -e "$cible" ] && cible_presente=oui
  fi
  verdict_lien_bureau "$present" "$cible" "$cible_presente" "${principal:+$principal/$LANCEUR_HORS_SITE}"
}

lien_bureau_selftest() {
  local echecs=0
  t() {  # $1 libellé · $2 verdict voulu · $3… arguments de verdict_lien_bureau
    local libelle="$1" voulu="$2" obtenu; shift 2
    obtenu=$(verdict_lien_bureau "$@"); obtenu=${obtenu%%|*}
    if [ "$obtenu" = "$voulu" ]; then echo "PASS  lien du Bureau : $libelle"
    else echo "ÉCHEC lien du Bureau : $libelle — attendu $voulu, obtenu $obtenu"; echecs=$((echecs+1)); fi
  }
  local A=/clone/scripts/poste/export-hors-site.command
  t "vise le lanceur du clone principal" OK      oui "$A" oui "$A"
  t "lanceur déplacé (lien cassé)"       ECART   oui "$A" non "$A"
  t "vise un worktree"                   ECART   oui /clone-2750/scripts/poste/export-hors-site.command oui "$A"
  t "vise un autre fichier"              ECART   oui /clone/scripts/poste/export-hors-site.sh oui "$A"
  t "lien absent"                        INCONNU non "" non "$A"
  t "cible non résolue"                  INCONNU oui "" non "$A"
  t "clone principal inconnu"            INCONNU oui "$A" oui ""

  #  De bout en bout, dans un dossier jetable : un vrai dépôt, un worktree, un lien.
  local tmp d
  tmp=$(mktemp -d); d=$(cd "$tmp" && pwd -P)
  git init -q "$d/clone" && mkdir -p "$d/clone/scripts/poste" \
    && touch "$d/clone/$LANCEUR_HORS_SITE" \
    && git -C "$d/clone" -c user.name=t -c user.email=t@example.org commit -q --allow-empty -m t \
    && git -C "$d/clone" worktree add -q "$d/wt" 2>/dev/null
  e2e() {  # $1 libellé · $2 cible du lien (vide : pas de lien) · $3 verdict voulu
    rm -f "$d/lien"; [ -n "$2" ] && ln -s "$2" "$d/lien"
    local obtenu; obtenu=$(LIEN_BUREAU_HORS_SITE="$d/lien" lien_bureau_releve "$d/wt"); obtenu=${obtenu%%|*}
    if [ "$obtenu" = "$3" ]; then echo "PASS  lien du Bureau, relevé : $1"
    else echo "ÉCHEC lien du Bureau, relevé : $1 — attendu $3, obtenu $obtenu"; echecs=$((echecs+1)); fi
  }
  e2e "lu depuis un worktree, lien vers le clone principal" "$d/clone/$LANCEUR_HORS_SITE" OK
  #  Le lanceur n'est pas versionné ici : le worktree n'a pas `scripts/poste/`, comme
  #  un worktree retiré — le lien est cassé jusqu'au dossier parent.
  e2e "lien vers un worktree (retiré)"                      "$d/wt/$LANCEUR_HORS_SITE"    ECART
  mv "$d/clone/$LANCEUR_HORS_SITE" "$d/clone/$LANCEUR_HORS_SITE.deplace"
  e2e "lanceur déplacé après la pose du lien"               "$d/clone/$LANCEUR_HORS_SITE" ECART
  e2e "pas de lien"                                         ""                            INCONNU
  rm -rf "$tmp"

  [ "$echecs" -eq 0 ] && echo "== lien du Bureau : TOUS OK ==" || echo "== lien du Bureau : $echecs ÉCHEC(S) =="
  return $((echecs > 0))
}
