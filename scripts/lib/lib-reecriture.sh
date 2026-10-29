#!/usr/bin/env bash
# =============================================================================
#  lib-reecriture.sh — la RÉÉCRITURE VOLONTAIRE d'une branche, déclarée et sûre
#
#  Module IMPORTÉ, jamais exécuté par un cron : pas de bit x, versionné en 100644.
#
#  ## Pourquoi ce module (#616, 29/08/2026)
#
#  Le point 0d du pré-check prescrit textuellement de RETIRER un bump de version
#  surnuméraire — « reset --soft puis push --force-with-lease ». Une fois le
#  remède appliqué, `origin/dev` porte un commit que HEAD n'a plus, et le point
#  0a le comptait comme un retard de clone.
#
#  **Corriger 0d faisait donc échouer 0a**, et les deux ne pouvaient pas être
#  verts en même temps avant le push. Or `.githooks/pre-push` exige une trace de
#  pré-check vert : la seule issue était `SKIP_PRECHECK=1`, c'est-à-dire désarmer
#  vingt-quatre contrôles pour en contourner un qui avait tort.
#
#  C'est le §25 du socle — « un contrôle dont le vert est INATTEIGNABLE finit par
#  se contourner » — et la deuxième occurrence sur ce fichier après #318, qui
#  l'avait corrigé sur le point 0c.
#
#  ## Ce que ce module refuse de faire
#
#  🔴 **Il ne devine aucune intention.** La réécriture se DÉCLARE, dans
#  `.git/reecriture-dev`, même forme datée que `.git/erreur-corrigee` :
#
#      commit: 601477b
#      137cab0
#
#  🔴 **Et déclarer ne suffit pas.** Ce qui rend le geste sûr est le
#  RECOUVREMENT : chaque fichier touché par un commit retiré doit avoir été
#  réécrit par HEAD. Sans cette condition, on aurait une case à cocher pour
#  écraser le travail d'une autre session — exactement ce que le point 0a existe
#  pour empêcher (26/07/2026 : `dev` à 16 commits de retard, `main` à 151).
#
#  ## Les trois moitiés, séparées exprès
#
#  | Fonction | Nature | Éprouvée par |
#  |---|---|---|
#  | `lire_declaration_reecriture` | parsing | des fichiers réels (CRLF, sha tronqué…) |
#  | `fichiers_non_recouverts` | mesure (interroge git) | un dépôt jetable |
#  | `verdict_reecriture` | décision **pure** | des valeurs |
#
#  La séparation n'est pas cosmétique : « l'autotest couvre la décision, jamais
#  les entrées/sorties qui l'alimentent » (socle 04 §11), et « un motif
#  d'extraction ne se relit pas, il s'exécute » (§22). Les deux premières sont
#  précisément celles qu'on aurait crues correctes à la relecture.
#
#  Extrait de `lib-verdicts-mep.sh` le 29/08/2026 : le garde-fou de modularité a
#  refusé les lignes ajoutées (388 → 516). La règle est « on découpe QUAND on y
#  touche » — et ces trois-là forment une notion, pas un fourre-tout.
#
#  Test : bash scripts/poste/precheck-mep.sh --selftest
# =============================================================================

