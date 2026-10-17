"""L'installation COMMUNE à plusieurs copropriétés (#1894, spec multi-copropriétés §4.1 bis).

Un seul code, deux façons de l'héberger (D27) : une copropriété a **sa propre
installation**, comme 5Hostachy — rien de ce paquet n'y sert —, ou elle est
**hébergée avec d'autres**. L'installation commune se déclare par un fichier
(`COPROPRIETES_FICHIER`, arbitrage du 17/10/2026) :

- `declaration` — le registre des copropriétés de l'installation (§4.2) : lu,
  validé, et remis au contexte (`app/contexte.registre`), qui résout chaque requête ;
- `alias` — l'alias `code-postal-nom` d'une copropriété, dont se dérive son
  adresse `<alias>.<hôte commun>` ;
- `routeur` — l'hôte commun, qui ne fait que REDIRIGER : l'aiguillage
  (code postal + nom) et la redirection des anciens alias.

Fichier absent : l'installation sert une seule copropriété, celle de sa
configuration, exactement comme avant.
"""
