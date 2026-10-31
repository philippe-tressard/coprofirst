import json
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, field_validator

from app.models.core import StatutTicket, StatutUtilisateur, RoleUtilisateur
from app.models.tickets import CategorieTicket
from app.utils.perimetres import perimetre_defaut_liste


#  `liste_depuis_json` et `ListeJson` vivent dans `schemas_communs.py` depuis le
#  19/08/2026 : `schemas_tickets` en a besoin et ne peut pas importer ce
#  fichier-ci, qui l’importe. Ré-exportés, donc rien à changer ailleurs.
from app.schemas_communs import (  # noqa: F401
    AffaireLieeLue,
    ChampsIntervenant,
    ChoixConciliation,
    ContratDeLAffaire,
    ListeJson as ListeJson,
    liste_depuis_json as liste_depuis_json,
)

#  Les trois champs « Saisi pour » sont HÉRITÉS, plus recopiés : la notion, ses
#  deux règles subtiles et son mixin vivent dans `utils/saisi_pour` depuis
#  qu'elle s'applique aussi aux actualités et aux événements (15/09/2026).
from app.utils.assiste_ia import AssisteIACorrection, AssisteIAEntree, AssisteIASortie
from app.utils.saisi_pour import SaisiPourEntree, SaisiPourSortie

#  Ne vivent ici que les schémas PARTAGÉS par plusieurs routeurs. Un schéma propre
#  à un seul routeur est déclaré à côté de lui (`<routeur>_schemas.py`) — #1566.


class UserRead(BaseModel):
    id: int
    nom: str
    prenom: str
    email: str
    telephone: Optional[str] = None
    societe: Optional[str] = None
    fonction: Optional[str] = None
    statut: StatutUtilisateur
    role: RoleUtilisateur
    roles: list[str] = []
    actif: bool
    email_verifie: bool = False
    onboarding_complete: bool
    onboarding_etape: int
    photo_url: Optional[str] = None
    preferences_notifications: str
    #  Préférence d'AFFICHAGE, jamais un droit — cf. models/core.py.
    restreindre_a_mes_batiments: bool = False
    decor_fetes: bool = True
    demarche_arrivant: Optional[str] = None
    batiment_id: Optional[int] = None
    batiment_nom: Optional[str] = None  # ex. "Bât. A"
    #  L'étage où la personne HABITE. Sans lui, le profil ne pourrait pas
    #  afficher la valeur qu'il vient d'enregistrer.
    etage: Optional[int] = None
    nom_proprietaire: Optional[str] = None
    nom_aide: Optional[str] = None
    prenom_aide: Optional[str] = None
    opt_out_telemetrie: bool = False
    communaute_interdit: bool = False
    communaute_ban_count: int = 0
    communaute_ban_jusqu_au: Optional[datetime] = None
    #  La CONCLUSION de la règle d'accès, calculée par `app/utils/communaute.py`.
    #  Le front l'affiche telle quelle au lieu de refaire le raisonnement : il en
    #  portait sa propre copie, avec un troisième libellé (29/08/2026).
    communaute_motif_refus: Optional[str] = None
    last_seen_actualites: Optional[datetime] = None
    delegations_aidant: list[dict] = []  # délégations actives où l'utilisateur est aidant
    cree_le: datetime
    derniere_connexion: Optional[datetime] = None
    #  L'avertissement avant purge pour inactivité (#1580) : l'écran des
    #  utilisateurs le montre, la reconnexion l'efface.
    purge_avertie_le: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_roles(
        cls, u, batiment_nom: Optional[str] = None, delegations_aidant: list[dict] | None = None
    ) -> "UserRead":
        from app.auth.operateur import roles_effectifs
        from app.utils.communaute import motif_de_refus

        data = cls.model_validate(u)
        #  L'Opérateur jugé selon l'instance : l'écran n'offre que ce que la route admet.
        data.roles = roles_effectifs(u)
        data.communaute_motif_refus = motif_de_refus(u)
        if batiment_nom is not None:
            data.batiment_nom = batiment_nom
        if delegations_aidant is not None:
            data.delegations_aidant = delegations_aidant
        return data


