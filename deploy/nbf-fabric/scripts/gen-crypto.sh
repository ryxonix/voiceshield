#!/usr/bin/env bash
# VoiceShield AI — generate Org1/Orderer crypto + system/channel config.
# Run from deploy/nbf-fabric/ inside WSL2 Ubuntu (or any host with Docker).
set -euo pipefail

echo "==> Cryptogen: Org1 + Orderer identities"
mkdir -p crypto-config channel-artifacts gateway/wallet
docker run --rm --user "$(id -u):$(id -g)" \
  -v ${PWD}:/work -w /work \
  hyperledger/fabric-tools:2.2 \
  cryptogen generate --config=./crypto-config.yaml --output=./crypto-config

echo "==> Configtxgen: genesis (system channel)"
docker run --rm --user "$(id -u):$(id -g)" \
  -v ${PWD}:/work -w /work \
  -e FABRIC_CFG_PATH=/work \
  hyperledger/fabric-tools:2.2 \
  configtxgen -profile VoiceShieldGenesis \
  -outputBlock ./channel-artifacts/genesis.block -channelID systemchannel

echo "==> Configtxgen: mychannel create tx"
docker run --rm --user "$(id -u):$(id -g)" \
  -v ${PWD}:/work -w /work \
  -e FABRIC_CFG_PATH=/work \
  hyperledger/fabric-tools:2.2 \
  configtxgen -profile VoiceShieldChannel \
  -outputCreateChannelTx ./channel-artifacts/channel.tx -channelID mychannel

echo "==> Crypto + config generated under crypto-config/ and channel-artifacts/"
ls -R crypto-config | head -30
echo "OK"