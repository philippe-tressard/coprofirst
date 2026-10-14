# La démo publique de CoproFirst

Une **installation standard** (`deploiement/standard/LISEZMOI.md`) devient la démo
publique en posant `MODE_DEMO=oui` dans son `.env`. Le même code, les mêmes
images : rien n'est construit pour la démo. Spécification :
`specs/architecture/mode-demo.md`.

⚠️ **Jamais sur une installation qui sert une vraie copropriété.** La remise à zéro
nocturne efface la base et les fichiers.

## Ce que le mode démo change

- **Entrée par le formulaire**, sous l'un de trois comptes partagés dont les
  identifiants sont publiés (`api/app/demo/personnages.py`, page « Démo » du
  site vitrine) : `user-cs`, `user-copro`, `user-loc` `@demo.coprofirst.fr`.
  L'administrateur est celui du seed (`admin@localhost`, administrateur et
  opérateur), réservé. Son mot de passe est **fixe et secret** si `.env` pose
  `DEMO_ADMIN_MOT_DE_PASSE` (jamais publié, contrairement aux trois autres) ;
  sinon il change à chaque remise à zéro et ne s'écrit que dans le **journal de
  la remise à zéro** — le jeu se charge dans un conteneur ponctuel, et l'API est
  recréée après : ses journaux ne l'ont jamais.
  ```bash
  grep -A3 'ADMIN INITIAL' /var/log/coprofirst-demo.log | tail -4
  ```
- **Rien ne part** : ni courriel, ni message WhatsApp, ni appel à l'IA. Un
  courriel qui serait parti s'inscrit à l'historique, « démonstration : non
  envoyé ».
- **Fermés** : l'inscription, les réglages, l'exploitation, les téléversements,
  les changements d'identité des comptes partagés (`utils/demo.GESTES_FERMES`).
- **Une résidence fictive**, fabriquée à chaque remise à zéro avec des dates
  relatives au jour : elle ne vieillit pas.

## Installer

1. Installer comme une réplique (`deploiement/standard/LISEZMOI.md`), base
   **PostgreSQL** pour la démo de CoproFirst (SQLite est aussi géré par la
   remise à zéro) — d'abord **sans** `MODE_DEMO` : une installation
   ordinaire, avec son administrateur initial.
2. **S'inscrire au registre** avec ce compte, qui est l'**opérateur** :
   *Administration › Maintenance › Inscription au registre*. La démo n'a pas
   d'opérateur — ses comptes publics ne le sont pas, et son administrateur change
   chaque nuit — et l'inscription, rangée dans
   le volume `app_data`, survit aux remises à zéro : c'est le seul moment pour
   la faire.
3. Dans `.env` :
   ```
   MODE_DEMO=oui
   MAINTENANCE_KEY=<openssl rand -hex 32>
   DEMO_EDITEUR=          # vide : « édité à titre non professionnel » (LCEN 6-III-2)
   DEMO_CONTACT=<adresse où exercer ses droits>
   DEMO_ADMIN_MOT_DE_PASSE=<secret, règle de robustesse du produit>  # vide : aléatoire
   ```
   Les mentions légales et la politique de confidentialité de la démo sont
   **reposées à chaque remise à zéro** (`api/app/demo/legal.py`) : elles nomment
   les hébergeurs (Oracle, Cloudflare) et prennent l'éditeur et le contact ici —
   jamais dans le dépôt, qui est public. Sans `DEMO_CONTACT`, le chargement le
   signale et la page n'a pas d'adresse : ne pas ouvrir la démo ainsi.
4. Le conteneur `whatsapp-bridge` démarre avec les autres services : sans session
   WhatsApp il ne fait rien, et les portes d'envoi de l'API lui sont fermées.
5. Charger la première fois — le script arrête l'API lui-même, et la base
   ordinaire de l'étape 1 est remplacée par la résidence fictive :
   ```bash
   deploiement/demo/reinitialiser.sh
   ```
6. Exposer le port 80 de la machine derrière un frontal HTTPS — pour la démo de
   CoproFirst, un tunnel Cloudflare vers `http://localhost:80`.

## Chaque nuit

Dans la crontab de l'utilisateur qui pilote Docker, **après** la mise à jour :

```
30 4 * * * /opt/coprofirst/deploiement/standard/mise-a-jour.sh >> /var/log/coprofirst-maj.log 2>&1
15 5 * * * /opt/coprofirst/deploiement/demo/reinitialiser.sh >> /var/log/coprofirst-demo.log 2>&1
```

Les deux scripts partagent un verrou : la remise à zéro attend une mise à jour qui
déborde, au plus une heure. Le jeu est ainsi fabriqué par la version qui vient
d'être installée.

🔒 Le journal de la remise à zéro porte le mot de passe de l'administrateur : le
créer lisible de son seul propriétaire, **avant** la première nuit.

```bash
sudo install -m 600 -o "$USER" -g "$USER" /dev/null /var/log/coprofirst-demo.log
```

La remise à zéro **ne vide jamais le volume `app_data` en entier** : elle n'y
supprime que le fichier de la base. L'inscription de l'installation au registre y
vit (`INSTALLATION_DIR`).

## Le registre des installations

🔴 **Jamais `docker compose down -v`** sur la démo, ni aucune reconstruction qui
efface le volume `app_data` : il porte l'identité de l'installation au registre
(`/app/data/installation` : sa clé privée et son état). La perdre oblige à
résilier l'identifiant et à se réinscrire — c'est arrivé à la mise en service,
le 13/10/2026 (CF-000002 perdu, CF-000003 inscrit). Une copie de l'identité se
garde hors du volume, lisible du seul utilisateur qui pilote Docker.

La démo **s'inscrit** comme toute réplique, à l'installation (étape 2 ci-dessus) :
l'inscription survit aux remises à zéro. Tant que la référence ne l'a pas validée,
elle s'affiche « limitée », sans effet : le plafond de cinq utilisateurs n'est pas
appliqué (mode constat). Le jour où il le sera (#1882),
la démo — une vingtaine de comptes — en est exemptée sous `est_demo()` (spec §11,
question 3).

## Quand ça échoue

- Le chargement refusé ou en erreur laisse l'**API arrêtée** : une démo à moitié
  chargée ne se sert pas. La cause est dans `/var/log/coprofirst-demo.log`.
- Une remise à zéro réussie, ou une santé KO après le rechargement, se lit dans
  *Administration › Maintenance* (tâche « Remise à zéro de la démo »).
- Relancer à la main : `deploiement/demo/reinitialiser.sh`.
