"""L'INSCRIPTION de cette installation au registre de la référence, et son BAIL (R2 #1878).

Spec `specs/architecture/multi-coproprietes.md` §4.11. Le côté INSTALLATION de ce
que `app/registre/` tient côté référence ; les deux parlent le même contrat
(`registre/contrat.py`).

🔴 **Mode constat** : l'état de l'installation — limitée, active, suspendue — est
CALCULÉ et AFFICHÉ (Administration › Maintenance), **jamais appliqué**. Le plafond
d'utilisateurs, la lecture seule et les services refusés attendent R6 (#1882), et
plusieurs semaines de constat sans faux positif.

| Module | Ce qu'il porte |
|---|---|
| `cles` | les clés publiques de la référence, par époque — dans l'image |
| `depot` | la clé privée et l'état d'inscription de l'installation (volume `app_data`) |
| `constat` | PUR : ce que l'état et le bail valent (limitée / active / suspendue) |
| `client` | les appels à la référence — inscription, bail — et la tâche de la nuit |
"""
