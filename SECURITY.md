# Politique de sécurité

## Version suivie

Une seule instance de production existe, et elle sert toujours la dernière
version publiée — celle qu'affiche le pied de page du site. Il n'y a pas de
rétroportage sur une version antérieure, donc pas de tableau de versions à
tenir : il annonçait la majeure 1 pour un produit en version 2 (#1582).

## Signaler une faille

Une faille ne s'ouvre **jamais** en ticket public.

Le signalement passe par les **avis de sécurité GitHub**, en privé :

1. onglet [Security](../../security/advisories) du dépôt ;
2. *New draft security advisory* ;
3. décrire la faille, comment la reproduire, et l'impact estimé.

### Ce à quoi s'attendre

| Étape | Délai |
|---|---|
| accusé de réception | 48 heures |
| première évaluation | 7 jours |
| correctif d'une faille critique | déployé dès qu'il est prêt et contrôlé |

Un correctif de sécurité suit le même chemin que tout autre lot — pré-contrôle,
contrôles d'intégration exigés, montée de version, déploiement observé — parce
qu'un correctif livré sans ces étapes n'est pas un correctif livré.

## Périmètre

| Composant | Ce qu'il porte |
|---|---|
| `api/` | interface de programmation, authentification, autorisations, accès à la base |
| `front/` | interface SvelteKit, manipulation des données côté client |
| infrastructure | Docker, proxy Caddy, agent Cloudflare |
| `whatsapp-bridge/` | relais de diffusion vers le groupe |

## Dispositifs en place

- **Authentification** : jeton JWT en témoin `HttpOnly` · `Secure` ·
  `SameSite=strict`, mots de passe hachés avec bcrypt.
- **Limitation de débit** : slowapi sur toute route qui éprouve un secret (mot de passe, clé partagée des tâches planifiées) et sur les routes d'authentification, une limite nommée par intention.
- **Validation des entrées** : schémas Pydantic et SQLModel.
- **Origines croisées** : liste blanche explicite, jamais de joker avec témoins.
- **Injection HTML** : assainissement DOMPurify sur tout contenu rédigé par un
  utilisateur. Un contrôle d'intégration refuse un rendu qui contourne
  l'assainisseur central, y compris par une fonction locale homonyme.
- **Traversée de chemin** : nom de fichier préfixé d'un identifiant unique et
  réduit à son nom de base.
- **Injection SQL** : requêtes paramétrées par SQLAlchemy.
- **En-têtes** : HSTS, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy` et politique de sécurité du contenu, servis par Caddy et par
  le rendu serveur.
- **Conteneurs** : aucun processus applicatif ne tourne en `root`, et un contrôle
  d'intégration le vérifie.
- **Dépendances** : audit à chaque demande de fusion, côté Python et côté Node,
  avec des dérogations **nominatives** et datées — jamais un seuil relevé en bloc.

Ces dispositifs sont vérifiés par des contrôles automatiques, pas déclarés :
chaque ligne ci-dessus qui pouvait être mesurée l'est, et un dispositif dont le
contrôle ne peut pas s'exécuter rend **inconnu**, jamais conforme.

## Données personnelles

Le logiciel traite des données de résidents. Ce qui est collecté, pour combien de
temps et qui le reçoit est décrit dans la politique de confidentialité servie par
le site. Un signalement portant sur une donnée exposée suit le même chemin privé
que toute autre faille.
