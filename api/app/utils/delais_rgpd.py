"""Les délais que la politique de confidentialité ANNONCE et que le code SERT — une seule fois.

Module pur, sans dépendance : le gabarit de la politique (`app/seed/`) et les
routes le lisent tous deux, et le texte publié ne peut pas diverger de ce que
l'API sert aux clients (le site, l'app iOS).
"""

#: Le délai maximal de traitement d'une demande de suppression de compte (#2699) —
#: celui du RGPD (art. 12-3 : un mois). Un délai MAXIMAL, pas une attente : la
#: demande peut être traitée le jour même (arbitrage du 12/11/2026).
DELAI_TRAITEMENT_DEMANDE_JOURS = 30
