"""Types de diagnostics réglementaires et leur fondement légal.

Chaque entrée cite l’article qui la rend obligatoire et sa périodicité. Ce sont
des références de droit, pas du texte d’interface : les modifier suppose de
vérifier la source — cf. `standards/14-conformite-juridique.md`.
"""

DIAGNOSTICS = [
    {
        "code": "dpe",
        "nom": "DPE collectif",
        "texte_legislatif": "Loi Grenelle II (2010) — obligatoire pour les copropriétés de plus de 50 lots avec équipements collectifs de chauffage ou de refroidissement. Valable 10 ans sauf réalisation de travaux importants.",
        "frequence": "10 ans",
        "ordre": 1,
    },
    {
        "code": "amiante",
        "nom": "Diagnostic amiante (DAPP)",
        "texte_legislatif": "Loi du 02/08/1997 et Décret n°96-97 — obligatoire pour tout immeuble bâti avant le 01/07/1997. Permanent si aucune trace d'amiante détectée. Révision tous les 3 ans ou après travaux si présence constatée.",
        "frequence": "Permanent (révision si amiante détecté)",
        "ordre": 2,
    },
    {
        "code": "plomb",
        "nom": "Diagnostic plomb — CREP parties communes",
        "texte_legislatif": "Décret n°99-483 du 09/06/1999 — obligatoire pour les parties communes d'immeubles construits avant le 01/01/1949. Permanent si aucun revêtement contenant du plomb au-dessus du seuil. Révision obligatoire si dépassement du seuil.",
        "frequence": "Permanent (révision si plomb > seuil)",
        "ordre": 3,
    },
    {
        "code": "electricite",
        "nom": "Diagnostic électricité — parties communes",
        "texte_legislatif": "Décret n°2016-1092 du 08/08/2016 — contrôle des installations électriques des parties communes d'immeubles de plus de 15 ans. Réalisé par un diagnostiqueur certifié.",
        "frequence": "3 ans",
        "ordre": 4,
    },
    {
        "code": "gaz",
        "nom": "Diagnostic gaz — parties communes",
        "texte_legislatif": "Décret n°2016-1250 du 22/09/2016 — contrôle des installations de gaz collectif dans les parties communes. Obligatoire si chaudière collective ou réseau gaz de plus de 15 ans.",
        "frequence": "3 ans",
        "ordre": 5,
    },
    {
        "code": "ascenseur",
        "nom": "CTQ ascenseurs",
        "texte_legislatif": "Décret n°2004-964 du 09/09/2004 — contrôle technique quinquennal obligatoire pour tout ascenseur, réalisé par un organisme agréé indépendant de l'entreprise de maintenance. À compléter par une vérification annuelle.",
        "frequence": "5 ans",
        "ordre": 6,
    },
    {
        "code": "pppt",
        "nom": "Plan Pluriannuel de Travaux (PPPT)",
        "texte_legislatif": "Loi Climat et Résilience du 22/08/2021 (art. 90) — obligatoire pour les copropriétés de plus de 15 ans. Réalisé par un professionnel qualifié, soumis au vote de l'AG et renouvelé tous les 10 ans.",
        "frequence": "10 ans",
        "ordre": 7,
    },
    {
        "code": "audit_energetique",
        "nom": "Audit énergétique global",
        "texte_legislatif": "Loi Énergie-Climat du 08/11/2019 — obligatoire préalablement à la réalisation du PPPT pour les copropriétés classées D, E, F ou G au DPE collectif. Permet d'identifier les travaux prioritaires de rénovation.",
        "frequence": "Selon DPE (avant PPPT)",
        "ordre": 8,
    },
    {
        "code": "erp",
        "nom": "État des Risques et Pollutions (ERP)",
        "texte_legislatif": "Loi Alur (2014) et Art. R125-26 CCH — obligatoire lors de toute vente ou mise en location d'un bien situé dans une zone à risques délimitée par arrêté préfectoral. Valable 6 mois. Document à annexer à toute promesse ou bail.",
        "frequence": "6 mois (lors de mutations)",
        "ordre": 9,
    },
    {
        "code": "termites",
        "nom": "Diagnostic termites",
        "texte_legislatif": "Code de la construction L271-6 — obligatoire dans les zones géographiques délimitées par arrêté préfectoral. Valable 6 mois pour les transactions immobilières. À renouveler à chaque vente ou bail dans les zones concernées.",
        "frequence": "6 mois (dans les zones à risque)",
        "ordre": 10,
    },
]
