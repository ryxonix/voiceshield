import type { ReactNode } from 'react'
import { Breadcrumbs, PageHeader, Divider } from '../components/ui'

const BRAND = '#2563EB'
const INK = '#18181B'
const MUTED = '#71717A'
const LINE = '#E4E4E7'
const CREAM = '#FAF8F5'
const GREEN = '#3F6F4F'
const AMBER = '#B45309'
const RED = '#DC2626'
const PURPLE = '#7C5CBF'
const BLUE50 = '#EFF6FF'
const GREEN50 = '#F0FDF4'
const AMBER50 = '#FFFBEB'
const RED50 = '#FEF2F2'
const VIOLET50 = '#F5F3FF'

const ANCHORS: ReadonlyArray<readonly [string, string]> = [
  ['solution', '1 · Proposed solution'],
  ['approach', '2 · Technical approach'],
  ['feasibility', '3 · Feasibility & viability'],
  ['impacts', '4 · Impacts & benefits'],
  ['references', '5 · Research & references'],
]

export default function ProjectWorking() {
  return (
    <article>
      <Breadcrumbs trail={['Project Working', 'Overview']} />
      <PageHeader
        title="Project Working"
        meta="How VoiceShield AI works — the proposed solution, technical approach, feasibility, impacts, and the research sources behind it."
      />

      <div className="sticky top-20 z-20 mt-6 flex gap-2 overflow-x-auto rounded-xl bg-[#FAF8F5]/95 pb-1 pt-0.5 backdrop-blur lg:hidden">
        {ANCHORS.map(([id, label]) => (
          <a
            key={id}
            href={`#${id}`}
            className="shrink-0 rounded-full border border-[#E4E4E7] bg-white px-3 py-1.5 text-[12.5px] font-medium text-zinc-700 transition-colors hover:bg-[#F1EEE9]"
          >
            {label}
          </a>
        ))}
      </div>

      <Divider />

      <Section id="solution" n="01" title="VoiceShield — Proposed Solution"
        lead="A zero-trust, real-time audio deepfake detection and mitigation platform for the Indian telecom context. VoiceShield listens to live voice calls over WebSocket streaming — or analyzes uploaded audio — and decides, in real time, whether the speaker is a real human (bonafide) or a synthetic / AI-cloned voice (spoof).">
        <h3 className="mt-1 text-[15px] font-bold text-zinc-900">The problem</h3>
        <p className="mt-2 leading-relaxed text-zinc-700">
          AI voice cloning has collapsed the cost of impersonation: a few seconds of
          leaked audio is enough to synthesize a convincing twin of a victim and
          drive OTP-call fraud, social-engineering scams, vishing and synthetic-voice
          robocalls across Indian telecom. Existing defenses are blocked,
          phone-number-level, or closed-source — and none produce tamper-evident
          evidence that survives a police or banking review.
        </p>

        <h3 className="mt-6 text-[15px] font-bold text-zinc-900">The proposed solution</h3>
        <p className="mt-2 leading-relaxed text-zinc-700">
          VoiceShield scores each window of a call with an ensemble of open Indian-language
          deepfake detectors fused with explainable prosodic evidence and an enterprise
          watermark verifier. Every forensic incident is anchored to a tamper-evident,
          mandatory on-chain ledger — fail-closed by design, so no report is ever issued
          without provable evidence.
        </p>

        <Fig title="How a call is processed — one continuous pipeline"
          caption="Raw audio lives in RAM only, overwritten every window (DPDP-aware). Every step is open, explainable and auditable.">
          <PipelineTimeline
            steps={[
              { n: '01', title: 'Call audio', sub: 'live PCM 16 kHz mono — mic stream or uploaded file', tone: 'brand' },
              { n: '02', title: 'WebSocket → ring buffer', sub: '3 s window / 1 s hop; RAM only, no disk write', tone: 'brand' },
              { n: '03', title: 'Model ensemble', sub: 'Dhwani (XLS-R + AASIST) · AASIST-L official · local fallback · Cloud XLS-R', tone: 'brand' },
              { n: '04', title: 'XAI prosody layer', sub: 'jitter · shimmer · phase continuity · pitch stability · voice-print', tone: 'brand' },
              { n: '05', title: 'Fusion → verdict', sub: 'score = 0.7 × model + 0.3 × XAI → risk band, role-aware thresholds', tone: 'brand' },
              { n: '06', title: 'Alerts + forensic PDF', sub: 'Telegram / Gmail / ntfy.sh / Fast2SMS / webhook → I4C-ready PDF', tone: 'brand' },
              { n: '07', title: 'NBF evidence anchor', sub: 'SHA-256 + Merkle root → PoW ledger → Fabric + IPFS, mandatory, fail-closed', tone: 'red' },
            ]}
          />
        </Fig>

        <h3 className="mt-8 text-[15px] font-bold text-zinc-900">Innovation and uniqueness</h3>
        <ul className="mt-3 grid gap-2.5 sm:grid-cols-2">
          <Fact dot={BRAND} title="Open, Indian-language stack" body="Dhwani (Wav2Vec2 XLS-R 300m + AASIST), AASIST-L official and local fine-tune, plus a Cloud XLS-R cross-lingual classifier — all MIT." />
          <Fact dot={PURPLE} title="Explainable prosody" body="Glottal jitter / shimmer, spectral phase continuity and cross-session voice-prints explain every verdict instead of returning a black box." />
          <Fact dot={GREEN} title="Watermark short-circuit" body="A 4096-point FFT scans 7.0–7.5 kHz for the enterprise pilot tone — a verified caller is accepted instantly with a score of zero." />
          <Fact dot={RED} title="Mandatory evidence anchor" body="Every report hash is anchored to Hyperledger Fabric + IPFS via NBF-Lite — fail-closed. No gateway, no unanchored report." />
          <Fact dot={AMBER} title="DPDP-safe by construction" body="Streaming keeps audio in a RAM ring buffer only; nothing is written or leaves the device except scalar scores." />
          <Fact dot={BRAND} title="Role-aware mitigation" body="Child calls trigger an immediate guardian shield at score ≥ 70% (single score from model + prosody, adult ≥ 85%); elevated ≥ 35% raises a warning band in the UI." />
        </ul>

        <h3 className="mt-8 text-[15px] font-bold text-zinc-900">Why this is unique versus similar projects</h3>
        <p className="mt-2 leading-relaxed text-zinc-700">
          VoiceShield targets a different layer than the established commercial
          players. Instead of a closed SaaS score, it is a fully open, language-tuned,
          evidence-producing system for live Indian calls.
        </p>
        <div className="mt-4 grid gap-3">
          <VsRow aspect="Live real-time calls"
            vs="Pindrop Pulse focuses on enterprise contact-center fraud analytics; Resemble Detect and Truecaller detect after the fact or at number level. VoiceShield scores streaming call audio live, every 3 s window." />
          <VsRow aspect="Open, auditable models"
            vs="All competitors are proprietary. VoiceShield ships an MIT ensemble — Dhwani, AASIST-L and a Cloud XLS-R fine-tune — retrainable on Indian languages, with every source licensed and cited." />
          <VsRow aspect="Explainability + evidence"
            vs="Pindrop / Resemble return scores and logs. VoiceShield explains each verdict with prosodic XAI and produces an I4C-ready forensic PDF anchored to a mandatory Fabric + IPFS ledger — court- and police-review-ready." />
          <VsRow aspect="Privacy posture"
            vs="Closed platforms ingest and retain audio or embeddings at customer scale. VoiceShield keeps raw audio in a RAM-only ring buffer, stores hashes not sound, and is built around DPDP Act 2023 norms." />
          <VsRow aspect="Cost and deployment"
            vs="Commercial products are per-minute / per-seat SaaS. VoiceShield runs CPU-only on free-tier infrastructure (Oracle Cloud Always-Free ARM A1 or WSL2) with an MIT codebase." />
        </div>
      </Section>

      <Section id="approach" n="02" title="Technical Approach"
        lead="A fast real-time detector keeps streaming analysis ahead of the audio cadence, while a heavier multi-model ensemble powers deep forensic analysis of recorded files.">
        <h3 className="mt-1 text-[15px] font-bold text-zinc-900">Detection pipeline and fusion</h3>
        <ul className="mt-3 grid gap-2.5 sm:grid-cols-2">
          <Fact dot={BRAND} title="Realtime profile (default)" body="AASIST-L official + XAI prosody per 3 s window — ~1.5–1.6 s median on a reference CPU, enforced fail-hard at a 2000 ms budget." />
          <Fact dot={PURPLE} title="Ensemble profile (forensic)" body="Always used for /api/analyze and gRPC Analyze: Dhwani ~1.9 s, + AASIST-L official ~4.1 s, + Cloud XLS-R ~5.7 s (cold load ~72 s)." />
          <Fact dot={GREEN} title="Fusion rule" body="score = 0.7 × model_probability + 0.3 × XAI_risk. Watermark short-circuit forces verified callers to 0.0." />
          <Fact dot={AMBER} title="Windows" body="3 s / 1 s hop by default (300 ms / 100 ms legacy fallback for small AASIST checkpoints)." />
        </ul>

        <Fig title="System architecture" caption="Three planes — data ingress, detection engine, and the mandatory evidence ledger.">
          <ArchSvg />
        </Fig>

        <Fig title="Evidence lifecycle" caption="Every incident produces a hash that cannot be silently amended — anchoring is mandatory and fail-closed.">
          <LifecycleSvg />
        </Fig>

        <h3 className="mt-8 text-[15px] font-bold text-zinc-900">Technology stack</h3>
        <div className="card mt-4 overflow-hidden">
          <table className="w-full text-left text-[13.5px]">
            <thead>
              <tr className="border-b border-[#E4E4E7] text-[11px] uppercase tracking-wide text-zinc-500">
                <th className="px-5 py-3 font-semibold">Layer</th>
                <th className="px-5 py-3 font-semibold">Technology</th>
                <th className="px-5 py-3 font-semibold">Notes</th>
              </tr>
            </thead>
            <tbody>
              <Row k="Frontend" v="React 19 · Vite 8 · Tailwind 4 · TypeScript" n="Editorial UI, i18n en / hi / kn, live WebSocket monitor" />
              <Row k="Backend" v="FastAPI · Uvicorn · WebSockets · Pydantic-settings" n="REST + streaming + in-process gRPC service on :50051" />
              <Row k="Inference" v="ONNX Runtime (2 inter / 4 intra CPU threads) · librosa" n="CPU-only for zero-cloud operation" />
              <Row k="Models" v="Dhwani (XLS-R 300m + AASIST, ONNX INT8) · AASIST-L ×2 · Cloud XLS-R" n="MIT weights; ~1.2 GB Dhwani, sub-2 MB AASIST-L official" />
              <Row k="XAI" v="jitter · shimmer · phase continuity · watermark FFT" n="4096-pt FFT, 7.0–7.5 kHz pilot, ≥ 12× noise floor" />
              <Row k="Storage" v="SQLite local · optional Neon PostgreSQL" n="RAM-only ring buffer for live audio; hashes, not audio" />
              <Row k="Alerts" v="Telegram · Gmail SMTP · ntfy.sh · Fast2SMS · webhook" n="Optional; missing keys skipped at runtime" />
              <Row k="Ledger" v="SHA-256 PoW · Hyperledger Fabric (NBFLite) · IPFS" n="Mandatory external anchor, fail-closed by default" />
              <Row k="Cloud training" v="Google Colab free T4 · Kaggle T4×2 (notebooks 01–04)" n="Only for optional cloud classifier training" />
              <Row k="Deploy" v="Docker Compose · WSL2 · Oracle Always-Free ARM A1" n="Zero-cost path verified end-to-end" />
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="feasibility" n="03" title="Feasibility and Viability"
        lead="The system is not a paper design — it is implemented, tested and measurable. The project is engineering-feasible, legally viable and deployable at near-zero cost.">
        <div className="mt-1 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Automated tests" value="142" note="of 142 pytest cases green — anchors, gRPC parity, latency gates" />
          <StatCard label="Latency gate" value="2000 ms" note="fail-hard realtime budget per 3 s window, measured ~1.5–1.6 s" />
          <StatCard label="Latency profiles" value="2" note="realtime (default) + ensemble for forensic file analysis" />
          <StatCard label="Cloud spend" value="$0/mo" note="Oracle Always-Free ARM A1 (4 OCPU / 24 GB) or WSL2" />
        </div>

        <h3 className="mt-8 text-[15px] font-bold text-zinc-900">Feasibility analysis</h3>
        <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
          <Fact dot={GREEN} title="Technical" body="Working code across backend, frontend, SDK (REST + gRPC), watermark engine, PoW ledger and mandatory anchor — with byte-parity tests REST ↔ gRPC." />
          <Fact dot={GREEN} title="Data & licensing" body="MIT model weights; FLEURS and Common Voice (CC-BY-4.0 / CC0) bonafide data; self-generated spoof audio; ASVspoof used only as an external benchmark, never bundled." />
          <Fact dot={BRAND} title="Operational" body="One-command start (start_all.bat); local SQLite; free-tier Fabric + IPFS anchor; degradation requires explicitly disabling two safety flags." />
          <Fact dot={AMBER} title="Regulatory" body="DPDP Act 2023 posture, DoT Sanchar Saathi / Chakshu / DIP webhook for suspected fraud, 1930 / cybercrime.gov.in / RBI Sachet flow for victims." />
        </div>

        <h3 className="mt-8 text-[15px] font-bold text-zinc-900">Challenges, risks and strategies</h3>
        <div className="mt-4 grid gap-3">
          <RiskRow sev="High" label="CPU inference latency" strat="Separate latency profiles; fail-hard 2000 ms gate; ONNX INT8 with 2/4 CPU threads; dedicated latency-gate test." />
          <RiskRow sev="Medium" label="Codec-degraded phone audio" strat="G.711 A-law / μ-law and AMR-NB / AMR-WB round-trips added as training augmentations via ffmpeg." />
          <RiskRow sev="High" label="License boundaries" strat="All shipped components MIT / CC-BY-4.0 / CC0; XTTS-v2 cloning kept research-only (CPML-1.0); ASVspoof referenced, not redistributed." />
          <RiskRow sev="Medium" label="Anchor network availability" strat="Local PoW ledger always runs; external Fabric/IPFS anchor is mandatory and fail-closed — demo degrade only with both flags off." />
          <RiskRow sev="Medium" label="Privacy / DPDP exposure" strat="RAM-only ring buffer; no raw audio persisted; on-chain evidence stores hashes, never content; optional webhooks." />
          <RiskRow sev="Low" label="Edge-case languages" strat="7 Indic languages (hi, en, kn, ta, te, ml, mr) plus accent-invariant features; fully retrainable pipeline." />
        </div>
      </Section>

      <Section id="impacts" n="04" title="Impacts and Benefits"
        lead="VoiceShield maps cleanly onto the parties who actually face AI-voice fraud — and the impact is measurable across social, economic and environmental lines.">
        <Fig title="Who benefits — stakeholder map" caption="One platform, four deployment targets, all served by the same open engine.">
          <StakeholderSvg />
        </Fig>

        <div className="mt-2 grid gap-3 md:grid-cols-3">
          <ImpactBand tone="green" title="Social" body="Protects children and seniors from cloned-voice scams with role-aware thresholds (child ≥ 70%, adult ≥ 85%); keeps caregivers in the loop via instant guardian alerts." />
          <ImpactBand tone="amber" title="Economic" body="Cuts OTP-call and social-engineering losses for banks and telcos, slashes contact-center deepfake screening cost, and runs on free-tier infrastructure — no per-minute fees." />
          <ImpactBand tone="brand" title="Environmental" body="CPU-only inference with 2 CPU threads and a small ONNX footprint; zero-cloud default — measurable energy savings versus GPU SaaS CDNs." />
        </div>
      </Section>

      <Section id="references" n="05" title="Research and References"
        lead="Every model, dataset, codec standard, regulator and platform referenced in this document — with links. All third-party content is attributed per its license.">
        <Fig title="Open-source and reference ecosystem" caption="Color-coded by role — models, datasets, benchmarks, codecs, regulators and free-tier infrastructure.">
          <div className="grid gap-3 sm:grid-cols-2">
            <Cluster tone="brand" title="Models (MIT)" chips={['AASIST / AASIST-L · clovaai', 'Dhwani · ayush2635 (XLS-R + AASIST)', 'Cloud XLS-R fine-tune · ours']} />
            <Cluster tone="green" title="Datasets" chips={['Google FLEURS · CC-BY-4.0', 'Mozilla Common Voice · CC0 / CC-BY-4.0']} />
            <Cluster tone="purple" title="Benchmarks" chips={['ASVspoof 2019 LA · research-only', 'Pindrop Pulse · Resemble Detect · Truecaller AI']} />
            <Cluster tone="amber" title="Codecs" chips={['ITU-T G.711 · PSTN', '3GPP TS 26.190 · AMR-WB (VoLTE)', 'ITU-T G.722.2 · AMR-WB']} />
            <Cluster tone="red" title="Regulators & reporting" chips={['cybercrime.gov.in · 1930', 'MeitY · DPDP Act 2023 · IndiaAI', 'TRAI lawful-interception', 'DoT Sanchar Saathi / Chakshu / DIP']} />
            <Cluster tone="brand" title="Deploy & comms (free-tier)" chips={['Hyperledger Fabric · NBFLite', 'IPFS · kubo', 'Oracle Cloud Always-Free ARM A1', 'E2E Networks', 'Fast2SMS DLT-SMS']} />
          </div>
        </Fig>

        <h3 className="mt-8 text-[15px] font-bold text-zinc-900">Reference list</h3>
        <div className="card mt-4 overflow-hidden">
          <table className="w-full text-left text-[13.5px]">
            <thead>
              <tr className="border-b border-[#E4E4E7] text-[11px] uppercase tracking-wide text-zinc-500">
                <th className="px-5 py-3 font-semibold">Category</th>
                <th className="px-5 py-3 font-semibold">Source</th>
                <th className="px-5 py-3 font-semibold">Link</th>
              </tr>
            </thead>
            <tbody>
              <RefRow k="Models" v="AASIST / AASIST-L — countermeasure (MIT, ICASSP 2022)" h="https://github.com/clovaai/aasist" />
              <RefRow k="Models" v="Dhwani — Wav2Vec2 XLS-R 300m + AASIST (MIT weights)" h="https://huggingface.co/ayush2635/Dhwani-Multilingual-Deepfake-Audio-Detection-Model" />
              <RefRow k="Benchmark" v="ASVspoof 2019 LA — reference benchmark only (not bundled)" h="https://www.asvspoof.org" />
              <RefRow k="Benchmark" v="Pindrop Pulse — commercial voice-fraud detection" h="https://www.pindrop.com" />
              <RefRow k="Benchmark" v="Resemble Detect — commercial AI-audio deepfake API" h="https://www.resemble.ai" />
              <RefRow k="Benchmark" v="Truecaller AI — caller-ID and spam defence" h="https://www.truecaller.com" />
              <RefRow k="Dataset" v="Google FLEURS (CC-BY-4.0) — hi/en/kn/ta/te/ml/mr bonafide" h="https://huggingface.co/datasets/google/fleurs" />
              <RefRow k="Dataset" v="Mozilla Common Voice (CC0 ≤ v13; CC-BY-4.0 v14+)" h="https://commonvoice.mozilla.org" />
              <RefRow k="Codec" v="ITU-T G.711 — PSTN A-law / μ-law (64 kbps)" h="https://www.itu.int/rec/T-REC-G.711" />
              <RefRow k="Codec" v="3GPP TS 26.190 — AMR-WB (VoLTE HD voice)" h="https://www.3gpp.org/DynaReport/26190.htm" />
              <RefRow k="Codec" v="ITU-T G.722.2 — AMR-WB wideband speech coding" h="https://www.itu.int/rec/T-REC-G.722.2" />
              <RefRow k="Regulatory" v="National Cyber Crime Reporting Portal — 1930 / cybercrime.gov.in" h="https://cybercrime.gov.in" />
              <RefRow k="Regulatory" v="MeitY India — DPDP Act 2023, IndiaAI Mission" h="https://www.meity.gov.in" />
              <RefRow k="Regulatory" v="TRAI — lawful-interception and telecom regulation" h="https://www.trai.gov.in" />
              <RefRow k="Ledger" v="Hyperledger Fabric — MeitY National Blockchain Framework (NBFLite)" h="https://www.hyperledger.org/projects/fabric" />
              <RefRow k="Ledger" v="IPFS — kubo implementation" h="https://github.com/ipfs/kubo" />
              <RefRow k="Infra" v="Oracle Cloud Always Free — ARM A1 (4 OCPU / 24 GB)" h="https://www.oracle.com/in/cloud/free/" />
              <RefRow k="Infra" v="E2E Networks — India cloud infrastructure" h="https://www.e2enetworks.com" />
              <RefRow k="Comms" v="Fast2SMS — DLT-registered Indian SMS gateway" h="https://www.fast2sms.com" />
            </tbody>
          </table>
        </div>

        <p className="mt-4 text-[12.5px] leading-relaxed text-zinc-500">
          Cost framing is intentionally qualitative: the verified zero-cost path is Oracle
          Cloud Always-Free ARM A1 plus WSL2; AWS/GCP, E2E Networks and Fast2SMS are listed
          as pay-as-you-go / DLT-registered options without quoted rates. As on the
          Dashboard, scores are synthetic; “≥ 35%” denotes the frontend “elevated suspicion”
          risk band, distinct from the role-aware thresholds (child ≥ 70%, adult ≥ 85%).
        </p>
      </Section>
    </article>
  )
}

