#!/usr/bin/env bash
# =============================================================================
#  Auto-tests des verdicts du PRÉ-CHECK MEP — extrait de `lib-verdicts-mep.sh`
#  le 20/08/2026, au fil de l'eau.
#
#  POURQUOI. Le garde-fou de modularité a refusé les lignes qu'ajoutait le point
#  18 (parité des IMAGES du standby, #511) : `lib-verdicts-mep.sh` passait de 491
#  à 523 lignes. La règle est « on découpe QUAND on y touche ».
#
#  La coupe reprend celle de `lib-verdicts.sh` → `lib-verdicts-selftest.sh`
#  (19/08/2026), et pour la même raison : d'un côté les fonctions PURES que le
#  pré-check appelle, de l'autre ce qui les éprouve. Les deux n'ont pas la même
#  raison de changer — et la seconde grossit à chaque incident, la première non.
#
#  ⚠️ Ce fichier a besoin de `lib-verdicts-mep.sh` : il est sourcé APRÈS lui,
#  jamais seul. `precheck-mep.sh --selftest` s'en charge.
# =============================================================================


verdicts_mep_selftest() {
  st=0
  #  `"$@"` et non `$1 $2 …` : la découpe des mots supprimait les arguments VIDES,
  #  qui sont précisément les cas à éprouver — une mesure manquante. Le self-test
  #  a attrapé le défaut dans sa propre plomberie avant de servir une seule fois.
  t() {
    local libelle=$1 attendu=$2; shift 2
    local r; r=$("$@")
    if [ "$r" = "$attendu" ]; then echo "PASS  $libelle → $r"
    else echo "FAIL  $libelle  attendu=$attendu obtenu=$r"; st=1; fi
  }
  t "site qui répond"                    OK      verdict_http 200
  t "site en erreur"                     FAIL    verdict_http 503
  t "hôte injoignable"                   INCONNU verdict_http 000
  t "sortie vide n'est pas un vert"      INCONNU verdict_http ""
  t "nominal : flags d'accord"           OK      verdict_role rpi1 rpi1 4 0
  t "flags divergents (26/07)"           FAIL    verdict_role rpi2 rpi1 4 0
  t "split-brain des deux côtés"         FAIL    verdict_role rpi1 rpi1 4 3
  t "personne ne sert"                   FAIL    verdict_role rpi1 rpi1 0 0
  t "flag ment : rpi2 porte la charge"   FAIL    verdict_role rpi1 rpi1 0 4
  t "mesure manquante"                   INCONNU verdict_role "" rpi1 4 0
  t "standby vide, rpi1 actif"           OK      verdict_standby rpi1 4 0
  t "standby vide, rpi2 actif (après bascule)" OK verdict_standby rpi2 0 4
  t "standby qui porte des conteneurs"   FAIL    verdict_standby rpi1 4 3
  t "drapeau inconnu"                    INCONNU verdict_standby rpi9 4 0
  t "comptes non mesurés"                INCONNU verdict_standby rpi1 "" 0
  t "un seul bump, le cas nominal"       OK      verdict_bumps 1 2.52.1 2.52.2
  t "deux bumps (PR #297, 11/08)"        FAIL    verdict_bumps 2 2.52.1 2.52.2
  t "cinq bumps"                         FAIL    verdict_bumps 5 2.52.1 2.52.2
  t "aucun bump : P3 ne prouvera rien"   ECART   verdict_bumps 0 2.52.1 2.52.1
  t "comptage impossible"                INCONNU verdict_bumps ""  2.52.1 2.52.2
  t "comptage aberrant"                  INCONNU verdict_bumps "deux" 2.52.1 2.52.2
  #  ── #308 : le FAIT, pas la forme du message de commit ─────────────────────
  #  Le cas vécu : bump replié dans un commit `fix(admin)`. 0d comptait zéro
  #  commit `chore(version)` et annonçait « la version servie sera identique »,
  #  alors que package.json passait de 2.52.1 à 2.52.2.
  t "bump replié dans un commit métier"  OK      verdict_bumps 0 2.52.1 2.52.2
  #  Un bump ANNONCÉ qui ne change rien reste un écart : P3 ne prouvera rien.
  t "commit de bump sans changement"     ECART   verdict_bumps 1 2.52.1 2.52.1

  #  ── 0g : le RANG du bump correspond à ce que le lot apporte ──────────────
  #  Le relevé du 07/09/2026 a trouvé SIX rangs faux sur dix-huit lots, tous
  #  surévalués. Ces cas rejouent les six.
  t "feat -> minor, le cas nominal"      OK      verdict_rang_version minor 3.111.0 3.112.0
  t "fix -> patch, le cas nominal"       OK      verdict_rang_version patch 3.111.0 3.111.1
  t "rupture -> major"                   OK      verdict_rang_version major 3.111.0 4.0.0
  t "docs bumpe en minor (3.112.0)"      FAIL    verdict_rang_version patch 3.111.1 3.112.0
  t "refactor bumpe en minor (3.109.0)"  FAIL    verdict_rang_version patch 3.108.0 3.109.0
  t "fix bumpe en minor (3.107.0)"       FAIL    verdict_rang_version patch 3.106.0 3.107.0
  t "feat bumpe en patch : sous-evalue"  FAIL    verdict_rang_version minor 3.111.0 3.111.1
  t "la version RECULE"                  FAIL    verdict_rang_version patch 3.112.0 3.111.0
  t "aucun bump : 0d le dit deja"        ECART   verdict_rang_version patch 3.112.0 3.112.0
  t "rang non calculable"                INCONNU verdict_rang_version inconnu 3.111.0 3.112.0
  t "version illisible"                  INCONNU verdict_rang_version patch 3.111.0 "v3.112"

  #  Le rang ANNONCÉ par les préfixes du lot — la moitié amont du point 0g.
  t "feat annonce un minor"              minor   rang_attendu "feat(accès) : lecture seule"
  t "fix annonce un patch"               patch   rang_attendu "fix(ux) : le formulaire"
  t "refactor annonce un patch"          patch   rang_attendu "refactor(rôles) : trois façons"
  t "docs annonce un patch"              patch   rang_attendu "docs(manuel) : compléter son ticket"
  t "le ! annonce une rupture"           major   rang_attendu "feat(api)! : les jetons changent"
  t "BREAKING CHANGE aussi"              major   rang_attendu "fix(api) : un correctif
BREAKING CHANGE: les jetons changent"
  t "un feat parmi des fix : minor"      minor   rang_attendu "fix(a) : un
feat(b) : deux"
  t "un feat CITÉ n'est pas un préfixe"  patch   rang_attendu "fix(a) : reprend le feat(b) livré hier"
  t "rien à lire : jamais patch"         inconnu rang_attendu ""
  t "version amont non mesurée"          INCONNU verdict_bumps 0 ""     2.52.2
  t "version locale non mesurée"         INCONNU verdict_bumps 0 2.52.1 ""
  #  La forme prime sur le fait dans un seul sens : deux bumps restent un échec
  #  même si la version finit par changer — c'est le défaut d'origine (#297).
  t "deux bumps malgré version changée"  FAIL    verdict_bumps 2 2.52.1 2.53.0
  t "brief du lot, corps fourni"         OK      verdict_brief abc123 abc123 40
  t "brief pile à la borne"              OK      verdict_brief abc123 abc123 5
  t "brief réduit à un titre"            FAIL    verdict_brief abc123 abc123 2
  t "brief du lot PRÉCÉDENT"             FAIL    verdict_brief vieux1 abc123 40
  t "aucun brief"                        INCONNU verdict_brief "" abc123 40
  t "compte de lignes illisible"         INCONNU verdict_brief abc123 abc123 ""
  t "zéro erreur"                        OK      verdict_compte 0 0
  t "erreurs présentes"                  FAIL    verdict_compte 3 0
  t "compte non mesuré"                  INCONNU verdict_compte "" 0
  t "piège du grep -c || echo 0"         INCONNU verdict_compte "0 0" 0
  t "compte non numérique"               INCONNU verdict_compte "abc" 0
  #  0c — un échec que le lot corrige ne bloque pas son propre push (#318).
  eb() {  # $1 = libellé, $2 = attendu, $3 = liste sha:ancêtre
    local got; got=$(echecs_bloquants "$3")
    if [ "$got" = "$2" ]; then echo "PASS  $1 → '$got'"
    else echo "FAIL  $1  attendu='$2' obtenu='$got'"; st=1; fi
  }
  eb "aucun échec"                        "0" ""
  eb "que des succès"                     "0" "success:b8aeb1e:non success:28b1e9f:non"
  #  (2) Le cas du 12/08 au matin : le correctif est commité, rien n a encore
  #  tourné après l échec, mais HEAD descend du commit fautif.
  eb "échec dépassé par HEAD"             "0" "failure:b003e0d:oui"
  #  (1) Le cas du 12/08 à midi : le squash a détruit l ascendance, mais des
  #  runs plus récents ont réussi. Sans cette règle, 0c bloquerait pour toujours.
  eb "échec suivi d un succès (squash)"   "0" "success:b8aeb1e:non failure:b003e0d:non"
  eb "échec sur un commit étranger"       "1 9f1c2ab" "failure:9f1c2ab:non"
  eb "le plus récent a échoué"            "1 9f1c2ab" "failure:9f1c2ab:non success:aaa1111:non"
  eb "deux échecs, un seul dépassé"       "1 9f1c2ab" "failure:9f1c2ab:non failure:b003e0d:oui"
  #  Ascendance non mesurable (sha absent du clone) : on ne conclut pas au vert.
  eb "ascendance inconnue"                "1 deadbee" "failure:deadbee:?"
  #  Un run annulé ou en cours n est ni un échec ni un succès : il ne doit ni
  #  bloquer, ni servir à déclarer un échec dépassé.
  eb "run annulé ignoré"                  "1 9f1c2ab" "cancelled:ccc3333:non failure:9f1c2ab:non"
  t "clone à jour"                       OK      verdict_clone 0 non
  t "retard sans apport (post-squash)"    OK      verdict_clone 2 oui
  t "retard avec apport manquant"        FAIL    verdict_clone 2 non
  t "retard non mesuré"                  INCONNU verdict_clone "" oui
  t "retard non numérique"               INCONNU verdict_clone "abc" oui
  #  🔴 La branche amont SUPPRIMÉE à la fusion : rien à rattraper, à condition de
  #  descendre de `origin/main`. Sans ce cas, le pré-check ne pouvait plus passer
  #  après aucune fusion — donc le hook pre-push refusait le push suivant.
  t "amont supprimée, aligné sur main"   OK      verdict_clone "" oui absent
  t "amont supprimée, clone divergent"   FAIL    verdict_clone "" non absent
  t "amont non déterminable"             INCONNU verdict_clone 0 oui inconnu

  # ── #616 : la réécriture volontaire de `dev`, déclarée et prouvée sans perte ──
  #  Sans ces cas, corriger le point 0d (retirer un bump surnuméraire) faisait
  #  échouer le point 0a, et la seule issue était `SKIP_PRECHECK=1` — désarmer
  #  vingt-quatre contrôles pour en contourner un. Socle 04 §25.
  t "réécriture déclarée et recouverte"   OK      verdict_clone 1 non present oui
  t "réécriture non déclarée : inchangé"  FAIL    verdict_clone 1 non present non
  t "réécriture indécidable"              INCONNU verdict_clone 1 non present inconnu
  #  🔴 Le 4e argument ne doit JAMAIS rattraper un vrai retard sur une branche
  #  supprimée ni sur un amont indéterminable : ces deux cas se tranchent avant.
  t "amont supprimée : la déclaration ne rattrape rien" FAIL verdict_clone 1 non absent oui
  t "amont inconnu : la déclaration ne rattrape rien"   INCONNU verdict_clone 1 non inconnu oui
  #  Rétro-compatibilité : les appels à trois arguments gardent leur verdict.
  t "sans 4e argument, comportement d'origine" FAIL verdict_clone 2 non

  # ── `verdict_reecriture` — ce qui autorise, et surtout ce qui refuse ──
  t "aucune déclaration : cas nominal"    non     verdict_reecriture "" "" "" "137cab0" ""
  t "déclarée, concordante, recouverte"   oui     verdict_reecriture 601477b 601477b "137cab0" "137cab0" ""
  #  Datée par le commit : une déclaration du lot précédent ne vaut plus.
  t "déclarée pour un AUTRE commit"       non     verdict_reecriture abc1234 601477b "137cab0" "137cab0" ""
  #  🔴 Le cœur du garde-fou : un fichier non réécrit par HEAD serait PERDU.
  t "un fichier ne serait pas recouvert"  non     verdict_reecriture 601477b 601477b "137cab0" "137cab0" "api/app/main.py"
  #  La dérogation ne survit pas à son objet — dans les deux sens.
  t "déclare moins que ce qui manque"     non     verdict_reecriture 601477b 601477b "137cab0" "137cab0 999aaaa" ""
  t "déclare plus que ce qui manque"      non     verdict_reecriture 601477b 601477b "137cab0 999aaaa" "137cab0" ""
  t "déclare un commit qui ne manque pas" non     verdict_reecriture 601477b 601477b "999aaaa" "137cab0" ""
  #  Déclaration partielle : on ne complète pas ce qu'elle ne dit pas.
  t "déclaration sans commit"             inconnu verdict_reecriture "" 601477b "137cab0" "137cab0" ""
  t "déclaration sans sha retiré"         inconnu verdict_reecriture 601477b 601477b "" "137cab0" ""
  t "HEAD non mesuré"                     inconnu verdict_reecriture 601477b "" "137cab0" "137cab0" ""
  #  Cas zéro : rien ne manque, mais une déclaration traîne. On ne peut pas dire
  #  qu'elle est concordante — elle ne décrit plus rien.
  t "rien ne manque, déclaration résiduelle" inconnu verdict_reecriture 601477b 601477b "137cab0" "" ""
  t "HEAD identiques"                    OK      verdict_parite abc1234 abc1234
  t "standby en retard : toléré"         ECART   verdict_parite abc1234 def4567
  #  🔴 #854 — le cas réel, absent jusqu'au 09/09/2026 : `rev-parse --short`
  #  abrège selon la taille du dépôt, donc les deux nœuds rendent le MÊME commit
  #  sur des longueurs différentes. Le point 10 était en ÉCART permanent.
  t "même commit, abréviations inégales" OK      verdict_parite ee33a715 ee33a71
  t "abréviation trop courte : rien de prouvé" INCONNU verdict_parite ee33a7 ee33a715
  #  🔴 #511 — le point 18 : la parité de CODE ci-dessus rend OK là où les
  #  IMAGES sont périmées. Les deux verdicts sont volontairement DISTINCTS, et
  #  ces cas-ci sont ce qui empêche de les refondre « pour simplifier ».
  t "images bâties sur le code du standby" OK      verdict_images_standby abc1234 abc1234
  t "build échoué : images en arrière"     FAIL    verdict_images_standby abc1234 def4567
  t "marqueur absent : rien de prouvé"     INCONNU verdict_images_standby abc1234 ""
  t "code du standby non mesuré"           INCONNU verdict_images_standby "" abc1234
  #  Le point 12 juge le CONTENU servi (#1675) : 1) les images étiquetées
  #  sont-elles bâties sur un code qui contient le dernier commit du service
  #  (`inclus`, lu au marqueur `.images-construites`) ? 2) le conteneur
  #  tourne-t-il sur le manifeste de l'image étiquetée ? Arguments : inclus,
  #  manifeste du conteneur, manifeste de l'image étiquetée.
  #  🔴 Le cas du 04/10 : `FROM caddy:2.11` commité, image bâtie depuis le
  #  cache (MÊME manifeste), conteneur non recréé — et à juste titre. La
  #  règle par date rendait FAIL et bloquait la MEP suivante.
  t "Caddy du 04/10 : commit sans effet sur l'image" OK   verdict_image_service oui sha256:80973cea sha256:80973cea
  #  whatsapp du 04/10 : index d'image différent (attestation de build), même
  #  manifeste — le conteneur sert bien l'image étiquetée.
  t "même manifeste, autre index : servi"  OK          verdict_image_service oui sha256:7b6475c0 sha256:7b6475c0
  t "conteneur ≠ image étiquetée"          NON_RECREE  verdict_image_service oui sha256:aaaa1111 sha256:bbbb2222
  t "images bâties sans le commit"         PERIMEE     verdict_image_service non sha256:aaaa1111 sha256:aaaa1111
  #  Les deux à la fois : recréer ne suffirait pas, le build d'abord.
  t "périmée ET non recréée : le build"    PERIMEE     verdict_image_service non sha256:aaaa1111 sha256:bbbb2222
  #  Le fait mesuré se dit même quand l'autre mesure manque.
  t "marqueur illisible, conteneur ≠"      NON_RECREE  verdict_image_service - sha256:aaaa1111 sha256:bbbb2222
  t "marqueur illisible, même manifeste"   INCONNU     verdict_image_service - sha256:aaaa1111 sha256:aaaa1111
  t "conteneur absent"                     INCONNU     verdict_image_service oui - sha256:aaaa1111
  t "image étiquetée illisible"            INCONNU     verdict_image_service oui sha256:aaaa1111 -
  t "aucune mesure"                        INCONNU     verdict_image_service "" "" ""
  #  La COLLECTE du point 12, exécutée sur un docker et un git simulés : la
  #  forme `--platform` du démon à magasin containerd, et l'ordre des champs
  #  que la boucle du pré-check lit. Un dépôt jetable tient lieu de /opt/5hostachy.
  _r12=$(mktemp -d 2>/dev/null)
  if [ -n "$_r12" ]; then
    echo b9cd7457 > "$_r12/.images-construites"
    _c12() { bash -c "$(declare -f collecte_images_servies)
      docker() { case \"\$*\" in
        *ImageManifestDescriptor.Digest*) [ \"\$2\" = hostachy_caddy ] && echo sha256:conteneur-caddy || echo sha256:m-\$2 ;;
        *Platform*) echo linux/arm64 ;;
        *Config.Image*) echo img-\$2 ;;
        'image inspect --platform linux/arm64 '*) echo sha256:m-\${5#img-} ;;
        *) return 1 ;; esac; }
      git() { case \"\$1\" in log) echo ce5cba6a ;; merge-base) [ \"\$4\" = b9cd7457 ] ;; esac; }
      eval \"\$(collecte_images_servies '$_r12')\"" | grep "^$1 "; }
    t "collecte : service, inclus, manifestes, commit, marqueur"       "api oui sha256:m-hostachy_api sha256:m-hostachy_api ce5cba6a b9cd7457" _c12 api
    t "collecte : le conteneur Caddy sur un autre manifeste"       "caddy oui sha256:conteneur-caddy sha256:m-hostachy_caddy ce5cba6a b9cd7457" _c12 caddy
    rm -f "$_r12/.images-construites"
    t "collecte : marqueur absent → inclus inconnu (-)"       "front - sha256:m-hostachy_front sha256:m-hostachy_front ce5cba6a -" _c12 front
    rm -rf "$_r12"
  else
    echo "SKIP  collecte du point 12 : pas de répertoire temporaire"
  fi
  t "parité non mesurable"               INCONNU verdict_parite "" def456
  t "battement récent"                   OK      verdict_age_min 5 20
  t "battement manquant"                 FAIL    verdict_age_min 90 20
  t "âge non mesurable"                  INCONNU verdict_age_min "" 20
  t "cache sous le seuil"                OK      verdict_cache "25.26GB"
  t "cache au-dessus du seuil"           FAIL    verdict_cache "64.1GB"
  t "cache en mégaoctets"                OK      verdict_cache "812.4MB"
  t "cache non mesuré"                   INCONNU verdict_cache ""
  t "nombre d'entrées pris pour Go"      INCONNU verdict_cache "589"
  #  Le 4ᵉ argument est le seuil ; 40 min = 2 ticks de 15 min manqués, comme C15.
  t "silence, producteur vivant"         OK      verdict_alerte "" "" 5 40
  t "échec sans aucune alerte"           FAIL    verdict_alerte "" 30 5 40
  t "alerte postérieure à l'échec"       OK      verdict_alerte 25 30 5 40
  t "alerte dans le cooldown d'1 h"      OK      verdict_alerte 80 30 5 40
  t "échec ancien jamais alerté"         FAIL    verdict_alerte 5000 30 5 40
  #  ── #306 : le silence d'un producteur mort n'est pas un silence normal ─────
  #  Le cas vécu le 11/08/2026 : check-reliability mort depuis 135 min sur
  #  l'actif, aucun FAIL au journal — le point répondait OK.
  t "silence, producteur mort (vécu)"    INCONNU verdict_alerte "" "" 135 40
  t "silence, producteur pile au seuil"  OK      verdict_alerte "" "" 40 40
  t "silence, producteur jamais vu"      INCONNU verdict_alerte "" "" "" 40
  t "silence, âge producteur illisible"  INCONNU verdict_alerte "" "" "x" 40
  t "silence, seuil non fourni"          INCONNU verdict_alerte "" "" 5 ""
  t "silence, seuil illisible"           INCONNU verdict_alerte "" "" 5 "x"
  #  Un échec DÉJÀ ÉCRIT prouve que le producteur a tourné : la vivacité ne doit
  #  pas rendre INCONNU un canal démontré muet, sinon on perd l'information.
  t "échec muet malgré producteur mort"  FAIL    verdict_alerte "" 30 999 40
  #  ── #2191 : la dernière ligne de pytest, lue sans faux vert ────────────────
  t "pytest vert"                        OK      verdict_pytest_resume "3 passed in 1.2s"
  t "pytest vert, avertissement"         OK      verdict_pytest_resume "3 passed, 1 warning in 1.2s"
  #  Le cas du 23/10 : les tests ne se sont pas exécutés (import manquant).
  t "pytest en erreur de collecte"       INCONNU verdict_pytest_resume "3 passed, 1 warning, 3 errors in 1.71s"
  t "pytest en échec"                    FAIL    verdict_pytest_resume "1 failed, 2 passed in 1.2s"
  t "pytest muet"                        INCONNU verdict_pytest_resume ""
  t "aucun test"                         INCONNU verdict_pytest_resume "no tests ran in 0.01s"
  #  ── #319 : la CI rejouée en local couvre-t-elle CE commit ? ───────────────
  t "rejeu complet et vert"              OK      verdict_rejeu_ci abc123 abc123 0 0
  t "rejeu en échec"                     FAIL    verdict_rejeu_ci abc123 abc123 1 0
  #  Une étape non rejouable ici n'est pas un succès : c'est une mesure absente.
  t "rejeu partiellement mesurable"      INCONNU verdict_rejeu_ci abc123 abc123 0 2
  #  Le piège que ce verdict existe pour fermer : une trace vieille d'un lot.
  t "trace d'un autre commit"            INCONNU verdict_rejeu_ci deadbee abc123 0 0
  t "aucune trace"                       INCONNU verdict_rejeu_ci "" abc123 0 0
  t "comptes illisibles"                 INCONNU verdict_rejeu_ci abc123 abc123 "x" 0
  #  ── #2245 : l'arbre, pas l'historique ──────────────────────────────────────
  #  Un reword ou un squash change le sha, jamais l'arbre : ce qui a été testé reste vrai.
  t "autre sha, même arbre"              OK      verdict_rejeu_ci deadbee abc123 0 0 tree1 tree1
  t "autre sha, même arbre, en échec"    FAIL    verdict_rejeu_ci deadbee abc123 1 0 tree1 tree1
  t "autre sha, même arbre, INCONNU"     INCONNU verdict_rejeu_ci deadbee abc123 0 2 tree1 tree1
  #  Le contenu a changé : la trace ne dit rien, comme avant.
  t "autre sha, autre arbre"             INCONNU verdict_rejeu_ci deadbee abc123 0 0 tree1 tree2
  t "trace d'avant #2245 (sans arbre)"   INCONNU verdict_rejeu_ci deadbee abc123 0 0 "" tree2
  t "arbre de HEAD illisible"            INCONNU verdict_rejeu_ci deadbee abc123 0 0 tree1 ""
  t "deux arbres vides ne s'égalent pas" INCONNU verdict_rejeu_ci deadbee abc123 0 0 "" ""
  #  ── #502 : l'erreur que CE lot corrige ─────────────────────────────────────
  #  Sans déclaration, rien ne change : le point reste intransigeant.
  t "prod saine, aucune déclaration"     OK      verdict_erreurs_api 0 "" "" abc123 ""
  t "erreurs, aucune déclaration"        FAIL    verdict_erreurs_api 3 "" "" abc123 ""
  t "logs non mesurés"                   INCONNU verdict_erreurs_api "" "" "" abc123 ""
  #  Le cas du 19/08 : les 2 erreurs observées sont celles que ce lot corrige.
  t "toutes les erreurs sont déclarées"  OK      verdict_erreurs_api 2 2 abc123 abc123 "auth/refresh"
  #  Une erreur de PLUS que la signature ne couvre : elle, on ne la connaît pas.
  t "une erreur hors signature"          FAIL    verdict_erreurs_api 3 2 abc123 abc123 "auth/refresh"
  #  🔴 Le cœur du mécanisme : la dérogation ne survit pas à son objet.
  t "signature qui ne sert plus"         FAIL    verdict_erreurs_api 0 0 abc123 abc123 "auth/refresh"
  #  Désarmer le point en le déclarant : refusé, la signature n'ancre rien.
  t "signature vide de littéral"         FAIL    verdict_erreurs_api 2 2 abc123 abc123 ".*"
  t "signature = le niveau de log"       FAIL    verdict_erreurs_api 2 2 abc123 abc123 "ERROR"
  #  Le faux vert par fichier périmé, cousin de celui de 0f.
  t "déclaration d'un autre lot"         FAIL    verdict_erreurs_api 2 2 deadbee abc123 "auth/refresh"
  #  On ne devine pas une déclaration à moitié écrite.
  t "signature sans commit"              INCONNU verdict_erreurs_api 2 2 "" abc123 "auth/refresh"
  t "écartées non mesurées"              INCONNU verdict_erreurs_api 2 "" abc123 abc123 "auth/refresh"
  t "plus d'écartées que d'observées"    INCONNU verdict_erreurs_api 1 2 abc123 abc123 "auth/refresh"
  t "ancrage : chemin"                   oui     signature_ancree "auth/refresh"
  #  ── Le MOTIF du point 6 (#1066) : ce qu'il compte, et ce qu'il laisse. ──
  #  🔴 Il ne comptait que les niveaux de log. Une bibliothèque qui écrit sur
  #  stderr n'a pas de niveau : 15 « Fontconfig error » à chaque démarrage de
  #  l'API, et le point rendait « compte=0 ».
  _compte() { printf '%s' "$1" | grep -cE "$MOTIF_ERREURS_API"; }
  t "motif : niveau ERROR"               1       _compte "2026-09-23 07:10:49,676 ERROR app.x — boum"
  t "motif : niveau CRITICAL"            1       _compte "2026-09-23 07:10:49,676 CRITICAL app.x — boum"
  t "motif : erreur de bibliothèque"     1       _compte "Fontconfig error: No writable cache directories"
  #  ⚠️ Un WARNING qui CITE une erreur reste un WARNING : le journal de sécurité
  #  et les échecs d'envoi l'emploient exprès pour ne pas faire sonner le point.
  t "motif : WARNING citant une erreur"  0       _compte "2026-09-19 14:54:14 WARNING app.utils.whatsapp — échec : Client error '413'"
  t "motif : INFO anodin"                0       _compte "2026-09-23 06:00:00 INFO httpx — HTTP Request: GET /status 200 OK"
  #  Une trace Python SUIT sa ligne ERROR : la compter aussi doublerait
  #  l'erreur, et l'écartement par signature rendrait « une erreur de plus ».
  t "motif : dernière ligne d'une trace" 0       _compte "ValueError: boum"
  t "ancrage : joker seul"               non     signature_ancree ".*"
  t "ancrage : motif vide"               non     signature_ancree ""
  t "ancrage : mot trop court"           non     signature_ancree "db|io"

  # ═══ Banc d'essai sur un dépôt JETABLE — la mesure, pas la décision ═══
  #
  #  🔴 Tout ce qui précède éprouve des VERDICTS : des fonctions pures à qui l'on
  #  donne des nombres. Aucun ne dit si `fichiers_non_recouverts` sait lire un
  #  vrai dépôt — et c'est là que vivent les défauts qui se relisent comme
  #  corrects (socle 04 §11 et §22). On rejoue donc le scénario du 29/08/2026,
  #  celui qui a coûté un `SKIP_PRECHECK=1`, sur un dépôt construit pour ça.
  if command -v git >/dev/null 2>&1; then
    _banc=$(mktemp -d 2>/dev/null) || _banc=""
    if [ -n "$_banc" ]; then
      (
        cd "$_banc" || exit 1
        git init -q . && git config user.email t@t && git config user.name t
        #  Base commune : la version 1.0.0.
        printf '1.0.0
' > version.txt && printf 'contenu
' > autre.txt
        git add -A && git commit -qm base
        git branch -q amont
        #  Sur l'amont : un bump qui sera RETIRÉ (le cas de #616).
        git checkout -q amont && printf '1.0.1
' > version.txt
        git add -A && git commit -qm "bump 1.0.1"
        #  Sur HEAD : le lot, qui réécrit le MÊME fichier avec une autre version.
        git checkout -q master 2>/dev/null || git checkout -q main
        printf '1.1.0
' > version.txt && git add -A && git commit -qm "bump 1.1.0"
      ) >/dev/null 2>&1
      _mesure() { local d=$1 a=$2 o c; o=$(cd "$d" && fichiers_non_recouverts "$a" 2>/dev/null); c=$?; printf '%s|%s' "$c" "$o"; }
      t "banc : bump retiré, fichier réécrit → rien de perdu" "0|" _mesure "$_banc" amont

      #  Et le cas DANGEREUX : l'amont porte un commit sur un fichier que HEAD
      #  n'a pas touché. C'est du travail d'ailleurs — il serait écrasé.
      (
        cd "$_banc" && git checkout -q amont && printf 'travail
' > ailleurs.txt
        git add -A && git commit -qm "travail d'une autre session"
        git checkout -q master 2>/dev/null || git checkout -q main
      ) >/dev/null 2>&1
      t "banc : travail d'ailleurs → nommé comme perdu" "0|ailleurs.txt" _mesure "$_banc" amont

      #  Cas zéro de la mesure : sans base commune, elle ne conclut pas.
      t "banc : amont inconnu → code d'erreur, pas une sortie vide" "1|" _mesure "$_banc" branche-absente
      t "banc : amont non fourni → code d'erreur" "1|" _mesure "$_banc" ""
      # ── Le PARSING de `.git/reecriture-dev`, sur de vrais fichiers ──────────
      #  Le CRLF est le piège numéro un de ce poste (socle 10) : un retour
      #  chariot collé au sha, et plus aucune comparaison ne correspond — sans
      #  erreur, sans trace.
      #
      #  ⚠️ Ces `printf` portent des échappements LITTÉRAUX (barre oblique
      #  inverse + n). Une réécriture qui les résoudrait à l'écriture du fichier
      #  casserait le cas CRLF en silence : le test resterait vert en ne testant
      #  plus rien. C'est arrivé le 29/08/2026, en écrivant ce banc.
      _porte_cr() { if od -c "$1" 2>/dev/null | grep -q '\\r'; then echo oui; else echo non; fi; }
      _lire() { lire_declaration_reecriture "$1" | tr '\n' '/'; }
      printf 'commit: 601477b\n137cab0\n' > "$_banc/d1"
      t "parsing : déclaration simple"            "601477b/137cab0/" _lire "$_banc/d1"
      printf 'commit: 601477b\r\n137cab0\r\n' > "$_banc/d2"
      t "parsing : fichier en CRLF"               "601477b/137cab0/" _lire "$_banc/d2"
      printf 'commit: 601477b\n\n137cab0\n# note\n999aaaa\n' > "$_banc/d3"
      t "parsing : lignes vides et commentaires ignorés" "601477b/137cab0 999aaaa/" _lire "$_banc/d3"
      #  Un sha trop court n'est pas un sha : le compter fausserait le décompte
      #  qui sert justement à refuser une déclaration périmée.
      printf 'commit: 601477b\n137c\n' > "$_banc/d4"
      t "parsing : sha tronqué rejeté"            "601477b//" _lire "$_banc/d4"
      #  Cas nominal : pas de fichier, pas de déclaration — et surtout pas une
      #  erreur (le pré-check tourne sans déclaration 99 fois sur 100).
      t "parsing : fichier absent → vide, sans erreur" "//" _lire "$_banc/pas-de-fichier"
      #  🔴 Le test du CRLF ne prouve rien s'il n'écrit pas de CRLF : on le
      #  vérifie, plutôt que de le supposer.
      t "parsing : le cas CRLF contient bien un CR" "oui" _porte_cr "$_banc/d2"
      rm -rf "$_banc"
    else
      echo "SKIP  banc d'essai : pas de répertoire temporaire"
    fi
  fi

  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  return $st
}
