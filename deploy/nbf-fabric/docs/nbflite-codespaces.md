# Run the NBF anchor in a GitHub Codespace (no card, no VM admin)

A card-free alternative to Oracle: run the whole Fabric + IPFS + gateway stack
inside a **GitHub Codespace** (free tier ≈ 120 core-hours/month; a 2-core
Codespace gives ~60 hours/month, more than enough for demo/CI-scale use), then
reach the gateway from the Windows backend over Codespaces **public port
forwarding**.

```
Windows backend ──https──▶ https://<cs>-4000.app.github.dev ──▶ gateway ──▶ Fabric + IPFS
```
The backend still decrypts IPFS ciphertext locally with the org master key —
only the hash/CID transaction traffic crosses the Codespace. Same zero-cost
promise as Oracle: no card at any step.

---

## 1. Repo is already on GitHub

This project is already pushed to **`github.com/ryxonix/voiceshield`** (private,
branch `main`). You only need to create the Codespace — no repo setup, no
`gh repo create`, no card.

## 2. Create the Codespace

- Open `https://github.com/ryxonix/voiceshield` → **Code ▸ Codespaces ▸
  Create codespace on main**.
- Pick a **2-core** machine (default; comfortable, free-tier friendly). The
  included `.devcontainer/devcontainer.json` is applied automatically: Ubuntu,
  Node, **Docker + Compose**, ports `4000` (public) / `8000` (private).

Sanity check in the Codespace terminal:

```bash
docker --version && docker compose version
```

## 3. Deploy the anchor stack (usual scripts, zero install work)

```bash
cd deploy/nbf-fabric
bash scripts/deploy-cloud.sh      # crypto -> profile+wallet -> compose up -> channel -> chaincode
curl http://localhost:4000/health
curl "http://localhost:4000/fabric/v1/querycc?fcn=QueryAll&ccname=voiceshield-report&channel=mychannel&mspId=Org1MSP&user=User1"
```

Same flow as the VM: crypto → wallet → connection profile → `docker compose up
--build` (peer, orderer, CA, CouchDB, Kubo IPFS, gateway) → `mychannel` →
`voiceshield-report` chaincode. Nothing extra to install — Docker ships in the
Codespace.

`deploy-cloud.sh` and `install-chaincode.sh` are idempotent: re-running them is
safe (skips an already-installed/committed chaincode). The querycc call above
should return the committed genesis record (`"call_id":"genesis"`), proving the
gateway wallet + connection profile + ledger all work end to end.

**Verified end-to-end 2026-09-19** on a 2-core Codespace (Docker 28 + Compose
v2): full deploy, chaincode `QueryAll` → genesis record, `/store` pinned a real
IPFS CID, and a Windows-side backend report anchored + decrypted + SHA-matched
through the public gateway URL.

## 4. Make the gateway public

Codespaces only lets you *announce* a port you are listening on. Port 4000 is
pre-marked `public` by the devcontainer, but you must have started the gateway:

- Codespace UI: **Ports** tab → port **4000** → right-click → **Port
  Visibility ▸ Public**, then copy the forwarded URL `https://<cs>-4000.app.github.dev`.
- Or from the terminal: `gh codespace ports visibility 4000:public -c <codespace>`.

Verify from a browser: `https://<cs>-4000.app.github.dev/health`.

## 5. Point the Windows backend at it

```ini
# backend/.env
BLOCKCHAIN_EXTERNAL_ANCHOR=true
NBF_GATEWAY_URL=https://<cs>-4000.app.github.dev
NBF_IPFS_MODE=auto
```

Restart the backend (`cd F:\voiceshield\backend && venv\Scripts\python.exe app\main.py`),
generate any forensic report, then:

```bash
curl http://127.0.0.1:8000/api/blockchain/onchain/<call_id>     # expect "verified": true
```

Note: uvicorn binds IPv4 only, so use `127.0.0.1` — `curl localhost` may hit the
IPv6 loopback `::1` and spuriously report "Connection refused" even while the
backend is up.

## 6. Housekeeping (staying free)

- Codespaces auto-stops after ~30 min of inactivity (restarting resumes the
  same container + state).
- Free quota: ~120 core-hours/month + 15 GB storage and ~15 GB egress — a
  2-core Codespace used a few hours a week for a demo stays well inside it.
- Stop it when idle: **Codespaces banner ▸ Stop**, or `gh codespace stop -c <cs>`.
- The gateway has **no auth** — treat the public URL as a demo-only endpoint;
  delete the Codespace (`gh codespace delete`) when done.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `curl :4000/health` works but backend gets connection error | Port not marked **Public** | Ports tab → 4000 → Port Visibility → Public; re-copy URL (`app.github.dev`, not `localhost`) |
| Backend "Connection refused" on `curl localhost:8000` | uvicorn binds IPv4, `localhost` → `::1` | Use `http://127.0.0.1:8000/...` |
| `on-chain query failed (fail-open)` | Wrong `NBF_CHANNEL/NBF_CC/NBF_USER/NBF_MSP` | Re-check values vs `deploy-cloud.sh` output |
| `chaincode install failed ... channelless check ... [Admins]` | Old image where install ran as the *peer node* identity | Pull latest; `install-chaincode.sh` now submits install/queryinstalled as the Org1 admin |
| `missing go.sum entry` / `exec: "go": executable file not found` | Packaging needs Go + complete `go.sum` | `go.sum` is committed; the script installs `go` in the peer (`apk`/`apt`) |
| `chaincode already successfully installed` / `new definition must be sequence 2` | Re-running after a successful run | Expected — script is idempotent and skips already-installed/committed definitions |
| `chaincode registration failed: container exited with 0` | Peer launched chaincode with Fabric's default `NetworkMode: host`, shim couldn't reach `peer0:7052` | `docker-compose.yml` pins `vshnet` + `restart: unless-stopped`; pull + `docker compose up -d` |
| `Error response from daemon: container ... is not running` | Transient peer crash (Codespace under memory pressure) | `docker compose up -d` (restart policy) then re-run the script |
| Chaincode slow / `container start timeout` | Cold Fabric chaincode container (first ccenv pull + Go build) | Retry after ~30 s; then it's instant |
| Disk blow-up on old chaincode containers | Repeat deploys | `docker system prune -af` in the Codespace |
| Codespace stopped → anchors `pending` | Gateway unreachable | Restart Codespace; `POST /api/blockchain/retry/{call_id}` re-anchors |

## Zero-cost checklist

- GitHub account + Codespaces free tier — **no card required**.
- Ubuntu + Docker come with the Codespace — no install/admin.
- Same NBF-compatible Fabric stack; backend parsing already tolerant
  (`NBF_IPFS_MODE=auto`, camelCase/txid handling).
- Nothing about the anchor design changes; the local PoW chain stays
  authoritative and fail-open throughout.