/* ------------------------------ Layout helpers ----------------------------- */

function Section({ id, n, title, lead, children }: { id: string; n: string; title: string; lead: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-36">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[12px] font-bold text-[#2563EB]">{n}</span>
        <h2 className="font-serif text-[26px] font-bold tracking-tight text-zinc-900">{title}</h2>
      </div>
      <p className="mt-2 leading-relaxed text-zinc-600">{lead}</p>
      {children}
      <div className="my-10 border-b border-[#E4E4E7]" />
    </section>
  )
}

function Fig({ title, caption, children }: { title: string; caption?: string; children: ReactNode }) {
  return (
    <div className="card mt-6 overflow-hidden">
      <div className="border-b border-[#E4E4E7] bg-[#FAF8F5] px-5 py-3.5">
        <h3 className="text-[13.5px] font-bold text-zinc-900">{title}</h3>
        {caption && <p className="mt-0.5 text-[12px] text-zinc-500">{caption}</p>}
      </div>
      <div className="overflow-x-auto p-4">
        <div className="min-w-[560px]">{children}</div>
      </div>
    </div>
  )
}

function Fact({ dot, title, body }: { dot: string; title: string; body: string }) {
  return (
    <div className="card flex gap-3 p-4">
      <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: dot }} />
      <div>
        <div className="text-[13.5px] font-bold text-zinc-900">{title}</div>
        <p className="mt-0.5 text-[13px] leading-relaxed text-zinc-600">{body}</p>
      </div>
    </div>
  )
}

