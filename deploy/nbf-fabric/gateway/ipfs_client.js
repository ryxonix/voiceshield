/**
 * Kubo (IPFS) client for the VoiceShield NBF gateway.
 * Pattern lifted from NBF-Lite `nbf-samplerest/ipfs_client.js`, which uses
 * the official `ipfs-http-client`. NOTE: with ipfs-http-client v60+ `add()`
 * resolves to a single `{ cid, path, size, ... }` object (not the `[{hash}]`
 * array of v0.x), so we resolve the CID from `result.cid.toString()`.
 */

const IPFS_API_HOST = process.env.IPFS_API_HOST || '127.0.0.1';
const IPFS_API_PORT = process.env.IPFS_API_PORT || '5001';
const IPFS_GATEWAY = process.env.IPFS_GATEWAY || 'http://127.0.0.1:8080';

const { create } = require('ipfs-http-client');

const ipfsClient = create({ host: IPFS_API_HOST, port: IPFS_API_PORT, protocol: 'http' });

/**
 * Upload base64 file contents to IPFS, return the CID (hash).
 * The bytes are stored raw (the backend already base64-encodes the
 * ciphertext); storing the decoded buffer keeps the equality check exact.
 */
async function uploadToIPFS(name, base64Contents) {
  const file = { path: name, content: Buffer.from(base64Contents, 'base64') };
  const result = await ipfsClient.add(file);
  if (Array.isArray(result)) {
    // Legacy v0.x shape: [{ path, hash, size }]
    if (!result[0] || !result[0].hash) {
      throw new Error('IPFS add returned no files');
    }
    return result[0].hash;
  }
  if (!result || !result.cid) {
    throw new Error('IPFS add returned no CID');
  }
  return result.cid.toString();
}

/** Fetch content for a CID from the configured HTTP gateway, base64 of the
 * RAW bytes (never decode to UTF-8 — the stored payload is opaque ciphertext). */
async function fetchFromIPFS(cid) {
  const url = `${IPFS_GATEWAY}/ipfs/${cid}`;
  const { get } = require('http');
  const buf = await new Promise((resolve, reject) => {
    get(url, (res) => {
      if (res.statusCode === 404) {
        res.resume();
        return reject(new Error(`IPFS content not found: ${cid}`));
      }
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('error', reject);
      res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', reject);
  });
  return buf.toString('base64');
}

module.exports = { uploadToIPFS, fetchFromIPFS, ipfsClient, IPFS_API_HOST, IPFS_API_PORT, IPFS_GATEWAY };