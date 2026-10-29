# Contribuer à CoproFirst

Merci de l'intérêt porté au projet. Ce document décrit la méthode **réellement**
suivie — pas une méthode générique : les commandes ci-dessous sont celles que
l'intégration continue exécute, et les contrôles qu'elles rejouent sont les mêmes.

> ⚠️ **Avant tout** : lire la section [Licence](#licence). Le code est
> *accessible*, il n'est pas libre au sens de l'OSI, et une contribution est
> versée sous la licence du projet.

---

## 1. Ce qu'il faut sur le poste

| Outil | Version | Où elle est décidée |
|---|---|---|
| Python | 3.12 | `api/Dockerfile` (`python:3.12-slim`) |
| Node.js | 26 | `front/Dockerfile` (`node:26-alpine`) |
| Docker et Docker Compose | — | `docker-compose.yml` |
| PostgreSQL | 17 | `docker-compose.yml` (image `postgres`) — un serveur sur le poste pour les tests, désigné par `TESTS_BASE_URL` |

Les versions ne sont pas recopiées ailleurs : ce tableau nomme le fichier qui
décide, pour qu'une montée de version ne laisse pas une documentation fausse
derrière elle.

## 2. Démarrer en local

```bash
git clone https://github.com/philippe-tressard/coprofirst.git
cd coprofirst
cp .env.example .env          # puis renseigner SECRET_KEY (32 caractères au moins)
docker compose up --build -d
```

Le site répond alors sur `http://localhost`.

**Armer les hooks git — une fois par clone**, sinon ils sont inertes :

```bash
git config core.hooksPath .githooks && git config pull.ff only
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

La dernière ligne fait sauter à `git blame` les commits purement mécaniques
(reformatage) déclarés dans `.git-blame-ignore-revs` ; GitHub le lit déjà seul.

Le hook de pré-commit refuse un commit dont la branche est en retard sur son
distant ; celui de pré-poussée refuse un envoi sans trace de pré-contrôle. Un
hook versionné n'est **pas** un hook actif.

### Sans Docker

```bash
cd api && python -m venv .venv && .venv/Scripts/activate  # ou source .venv/bin/activate
pip install -r requirements.txt && uvicorn app.main:app --reload
```

`DATABASE_URL` désigne alors un PostgreSQL joignable depuis le poste.

```bash
cd front && npm install && npm run dev
```

## 3. Signaler une anomalie ou proposer une évolution

Les tickets passent par **les issues GitHub**, avec le gabarit proposé à
l'ouverture. Le format attendu est celui des tickets d'audit du dépôt :

1. **Constat** — ce qui est observé, avec le fichier et la ligne, ou la sortie de
   commande. Un constat non reproduit n'est pas établi.
2. **Ce que le ticket demande** — le comportement attendu, pas la solution.
3. **Verrous connus** — ce qui est irréversible, ce qui a déjà été essayé.

### Les étiquettes, et ce qu'elles engagent

| Étiquette | Sens |
|---|---|
| `priorité haute` · `priorité normale` · `priorité basse` | ordre de traitement |
| `en cours` | posée **au moment** de commencer, jamais d'avance |
| `livré · à vérifier` | le code est en production, une observation manque |
| `rendez-vous` | la preuve dépend d'une date |
| `bloqué` | une décision manque — le ticket dit laquelle, et de qui |

Un ticket se ferme sur une **preuve** : la commande et sa sortie, ou le
comportement observé en production. Jamais sur « ça devrait aller ».

## 4. Proposer du code

> **Modèle de branches** : `main` est la production, protégée — aucun envoi
> direct, aucun forçage, et les contrôles d'intégration y sont exigés. Tout passe
> par `dev`.

1. **Dupliquer** le dépôt, puis créer une branche depuis `dev` :
   `git checkout dev && git checkout -b feat/mon-sujet`
2. Des commits atomiques, un par nature de changement.
3. **Rejouer l'intégration continue en local** — tous les travaux, pas un seul :

   ```bash
   bash scripts/poste/rejouer-ci.sh
   ```

   Ce script **extrait** ses commandes de `.github/workflows/ci.yml` : une liste
   tenue à la main divergerait au premier travail ajouté, et c'est justement
   celui qu'on n'a pas pensé à lancer qui échoue.

4. Ouvrir la demande de fusion **vers `dev`**. Une demande visant `main`
   directement est refusée.

### Messages de commit

Préfixes : `feat` · `fix` · `docs` · `refactor` · `test` · `chore` · `perf`.

```
feat: barre de progression au dépôt d'un document
fix: décompte des badges expirés
docs: procédure de restauration après bascule
```

### Ce qu'un lot doit porter, en plus du correctif

- **Un garde-fou.** Un correctif sans test ni contrôle qui refuse la récidive est
  un correctif qui revient. Écrire d'abord le cas fautif, prouver que le contrôle
  le refuse, puis corriger.
- **Sa consigne.** Si le lot change un motif d'interface, d'API ou d'infra, la
  documentation qui l'enseigne bouge dans le **même** commit — sinon la consigne
  périmée régénère le défaut au lot suivant.
- **La documentation utilisateur**, dès qu'un écran, un libellé ou un parcours
  change : `docs/manuel-utilisateur.html` (comment on s'en sert) et `README.md`
  (ce que le produit est) sont de même rang. Un lot qui ne touche qu'un seul des
  deux le **dit**.

## 5. Style de code

- **Python** : PEP 8, annotations de types là où elles servent. `ruff` est exigé.
- **TypeScript et Svelte** : types explicites, motifs existants réutilisés plutôt
  que variantes locales. Plusieurs contrôles dédiés refusent une réécriture
  locale de ce qui existe au centre (assainissement HTML, formats de date et de
  montant, champs de formulaire, client d'API).
- **Migrations** : Alembic, identifiant séquentiel à quatre chiffres. Une
  migration déjà appliquée **ne se modifie jamais** — on en crée une nouvelle.
- **Français exclusif** : interface, nommage des champs, messages de commit,
  commentaires. Seuls les identifiants techniques imposés restent en anglais.
- **Fins de ligne** : `.editorconfig` décide. Les scripts shell sont en LF sans
  marque d'ordre d'octets, et l'intégration continue le refuse autrement.

## 6. Mise en production

La demande de fusion `dev → main` est créée, contrôlée et fusionnée par le
mainteneur, après le pré-contrôle complet (`scripts/poste/precheck-mep.sh`) et la
montée de version dans `front/package.json`. Le déploiement suit tout seul sur le
nœud actif ; **la fusion n'est pas le déploiement**, et un lot n'est terminé que
lorsque la version est servie et le comportement observé.

## 7. Sécurité

Une faille ne s'ouvre **pas** en ticket public : la conduite à tenir est dans
[SECURITY.md](SECURITY.md).

## Licence

En contribuant, la contribution est versée sous la licence du projet,
**AGPL-3.0-or-later** — la GNU Affero General Public License, version 3 ou
ultérieure, dont le texte officiel est dans [LICENSE](LICENSE). C'est un logiciel
libre : la contribution pourra être utilisée, modifiée et redistribuée par
chacun, à condition que les versions modifiées restent sous la même licence.
Les mentions de copyright et l'historique de la licence sont dans
[NOTICE.md](NOTICE.md).
