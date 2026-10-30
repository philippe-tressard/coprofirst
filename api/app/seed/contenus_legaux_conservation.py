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


#: Comment la phrase nomme chaque type — le nombre d'années, lui, vient de `TYPES`.
_EN_CLAIR = {
    "breves": "les actualités et questions",
    "entretien": "les pannes et l’entretien",
    "travaux": "les travaux et sinistres",
}


def _duree(type_conservation) -> str:
    return f"{type_conservation.exercices} ans pour {_EN_CLAIR[type_conservation.code]}"


#: L'entrée de la section « Durée de conservation » — en langage courant, la rigueur
#: (exercices, fondements) se lit dans `DUREES` et à l'écran d'administration.
CONSERVATION_AFFAIRES = (
    "<li><strong>Affaires (pannes, travaux, questions…)</strong>\xa0: quand une affaire est "
    "terminée, nous la gardons un certain temps, puis nous retirons les photos et documents "
    "joints ainsi que le nom des personnes concernées. Le texte de l’affaire reste. Les durées, "
    "comptées en années civiles complètes après l’année de clôture\xa0: "
    + ", ".join(_duree(t) for t in sorted(TYPES, key=lambda t: t.exercices))
    + ". Les photos et documents retirés sont mis de côté hors ligne par le responsable du "
    "site. Pour faire retirer un passage ou une photo qui vous identifie, écrivez à l’adresse "
    "de contact du site.</li>"
)

#: L'entrée devant laquelle elle s'insère — telle que le gabarit la porte.
AVANT_CONSERVATION = "<li>Tokens de rafraîchissement\xa0: 7 jours glissants.</li>"
