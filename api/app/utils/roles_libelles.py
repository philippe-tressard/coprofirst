"""Comment un RÔLE et un STATUT s'écrivent — jumeau serveur de `#lib/roles.ts`.

## 🔴 Pourquoi ce module (#801, 06/09/2026)

La table des libellés de rôles était écrite **trois fois dans le même fichier**
(`routers/admin/utilisateurs.py`, aux lignes 137, 176 et 410), et **elles avaient
divergé** :

    ajouter_role   conseil_syndical → « Membre du Conseil Syndical »
    retirer_role   conseil_syndical → « Conseil Syndical »      ← ni le même mot,
    changer_role   conseil_syndical → « Membre du Conseil Syndical »   ni la même casse

Le même rôle s'annonçait donc autrement selon qu'on l'attribuait ou qu'on le
retirait — dans deux notifications que **la même personne** reçoit. Aucune n'était
fausse ; c'est l'ensemble qui n'avait pas de logique.

Côté front, trois autres tables (`admin`, `profil`, `tableau-de-bord`) portaient
les **statuts**, avec la même dérive : « Copropriétaire Résident » dans deux
écrans, « Copropriétaire résident » dans le troisième.

Six écritures d'une même notion, trouvées en tirant le fil d'une méthode de client
sans appelant.

## Ce que ce module tranche, et pourquoi

| Clé | Retenu | Écarté |
|---|---|---|
| `conseil_syndical` | **« Conseil syndical »** | « Conseil Syndical », « Membre du Conseil Syndical » |
| `copropriétaire_résident` | **« Copropriétaire résident »** | « Copropriétaire Résident » |

L'orthographe française ne met pas de capitale au second terme d'un nom commun
composé, et c'est déjà la forme qu'employait la majorité des écrans. « Membre du
Conseil Syndical » disait la même chose en plus long, dans une phrase qui portait
déjà le mot « rôle ».

## La duplication front ⇄ API est INÉVITABLE — d'où le test

Les contextes de build sont `./api` et `./front` : rien de la racine n'entre dans
les images (mémoire `project_partage_front_api_impossible`). Le seul motif viable
est **copie + concordance exécutée**, celui de `noms.py` / `noms.ts` et de
`perimetre_label` — cette dernière ayant été corrigée d'un seul côté le
18/08/2026, et l'écart ayant mis neuf jours à se voir.

🔒 `api/tests/test_roles_libelles.py` vérifie les deux tables **et** que le
fichier front porte exactement les mêmes chaînes.

## Ce que ce module ne fait pas

Il ne décide pas **quels** rôles existent : c'est `RoleUtilisateur` et
`StatutUtilisateur` (`models/core.py`). Il ne dit que comment ils s'écrivent pour
un humain. Une clé inconnue rend la clé elle-même, jamais une chaîne vide : un
libellé manquant doit se voir, pas disparaître.
"""

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.models.roles import ROLE_OPERATEUR
from app.utils.valeurs import valeur

#  Les RÔLES — ce qu'un compte a le droit de faire.
LIBELLES_ROLE: dict[str, str] = {
    RoleUtilisateur.résident.value: "Résident",
    RoleUtilisateur.propriétaire.value: "Propriétaire",
    RoleUtilisateur.conseil_syndical.value: "Conseil syndical",
    RoleUtilisateur.admin.value: "Admin",
    RoleUtilisateur.externe.value: "Externe",
    #  Pas un rôle de la copropriété (`models/roles.ROLE_OPERATEUR`, #1750), mais
    #  un compte le porte : son badge le dit dans la liste des utilisateurs.
    ROLE_OPERATEUR: "Opérateur",
}

#  Les STATUTS — ce qu'une personne EST dans la copropriété. Distinct du rôle :
#  un copropriétaire bailleur peut être membre du conseil syndical.
LIBELLES_STATUT: dict[str, str] = {
    StatutUtilisateur.copropriétaire_résident.value: "Copropriétaire résident",
    StatutUtilisateur.copropriétaire_bailleur.value: "Copropriétaire bailleur",
    StatutUtilisateur.locataire.value: "Locataire",
    StatutUtilisateur.syndic.value: "Syndic",
    StatutUtilisateur.mandataire.value: "Mandataire",
    StatutUtilisateur.aidant.value: "Aidant (proche)",
    StatutUtilisateur.admin_technique.value: "Compte technique",
}


#  🔴 La forme COURTE, pour une signature — et c'est une notion différente, pas
#  une septième copie. Elle vivait dans `utils/reponses.py` sous le nom
#  `_STATUT_ROLE_LABELS`, sans dire pourquoi elle divergeait ; elle le dit ici.
#
#  À côté d'une réponse dans un fil, un copropriétaire s'annonce
#  « Copropriétaire », sans le « résident » ni le « bailleur » : cette précision
#  révélerait s'il habite son lot ou le loue, ce qui n'a aucun rapport avec le
#  message et regarde ses voisins de plus près qu'il ne l'a demandé.
#
#  ⚠️ Une table qui diverge sans dire pourquoi est indistinguable d'un oubli.
#  Celle-ci est délibérée, et la placer à côté de la table longue est ce qui
#  permet de le voir — les deux se lisent d'un coup d'œil.
LIBELLES_STATUT_COURT: dict[str, str] = {
    StatutUtilisateur.copropriétaire_résident.value: "Copropriétaire",
    StatutUtilisateur.copropriétaire_bailleur.value: "Copropriétaire",
    StatutUtilisateur.locataire.value: "Locataire",
    StatutUtilisateur.syndic.value: "Syndic",
    StatutUtilisateur.mandataire.value: "Mandataire",
    StatutUtilisateur.aidant.value: "Aidant",
    StatutUtilisateur.admin_technique.value: "Admin technique",
}


def libelle_statut_court(statut) -> str:
    """La signature d'un auteur dans un fil — voir `LIBELLES_STATUT_COURT`."""
    cle = str(valeur(statut))
    return LIBELLES_STATUT_COURT.get(cle, cle)


def libelle_role(role) -> str:
    """« conseil_syndical » → « Conseil syndical ».

    Accepte l'enum ou la chaîne. Une clé inconnue est rendue **telle quelle** :
    un libellé manquant doit se voir dans l'interface, pas s'effacer.
    """
    cle = str(valeur(role))
    return LIBELLES_ROLE.get(cle, cle)


def libelle_statut(statut) -> str:
    """« copropriétaire_résident » → « Copropriétaire résident »."""
    cle = str(valeur(statut))
    return LIBELLES_STATUT.get(cle, cle)
