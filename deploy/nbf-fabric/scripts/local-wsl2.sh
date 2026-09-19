#!/usr/bin/env bash
# VoiceShield AI — bring up the NBF anchor network on the DEV box (WSL2 Ubuntu).
# Zero-cost: no cloud spend, uses Docker inside WSL2.
#
#   wsl -d Ubuntu
#   cd /mnt/f/voiceshield/deploy/nbf-fabric
#   bash scripts/local-wsl2.sh
set -euo pipefail

CHANNEL=${CHANNEL:-mychannel}
ORDERER=orderer.vsh.example.com:7050
ADMIN_MSP=/etc/hyperledger/crypto/peerOrganizations/vsh.example.com/users/Admin@vsh.example.com/msp

echo "==> [1/4] Generate Org1 + Orderer crypto and channel config"
bash scripts/gen-crypto.sh

echo "==> [2/4] Start peer+orderer+CA+couchdb+IPFS+gateway"
docker compose up -d

echo "==> [3/4] Create + join channel '${CHANNEL}'"
# Wait for the peer to be live
until docker exec vsh-peer0 peer node status 2>/dev/null | grep -q SERVER; do sleep 2; done

docker exec \
  -e CORE_PEER_LOCALMSPID=Org1MSP \
  -e CORE_PEER_MSPCONFIGPATH=${ADMIN_MSP} \
  -e CORE_PEER_ADDRESS=peer0:7051 \
  -e CORE_PEER_TLS_ENABLED=false \
  vsh-peer0 peer channel create \
  --orderer ${ORDERER} \
  --channelID ${CHANNEL} \
  --file /chaincode/channel-artifacts/channel.tx \
  --outputBlock /chaincode/channel-artifacts/${CHANNEL}.block

docker exec \
  -e CORE_PEER_LOCALMSPID=Org1MSP \
  -e CORE_PEER_MSPCONFIGPATH=${ADMIN_MSP} \
  -e CORE_PEER_ADDRESS=peer0:7051 \
  -e CORE_PEER_TLS_ENABLED=false \
  vsh-peer0 peer channel join \
  --blockpath /chaincode/channel-artifacts/${CHANNEL}.block

echo "==> [4/4] Install, approve and commit chaincode"
bash scripts/install-chaincode.sh

echo "==> Gateway: connection profile + wallet"
PEER_URL=peer0:7051 ORDERER_URL=orderer.vsh.example.com:7050 bash scripts/gen-connection-profile.sh
bash scripts/build-wallet.sh

echo ""
echo "NBF anchor network up; channel '${CHANNEL}' created."
echo "Gateway:    http://localhost:4000/health"
echo "Backend:    BLOCKCHAIN_EXTERNAL_ANCHOR=true NBF_GATEWAY_URL=http://localhost:4000 python app/main.py"