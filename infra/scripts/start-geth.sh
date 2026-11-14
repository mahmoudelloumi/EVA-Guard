#!/bin/sh
# Lance un nœud Geth du labo EVA-Guard.
#
# Variables (données par docker-compose.yml) :
#   NODE_NAME    nom du nœud (signer, reference, honest1, victim, ...)
#   NODE_IP      IP du nœud dans honest_net (annoncée aux autres pairs)
#   NETWORK_ID   id du réseau privé
#   NETRESTRICT  sous-réseaux autorisés pour le P2P (le labo seulement)
# Les options propres à chaque nœud arrivent dans "$@" (champ "command:").
set -eu

DATADIR=/data

# Premier démarrage : on crée la chaîne à partir du genesis
if [ ! -d "$DATADIR/geth/chaindata" ]; then
  echo "[$NODE_NAME] Premier démarrage : geth init"
  geth init --datadir "$DATADIR" /config/genesis.json
fi

# ⚠ Options ouvertes (admin, debug, 0.0.0.0) : OK dans le labo isolé, JAMAIS en vrai.
exec geth \
  --datadir "$DATADIR" \
  --networkid "$NETWORK_ID" \
  --nodekey "/config/nodes/$NODE_NAME/nodekey" \
  --port 30303 \
  --nat "extip:$NODE_IP" \
  --netrestrict "$NETRESTRICT" \
  --syncmode full \
  --cache 128 \
  --http --http.addr 0.0.0.0 --http.port 8545 --http.vhosts '*' \
  --http.api eth,net,web3,admin,txpool,debug \
  --metrics --metrics.addr 0.0.0.0 --metrics.port 6060 \
  "$@"
