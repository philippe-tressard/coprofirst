"""Ce que la politique dit de QUI LIT QUOI, et des personnes SANS COMPTE (#2917, #2957).

## 🔴 Pourquoi (audit du 23/11/2026)

La section « 4. Destinataires » disait, depuis la première version (07/09/2026) :
« Les données sont accessibles uniquement aux membres du conseil syndical et à
l'administrateur. » C'était faux, et sur une page publique : un résident lit le nom de
l'auteur d'une affaire, d'une annonce ou d'une réponse, l'annuaire du conseil syndical
et du syndic, l'annonce d'une arrivée ; un locataire lit les coordonnées de son
bailleur. Le test de la politique lisait l'autre moitié du paragraphe (« ni cédées »),
la CESSION, jamais l'ACCÈS.

La phrase dit désormais ce que l'API sert, rôle par rôle, sans changer aucun droit
(arbitrage par délégation de Philippe à la coordination, 23/11/2026 : « la politique dit
la vérité du code »). Un accès jugé excessif se traite par un ticket de sécurité, pas en
rétrécissant ce texte. Chaque accès nommé est lié
à son déclencheur dans le code par `test_politique_qui_lit_quoi.py`. Ce qu'elle promet
de NE PAS montrer — l'adresse et le téléphone d'un résident à un autre, hors les cas
nommés — vient de l'inventaire des routes du 23/11/2026 : aucun contrôle ne le tient
encore, et une route qui rendrait l'un ou l'autre la rendrait fausse.

⚠️ Comme le reste du gabarit : un choix d'ingénierie, pas un avis juridique ; modèle à
faire relire (`standards/14`).
"""

#: La phrase d'origine, recopiée littéralement : la migration la cherche dans le texte
#: servi, et le test de la politique refuse qu'elle revienne.
ACCES_ANCIEN = (
    "Les données sont accessibles uniquement aux membres du conseil syndical et à l'administrateur."
)

#: Ce qui la remplace : elle FERME le paragraphe ouvert par le titre, pose la liste, et
#: en rouvre un pour la suite de la section (accès technique de l'opérateur, cession).
QUI_LIT_QUOI = (
    "Chacun ne lit que ce que son rôle lui ouvre\xa0:</p><ul>"
    "<li><strong>le conseil syndical et l'administrateur</strong> accèdent aux données "
    "nécessaires à la gestion de la copropriété\xa0;</li>"
    "<li><strong>les autres comptes de la copropriété</strong> peuvent lire votre nom, et ce "
    "que vous publiez pour eux\xa0: une affaire, avec votre nom et votre bâtiment\xa0; une "
    "actualité, avec votre nom\xa0; une annonce, avec votre nom et votre adresse "
    "électronique, sauf si vous décochez cette option\xa0; une réponse ou un commentaire, "
    "avec votre nom, votre bâtiment et votre qualité (copropriétaire, locataire…)\xa0; un "
    "avis dont vous avez accepté la publication. Ils lisent aussi l'annonce de votre arrivée "
    "si elle est publiée (nom, bâtiment, étage s'il est renseigné, et le nom de l'occupant "
    "précédent), l'annuaire du conseil syndical (nom, bâtiment, étage, photo) et celui du "
    "syndic, avec ses coordonnées\xa0;</li>"
    "<li><strong>votre locataire</strong> lit votre nom, votre adresse électronique et votre "
    "téléphone\xa0; un copropriétaire qui enregistre un bail peut retrouver le compte d'un "
    "locataire par son nom ou par son adresse, dont il ne voit qu'une forme masquée\xa0;</li>"
    "<li><strong>une délégation</strong> fait lire à l'aidant ce que lit la personne "
    "aidée.</li></ul><p>Hors ces cas, votre adresse électronique et votre téléphone ne sont "
    "montrés à aucun autre résident."
)

#: Les personnes dont le site garde l'identité SANS qu'elles aient de compte (#2957) :
#: le locataire saisi par son bailleur (`models/bailleur.LocationBail.locataire_*`), les
#: membres du syndic (`models/gouvernance.MembreSyndic`) et les contacts des prestataires
#: (`models/prestataires.Prestataire.contacts_json`). Puce de « 2. Données collectées ».
PERSONNES_SANS_COMPTE = (
    "<li><strong>Personnes sans compte\xa0:</strong> un copropriétaire bailleur peut "
    "enregistrer l'identité de son locataire (nom, prénom, adresse électronique, téléphone) "
    "pour un bail, que ce locataire ait un compte ou non\xa0; l'administration de la "
    "copropriété tient les coordonnées des membres du syndic et des contacts des "
    "prestataires. Ces personnes ont les mêmes droits que les titulaires d'un compte "
    "(point\xa06).</li>"
)

#: La conservation d'un bail, telle que le code la pratique : aucune purge à la fin du
#: bail ; il part avec le compte du bailleur (`utils/suppression_compte`, étape 10). La
#: suppression du compte du LOCATAIRE ne retire que son rattachement : l'identité saisie
#: par le bailleur reste au bail. Écrire une durée de fin de bail exigerait d'abord la
#: purge qui l'applique (`standards/14` §1 : une durée sans purge est fictive).
CONSERVATION_BAUX = (
    "<li>Baux enregistrés par un bailleur, avec l'identité du locataire qu'il y a saisie\xa0: "
    "conservés tant que le compte du bailleur existe, et supprimés avec lui.</li>"
)


__all__ = ["ACCES_ANCIEN", "CONSERVATION_BAUX", "PERSONNES_SANS_COMPTE", "QUI_LIT_QUOI"]
