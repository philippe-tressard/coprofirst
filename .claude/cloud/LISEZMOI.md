# Session cloud Claude Code (claude.ai/code) — l'environnement 5Hostachy

L'environnement se configure dans l'interface claude.ai, **pas dans le dépôt** :
ce fichier dit quoi y saisir. Tout ce qui peut vivre dans le dépôt y vit —
l'interface ne porte qu'un appel à `setup.sh`, pour qu'aucune configuration ne
diverge sans que personne la relise (24/09/2026).

## À saisir dans l'interface

**Nom** : `5hostachy`

**Réseau** : *Trusted* (PyPI, npm, GitHub, miroirs Ubuntu). Si `setup.sh`
signale l'échec de `playwright install`, passer en *Custom* et ajouter
`cdn.playwright.dev`, `playwright.azureedge.net`,
`playwright.download.prss.microsoft.com`.
🔴 Ni le domaine de production ni les IP des RPi.

**Variables d'environnement** — aucune n'est un secret, et aucune ne doit l'être :
elles sont visibles de tous les utilisateurs de l'environnement (socle 03).

```
SECRET_KEY=cloud-dev-placeholder-0123456789abcdef0123
DATABASE_URL=postgresql+psycopg://essai:essai@localhost:5432/essai
TESTS_BASE_URL=postgresql+psycopg://essai:essai@localhost:5432/essai
ENABLE_API_DOCS=false
MAIL_ENABLED=false
UPLOADS_DIR=/tmp/hostachy-uploads
```

Les deux URL désignent le PostgreSQL que `setup.sh` installe dans la VM — rôle et
base `essai`, ceux du job de CI : la suite pytest ne tourne que sur PostgreSQL, et
chaque test y reçoit un schéma neuf.

**Script de setup** — il ne fait que retrouver le dépôt et appeler `setup.sh` :

```bash
#!/bin/bash
f=$(find / -maxdepth 6 -path '*/.claude/cloud/setup.sh' -not -path '/proc/*' 2>/dev/null | head -1)
[ -n "$f" ] && exec bash "$f"
echo "⚠️ setup.sh introuvable (dépôt pas encore cloné ?) : lancer « bash .claude/cloud/setup.sh » en session."
exit 0
```

🔴 **`-maxdepth 6`, pas 5** (24/09/2026). Le dépôt est cloné sous
`/home/user/5hostachy`, donc `setup.sh` est au **sixième** niveau depuis `/`.
Avec 5, le `find` ne trouvait rien, le script affichait son message et sortait
en **succès** : l'environnement démarrait sans rien installer, et l'interface
n'en disait rien. Mesuré dans une session : `-maxdepth 5` → vide,
`-maxdepth 6` → `/home/user/5hostachy/.claude/cloud/setup.sh`.

La documentation ne dit pas si le dépôt est déjà cloné quand le setup s'exécute.
S'il ne l'est pas, rien n'est perdu : `env-report.sh` affiche
« Dépendances : 🔴 ABSENTES » au démarrage, et la commande à lancer.

## Ce que la session cloud n'a pas — et que `env-report.sh` affiche

| Absent | Pourquoi | Conséquence |
|---|---|---|
| SSH vers les RPi | réseau local injoignable | pré-check **INCONNU** et post-check au poste ; la MEP, elle, **s'enchaîne sans validation intermédiaire** jusqu'à `main` — la règle vit dans `CLAUDE.md`, « Session cloud », et nulle part ailleurs |
| `~/.claude` (consignes globales, mémoire) | le cloud ne lit que le `.claude/` du dépôt | la banque de mémoire n'est ni lue ni écrite |
| le socle `claude-config` | le proxy GitHub ne sert que les dépôts **attachés** à la session | l'attacher à la session le rend disponible (`~/claude-config`, liens dans `~/.claude/`) |
| le garde-fou `git reset --hard` | il vit dans `claude-config` | relayé par `garde-git.sh` **s'il est présent** ; sinon affiché 🔴 ABSENT |

`garde-git.sh` **appelle** le garde-fou du socle, il ne le recopie pas : une
seconde version divergerait à la première règle ajoutée. Sur le poste il ne fait
rien — le hook global y tourne déjà.
