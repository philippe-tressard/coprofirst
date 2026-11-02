#!/usr/bin/env bash
# =============================================================================
#  lib-autodeploy.sh — les contrôles du seul cron UTILISATEUR (C13 et C27)
#
#  Extrait le 21/09/2026, au fil de l'eau : `check-reliability.sh` était à 499
#  lignes et `lib-verdicts.sh` à 484 ; C27 leur faisait franchir le plafond de
#  500 (rang 1 §4), et le garde-fou de modularité l'a refusé.
#
#  La coupe suit la NATURE, pas le numéro — comme `lib-conformite.sh` avant
#  elle. Ces deux contrôles partagent une question, et ils sont les seuls à la
#  poser : *le seul cron utilisateur fait-il son travail ?*
#
#    C13  peut-il ÉCRIRE son journal ?   (sinon il ne tourne plus, en silence)
#    C27  son travail ABOUTIT-il ?       (sinon le code est à jour, pas l'image)
#
#  ⚠️ Les deux ne se mesurent pas de la même façon, et c'est délibéré : C13
#  regarde un ARTEFACT (le propriétaire du log), parce que sa cause est unique
#  et connue — la rotation le re-chown en root. C27 regarde le COMPORTEMENT (le
#  build a-t-il abouti), parce que ses causes sont ouvertes : droits, disque,
#  registre, Dockerfile. Un contrôle sur les droits du `.env` serait vert le
#  jour où le build échouera pour une autre raison.
#
#  ⚠️ Ce module n'est PAS autonome. Il emploie `ok`, `warn`, `fail`, `$SELF`,
#  `$PEER` et `$PEER_OK` définis par son appelant : il est sourcé APRÈS eux et
#  appelé par `autodeploy_verdicts`.
# =============================================================================
# ── C27. auto-deploy a-t-il RÉUSSI son build ? (PURE) ────────────────────────
#
# 🔴 Né du 21/09/2026 : la bascule nocturne avait mis rpi1 en standby, et son
# `auto-deploy` n'a pas pu lire `/opt/5hostachy/.env` — root:root là-bas,
# ptressard:ptressard sur rpi2. Le code s'est aligné, **les images non**, et
# l'alerte qui devait le dire est morte de la MÊME cause : elle cherche la
# configuration SMTP dans ce `.env` illisible.
#
# C'est la troisième divergence rpi1/rpi2 du dépôt, après les sudoers (09/08)
# et un cron en trop sur rpi2 (06/08).
#
# ⚠️ Ce contrôle regarde le COMPORTEMENT — « le build a-t-il réussi ? » — et
# non la cause connue (les droits du `.env`). Un contrôle sur les droits serait
# vert le jour où le build échouera pour une autre raison : disque plein,
# registre injoignable, Dockerfile cassé. C13 fait l'inverse pour le LOG, et
# c'est cohérent : là-bas la cause est unique et connue (la rotation re-chown),
# ici elles sont ouvertes.
#
# ⚠️ Motif SANS accent : la ligne traverse SSH depuis le peer, et « ÉCHEC »
# dépendrait de la locale des deux bouts. « CHEC du build » est distinctif —
# même raison que la marque ASCII de C17 (`lib-maintenance-trace.sh`).
#
# 🔴 Depuis #1587, CHAQUE sortie d'auto-deploy est datée — celle d'un fetch en
# échec comme celle d'un `set -e` imprévu. C14 (le battement) les voit donc
# vivantes, et c'est juste : le script tourne. Ce qu'elles disent de son
# TRAVAIL se lit ici, sinon une clé révoquée ou un `up -d` en échec à chaque
# passage serait vert partout, là où le silence d'avant faisait au moins
# tomber C14.
#   « fetch impossible »  GitHub injoignable : rien ne se déploie (REPORTE) ;
#   « CHEC inattendu »    le filet de `lib-journal` : sortie non prévue.
verdict_build_autodeploy() {  # $1 = dernière ligne horodatée du deploy.log
                              # → OK | FAIL | REPORTE | INTERROMPU | INCONNU
  local ligne="${1:-}"
  [ -z "$ligne" ] && { echo INCONNU; return; }
  case "$ligne" in
    *"CHEC du build"*)    echo FAIL ;;
    *"CHEC inattendu"*)   echo INTERROMPU ;;
    *"fetch impossible"*) echo REPORTE ;;
    *) echo OK ;;
  esac
}

