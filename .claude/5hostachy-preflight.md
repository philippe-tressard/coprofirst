============== PRÉ-FLIGHT 5HOSTACHY ==============
(injecté par le hook SessionStart — non négociable)

Ce bloc ne RECOPIE plus les règles : elles vivent dans `CLAUDE.md` (déjà en
contexte) et dans le socle `~/.claude/standards/`. Sept notions permanentes sur
huit y étaient écrites deux ou trois fois — et je les ai enfreintes quand même
(09/08/2026). Répéter n'augmente pas l'observance ; seuls un déclencheur
observable et un contrôle qui échoue le font.

Il ne reste ici que ce qu'un hook seul peut apporter : des DÉCLENCHEURS liés à
une action concrète, et non à une intention.

┌─ AVANT CETTE ACTION ──────────────→ CHARGER / LANCER ─────────────────────┐
│ `git push` sur dev ou main          bash scripts/poste/precheck-mep.sh   (le hook        │
│   = tu t'apprêtes à déployer          pre-push le refuse sans sa trace)    │
│ écrire dans front/src/**             .claude/skills/ux-patterns            │
│                                      + svelte-patterns                     │
│ nouveau modèle / route / migration   .claude/skills/api-scaffold           │
│ toucher aux droits, secrets, à une   .claude/skills/security-audit         │
│   exposition publique                                                      │
│ ssh sur un RPi, bascule, incident    .claude/skills/infra-rpi              │
│ fonctionnalité visible livrée        .claude/skills/user-manual            │
│ avant tout commit                    skill globale `avant-commit`          │
└───────────────────────────────────────────────────────────────────────────┘

UN SEUL INTERDIT RAPPELÉ ICI — le seul dont la violation est IRRÉVERSIBLE :
  • Jamais deux primaires PostgreSQL, ni une base absente démarrée sur un nœud
    qui prend la main (elle naîtrait primaire VIDE) : passer par lib-promotion.sh
    et reconstruire-replique.sh. Jamais `docker volume rm 5hostachy_pg_data`.

Les autres règles (INCONNU jamais OK, français exclusif, bump de version, PR
dev→main) sont dans CLAUDE.md, déjà en contexte. Les recopier ici ne les a pas
fait respecter — c'est mesuré, pas supposé.

CONFORMITÉ : en tête de la 1ʳᵉ réponse impliquant du travail sur 5Hostachy,
écrire « ✅ Consignes 5Hostachy chargées » + la liste de ce qui a réellement été
LU. Sinon « ⚠️ NON CONFORME : <raison> », et corriger avant d'agir.
=================================================================