function VsRow({ aspect, vs }: { aspect: string; vs: string }) {
  return (
    <div className="card grid gap-1 p-4 sm:grid-cols-[220px_1fr] sm:gap-4">
      <div className="text-[13.5px] font-bold text-zinc-900">{aspect}</div>
      <p className="text-[13px] leading-relaxed text-zinc-600">{vs}</p>
    </div>
  )
}

function Row({ k, v, n }: { k: string; v: string; n: string }) {
  return (
    <tr className="border-b border-[#F1EEE9] align-top last:border-0 hover:bg-[#FAF8F5]">
      <td className="px-5 py-3 font-semibold text-zinc-900">{k}</td>
      <td className="px-5 py-3 text-[12.5px] text-zinc-700">{v}</td>
      <td className="px-5 py-3 text-[12.5px] text-zinc-500">{n}</td>
    </tr>
  )
}

function RefRow({ k, v, h }: { k: string; v: string; h: string }) {
  return (
    <tr className="border-b border-[#F1EEE9] align-top last:border-0 hover:bg-[#FAF8F5]">
      <td className="whitespace-nowrap px-5 py-3 align-middle text-[12.5px] font-semibold text-zinc-900">{k}</td>
      <td className="px-5 py-3 text-[12.5px] text-zinc-700">{v}</td>
      <td className="px-5 py-3">
        <a className="break-all text-[12.5px] text-[#2563EB] underline decoration-[#DBEAFE] underline-offset-2 hover:decoration-[#2563EB]" href={h} target="_blank" rel="noreferrer">
          {h}
        </a>
      </td>
    </tr>
  )
}

