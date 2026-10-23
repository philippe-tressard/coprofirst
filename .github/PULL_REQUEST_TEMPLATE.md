<!-- Un lot = une notion = une demande de fusion = une montée de version. -->

## Ce que ce lot apporte

<!-- En une phrase par changement, du point de vue de qui s'en sert. -->

Tickets : closes #

## Ce qui refuse la récidive

<!-- Le test ou le contrôle ajouté, et son branchement dans l'intégration
     continue. Le CAS ZÉRO est-il prouvé — le contrôle refuse-t-il bien l'état
     fautif d'avant ? Un contrôle vert peut mentir : motif trop étroit, portée
     qui n'inclut pas le bon répertoire, sortie vide lue comme un succès. -->

- [ ] garde-fou ajouté, **branché**, et cas zéro vérifié
- [ ] ou bien : rien à garder, et la raison est écrite ci-dessus

## Documentation — point 0e du pré-contrôle

Le manuel et le `README` sont de **même rang**. Un lot qui ne touche qu'un seul
des deux le dit, et pourquoi.

- [ ] `docs/manuel-utilisateur.html` — comment on s'en sert (écran, libellé,
      geste, parcours) ; il ne porte ni version ni date à bumper
- [ ] `front/static/manuel-utilisateur.html` resynchronisé
- [ ] `README.md` — ce que le produit est (module, écran de premier niveau,
      capacité ajoutée, retirée ou renommée)
- [ ] la consigne, la skill ou la mémoire qui enseigne le motif touché

> ⚠️ Le manuel est versionné en CRLF : jamais de `sed -i` dessus, et vérifier
> `git diff --stat` — un diff disproportionné est un accident d'encodage.

## Avant de demander la fusion

- [ ] `bash scripts/poste/rejouer-ci.sh` — **tous** les travaux, pas un seul
- [ ] `bash scripts/poste/precheck-mep.sh` — chaque point s'exécute ; un point
      qui ne peut pas s'exécuter rend **inconnu**, jamais conforme
- [ ] montée de version dans `front/package.json`, en commit dédié et **en
      dernier**
- [ ] aucun secret ni donnée personnelle dans le diff — l'historique conserve ce
      qu'on y met
