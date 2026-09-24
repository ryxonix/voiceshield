#!/usr/bin/env bash
# VoiceShield AI — wait for the peer gRPC endpoint to accept connections.
set -uo pipefail

for _ in $(seq 1 300); do
  if (echo > /dev/tcp/127.0.0.1/7051) >/dev/null 2>&1; then
    exit 0
  fi
  sleep 2
done
echo "peer :7051 not reachable after wait" >&2
exit 1