function RiskRow({ sev, label, strat }: { sev: string; label: string; strat: string }) {
  const sevColor = sev === 'High' ? RED : sev === 'Medium' ? AMBER : GREEN
  return (
    <div className="card grid gap-1.5 p-4 sm:grid-cols-[140px_180px_1fr] sm:gap-4 sm:items-center">
      <span className="w-fit rounded-full px-2.5 py-0.5 text-[11px] font-bold text-white" style={{ background: sevColor }}>
        {sev}
      </span>
      <div className="text-[13.5px] font-bold text-zinc-900">{label}</div>
      <p className="text-[13px] leading-relaxed text-zinc-600">{strat}</p>
    </div>
  )
}

function ImpactBand({ tone, title, body }: { tone: 'green' | 'amber' | 'brand'; title: string; body: string }) {
  const dot = tone === 'green' ? GREEN : tone === 'amber' ? AMBER : BRAND
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: dot }} />
        <h3 className="text-[15px] font-bold text-zinc-900">{title}</h3>
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-zinc-600">{body}</p>
    </div>
  )
}

function Cluster({ tone, title, chips }: { tone: 'brand' | 'green' | 'purple' | 'amber' | 'red'; title: string; chips: string[] }) {
  const fill = tone === 'brand' ? BLUE50 : tone === 'green' ? GREEN50 : tone === 'purple' ? VIOLET50 : tone === 'amber' ? AMBER50 : RED50
  const dot = tone === 'brand' ? BRAND : tone === 'green' ? GREEN : tone === 'purple' ? PURPLE : tone === 'amber' ? AMBER : RED
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: dot }} />
        <h3 className="text-[13.5px] font-bold text-zinc-900">{title}</h3>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {chips.map((c) => (
          <span key={c} className="rounded-full px-2.5 py-1 text-[11.5px] font-medium text-zinc-700" style={{ background: fill }}>
            {c}
          </span>
        ))}
      </div>
    </div>
  )
}

function StatCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="card p-5">
      <div className="text-[11px] font-bold uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 font-serif text-[26px] font-bold tracking-tight tabular-nums text-zinc-900">{value}</div>
      <div className="mt-0.5 text-[12.5px] text-zinc-500">{note}</div>
    </div>
  )
}

function PipelineTimeline({ steps }: { steps: ReadonlyArray<{ n: string; title: string; sub: string; tone: 'brand' | 'red' }> }) {
  return (
    <div>
      {steps.map((s, i) => (
        <div key={s.n} className="flex gap-3.5">
          <div className="flex flex-col items-center">
            <span
              className="z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-bold text-white"
              style={{ background: s.tone === 'red' ? RED : BRAND }}
            >
              {s.n}
            </span>
            {i < steps.length - 1 && <span className="w-px flex-1 bg-[#E4E4E7]" />}
          </div>
          <div className="card mb-5 min-w-0 flex-1 p-4">
            <div className="text-[14px] font-bold text-zinc-900">{s.title}</div>
            <p className="mt-0.5 text-[12.5px] leading-relaxed text-zinc-600">{s.sub}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ------------------------------ Infographic SVGs ---------------------------- */

function ArchSvg() {
  return (
    <svg viewBox="0 0 720 462" className="block h-auto w-full" role="img" aria-label="System architecture — data plane, engine, evidence ledger">
      <rect x="14" y="50" width="692" height="96" rx="10" fill={CREAM} stroke={LINE} />
      <rect x="14" y="178" width="692" height="164" rx="10" fill={CREAM} stroke={LINE} />
      <rect x="14" y="374" width="692" height="70" rx="10" fill={CREAM} stroke={LINE} />

      <text x="30" y="35" fontSize="11" fontWeight="700" fill={MUTED} fontFamily="ui-monospace, monospace">1 · DATA PLANE</text>
      <text x="30" y="163" fontSize="11" fontWeight="700" fill={MUTED} fontFamily="ui-monospace, monospace">2 · ENGINE</text>
      <text x="30" y="359" fontSize="11" fontWeight="700" fill={MUTED} fontFamily="ui-monospace, monospace">3 · EVIDENCE LEDGER</text>

      <g>
        <rect x="16" y="64" width="160" height="58" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="16" y="64" width="160" height="3" rx="1.5" fill={BRAND} />
        <text x="28" y="86" fontSize="12.5" fontWeight="700" fill={INK}>WebSocket</text>
        <text x="28" y="104" fontSize="10.5" fill={MUTED}>live PCM 16 kHz</text>
        <rect x="188" y="64" width="160" height="58" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="188" y="64" width="160" height="3" rx="1.5" fill={BRAND} />
        <text x="200" y="86" fontSize="12.5" fontWeight="700" fill={INK}>REST /api/*</text>
        <text x="200" y="104" fontSize="10.5" fill={MUTED}>analyze · detect</text>
        <rect x="360" y="64" width="160" height="58" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="360" y="64" width="160" height="3" rx="1.5" fill={BRAND} />
        <text x="372" y="86" fontSize="12.5" fontWeight="700" fill={INK}>gRPC :50051</text>
        <text x="372" y="104" fontSize="10.5" fill={MUTED}>SDK streaming</text>
        <rect x="532" y="64" width="160" height="58" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="532" y="64" width="160" height="3" rx="1.5" fill={BRAND} />
        <text x="544" y="86" fontSize="12.5" fontWeight="700" fill={INK}>Python SDK</text>
        <text x="544" y="104" fontSize="10.5" fill={MUTED}>client + async</text>
      </g>

      <line x1="140" y1="146" x2="140" y2="186" stroke={LINE} strokeWidth="1.5" />
      <path d="M140 190 l-4 -6 h8 z" fill={MUTED} />

      <g>
        <rect x="16" y="196" width="250" height="130" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="16" y="196" width="250" height="3" rx="1.5" fill={BRAND} />
        <text x="28" y="219" fontSize="12.5" fontWeight="700" fill={INK}>Model ensemble</text>
        <circle cx="24" cy="236" r="2.5" fill={BRAND} />
        <text x="34" y="240" fontSize="11" fill="#52525B">Dhwani — XLS-R 300m + AASIST</text>
        <circle cx="24" cy="252" r="2.5" fill={BRAND} />
        <text x="34" y="256" fontSize="11" fill="#52525B">AASIST-L official (clovaai)</text>
        <circle cx="24" cy="268" r="2.5" fill={BRAND} />
        <text x="34" y="272" fontSize="11" fill="#52525B">AASIST-L local fine-tune</text>
        <circle cx="24" cy="284" r="2.5" fill={BRAND} />
        <text x="34" y="288" fontSize="11" fill="#52525B">Cloud XLS-R cross-lingual</text>

        <rect x="282" y="196" width="250" height="130" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="282" y="196" width="250" height="3" rx="1.5" fill={PURPLE} />
        <text x="294" y="219" fontSize="12.5" fontWeight="700" fill={INK}>XAI prosody layer</text>
        <circle cx="290" cy="236" r="2.5" fill={PURPLE} />
        <text x="300" y="240" fontSize="11" fill="#52525B">jitter · shimmer</text>
        <circle cx="290" cy="252" r="2.5" fill={PURPLE} />
        <text x="300" y="256" fontSize="11" fill="#52525B">phase continuity · pitch</text>
        <circle cx="290" cy="268" r="2.5" fill={PURPLE} />
        <text x="300" y="272" fontSize="11" fill="#52525B">noise-floor dropouts</text>
        <circle cx="290" cy="284" r="2.5" fill={PURPLE} />
        <text x="300" y="288" fontSize="11" fill="#52525B">speaker voice-print</text>

        <rect x="548" y="196" width="158" height="130" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="548" y="196" width="158" height="3" rx="1.5" fill={GREEN} />
        <text x="560" y="219" fontSize="12.5" fontWeight="700" fill={INK}>Fusion</text>
        <text x="560" y="256" fontSize="14" fontWeight="700" fill={INK}>0.7 × model</text>
        <text x="560" y="278" fontSize="14" fontWeight="700" fill={INK}>0.3 × XAI</text>
        <text x="560" y="308" fontSize="10.5" fill={MUTED}>→ verdict</text>

        <line x1="266" y1="260" x2="278" y2="260" stroke={MUTED} strokeWidth="1.5" />
        <path d="M282 260 l-6 -4 v8 z" fill={MUTED} />
        <line x1="532" y1="260" x2="545" y2="260" stroke={MUTED} strokeWidth="1.5" />
        <path d="M548 260 l-6 -4 v8 z" fill={MUTED} />
      </g>

      <line x1="560" y1="342" x2="560" y2="370" stroke={LINE} strokeWidth="1.5" />
      <path d="M560 374 l-4 -6 h8 z" fill={MUTED} />

      <g>
        <rect x="16" y="384" width="210" height="46" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="16" y="384" width="210" height="3" rx="1.5" fill={BRAND} />
        <text x="121" y="412" fontSize="12" fontWeight="700" fill={INK} textAnchor="middle">SHA-256 + Merkle root</text>

        <line x1="226" y1="407" x2="238" y2="407" stroke={MUTED} strokeWidth="1.5" />
        <path d="M242 407 l-6 -4 v8 z" fill={MUTED} />

        <rect x="242" y="384" width="210" height="46" rx="8" fill="#ffffff" stroke={LINE} />
        <rect x="242" y="384" width="210" height="3" rx="1.5" fill={BRAND} />
        <text x="347" y="412" fontSize="12" fontWeight="700" fill={INK} textAnchor="middle">Local PoW ledger</text>

        <line x1="452" y1="407" x2="464" y2="407" stroke={RED} strokeWidth="1.5" />
        <path d="M468 407 l-6 -4 v8 z" fill={RED} />

        <rect x="468" y="384" width="238" height="46" rx="8" fill={RED50} stroke={LINE} />
        <rect x="468" y="384" width="238" height="3" rx="1.5" fill={RED} />
        <text x="587" y="405" fontSize="11.5" fontWeight="700" fill={INK} textAnchor="middle">Fabric + IPFS anchor</text>
        <text x="587" y="421" fontSize="9.5" fontWeight="700" fill={RED} textAnchor="middle" letterSpacing="0.08em">MANDATORY · FAIL-CLOSED</text>
      </g>
    </svg>
  )
}

function LifecycleSvg() {
  const nodes = [
    { t: 'PCM 16 kHz', s: 'mono int16' },
    { t: 'features', s: 'acoustic-prosody' },
    { t: 'fused verdict', s: 'risk band' },
    { t: 'SHA-256', s: 'Merkle root' },
    { t: 'local PoW', s: 'ledger' },
    { t: 'Fabric + IPFS', s: 'anchor · mandatory' },
  ] as const
  return (
    <svg viewBox="0 0 720 150" className="block h-auto w-full" role="img" aria-label="Evidence lifecycle — hash to mandatory anchor">
      {nodes.map((n, i) => {
        const x = 18 + i * 116
        const last = i === nodes.length - 1
        return (
          <g key={n.t}>
            <rect x={x} y="24" width="104" height="96" rx="10" fill={last ? RED50 : '#ffffff'} stroke={LINE} />
            <rect x={x} y="24" width="104" height="3" rx="1.5" fill={last ? RED : BRAND} />
            <circle cx={x + 52} cy="44" r="12" fill={BLUE50} />
            <circle cx={x + 52} cy="44" r="4.5" fill={last ? RED : BRAND} />
            <text x={x + 52} y="74" fontSize="11.5" fontWeight="700" fill={INK} textAnchor="middle">{n.t}</text>
            <text x={x + 52} y="90" fontSize="9.5" fill={MUTED} textAnchor="middle">{n.s}</text>
            {!last && (
              <g>
                <line x1={x + 104} y1="44" x2={x + 112} y2="44" stroke={MUTED} strokeWidth="1.5" />
                <path d={`M${x + 114} 44 l-6 -4 v8 z`} fill={MUTED} />
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}

function StakeholderSvg() {
  return (
    <svg viewBox="0 0 720 300" className="block h-auto w-full" role="img" aria-label="Stakeholder map — telco, banks, contact centers, parents">
      <circle cx="360" cy="150" r="84" fill="none" stroke={LINE} strokeWidth="1.5" strokeDasharray="4 6" />

      <line x1="360" y1="150" x2="160" y2="59" stroke={BRAND} strokeWidth="1.5" />
      <line x1="360" y1="150" x2="560" y2="59" stroke={GREEN} strokeWidth="1.5" />
      <line x1="360" y1="150" x2="160" y2="250" stroke={PURPLE} strokeWidth="1.5" />
      <line x1="360" y1="150" x2="560" y2="250" stroke={AMBER} strokeWidth="1.5" />

      <circle cx="360" cy="150" r="42" fill={BRAND} />
      <text x="360" y="146" fontSize="14" fontWeight="700" fill="#ffffff" textAnchor="middle">VoiceShield</text>
      <text x="360" y="164" fontSize="9.5" fill="#DBEAFE" textAnchor="middle" letterSpacing="0.1em">AI INTEGRITY</text>

      <g>
        <rect x="85" y="28" width="150" height="62" rx="10" fill="#ffffff" stroke={LINE} />
        <rect x="85" y="28" width="150" height="3" rx="1.5" fill={BRAND} />
        <text x="160" y="62" fontSize="11" fontWeight="700" fill={INK} textAnchor="middle">Telco / network</text>
        <text x="160" y="79" fontSize="9.5" fill={MUTED} textAnchor="middle">OTP + spam defence</text>
      </g>

      <g>
        <rect x="485" y="28" width="150" height="62" rx="10" fill="#ffffff" stroke={LINE} />
        <rect x="485" y="28" width="150" height="3" rx="1.5" fill={GREEN} />
        <text x="560" y="62" fontSize="11" fontWeight="700" fill={INK} textAnchor="middle">Banks</text>
        <text x="560" y="79" fontSize="9.5" fill={MUTED} textAnchor="middle">voice-AI fraud guard</text>
      </g>

        <rect x="85" y="219" width="150" height="62" rx="10" fill="#ffffff" stroke={LINE} />
        <rect x="85" y="219" width="150" height="3" rx="1.5" fill={PURPLE} />
        <text x="160" y="253" fontSize="11" fontWeight="700" fill={INK} textAnchor="middle">Contact centers</text>
        <text x="160" y="270" fontSize="9.5" fill={MUTED} textAnchor="middle">deepfake screening</text>

      <g>
        <rect x="485" y="219" width="150" height="62" rx="10" fill="#ffffff" stroke={LINE} />
        <rect x="485" y="219" width="150" height="3" rx="1.5" fill={AMBER} />
        <text x="560" y="253" fontSize="11" fontWeight="700" fill={INK} textAnchor="middle">Parents · Child Shield</text>
        <text x="560" y="270" fontSize="9.5" fill={MUTED} textAnchor="middle">guardian alert ≥ 70%</text>
      </g>
    </svg>
  )
}