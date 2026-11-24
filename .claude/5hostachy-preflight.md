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
│ ouvrir la PR d'un lot                bash scripts/poste/rejouer-ci.sh      │
│ lancer conduire-mep.sh (déployer)    bash scripts/poste/precheck-mep.sh    │
│   — ordre : CLAUDE.md, « Ordre       après la CI verte de la PR            │
│   d'un lot »                         + .claude/skills/mep-precheck         │
│ écrire dans front/src/**             .claude/skills/ux-patterns            │
│                                      + svelte-patterns                     │
│ écrire dans api/** (modèle, route…)  .claude/skills/api-scaffold           │
│ toucher aux droits, secrets, à une   .claude/skills/security-audit         │
│   exposition publique                                                      │
│ ssh sur un RPi, bascule, incident    .claude/skills/infra-rpi              │
│ fonctionnalité visible livrée        .claude/skills/user-manual            │
│ avant tout commit                    skill globale `avant-commit`          │
└───────────────────────────────────────────────────────────────────────────┘

UNE SEULE RÈGLE RAPPELÉE ICI — la seule dont la violation est IRRÉVERSIBLE :
  • la « Règle d'or des données » de CLAUDE.md, en tête (déjà en contexte). Ses
    interdits — tous, y compris `docker compose` sans liste de services — y sont
    écrits une fois ; les relire avant tout geste sur un nœud ou sur la base.

Les autres règles (INCONNU jamais OK, français exclusif, bump de version, PR
dev→main) sont dans CLAUDE.md, déjà en contexte. Les recopier ici ne les a pas
fait respecter — c'est mesuré, pas supposé.

CONFORMITÉ : en tête de la 1ʳᵉ réponse impliquant du travail sur 5Hostachy,
écrire « ✅ Consignes 5Hostachy chargées » + la liste de ce qui a réellement été
LU. Sinon « ⚠️ NON CONFORME : <raison> », et corriger avant d'agir.
=================================================================
