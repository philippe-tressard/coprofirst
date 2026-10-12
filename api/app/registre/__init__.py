"""Le REGISTRE DES INSTALLATIONS — tenu par la référence, dans sa base `plateforme` (§4.11).

Spec `specs/architecture/multi-coproprietes.md` §4.11, décisions D17 à D24 ; lots
R0 (#1876, conditions) et R1 (#1877, base et contrat de données). Éteint partout
ailleurs que chez la référence dont le registre est déclaré (`base.registre_actif`).

| Module | Ce qu'il porte |
|---|---|
| `contrat` | ce qu'une installation envoie à la référence — la seule écriture |
| `conditions` | le contrat d'engagements réciproques, une version par fichier |
| `signature` | les signatures Ed25519 |
| `modeles` | les tables de la base `plateforme`, hors des métadonnées de la résidence |
| `base` | la base `plateforme` et l'interrupteur du registre |
| `migrer` | ses migrations (`alembic_plateforme/`) et l'inscription de la référence |
| `routeur` | le point d'inscription |
"""
