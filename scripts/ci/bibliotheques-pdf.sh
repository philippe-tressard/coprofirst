#!/bin/bash
# =============================================================================
#  bibliotheques-pdf.sh — Les bibliothèques système du rendu PDF, sur le runner
#
#  WeasyPrint a besoin de pango/cairo/harfbuzz pour RENDRE un document ; sans
#  elles, les tests de rendu échouent (`test_documents_pdf`, qui échoue exprès
#  en intégration continue). Appelé par DEUX workflows : « CI » (job pytest) et
#  « PostgreSQL » (#1747) — ce dernier n'avait pas l'étape, et le rendu y
#  échouait faute de HarfBuzz-Subset. Écrit une fois, ici.
#
#  ⚠️ N'INSTALLE RIEN dans le cas normal : on regarde avant d'agir. `apt-get
#  update` contacte les miroirs Debian — 6 s d'habitude, plus de dix minutes le
#  19/08/2026. On ne paie l'installation que si une bibliothèque manque.
#
#  Hors Debian (poste Windows, `scripts/poste/rejouer-ci.sh`), l'étape n'a pas
#  d'objet : elle le DIT et rend la main sans échouer — en intégration continue,
#  l'environnement est Ubuntu et le contrôle s'exécute réellement.
# =============================================================================
set -euo pipefail

if ! command -v dpkg-query >/dev/null 2>&1; then
    echo "· dpkg absent : étape sans objet hors Debian, rien à vérifier ici."
    exit 0
fi
PAQUETS="libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 libfribidi0 libcairo2"
manquants=""
for p in $PAQUETS; do
    _st=$(dpkg-query -W -f='${Status}' "$p" 2>/dev/null)
    grep -q "install ok installed" <<<"$_st" \
        || manquants="$manquants $p"
done
if [ -z "$manquants" ]; then
    echo "✓ Les bibliothèques de rendu PDF sont déjà sur le runner — rien à installer."
else
    echo "→ Manquant(s) :$manquants — installation depuis les miroirs."
    sudo apt-get update -qq
    # shellcheck disable=SC2086 # une bibliothèque par mot
    sudo apt-get install -y --no-install-recommends $manquants
fi
