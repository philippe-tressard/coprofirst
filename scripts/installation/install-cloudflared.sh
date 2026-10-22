#!/bin/bash
# install-cloudflared.sh — installe et configure cloudflared sur le RPi5
# Usage : bash install-cloudflared.sh <TOKEN>

set -eu

TOKEN="${1:-}"

if [ -z "$TOKEN" ]; then
  echo "Usage: bash install-cloudflared.sh <TOKEN>"
  echo "Le token se trouve dans Cloudflare Zero Trust > Networks > Tunnels > ton tunnel > Ajouter un connecteur :"
  echo "c'est la longue chaîne eyJ… de la commande d'installation — PAS l'« ID du tunnel » (91d1afa9-…)."
  exit 1
fi

# L'identifiant du tunnel a déjà été collé à la place du jeton (25/09/2026, #1318).
# La règle (et l'unité modèle) vit dans lib-jeton-tunnel.sh, partagée avec changer-jeton-tunnel.sh.
# shellcheck source=../lib/lib-jeton-tunnel.sh
source "$(dirname "$0")/../lib/lib-jeton-tunnel.sh"
VERDICT=$(verdict_jeton "$TOKEN" "")
if [ "$VERDICT" != "ok" ]; then
  echo "REFUSÉ — $(motif_refus "$VERDICT")"
  exit 1
fi

#  Par le dépôt apt de Cloudflare, jamais en binaire téléchargé (#1591, 04/10/2026).
#  Ce script posait `/usr/local/bin/cloudflared` depuis les « releases » GitHub :
#  apt ne le mettait jamais à jour, et rpi2 a tourné sept mois sur la 2026.3.0
#  pendant que rpi1, passé par le paquet, suivait. Mêmes source et clé que les
#  deux nœuds de production. 🔒 api/tests/test_paquets_systeme_par_apt.py
CLE=/usr/share/keyrings/cloudflare-public-v2.gpg
echo "==> Dépôt apt de Cloudflare..."
mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg -o "$CLE"
echo "deb [signed-by=$CLE] https://pkg.cloudflare.com/cloudflared any main" \
  > /etc/apt/sources.list.d/cloudflared.list
apt-get update -qq
apt-get install -y cloudflared

#  Un binaire posé à la main par l'ancienne version de ce script passerait
#  DEVANT le paquet dans le PATH : on le retire (un lien vers le paquet reste).
if [ -f /usr/local/bin/cloudflared ] && [ ! -L /usr/local/bin/cloudflared ]; then
  echo "==> Retrait de l'ancien binaire /usr/local/bin/cloudflared (hors apt)"
  rm -f /usr/local/bin/cloudflared
fi
hash -r

echo "==> Version installée : $(cloudflared --version)"

#  Le jeton va dans un FICHIER root 600, jamais dans l'unité (#2115, 22/10/2026) :
#  `cloudflared service install <jeton>` l'écrivait en clair dans `ExecStart`, lisible
#  par tout compte local (`ps`, `systemctl cat`). C39 de check-reliability.sh échoue
#  si l'ancienne forme revient.
echo "==> Jeton dans $JETON_FICHIER (root 600) et unité systemd..."
install -d -m 700 -o root -g root "$(dirname "$JETON_FICHIER")"
( umask 077; printf '%s' "$TOKEN" > "$JETON_FICHIER" )
chown root:root "$JETON_FICHIER"; chmod 600 "$JETON_FICHIER"
unite_modele > /etc/systemd/system/cloudflared.service
chmod 644 /etc/systemd/system/cloudflared.service
systemctl daemon-reload

echo "==> Démarrage du service..."
systemctl enable cloudflared
systemctl start cloudflared
systemctl status cloudflared --no-pager

echo ""
echo "✓ cloudflared installé et démarré."
echo "  Vérifie le statut du tunnel dans Cloudflare Zero Trust > Networks > Tunnels"
