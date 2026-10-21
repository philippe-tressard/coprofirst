"""La rubrique du gabarit légal sur la CONSERVATION des affaires (#2014).

Une affaire close perd ses auteurs et ses pièces jointes à l'échéance de sa
catégorie (`utils/conservation_affaires.DUREES`) ; les pièces jointes partent dans
une archive que le responsable du site garde hors ligne. La politique doit le dire
— mais **seulement quand la case est cochée** (`SERVICE_CONSERVATION`, coupée à la
livraison) : tant que rien n'est appliqué, annoncer ces durées les rendrait
fictives (`standards/14`, spec §11 arbitrage 1).

Elle n'entre donc PAS dans `DEFAULT_LEGAL` : `utils/conservation_politique` l'insère
au moment où l'administrateur coche la case. Les durées et leur fondement se lisent
dans `DUREES`, jamais recopiés ici — la phrase ne peut pas diverger de la règle.

⚠️ **Projet, à faire relire**, comme les autres rubriques : un choix d'ingénierie,
pas un avis juridique ; les fondements des durées sont à valider avec le syndic.
"""

from app.utils.conservation_affaires import TYPES


def _duree(type_conservation) -> str:
    return (
        f"<strong>{type_conservation.exercices}\xa0exercices</strong> pour "
        f"{type_conservation.libelle.lower()} ({type_conservation.fondement})"
    )


#: L'entrée de la section « Durée de conservation ».
CONSERVATION_AFFAIRES = (
    "<li>Affaires (tickets, actualités, questions)\xa0: une affaire close est conservée, avec "
    "son texte, un nombre d'<strong>exercices complets</strong> après celui de sa clôture — "
    + " ; ".join(_duree(t) for t in TYPES)
    + ". L'exercice est l'année civile, sauf réglage de la copropriété. Au-delà, une affaire est "
    "conservée <strong>sans ses auteurs ni ses pièces jointes</strong>\xa0; celles-ci sont "
    "archivées hors ligne par le responsable du site, sans limite de durée. L'archive ne porte "
    "aucun nom, mais une photo peut montrer des personnes\xa0; les textes ne sont pas réécrits. "
    "Pour faire retirer un passage ou une photo qui vous identifie, écrivez à l'adresse "
    "indiquée au point\xa01.</li>"
)

#: L'entrée devant laquelle elle s'insère — telle que le gabarit la porte.
AVANT_CONSERVATION = "<li>Tokens de rafraîchissement\xa0: 7 jours glissants.</li>"
