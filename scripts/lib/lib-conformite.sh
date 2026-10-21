#!/usr/bin/env bash
# =============================================================================
#  lib-conformite.sh — les contrôles de CONFORMITÉ de `check-reliability.sh`
#                      (C20 à C25, C30, C32 à C39)
#
#  Extrait le 20/08/2026, au fil de l'eau : `check-reliability.sh` a dépassé son
#  plafond en recevant C23 (les en-têtes de sécurité réellement servis), et le
#  garde-fou de modularité l'a refusé.
#
#  La coupe suit la NATURE des contrôles, pas leur numéro. Ceux-ci partagent une
#  question : *le nœud est-il conforme à ce qu'on croit qu'il est ?*
#
#    C20  les permissions élevées sont-elles les mêmes sur les deux nœuds ?
#    C21  une permission élevée vaut-elle mieux que la cible qu'elle désigne ?
#    C22  les points d'entrée du nœud sont-ils ceux du dépôt ?
#    C23  les en-têtes de sécurité sont-ils réellement servis ?
#    C25  un script TIERS est-il servi dans la page publique ?
#    C30  le nœud reçoit-il ses correctifs système ? (`lib-mises-a-jour.sh`)
#    C32  quels ports écoutent sur toutes les interfaces ? (`lib-ports-ecoute.sh`)
#    C33  des copies de `.env` traînent-elles à côté de l'original ?
#    C34  le volume de données porte-t-il d'autres bases que celle de l'API ?
#         (C33 et C34 : `lib-fichiers-parasites.sh`)
#    C35  la pile de bureau retirée des nœuds est-elle revenue ?
#         (`lib-paquets-proscrits.sh`)
#    C36  le journal d'accès de Caddy est-il écrit, et que dit-il des erreurs 500 ?
#         (`lib-journal-acces.sh`)
#    C37  la base PostgreSQL est-elle répliquée ? (`lib-replication.sh`)
#    C38  chaque nœud refuse-t-il le mot de passe SSH ? (`lib-ssh-mot-de-passe.sh`)
#    C39  le jeton du tunnel est-il en clair dans l'unité cloudflared ?
#         (`lib-jeton-tunnel-clair.sh`)
#
#  Les contrôles restés dans `check-reliability.sh` posent l'autre question :
#  *le service fonctionne-t-il ?* — la base, le rôle actif, le tunnel, la
#  maintenance. Deux raisons de changer, deux fichiers.
#
#  ⚠️ Ce module n'est PAS autonome. Il emploie `ok`, `warn`, `$SELF`, `$REPO` et
#  les `verdict_*` définis par son appelant : il est sourcé APRÈS eux, et appelé
#  par `conformite_verdicts`. Le sourcer seul ne produirait rien — et surtout
#  aucune erreur, ce pourquoi il ne s'exécute pas au chargement.
# =============================================================================

