"""
Règles de visibilité centralisées — source de vérité unique.

⚠️ **La règle reste unique** : elle a seulement cessé de tenir dans un seul fichier
(#547, 20/08/2026). Le paquet expose la même surface qu'avant — `from
app.utils.visibility import …` ne change pas d'une ligne pour ses seize importateurs.

Le découpage suit une couture réelle, pas la ligne où le compteur a dépassé :
`socle` porte les deux primitives que tout le reste compose (géographie et public
visé), `objets` les règles par entité, `documents` l'algorithme d'accès en cinq
étapes — le seul qui interroge la base, et le seul adossé à un modèle de profil
d'accès. Chaque fragment renvoie ici au lieu de redire ce paragraphe (#1564).

Toute logique de filtrage par rôle/périmètre/profil doit passer par ce module.
Ne jamais dupliquer ces règles dans les routers.

Règles métier appliquées :
  - CS et Admin voient toujours tout (pas de filtre).
  - Syndic : lecture seule sur tout (pas filtré ici — géré par les dépendances auth).
  - Mandataire : non géré ici (filtrage lot dans bailleur.py — périmètre trop spécifique).
  - Périmètre géographique : un nœud à portée globale (ou dont un ancêtre l'est) est
      visible par tous les résidents ; sinon, visible si le bâtiment du nœud — ou de
      son plus proche ancêtre qui en porte un — est celui de l'utilisateur.
      La liste des périmètres transverses n'est plus écrite ici : elle était en trois
      exemplaires (ici, `flux/evenements.py`, et le tableau de bord côté front) et
      c'est désormais le drapeau `portee_globale` de la table `perimetre`.
  - public_cible : résidents = tous ; copropriétaires = statut copropriétaire_* ;
      copropriétaires_occupants = copropriétaire_résident uniquement ; bailleurs =
      copropriétaire_bailleur uniquement ; locataires = statut locataire uniquement ;
      conseil_syndical = CS/admin uniquement.
      Si public_cible contient une valeur non reconnue ou non correspondante → non visible.
  - AG (événements) : visible uniquement par propriétaires, CS et admins.
  - Sondages : MÊME règle que les publications — perimetre_cible + public_cible.
      Ils ciblaient par `batiments_ids` + `profils_autorises`, seuls de tout le
      site : une deuxième règle d'accès à maintenir, et un écran qui ne savait
      cibler ni le parking, ni l'AFUL, ni un espace. Unifié le 16/08/2026.
"""

#  🔴 La surface publique NE BOUGE PAS. Seize modules et huit tests écrivent
#  `from app.utils.visibility import …` ; un découpage qui casse ses importateurs
#  n'est pas un découpage, c'est un déménagement à leurs frais.
from .socle import (
    CODES_PUBLIC_CIBLE,
    LIBELLES_PUBLIC_CIBLE,
    cible_visible,
    concerne,
    perimetre_visible,
    public_cible_visible,
    reserve_au_conseil,
)
from .objets import (
    adresse_de_contact,
    annonce_visible,
    can_see_ag,
    contenu_hors_du_groupe,
    sondage_hors_du_groupe,
    evenement_visible,
    hors_du_hall,
    idee_visible,
    actualite_visible,
    resultats_sondage_visibles,
    sondage_accessible,
    sondage_clos,
    reservee_au_conseil,
    ticket_visible,
)
from .documents import (
    CATEGORIES_ADMIN_SEUL,
    document_visible,
    peut_ecrire_dans,
    profil_admet,
    reserve_a_l_admin,
)
from .trace_droits import trace_droits, trace_lecture_par_defaut
from .fichiers import (
    PORTEURS,
    TOUTE_SESSION,
    Porteur,
    exiger_fichier_lisible,
    fichier_lisible,
    porteurs_du_fichier,
)
from .defauts_affaire import (
    CONCERNE,
    DEFAUT_INCONNU,
    DEFAUT_PAR_CATEGORIE,
    destinataires_par_defaut,
    lus_dans_toute_la_residence,
)

#  ⚠️ Cette liste ne se tient pas à la main : `test_visibilite_surface.py` la
#  compare aux noms publics RÉELLEMENT définis par les trois fragments, et échoue
#  si l'un manque. Le premier jet en avait oublié un — `CODES_PUBLIC_CIBLE`, une
#  constante et non une fonction — et la suite de tests ne démarrait plus.
__all__ = [
    "perimetre_visible",
    #  « Ce contenu me concerne-t-il ? » — le cœur de `perimetre_visible`, lu
    #  aussi par la pastille « Ce qui me concerne » des listes (#2215).
    "concerne",
    #  La règle des deux axes (périmètre puis public cible), composée par la
    #  publication, le sondage, la petite annonce et l'idée. Ce n'est pas une
    #  primitive de plus : c'est leur écriture UNIQUE, depuis le 06/09 (#782).
    "cible_visible",
    "CODES_PUBLIC_CIBLE",
    "LIBELLES_PUBLIC_CIBLE",
    "public_cible_visible",
    "reserve_au_conseil",
    "annonce_visible",
    "adresse_de_contact",
    "idee_visible",
    "actualite_visible",
    "sondage_clos",
    "resultats_sondage_visibles",
    "sondage_accessible",
    "evenement_visible",
    "can_see_ag",
    "ticket_visible",
    "CONCERNE",
    "DEFAUT_INCONNU",
    "DEFAUT_PAR_CATEGORIE",
    "destinataires_par_defaut",
    "lus_dans_toute_la_residence",
    "reservee_au_conseil",
    "hors_du_hall",
    "contenu_hors_du_groupe",
    "sondage_hors_du_groupe",
    "CATEGORIES_ADMIN_SEUL",
    "document_visible",
    "peut_ecrire_dans",
    "profil_admet",
    "reserve_a_l_admin",
    "trace_droits",
    #  Le droit de lire un fichier servi en direct : celui de son porteur (#2154).
    "PORTEURS",
    "TOUTE_SESSION",
    "Porteur",
    "exiger_fichier_lisible",
    "fichier_lisible",
    "porteurs_du_fichier",
    "trace_lecture_par_defaut",
]