class TicketCreate(SaisiPourEntree, AssisteIAEntree, ChampsIntervenant):
    #  Section « Affaires liées » (#1342) : les affaires à lier. En création et
    #  en correction, la liste REMPLACE les liens que l'auteur voit ; en Suite,
    #  elle les complète (`utils/affaires_liees`). Absente : rien ne change.
    affaires_liees: Optional[List[int]] = None
    #  Section « Quand » (#1092) : quand ça se passe — le calendrier.
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    titre: str
    description: str
    #  🔴 AUCUN défaut, et c'est le pendant serveur de la décision d'écran du
    #  21/09/2026 : « Panne » n'est plus présélectionnée dans le formulaire.
    #  Laisser `= "panne"` ici aurait rendu le retrait purement décoratif — un
    #  corps sans catégorie serait reparti en panne, silencieusement, et c'est
    #  exactement ce qu'on vient d'interdire à l'écran.
    #
    #  ⚠️ Typée par l'énumération, contrairement au `statut` deux champs plus
    #  bas — lui garde `str` parce que le routeur lui applique une liste
    #  blanche dérivée. La catégorie n'en avait AUCUNE : `body.categorie`
    #  allait jusqu'à `Ticket(categorie=…)`, dont la validation est désactivée
    #  (SQLModel `table=True`). Une chaîne inventée entrait donc en base.
    #
    #  Aucun client existant n'est affecté : le formulaire envoyait déjà la
    #  valeur, présélectionnée ou non — y compris un onglet PWA resté ouvert.
    categorie: CategorieTicket
    epingle: bool = False
    #  🔴 DÉCLARÉES depuis le 23/09/2026 (#1171) : le formulaire les envoyait,
    #  Pydantic les ignorait — « 🛡️ réservée au conseil » cochée à la création
    #  laissait l'affaire lisible de tout son périmètre. `None` : le corps n'en
    #  dit rien. Le droit est dans `appliquer_options`, pas ici.
    urgente: Optional[bool] = None
    confidentiel: Optional[bool] = None
    #  Un ACTE, pas une colonne : produire l'affiche de hall d'une actualité (#1091).
    annonce_hall: Optional[bool] = None
    #  🔴 `None` = « le corps n'en dit rien », et le serveur pose alors le défaut
    #  de la CATÉGORIE (`kanban_tickets.suivi_par_defaut`). Un `bool = False`
    #  aurait rendu un formulaire silencieux indiscernable d'un décochage
    #  délibéré — et « Étude & travaux » n'entrerait jamais au tableau.
    suivi_kanban: Optional[bool] = None
    #  🔁 La case « Activer le suivi » d'une actualité (10/10/2026) — du conseil seul, comme
    #  le kanban ; elle pose `suivi_actualite` (`utils/suivi_actualite`).
    suivre_actualite: Optional[bool] = None
    #  …et son ÉTAT, choisi dès l'ouverture : Ouvert, Résolu ou Annulé (10/10/2026).
    suivi_actualite: Optional[str] = None
    #  Le workflow du ticket est saisissable DÈS la création (16/08/2026) : il
    #  ne se changeait qu'après coup, depuis la carte, alors qu'un membre du CS
    #  qui saisit un ticket déjà traité connaît son étape. Défaut inchangé —
    #  « ouvert » — donc aucun appelant existant n'est affecté.
    #  Reste `str` — délibérément, et c'est le seul des trois : le routeur y
    #  applique une liste blanche **dérivée de l'énumération** (aucune liste
    #  écrite à la main, donc rien qui puisse en diverger) et retombe sur
    #  « ouvert » au lieu de refuser. Un type refuserait la création entière
    #  pour un champ accessoire.
    statut: Optional[str] = None
    lot_id: Optional[int] = None
    batiment_id: Optional[int] = None
    perimetre_cible: Optional[List[str]] = None
    #  Ce que porte une affaire de catégorie « Actualité » (#1091) — vide : tous.
    public_cible: Optional[List[str]] = None
    reserve_perimetre: bool = False
    destinataire_syndic: bool = False
    destinataire_cs: bool = False
    envoyer_auteur: bool = False
    #  Troisième canal, aligné sur les actualités, le calendrier et les sondages.
    #  Il manquait ici et NULLE PART ailleurs : un ticket ne pouvait être partagé
    #  sur le groupe qu'après coup, via un commentaire (signalé le 08/08/2026).
    #  Comme `destinataire_*`, c'est une intention d'envoi et non un état du
    #  ticket : rien n'est stocké sur le modèle.
    partager_whatsapp: bool = False
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement
    # Pièces jointes déjà téléversées via POST /uploads/fichier — photos et
    # documents. Les fournir DÈS la création, et non après, est ce qui permet à
    # l'e-mail syndic/CS de partir avec : il est construit dans la foulée.
    # Filtrées par `photos_internes` côté routeur : le client ne choisit pas
    # quelle URL est jointe, il ne peut que désigner nos propres fichiers.
    photos_urls: List[str] = []
    fichiers_urls: List[str] = []
    #  Intervenant, récurrence, équipement : `ChampsIntervenant` — conseil seul.


