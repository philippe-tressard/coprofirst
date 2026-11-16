"""L'INSCRIPTION de cette installation au registre de la référence, et son BAIL (R2 #1878).

Spec `specs/architecture/multi-coproprietes.md` §4.11. Le côté INSTALLATION de ce
que `app/registre/` tient côté référence ; les deux parlent le même contrat
(`registre/contrat.py`).

🔴 **Ce qui s'applique** (R6 #1882, 16/11/2026) : l'état de l'installation — limitée,
active, suspendue — se CALCULE (`constat`) et s'AFFICHE (Administration › Installation) ;
à une réplique, il S'APPLIQUE (`regime`) : services du bail, plafond de comptes actifs
(`plafond`), lecture seule (`suspension`). `REGISTRE_CONSTAT=true` ramène au constat.

| Module | Ce qu'il porte |
|---|---|
| `cles` | les clés publiques de la référence, par époque — dans l'image |
| `depot` | la clé privée et l'état d'inscription de l'installation (volume `app_data`) |
| `constat` | PUR : ce que l'état et le bail valent (limitée / active / suspendue) |
| `client` | les appels à la référence — inscription, bail — et la tâche de la nuit |
| `regime` | ce qui S'APPLIQUE ici — une réplique seulement, sauf retour au constat |
| `plafond` | le mode limité : 5 comptes actifs au plus, à l'écriture en base |
| `suspension` | la lecture seule : la garde des écritures, et ce qu'elle laisse ouvert |
"""
