# Déploiement automatique — RPi 5

> 🔴 **Ce document ne décrit plus de procédure.** Il enseignait un script
> `/opt/hostachy-deploy.sh` écrit à la main, un cron `0 3 * * *` ou `*/10`, et
> recommandait `git reset --hard origin/main` en cas de conflit : tout cela avait
> été remplacé, et le dernier geste est **interdit** sans l'accord explicite de
> Philippe (#1049, audit du 19/09/2026). Il ne garde que des renvois vers ce qui
> est vrai aujourd'hui — une consigne dit où la vérité se lit, elle ne la recopie
> pas.

## Où lire ce qui tourne réellement

| Question | Source vivante |
|---|---|
| Quel script déploie, et comment | `scripts/exploitation/auto-deploy.sh` — son en-tête : verrou, parité des images, actif qui déploie, standby qui s'aligne sans rien démarrer (#448) |
| Quand il tourne, sous quel compte | `infra/points-entree/cron-ptressard.crontab` — seule source versionnée, comparée à l'installé par le point 17 du pré-check |
| Les autres crons et l'unité systemd | `infra/points-entree/` et son `LISEZMOI.md` |
| Installer un nœud neuf (durcissement, clone, `.env`, réplique) | [restauration-complete.md](restauration-complete.md) |
| Conduire une MEP, savoir si elle a eu lieu, revenir en arrière | skill `.claude/skills/mep-precheck` |

## Les trois faits à ne pas oublier

- **Fusionner vers `main` n'est pas déployer.** `auto-deploy.sh` fait le `git pull`
  puis le build ; la MEP n'est faite qu'à la ligne `Déployé: <sha>` dans
  `/var/log/hostachy-deploy.log` **sur l'actif**.
- **Reprise en main** : `sudo bash scripts/exploitation/MaJ-Hostachy.sh`, sur le RPi
  **actif** uniquement (le script bloque sur le standby, et pose le verrou de
  bascule sur les deux nœuds).
- **Un clone qui refuse le `git pull`** (modifications locales sur un nœud) est une
  anomalie à **comprendre** — `git status`, `git diff` — et non à écraser. Aucun
  `git reset --hard`, `git clean -f` ni `git checkout -- .` sans l'accord de
  Philippe : c'est ce qu'enseignait ce document, et c'est ce qu'il ne doit plus
  enseigner.