class TicketRead(SaisiPourSortie, AssisteIASortie, ChampsIntervenant):
    id: int
    numero: str
    titre: str
    description: str
    categorie: str
    statut: str
    priorite: str
    auteur_id: Optional[int] = None  # « Ancien résident » quand le compte est supprimé (#1688)
    auteur_nom: Optional[str] = None
    auteur_batiment_nom: Optional[str] = None
    lot_id: Optional[int] = None
    batiment_id: Optional[int] = None
    perimetre_cible: Optional[List[str]] = None
    #: « Cette affaire me concerne-t-elle ? » pour QUI la lit (#2215) — la règle de
    #: l'accès (`visibility.concerne`), pas une seconde : la pastille « Ce qui me
    #: concerne » filtre avec, sans rien recomposer. `None` sans lecteur.
    me_concerne: Optional[bool] = None
    photos_urls: Optional[ListeJson] = None
    fichiers_urls: ListeJson = []
    #  Ce que la carte REPLIÉE montre en vignette — dérivé, jamais saisi. Le
    #  pourquoi et la règle du repli vivent avec le calcul, dans
    #  `routers/tickets/commun.py::apercu_pieces` (#464) : les répéter ici en
    #  ferait deux écritures libres de diverger.
    apercu_pieces: ListeJson = []
    #  Les affaires liées que CE lecteur peut lire (#1342) — dérivé, jamais saisi.
    affaires_liees: List[AffaireLieeLue] = []
    #  🔀 L'affaire qui l'a absorbée (#1704) — rendue seulement si CE lecteur la lit.
    fusionnee_dans: Optional[AffaireLieeLue] = None
    #  …et le FAIT, pour tous : son suivi est clos, l'écran n'offre plus de Suite.
    fusionnee: bool = False
    destinataire_syndic: bool = False
    destinataire_cs: bool = False
    envoyer_auteur: bool = False
    #  `proprietaire_nom` est HÉRITÉ de `SaisiPourSortie` depuis le 21/09/2026
    #  (#1104) : il n'était déclaré qu'ici, si bien que l'actualité et
    #  l'événement n'avaient aucun moyen d'afficher autre chose que leur
    #  rédacteur. Les trois schémas héritent de la même classe — c'est ce qui
    #  rend la règle vraie partout d'une seule ligne.
    relance_count: int = 0
    #: Règle du SITE (`utils/archivage`, #515) — l'écran en appliquait une autre.
    archivee: bool = False
    #: ✨ Une synthèse VALIDÉE l'accompagne (#1643) : la carte repliée le dit.
    #: Validée seulement — lue alors par qui lit l'affaire (`synthese_affaire.lisible`).
    synthese_validee: bool = False
    confidentiel: bool = False
    #  📌 Épinglé — RELU, contrairement à `partager_whatsapp` juste en dessous :
    #  c'est un ÉTAT du ticket, pas un acte. L'écran doit pouvoir le reprendre.
    epingle: bool = False
    #  Même raison : un état, donc relu. La case doit refléter ce qui est.
    suivi_kanban: bool = False
    #  🔁 Le suivi d'une actualité : `None` (sans suivi), « ouvert », « résolu »
    #  ou « annulé » — un état, donc relu (`utils/suivi_actualite`).
    suivi_actualite: Optional[str] = None
    #  🗄️ Conservée (#2014) : le jour où, échue, l'affaire a perdu ses pièces jointes
    #  (archivées hors ligne) et ses auteurs. L'écran le dit en bandeau.
    conservee_le: Optional[datetime] = None
    #  Section « Quand » (#1092) — RELUE depuis le 23/09/2026 : acceptée en
    #  entrée depuis la 0200, elle n'était jamais rendue. Le calendrier et le
    #  filtre « Événement » n'avaient rien à lire, et une édition l'effaçait.
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    #  Une affaire de catégorie « Actualité » (#1091). `natures` est DÉRIVÉE
    #  (`utils/nature_affaire.natures`) : l'écran filtre dessus, sans redériver.
    public_cible: Optional[List[str]] = None
    reserve_perimetre: bool = False
    archive_manuel: bool = False
    natures: List[str] = []
    #  La date où une actualité cesse d'être utile — DÉRIVÉE, jamais saisie
    #  (#1093, `utils/archivage.perime_le`). `None` pour une affaire suivie :
    #  elle ne périme pas, elle se clôt.
    perime_le: Optional[date] = None
    prestataire_nom: Optional[str] = None  # dérivé, pour la fiche et la carte
    #  Le contrat qui cadre l'intervention (#1445), dérivé — le rythme pour
    #  tous, le libellé et le numéro pour le conseil seul (`contrat_de_l_affaire`).
    contrat: Optional[ContratDeLAffaire] = None
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None

    @field_validator("public_cible", mode="before")
    @classmethod
    def parse_public_ticket(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v) or None
            except Exception:
                return None
        return v

    @field_validator("perimetre_cible", mode="before")
    @classmethod
    def parse_perimetre_ticket(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return perimetre_defaut_liste()
        return v

    class Config:
        from_attributes = True


class TicketUpdate(SaisiPourEntree, AssisteIACorrection, ChampsIntervenant):
    #  Section « Affaires liées » (#1342) : les affaires à lier. En création et
    #  en correction, la liste REMPLACE les liens que l'auteur voit ; en Suite,
    #  elle les complète (`utils/affaires_liees`). Absente : rien ne change.
    affaires_liees: Optional[List[int]] = None
    #  Section « Quand » (#1092) : quand ça se passe — le calendrier.
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    #  ⚠️ `Optional[str]` jusqu'au 17/08/2026, et c'était la **seule** barrière :
    #  `Ticket` est un modèle `table=True`, donc SQLModel ne valide rien à
    #  l'affectation. `PATCH /tickets/{id}` écrivait en base la chaîne qu'on lui
    #  donnait, quelle qu'elle soit. #415 décrivait ce chemin comme « validé par
    #  le type » : il ne l'est que depuis cette ligne.
    statut: Optional[StatutTicket] = None
    #  🔀 Les affaires liées à absorber quand ce `statut` clôt l'affaire (#1704).
    fusionner: Optional[List[int]] = None
    #  Les fusions refusées pour fuite de lecture que le conseil a conciliées.
    conciliations: Optional[List[ChoixConciliation]] = None
    priorite: Optional[str] = None
    titre: Optional[str] = None
    description: Optional[str] = None
    categorie: Optional[str] = None
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    reserve_perimetre: Optional[bool] = None
    archive_manuel: Optional[bool] = None
    lot_id: Optional[int] = None
    batiment_id: Optional[int] = None
    destinataire_syndic: Optional[bool] = None
    destinataire_cs: Optional[bool] = None
    confidentiel: Optional[bool] = None
    epingle: Optional[bool] = None
    urgente: Optional[bool] = None  # #1171 : ignorée en silence jusqu'au 23/09/2026
    annonce_hall: Optional[bool] = None  # un acte : l'affiche d'une actualité (#1091)
    suivi_kanban: Optional[bool] = None
    suivre_actualite: Optional[bool] = None  # la case du conseil (10/10/2026)
    suivi_actualite: Optional[str] = None  # …et l'état qu'elle corrige
    #  ⚠️ N'est PAS un champ du ticket : `Ticket` n'a pas cette colonne, à la
    #  différence de `Publication`. C'est un ACTE — « publie ce ticket sur le
    #  groupe, maintenant » — et il ne se relit donc pas. La case repart décochée
    #  à chaque ouverture du formulaire, et c'est juste : il n'y a pas d'état à
    #  restaurer, seulement un envoi à demander. Trouvé le 18/08/2026 en écrivant
    #  la réouverture de la Diffusion — le test `test_correction_pas_transition`
    #  a refusé l'affectation d'un attribut qui n'existe pas.
    partager_whatsapp: Optional[bool] = None
    # Sert à retirer ou réordonner des pièces jointes déjà téléversées : l'ajout
    # passe par POST /uploads/fichier, seul endroit qui valide le type MIME.
    fichiers_urls: Optional[List[str]] = None
    #  ✅ Ouvert à l'édition le 18/08/2026 : c'était la dette `api` que la
    #  déclaration du cadre citait (#431, motif de DETTE jamais de conception).
    #  Les photos se corrigent désormais comme les documents — même règle, même
    #  endpoint de téléversement, et une liste vide efface sans ambiguïté.
    photos_urls: Optional[List[str]] = None


#  Les schémas du fil d’un ticket vivent dans `schemas_tickets.py` depuis le
#  19/08/2026 (modularité, rang 1). Ré-exportés : les routeurs appelants ne
#  changent pas d’import.
from app.schemas_tickets import (  # noqa: E402,F401
    TicketEvolutionCreate as TicketEvolutionCreate,
    TicketEvolutionRead as TicketEvolutionRead,
    TicketEvolutionUpdate as TicketEvolutionUpdate,
)


#  Les schémas des PUBLICATIONS (`schemas_publications.py`) ont été retirés le
#  23/09/2026 avec leur routeur : une actualité est une affaire de catégorie
#  « Actualité » (#1091, lot 4), elle se lit et s'écrit par `schemas_tickets`.

#  La synthèse d'une affaire close (#1643) — fiche de l'affaire et carnet.
from app.schemas_synthese import SyntheseLue as SyntheseLue  # noqa: E402,F401
from app.schemas_synthese import EtapeMoyenne as EtapeMoyenne  # noqa: E402,F401
from app.schemas_synthese import ExerciceLu as ExerciceLu  # noqa: E402,F401
from app.schemas_synthese import ResumeAffaires as ResumeAffaires  # noqa: E402,F401