conformite_verdicts() {
  # ── C20. Les permissions élevées sont-elles les MÊMES sur les 2 nœuds ? ───────
  # Jumeau de C18, né du même défaut : une divergence que personne ne pouvait voir,
  # chaque nœud ayant l'air normal vu de lui-même. C18 a rendu vraie la phrase
  # « cron root identique sur les 2 nœuds » ; celui-ci fait le même travail pour
  # les règles `sudo`, posées à la main nœud par nœud — donc divergentes par
  # construction, ce qu'a établi #302.
  #
  # La divergence n'est pas un détail d'hygiène : c'est elle qui a fait échouer la
  # copie hors site UNE NUIT SUR DEUX (09/08/2026), la permission n'existant que
  # sur le nœud actif un jour sur deux. Un nœud plus permissif que l'autre, c'est
  # aussi une surface d'attaque qui dépend du jour de la semaine.
  #
  # WARN et non FAIL : cela ne coupe pas la production, et un FAIL à */15 enverrait
  # un mail par heure jusqu'à correction — c'est-à-dire une alerte qu'on apprend à
  # ignorer, le défaut exact qu'on a retiré de C16 le 06/08.
  if [ "$PEER_OK" -eq 0 ]; then
    case "$(sudo_parite "${S_sudofiles:-}" "${P_sudofiles:-}")" in
      OK)         ok "Permissions élevées identiques sur les 2 nœuds" ;;
      DIVERGENCE) warn "Permissions élevées DIVERGENTES entre $SELF et $PEER — écarts : $(sudo_ecarts "${S_sudofiles:-}" "${P_sudofiles:-}") ; une règle posée d'un seul côté ne vaut qu'un jour sur deux, et rend un nœud plus permissif que l'autre (#302)" ;;
      *)          warn "Permissions élevées INCONNUES ($SELF='${S_sudofiles:-vide}' $PEER='${P_sudofiles:-vide}') — comparaison impossible, ni vert ni rouge" ;;
    esac
  fi

  # ── C21. Une permission élevée vaut-elle mieux que sa cible ? ─────────────────
  # `standards/03-securite.md` §8 bis : une permission élevée ne vaut que ce que
  # vaut la cible qu'elle désigne. Une règle qui a l'air bornée à un script précis
  # ne borne rien si le compte appelant peut réécrire ce script — la permission
  # porte sur un CHEMIN, pas sur le code qu'il contiendra à l'exécution.
  #
  # Analyse locale (root). Sur le peer le champ est vide et vaut INCONNU : c'est
  # assumé, puisque le contrôle tourne des deux côtés et que chaque nœud examine
  # donc les siennes. Ne jamais rabattre ce vide sur OK — ce serait le nœud le
  # moins surveillé qui rassurerait le plus.
  case "$(verdict_sudo_risque "${S_sudorisk:-}")" in
    OK)     ok "Permissions élevées de $SELF : aucune cible réinscriptible par son appelant" ;;
    RISQUE) warn "Permissions élevées de $SELF : cible(s) réinscriptible(s) par l'appelant ou règle sans borne →${S_sudorisk#ok:} — qui obtient ce compte obtient root (#302)" ;;
    *)      warn "Permissions élevées de $SELF : non mesurables (exige root) — ni vert ni rouge" ;;
  esac

  # ── C22. Les points d'entrée de CE nœud sont-ils conformes au DÉPÔT ? ─────────
  # C18 compare les deux nœuds ENTRE EUX : deux crontabs identiquement périmés lui
  # paraissent parfaits. Ici on compare au dépôt, et en continu (#352). Le pourquoi
  # détaillé, la priorité ECART > INCONNU et le choix du WARN : lib-points-entree.sh.
  PE=$(points_entree_verdicts_locaux "$REPO" | agreger_points_entree)
  case "${PE%%|*}" in
    OK)      ok   "Points d'entrée de $SELF conformes au dépôt (crons root et ptressard, unité role-guard)" ;;
    ECART)   warn "Points d'entrée de $SELF NON conformes au dépôt : ${PE#*|} — le nœud ne lance pas ce que infra/points-entree/ décrit" ;;
    *)       warn "Points d'entrée de $SELF non lisibles : ${PE#*|} — ni vert ni rouge (sudo -n refusé, ou nœud non provisionné)" ;;
  esac

  # ── C24. La surface sudo INSTALLÉE est-elle celle que le dépôt compose ? ──────
  #  🔴 Le 31/08/2026, `NOPASSWD: /usr/bin/rsync` — un rsync privilégié sans borne
  #  de chemin, donc une escalade root complète — a été retiré du dépôt (#582) avec
  #  un commentaire disant « c'est la fin du chantier ». Il est resté installé sur
  #  les DEUX machines : `durcir-sudoers.sh` n'avait jamais été rejoué. Vingt-quatre
  #  heures, et vingt-trois contrôles au vert à chaque quart d'heure.
  #
  #  ⚠️ C20 ne pouvait pas le voir : il compare les deux nœuds ENTRE EUX, et deux
  #  nœuds identiquement périmés lui paraissent parfaits. C21 non plus : rsync n'est
  #  pas réinscriptible par son appelant. C'est le même trou que C22 comble pour les
  #  points d'entrée — comparer au DÉPÔT, et pas seulement au voisin.
  #
  #  WARN et non FAIL : une permission en trop n'interrompt pas le service. Mais
  #  elle a un destinataire — le digest quotidien (#449) —, ce qui est toute la
  #  différence entre un contrôle et un contrôle mort.
  SURF_ATTENDUE=$(sudoers_regle ptressard 2>/dev/null     | sed -n 's/^ptressard[[:space:]]*ALL=(root)[[:space:]]*NOPASSWD:[[:space:]]*//p'     | sed 's/[[:space:]]*$//' | sort -u | tr '
' '|')
  case "$(verdict_sudo_surface "${S_sudosurface:-}" "$SURF_ATTENDUE")" in
    OK)           ok   "Surface sudo de $SELF conforme au dépôt" ;;
    EN_TROP:*)    V24=$(verdict_sudo_surface "${S_sudosurface:-}" "$SURF_ATTENDUE")
                  warn "Surface sudo de $SELF : permission(s) EN TROP → ${V24#EN_TROP:} — le dépôt ne les accorde plus, la machine si (relancer scripts/installation/durcir-sudoers.sh)" ;;
    MANQUANTES:*) V24=$(verdict_sudo_surface "${S_sudosurface:-}" "$SURF_ATTENDUE")
                  warn "Surface sudo de $SELF : permission(s) MANQUANTE(S) → ${V24#MANQUANTES:} — un geste de la bascule échouera au prochain passage" ;;
    ECART:*)      V24=$(verdict_sudo_surface "${S_sudosurface:-}" "$SURF_ATTENDUE")
                  warn "Surface sudo de $SELF NON conforme au dépôt → ${V24#ECART:} (en trop / manquantes)" ;;
    *)            warn "Surface sudo de $SELF non mesurable — ni vert ni rouge" ;;
  esac

  # ── C23. Les en-têtes de sécurité sont-ils RÉELLEMENT servis ? ────────────────
  # 🔴 Un contrôle des en-têtes existait — dans `check-stack.sh`, RETIRÉ du cron de
  # rpi2 le 06/08/2026 parce qu'il y échouait 144 fois par jour. Il échouait parce
  # qu'il attendait `X-Frame-Options: SAMEORIGIN` là où le Caddyfile dit `DENY`.
  #
  # Le seul contrôle des en-têtes portait donc une attente FAUSSE, il criait, on
  # l'a fait taire — et depuis, plus rien ne regarde. Un en-tête de sécurité peut
  # disparaître d'un Caddyfile sans que personne ne le sache.
  #
  # ⚠️ Celui-ci lit ce qui est SERVI, pas ce que le fichier déclare : c'est la
  # différence entre vérifier le fait et vérifier son intention. Et il ne regarde
  # que la PRÉSENCE — une attente de valeur se périme au premier ajustement, et
  # c'est exactement ce qui a tué le précédent.
  #
  # WARN et non FAIL : un en-tête manquant n'interrompt pas le service, il retire
  # une protection. Le distinguer d'une panne évite de noyer les FAIL.
  ENTETES_ATTENDUS="X-Content-Type-Options X-Frame-Options Referrer-Policy Strict-Transport-Security Content-Security-Policy"
  #  ⚠️ Le RÔLE est passé à la décision : sur le standby, les conteneurs ne
  #  tournent pas (c'est l'invariant, pas un incident), donc il n'y a rien à
  #  constater. Sans cela, le contrôle rendait INCONNU toutes les quinze minutes
  #  sur la moitié du parc et un digest partait chaque jour — un contrôle dont le
  #  vert est inatteignable finit par se contourner (`standards/04` §25).
  ENTETES_RECUS=$(curl -sI --max-time 8 http://localhost/ 2>/dev/null)
  ENTETES_ROLE=$([ "${S_active:-}" = "${SELF:-}" ] && echo actif || echo standby)
  case "$(verdict_entetes_securite "$ENTETES_RECUS" "$ENTETES_ATTENDUS" "$ENTETES_ROLE")" in
    OK)          ok   "En-têtes de sécurité servis (${ENTETES_ATTENDUS// /, })" ;;
    SANS_OBJET)  ok   "En-têtes de sécurité : sans objet sur le standby (aucun conteneur n'y sert)" ;;
    MANQUANT:*)  V23=$(verdict_entetes_securite "$ENTETES_RECUS" "$ENTETES_ATTENDUS" "$ENTETES_ROLE")
                 warn "En-tête(s) de sécurité ABSENT(S) de la réponse : ${V23#MANQUANT:} — la protection correspondante ne s'applique plus, et le Caddyfile peut dire le contraire" ;;
    *)           warn "En-têtes de sécurité non mesurables sur l'ACTIF (aucune réponse locale) — le site ne répond plus en local, ni vert ni rouge" ;;
  esac

  # ── C23 bis. La CSP bloquante porte-t-elle ses directives ? ───────────────────
  #  C23 dit que l'en-tête EXISTE. Il existait déjà quand la politique ne portait
  #  que quatre directives inoffensives, et il existerait encore si l'une d'elles
  #  disparaissait du Caddyfile. « Présent » ne dit rien de ce qu'il contient.
  #
  #  🔴 `connect-src` est passée en bloquant le 01/09/2026 (#536), sur la foi du
  #  relevé : aucune violation la concernant sur 104 rapports. C'est la directive
  #  qui empêche l'EXFILTRATION — même si un XSS s'exécutait, il ne pourrait rien
  #  envoyer vers un domaine tiers. La perdre en silence retirerait la moitié utile
  #  de la politique, et rien ne le dirait.
  #
  #  ⚠️ PRÉSENCE, jamais valeur : c'est une attente de valeur exacte qui a fait
  #  désarmer `check-stack.sh` le 06/08/2026, après quoi plus rien n'a regardé les
  #  en-têtes pendant quinze jours.
  CSP_DIRECTIVES="frame-ancestors object-src base-uri form-action connect-src"
  case "$(verdict_csp_directives "$ENTETES_RECUS" "$CSP_DIRECTIVES" "$ENTETES_ROLE")" in
    OK)          ok   "CSP bloquante complète (${CSP_DIRECTIVES// /, })" ;;
    SANS_OBJET)  ok   "CSP bloquante : sans objet sur le standby (aucun conteneur n'y sert)" ;;
    MANQUANT:*)  V23B=$(verdict_csp_directives "$ENTETES_RECUS" "$CSP_DIRECTIVES" "$ENTETES_ROLE")
                 warn "Directive(s) ABSENTE(S) de la CSP bloquante : ${V23B#MANQUANT:} — la protection correspondante ne s'applique plus, et l'en-tête est pourtant bien servi" ;;
    *)           warn "CSP bloquante non mesurable (aucune réponse locale, ou en-tête absent) — ni vert ni rouge" ;;
  esac

  # ── C25. Un script TIERS est-il servi dans la page publique ? ─────────────────
  #  🔴 Pourquoi (#701, 02/09/2026). Le relevé CSP a trouvé le beacon de Cloudflare
  #  Web Analytics chargé sur chaque page. AUCUN `<script>` du dépôt ne le
  #  référence : il est injecté par Cloudflare, à l'arête, APRÈS notre origine.
  #  Aucun contrôle de code ne pouvait le voir, et `curl http://localhost/` non
  #  plus — l'injection a lieu en aval.
  #
  #  Décision de l'utilisateur : le couper. Ce contrôle rend la décision DURABLE :
  #  réactiver l'option d'un clic dans un tableau de bord tiers remettrait un
  #  script sur le chemin de chaque résident, et rien ne le dirait.
  #
  #  ⚠️ Il mesure donc l'URL PUBLIQUE, avec un `Accept: text/html` et un UA de
  #  navigateur — Cloudflare n'injecte que dans du HTML rendu à un navigateur.
  #  C'est `standards/04` §14 : observer la chose, pas son enregistrement.
  #
  #  ⚠️ Et il ne tourne QUE sur l'actif : depuis le standby, la même URL publique
  #  répond (elle sort par le WAN et revient sur l'actif), donc le contrôle
  #  passerait deux fois sur le même fait — `standards/04` §33.
  HOTES_TIERS="static.cloudflareinsights.com googletagmanager.com google-analytics.com"
  #
  #  ⚠️ La page est relue une fois avant de conclure (`page_html`, lib-sonde) :
  #  le 20/10/2026, une seule résolution DNS expirée a fait partir le digest.
  #  Deux échecs restent un WARN, et il dit alors ce que curl a vu.
  PAGE_PUBLIQUE=""
  CAUSE25=$(mktemp)
  if [ "$ENTETES_ROLE" = "actif" ]; then
    PAGE_PUBLIQUE=$(page_html "${SITE_PUBLIC_HTML:-https://5hostachy.fr/auth/connexion}" "${SONDE_RETRY_S:-10}" "$CAUSE25")
  fi
  case "$(verdict_script_tiers "$PAGE_PUBLIQUE" "$HOTES_TIERS" "$ENTETES_ROLE")" in
    OK)          ok   "Aucun script tiers dans la page publique (${HOTES_TIERS// /, } surveillés)" ;;
    SANS_OBJET)  ok   "Scripts tiers : sans objet sur le standby (il ne sert pas la page publique)" ;;
    TIERS:*)     V25=$(verdict_script_tiers "$PAGE_PUBLIQUE" "$HOTES_TIERS" "$ENTETES_ROLE")
                 warn "Script TIERS servi à chaque résident : ${V25#TIERS:} — il n'est dans aucun fichier du dépôt, donc il vient d'un réglage d'arête (Cloudflare). Le couper, ou l'écrire dans les pages légales (#701)" ;;
    *)           warn "Scripts tiers non mesurables (page publique non reçue deux fois à ${SONDE_RETRY_S:-10} s d'écart : $(tr '\n' ' ' < "$CAUSE25" | sed 's/^curl: //; s/ *$//')) — ni vert ni rouge" ;;
  esac
  rm -f "$CAUSE25"

  # ── C30. Ce nœud reçoit-il ses correctifs ? (#1378) ──────────────────────────
  #  rpi2 n'en recevait plus depuis cinq mois, et aucun des contrôles ci-dessus ne
  #  pouvait le voir (#1377). Collecte, décisions et messages : `lib-mises-a-jour.sh`.
  mises_a_jour_verdicts

  # ── C32. Quels ports écoutent sur TOUTES les interfaces ? (#1593) ────────────
  #  rpcbind écoutait sur rpi1 seul, et aucun contrôle ne comparait les ports.
  #  Mesure, liste blanche et constats : `lib-ports-ecoute.sh`.
  ports_ecoute_verdicts

  # ── C33 et C34. Des copies laissées à côté de l'original ? (#1609, #1592) ────
  #  Des `.env*` à la racine du dépôt déployé, des bases autres que celle de l'API
  #  dans le volume de données. Mesure et constats : `lib-fichiers-parasites.sh`.
  fichiers_parasites_verdicts

  # ── C35. La pile de bureau est-elle REVENUE ? (#1648) ────────────────────────
  #  Retirée du standby le 03/10/2026 ; une mise à jour, un paquet recommandé ou une
  #  réinstallation depuis l'image la ramène sans que personne le décide. Liste,
  #  mesure et constats : `lib-paquets-proscrits.sh`.
  paquets_proscrits_verdicts

  # ── C36. Le journal d'accès de Caddy, sur l'ACTIF (#1588) ────────────────────
  #  Il disparaissait à chaque déploiement ; il est désormais un fichier du volume
  #  `caddy_logs`. Mesure, seuil et constats : `lib-journal-acces.sh`.
  acces_caddy_verdicts

  # ── C37. La base PostgreSQL est-elle répliquée vers le standby ? (#1781) ─────
  #  Sous PostgreSQL (D16), un primaire sur l'actif, une réplique en continu sur
  #  le standby. Deux primaires, une réplique déconnectée ou en retard : le
  #  failover promouvrait une base périmée ; aucune base nulle part est un
  #  échec. Collecte, décision et constats : `lib-replication.sh`.
  replication_verdicts

  # ── C38. Chaque nœud refuse-t-il le mot de passe SSH ? (#1941) ───────────────
  #  D'avril à octobre 2026, les deux l'acceptaient : `50-cloud-init.conf`
  #  l'emportait sur le durcissement, et rien ne mesurait ce que sshd SERT
  #  (#1918). Sonde par la méthode `none`, sans rien tenter ; décision dans
  #  `lib-durcissement.sh`, sonde et constats dans `lib-ssh-mot-de-passe.sh`.
  ssh_mot_de_passe_verdicts

  # ── C39. Le jeton du tunnel est-il EN CLAIR dans l'unité cloudflared ? (#2115) ─
  #  `--token <valeur>` dans `ExecStart` est lisible par tout compte local (`ps`,
  #  `systemctl cat`). Il l'est resté des mois sur les deux nœuds, noté dans une
  #  mémoire et jamais mesuré. La collecte ne rend qu'un verdict, jamais l'unité ;
  #  mesure et constats : `lib-jeton-tunnel-clair.sh`.
  jeton_tunnel_clair_verdicts
}
