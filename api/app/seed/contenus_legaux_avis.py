"""La rubrique du gabarit légal sur les AVIS sur l'application (#2075).

Un avis peut sortir de l'application : avec l'accord exprès de son auteur, il
paraît sur le site de présentation du logiciel. Le texte doit le dire — 🔒
`tests/test_politique_confidentialite_couvre_le_code.py` l'exige tant que le
modèle porte `consentement_publication`.

Écrite une fois : le gabarit (`contenus_legaux.DEFAULT_LEGAL`) et la migration
0300, qui l'insère dans le texte servi, la lisent ici.

⚠️ **Projet, à faire relire**, comme les autres rubriques (`standards/14`) : un
choix d'ingénierie, pas un avis juridique. Base retenue : le consentement
(art. 6-1-a) pour la publication — c'est lui que l'écran recueille.

Séparé de `contenus_legaux.py`, qui atteint 500 lignes (modularité, rang 1).
"""

#: L'entrée de la liste « Finalités et bases légales ».
AVIS_SITE_PRESENTATION = (
    "<li><strong>Avis sur l'application</strong> — un avis (note, titre, texte) se lit de son "
    "auteur et du conseil syndical. S'il compte au moins 4 étoiles et que son auteur l'accepte "
    "<strong>expressément</strong> — Oui ou Non, sans réponse par défaut —, il se lit aussi "
    "de tous les comptes de la copropriété et peut paraître sur le <strong>site de "
    "présentation du logiciel</strong>, une fois retenu par le gestionnaire du site, avec le "
    "prénom, l'initiale du nom et le rôle de son auteur, et rien d'autre — base : "
    "consentement (art. 6-1-a), qui se retire à tout moment depuis l'onglet Avis. L'avis "
    "part avec le compte de son auteur.</li>"
)

#: L'entrée après laquelle il s'insère — telle que le gabarit la porte.
APRES_EMAILS_TRANSACTIONNELS = (
    "<li><strong>E-mails transactionnels</strong> — base\xa0: intérêt légitime / consentement.</li>"
)
