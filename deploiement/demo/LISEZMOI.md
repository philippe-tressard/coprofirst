# La démo publique de CoproFirst

Une **installation standard** (`deploiement/standard/LISEZMOI.md`) devient la démo
publique en posant `MODE_DEMO=oui` dans son `.env`. Le même code, les mêmes
images : rien n'est construit pour la démo. Spécification :
`specs/architecture/mode-demo.md`.

⚠️ **Jamais sur une installation qui sert une vraie copropriété.** La remise à zéro
nocturne efface la base et les fichiers.

## Ce que le mode démo change

- **Entrée sans compte**, par un personnage partagé : `/api/demo/entrer/resident`,
  `locataire`, `conseil-syndical`, `administrateur`.
- **Rien ne part** : ni courriel, ni message WhatsApp, ni appel à l'IA. Un
  courriel qui serait parti s'inscrit à l'historique, « démonstration : non
  envoyé ».
- **Fermés** : l'inscription, les réglages, l'exploitation, les téléversements,
  les changements d'identité des personnages (`utils/demo.GESTES_FERMES`).
- **Une résidence fictive**, fabriquée à chaque remise à zéro avec des dates
  relatives au jour : elle ne vieillit pas.

## Installer

1. Installer comme une réplique (`deploiement/standard/LISEZMOI.md`), base
   **SQLite** (le défaut).
2. Dans `.env` :
   ```
   MODE_DEMO=oui
   MAINTENANCE_KEY=<openssl rand -hex 32>
   ```
3. Le conteneur `whatsapp-bridge` démarre avec les autres services : sans session
   WhatsApp il ne fait rien, et les portes d'envoi de l'API lui sont fermées.
4. Charger la première fois — le script arrête l'API lui-même :
   ```bash
   deploiement/demo/reinitialiser.sh
   ```
5. Exposer le port 80 de la machine derrière un frontal HTTPS — pour la démo de
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

La remise à zéro **ne vide jamais le volume `app_data` en entier** : elle n'y
supprime que le fichier de la base. L'inscription de l'installation au registre y
vit (`INSTALLATION_DIR`).

## Quand ça échoue

- Le chargement refusé ou en erreur laisse l'**API arrêtée** : une démo à moitié
  chargée ne se sert pas. La cause est dans `/var/log/coprofirst-demo.log`.
- Une remise à zéro réussie, ou une santé KO après le rechargement, se lit dans
  *Administration › Maintenance* (tâche « Remise à zéro de la démo »).
- Relancer à la main : `deploiement/demo/reinitialiser.sh`.
