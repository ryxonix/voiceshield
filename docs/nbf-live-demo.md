# NBF anchor — live end-to-end verification

**Verified live: 2026-09-19** on a GitHub Codespace-hosted NBF-Lite-compatible stack
(Fabric 2.2 peer/orderer/CouchDB + Kubo IPFS + trimmed REST gateway), called from the
Windows-hosted FastAPI backend over the public gateway URL
(`https://<codespace>-4000.app.github.dev`, the same pattern documented in
`deploy/nbf-fabric/docs/nbflite-codespaces.md`).

## What was verified

End-to-end anchor of forensic report `e2e-NBF-LIVE-01`:

```
Forensic PDF ──▶ AES-256-GCM ──▶ IPFS /store ──▶ CID ──▶ /retrieve round-trip ✓
                │
Local PoW block ──▶ NBF gateway ──▶ Fabric chaincode AnchorReport ──▶ tx_id ✓
```

| Check | Result |
| --- | --- |
| `GET /api/report/e2e-NBF-LIVE-01` (forensic PDF) | `200`, PDF generated |
| `GET /api/blockchain/onchain/e2e-NBF-LIVE-01` | `anchor_status: anchored`, `verified: true`, `problems: []` |
| Fabric `invokecc AnchorReport` | `tx_id: tx-test-1`, `status: SUCCESS` |
| IPFS `POST /store` | CID `QmZimdoSUNhXCrtNKzR62ZgW4haHNVLPWRqVvTrHW48kBa` |
| IPFS `GET /retrieve/:cid` | round-trip decodes to the exact ciphertext |
| Local PoW chain (`GET /api/blockchain`) | `chain_id: VoiceShieldAIV1`, `valid: true`, `difficulty: 4`, `height: 14` |
| Anchored blocks | block 12 (prior test run, placeholder CID) + block 13 (live anchor) |
| Backend test suite | 78 passed (`pytest`) |

## Fail-open behaviour (by design, also demonstrated)

Privacy/availability design guarantee: when no Fabric/IPFS gateway is reachable the local
PoW chain stays authoritative — the anchor row is marked `pending` (never falsely
`anchored`) and verification returns `gateway_unreachable`. Re-anchoring is a
single call: `POST /api/blockchain/retry/{call_id}`. This is what happens if the
Codespace is stopped and restarted; the playbook in
`deploy/nbf-fabric/docs/nbflite-codespaces.md` covers cold-start.

## Reproduce in 3 commands

```bash
cd deploy/nbf-fabric
docker compose up -d --force-recreate   # peer, orderer, CouchDB, Kubo IPFS, gateway
bash scripts/deploy-cloud.sh            # create channel + install/approve/commit chaincode
# backend/.env: NBF_GATEWAY_URL=http://<host>:4000  (or the <codespace>-4000.app.github.dev URL)
```

Then generate a report and call `GET /api/blockchain/onchain/<call_id>` — see the README
NBF section and `deploy/nbf-fabric/README.md` for the full API surface
(`/fabric/v1/invokecc`, `/fabric/v1/querycc`, `/store`, `/retrieve`, `/health`).

## What this protects (DPDP-safe evidence trail for AI-voice/fraud reports)

- Only **hashes** (block hash, Merkle root, file SHA-256), the **IPFS CID**, and a 16-hex
  **key fingerprint** are written to the Fabric ledger.
- The full report is **AES-256-GCM ciphertext pinned to IPFS**, decryptable only with the
  operator-held master key (`reports/keys/org_master.key`).
- Raw audio never leaves operator custody — a legally clean evidentiary/audit trail for
  scam-voice and impersonation reports, immune to tampering after the fact.