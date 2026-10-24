"""Modèles SQLModel.

`Perimetre`, et depuis le 13/08/2026 `Copropriete`/`Batiment`/`Lot`,
vivent dans leur propre module, comme tout modèle qui a un domaine :
`core.py` a dépassé 1 500 lignes, et n'est repassé sous 500 que le 28/09/2026
(#779). Il ne reçoit plus de classe (`test_core_sans_modele_neuf.py`).

L'import ci-dessous n'est pas décoratif : c'est lui qui enregistre la table
auprès de SQLModel avant `create_all`. Un modèle défini dans un module que
personne n'a importé n'existe pas pour `metadata.create_all`, et la table
manquerait sans le moindre message.
"""

from app.models.copropriete import (  # patrimoine PHYSIQUE, extrait le 13/08/2026
    Batiment as Batiment,
    Copropriete as Copropriete,
    Lot as Lot,
)
from app.models.courriel import CourrielReleve as CourrielReleve
from app.models.courriel import RelanceCourriel as RelanceCourriel
from app.models.courriel import ReponseRelance as ReponseRelance
from app.models.courriel import FilCourriel as FilCourriel
from app.models.courriel import MessageVerse as MessageVerse
from app.models.courriel import VersementCourriel as VersementCourriel
from app.models.perimetre import LotPerimetre as LotPerimetre
from app.models.perimetre import Perimetre as Perimetre
from app.models.charges import CleDeCharges as CleDeCharges
from app.models.charges import QuotePartLot as QuotePartLot
from app.models.etat_descriptif import ImportEtatDescriptif as ImportEtatDescriptif
from app.models.etat_descriptif import LigneEtatDescriptif as LigneEtatDescriptif
from app.models.whatsapp import WhatsAppLog as WhatsAppLog
from app.models.whatsapp import WhatsAppScheduled as WhatsAppScheduled
from app.models.gouvernance import AgCsInfo as AgCsInfo
from app.models.gouvernance import MembreCS as MembreCS
from app.models.gouvernance import MembreSyndic as MembreSyndic
from app.models.gouvernance import SyndicInfo as SyndicInfo
from app.models.evenement import EvenementEvolution as EvenementEvolution
from app.models.affaires_liees import AffaireLiee as AffaireLiee
from app.models.fichiers_recus import FichierRecu as FichierRecu
from app.models.ia import AppelIA as AppelIA
from app.models.diagnostics import DiagnosticRapport as DiagnosticRapport
from app.models.diagnostics import DiagnosticType as DiagnosticType
from app.models.lot_import import LotImport as LotImport
from app.models.bailleur import LocationBail as LocationBail
from app.models.delegations import Delegation as Delegation
from app.models.synthese import SyntheseAffaire as SyntheseAffaire
from app.models.synthese import TentativeSynthese as TentativeSynthese
from app.models.reglement import QuestionReglement as QuestionReglement
from app.models.reglement import TexteReglement as TexteReglement
from app.models.points_conseil import CommentairePoint as CommentairePoint
from app.models.points_conseil import CompteRenduAffaire as CompteRenduAffaire
from app.models.points_conseil import PointConseil as PointConseil
from app.models.points_conseil import PresentPoint as PresentPoint
from app.models.conservation import ArchiveAffaires as ArchiveAffaires
from app.models.avis import Avis as Avis