#  Lire `.git/reecriture-dev` — le parsing, isolé pour être éprouvé.
#
#  ⚠️ C'est ici que vivent les pièges silencieux : un CRLF venu de Windows colle
#  un `` au sha et aucune comparaison ne correspond plus ; une ligne vide ou un
#  commentaire compte pour un commit ; un sha tronqué passe pour valide. Aucun de
#  ces défauts ne lève — ils rendent seulement la déclaration inopérante, ou pire,
#  la font correspondre à autre chose. Socle 04 §22 : un motif d'extraction ne se
#  relit pas, il s'exécute.
#
#  Rend deux lignes : le commit déclaré, puis les sha retirés séparés par des
#  espaces. Un fichier absent rend deux lignes vides — c'est le cas nominal, pas
#  une erreur.
#   $1 = chemin du fichier de déclaration
lire_declaration_reecriture() {
    local f="${1:-}"
    if [ ! -f "$f" ]; then printf '

'; return 0; fi
    local commit shas
    commit=$(sed -n '1s/^commit:[[:space:]]*//p' "$f" | tr -d '' | tr -d '[:space:]')
    #  Seules les lignes qui SONT un sha comptent : un commentaire ou une ligne
    #  vide ne doit pas gonfler le décompte, qui sert à refuser une déclaration
    #  qui ne correspond plus.
    shas=$(tail -n +2 "$f" | tr -d '' | grep -oE '^[0-9a-f]{7,40}$' | tr '
' ' ')
    printf '%s
%s
' "$commit" "${shas% }"
}

#  ── La MESURE qui nourrit `verdict_reecriture` ──────────────────────────────
#
#  ⚠️ Celle-ci n'est PAS pure : elle interroge git. Elle est isolée ici quand
#  même, et éprouvée sur un dépôt jetable — parce que « l'autotest couvre la
#  décision, jamais les entrées/sorties qui l'alimentent » (socle 04 §11), et que
#  c'est précisément dans l'extraction que vivent les défauts qui se relisent
#  comme corrects (§22).
#
#  Rend les FICHIERS que les commits manquants touchent et que HEAD n'a PAS
#  réécrits depuis la base commune — c'est-à-dire ce qui serait perdu. Sortie
#  vide = rien de perdu.
#
#  🔴 Une sortie vide n'est un vert que si la mesure a pu se faire : sans base
#  commune, la fonction sort en 1 et l'appelant doit lire INCONNU, jamais OK
#  (socle 04 §1).
#   $1 = référence amont (ex. origin/dev)
fichiers_non_recouverts() {
    local amont="${1:-}" base perdus="" c f
    [ -n "$amont" ] || return 1
    base=$(git merge-base HEAD "$amont" 2>/dev/null) || return 1
    [ -n "$base" ] || return 1
    for c in $(git rev-list "HEAD..$amont" 2>/dev/null); do
        for f in $(git show --pretty=format: --name-only "$c" 2>/dev/null); do
            [ -n "$f" ] || continue
            #  HEAD n'a pas touché ce fichier depuis la base : l'apport du commit
            #  retiré n'est recouvert par rien.
            if git diff --quiet "$base" HEAD -- "$f" 2>/dev/null; then
                case " $perdus " in *" $f "*) ;; *) perdus="$perdus $f" ;; esac
            fi
        done
    done
    printf '%s' "${perdus# }"
}

#  La réécriture est-elle déclarée ET sûre ? Fonction PURE : elle juge des
#  mesures, elle ne les prend pas.
#
#  Même forme de dérogation que `.git/erreur-corrigee` au point 6, et pour la
#  même raison : on ne DEVINE pas une intention, on la fait ÉCRIRE — puis on
#  vérifie qu'elle décrit encore la réalité.
#
#  🔴 Ce qui rend le geste sûr n'est PAS la déclaration, c'est le RECOUVREMENT :
#  chaque fichier touché par un commit retiré doit avoir été réécrit par HEAD.
#  Sans cette condition, on aurait une case à cocher pour écraser le travail d'une
#  autre session — exactement ce que le point 0a existe pour empêcher (26/07/2026 :
#  `dev` à 16 commits de retard, `main` à 151).
#
#   $1 commit de la déclaration   $2 HEAD   $3 commits déclarés retirés
#   $4 commits réellement manquants   $5 fichiers NON recouverts par HEAD
verdict_reecriture() {
  #  Aucune déclaration : ce n'est pas un défaut, c'est le cas nominal.
  { [ -z "${1:-}" ] && [ -z "${3:-}" ]; } && { echo non; return; }
  #  Déclaration partielle : on ne complète pas ce qu'elle ne dit pas.
  { [ -z "${1:-}" ] || [ -z "${3:-}" ] || [ -z "${2:-}" ]; } && { echo inconnu; return; }
  #  Datée par le commit, comme le brief de PR : une déclaration laissée par le
  #  lot précédent décrirait une réécriture qui n'est plus le sujet.
  [ "$1" != "$2" ] && { echo non; return; }
  case "${4:-}" in '') echo inconnu; return ;; esac
  #  🔴 La dérogation ne survit pas à son objet : les commits déclarés doivent
  #  être EXACTEMENT ceux qui manquent. Trop peu, et un commit d'ailleurs passerait
  #  dans l'ombre ; trop, et la déclaration décrit autre chose que ce qui se passe.
  [ "$(printf '%s
' "$3" | tr ' ' '
' | grep -c .)"       != "$(printf '%s
' "$4" | tr ' ' '
' | grep -c .)" ] && { echo non; return; }
  local _l4; _l4=$(printf '%s\n' $4)
  for c in $3; do
    grep -qF -- "$c" <<<"$_l4" || { echo non; return; }
  done
  #  Et surtout : rien de perdu. Un seul fichier non recouvert suffit à refuser.
  [ -n "${5:-}" ] && { echo non; return; }
  echo oui
}