autodeploy_verdicts() {
  # ── C13. Log auto-deploy inscriptible par le cron USER (sinon auto-deploy KO) ─
  # auto-deploy = SEUL cron user ; /var/log est root:root. Si le log repasse
  # root-owned (rotation maintenance en root), la redirection du cron user échoue
  # → auto-deploy ne tourne plus SILENCIEUSEMENT (bug rpi1 du 15/07). maintenance.sh
  # re-chown le log après rotation ; ce contrôle attrape toute régression.
  for pair in "$SELF:${S_deploylog_owner:-missing}" "$PEER:${P_deploylog_owner:-missing}"; do
    n=${pair%:*}; o=${pair#*:}; [ "$n" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
    [ "$o" = "ptressard" ] && ok "Log auto-deploy inscriptible par le cron user sur $n" \
      || warn "Log auto-deploy NON inscriptible par le cron user sur $n (owner=$o) → auto-deploy silencieusement KO (sudo chown ptressard:ptressard /var/log/hostachy-deploy.log)"
  done


  # ── C27. auto-deploy a-t-il RÉUSSI son build ? (les DEUX nœuds) ─────────────
  # Pendant de C13 : celui-là vérifie que le cron user peut ÉCRIRE son log,
  # celui-ci que son travail ABOUTIT.
  #
  # Le 21/09/2026, la bascule nocturne a mis rpi1 en standby : son auto-deploy a
  # aligné le code et **pas les images**, faute de pouvoir lire
  # /opt/5hostachy/.env — root:root là-bas, ptressard:ptressard sur rpi2. La
  # parité git n'est pas la parité d'image (mémoire `bascule_image_stale`), et le
  # point 10 du pré-check restait vert : c'est le 18 qui l'a attrapé, en MEP
  # seulement. Ce qui est critique en continu ne se vérifie pas qu'en MEP.
  #
  # ⚠️ L'alerte qui aurait dû le dire est morte de la MÊME cause : elle cherche
  # sa configuration SMTP dans ce .env illisible. Un canal d'alerte muet
  # précisément quand il a quelque chose à dire — d'où ce contrôle-ci, qui passe
  # par un autre chemin (le journal, lu par le peer).
  for pair in "$SELF:${S_deploy_dernier:-}" "$PEER:${P_deploy_dernier:-}"; do
    n=${pair%%:*}; d=${pair#*:}
    [ "$n" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
    case "$(verdict_build_autodeploy "$d")" in
      OK)   ok "auto-deploy a construit sans echec sur $n" ;;
      FAIL) fail "auto-deploy a ECHOUE a construire sur $n : le code est a jour, PAS les images (cause connue : /opt/5hostachy/.env illisible par ptressard ; comparer le proprietaire sur les deux noeuds)" ;;
      INTERROMPU) fail "auto-deploy s est INTERROMPU sur $n sans sortie prevue (${d#*] }) — lire /var/log/hostachy-deploy.log autour de cette ligne (#1587)" ;;
      REPORTE) warn "auto-deploy sur $n n a pas pu joindre GitHub a son dernier passage (git fetch) : rien ne se deploie tant que ca dure — isole, c est transitoire ; durable, lire le message de git dans /var/log/hostachy-deploy.log : le code se tire en HTTPS, la sortie 443 doit rester ouverte vers github.com (#1587, #2367)" ;;
      *)    warn "auto-deploy sur $n : aucune ligne horodatee lisible, son silence ne prouve rien" ;;
    esac
  done


  # ── C28. Ce que lit auto-deploy est-il LISIBLE par lui ? ───────────────────
  #
  # C13 mesure la sortie (le log est-il inscriptible ?), C27 le resultat (le
  # build aboutit-il ?). Aucun ne mesurait l ENTREE — et c est elle qui a
  # lache : le 22/09/2026 le .env du standby est passe root:root a la bascule
  # de 02:03. Plus aucun build possible, ET plus aucune alerte, puisqu elle
  # cherche le SMTP dans ce meme fichier. Aveugle et muet 70 minutes (#1135).
  #
  # ⚠️ C27 le voyait deja, mais APRES coup et par deduction : « le code est a
  # jour, pas les images ». Celui-ci nomme la cause, avant la consequence.
  #
  # La decision est pure (`verdict_env_lisible`, dans `lib-env-role.sh` avec le
  # code qui ECRIT ce fichier) : les deux vivent ensemble, donc une regression
  # de l un casse les cas de l autre.
  for pair in "$SELF:${S_envdroits:-}" "$PEER:${P_envdroits:-}"; do
    n=${pair%%:*}; d=${pair#*:}
    [ "$n" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
    case "$(verdict_env_lisible "${d%%:*}" "$(echo "$d" | cut -d: -f2)" "${d##*:}" ptressard)" in
      OK)        ok "/opt/5hostachy/.env lisible par le cron user sur $n" ;;
      ILLISIBLE) fail "/opt/5hostachy/.env ILLISIBLE par ptressard sur $n ($d) : auto-deploy ne construira plus, et l alerte est muette (sudo chown ptressard:ptressard /opt/5hostachy/.env)" ;;
      EXPOSE)    warn "/opt/5hostachy/.env lisible de TOUS sur $n ($d) : il porte le SECRET_KEY et le SMTP (sudo chmod 600 /opt/5hostachy/.env)" ;;
      *)         warn "/opt/5hostachy/.env sur $n : droits non releves, son silence ne prouve rien" ;;
    esac
  done
}
