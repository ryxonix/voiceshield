import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type Lang = 'en' | 'hi' | 'kn'

export const LANGS: Lang[] = ['en', 'hi', 'kn']
export const LANG_NAMES: Record<Lang, string> = { en: 'English', hi: 'हिन्दी', kn: 'ಕನ್ನಡ' }

/**
 * Contextual translations. Technical terms that have no natural equivalent in
 * everyday Hindi/Kannada (XAI, AASIST-L, watermark, score, risk, threshold,
 * jitter/shimmer, spectrogram, hash, ledger, MFA …) are intentionally kept in
 * Latin script — translating them word-for-word makes them harder to
 * understand, not easier.
 */

const hi: Record<string, string> = {
  /* ── Top bar / sidebar ─────────────────────────────────────────────── */
  'Live Monitor': 'लाइव मॉनिटर',
  Incidents: 'घटनाएँ',
  Forensics: 'फोरेंसिक्स',
  Monitoring: 'निगरानी',
  Overview: 'अवलोकन',
  'Live call monitor': 'लाइव कॉल मॉनिटर',
  'Risk & incidents': 'जोखिम और घटनाएँ',
  'Incident log': 'घटना लॉग',
  'Session forensics': 'सत्र फोरेंसिक्स',
  'File analysis': 'फ़ाइल विश्लेषण',
  Identity: 'पहचान',
  'Speaker enrollment': 'स्पीकर पंजीकरण',

  /* ── Footer ────────────────────────────────────────────────────────── */
  'VoiceShield AI — real-time voice integrity verification · AASIST-L inference, prosodic XAI, watermark verification · API served from {base}':
    'VoiceShield AI — रियल-टाइम आवाज़ पहचान जाँच · AASIST-L inference, prosodic XAI, watermark verification · API {base} से उपलब्ध',
  'this origin': 'इस ओरिजिन से',

  /* ── Dashboard: header ─────────────────────────────────────────────── */
  'Back to overview': 'अवलोकन पर वापस जाएँ',
  'Start session': 'सत्र शुरू करें',
  'End session': 'सत्र समाप्त करें',
  'Voice integrity, verified in real time.': 'आवाज़ की असली पहचान, रियल-टाइम में पुख्ता।',
  'VoiceShield analyzes live call audio for AI-generated speech — acoustic model, prosodic evidence and enterprise watermarking, fused into a single actionable score.':
    'VoiceShield कॉल के लाइव ऑडियो में AI-जनित भाषण की जाँच करता है — एकॉस्टिक मॉडल, प्रोज़ोडिक साक्ष्य और एंटरप्राइज़ वॉटरमार्किंग, सब मिलाकर एक actionable स्कोर।',
  'View forensics': 'फोरेंसिक्स देखें',
  'Start live session': 'लाइव सत्र शुरू करें',

  /* ── Dashboard: intro paragraphs ───────────────────────────────────── */
  'Every 300 milliseconds, VoiceShield extracts a fresh window from the call stream and runs it through three independent checks: a graph-attention acoustic model (AASIST-L), sub-phonemic prosodic analysis — jitter, shimmer and spectral phase continuity — and a watermark verifier that recognizes authorized enterprise callers instantly.':
    'हर 300 मिलीसेकंड पर VoiceShield कॉल स्ट्रीम से नई विंडो निकालकर उसे तीन स्वतंत्र जाँचों से गुज़ारता है: ग्राफ़-अटेंशन एकॉस्टिक मॉडल (AASIST-L), सब-फ़ोनीमिक प्रोज़ोडिक विश्लेषण — जिटर, शिमर और स्पेक्ट्रल फ़ेज़ निरंतरता — और वॉटरमार्क वेरिफ़ायर जो अधिकृत एंटरप्राइज़ कॉलर को तुरंत पहचान लेता है।',
  'The results are fused into a single synthetic score. Crossings trigger role-aware mitigation: 70% for calls involving children, 85% for adults, with alerts dispatched to Telegram, email, SMS and webhooks, and an I4C-ready forensic PDF generated for every incident.':
    'इन्हीं नतीजों को एक ही synthetic score में मिलाया जाता है। सीमा पार होते ही रोल-अवेयर उपाय लागू होते हैं: बच्चों वाली कॉल के लिए 70%, वयस्कों के लिए 85%। टेलीग्राम, ईमेल, एसएमएस और वेबहुक पर अलर्ट जाते हैं और हर घटना की I4C-रेडी फोरेंसिक PDF बनती है।',

  /* ── Dashboard: stat cards ─────────────────────────────────────────── */
  'Detection latency': 'डिटेक्शन विलंबता',
  'Window cadence': 'विंडो गति',
  Languages: 'भाषाएँ',
  'per-window design budget, ONNX, 2 CPU threads': 'प्रति-विंडो डिज़ाइन बजट, ONNX, 2 CPU थ्रेड',
  'Dhwani window / hop · 300 ms / 100 ms legacy fallback': 'Dhwani विंडो / हॉप · 300 ms / 100 ms लेगेसी फ़ॉलबैक',
  'accent-invariant features': 'उच्चारण-स्वतंत्र विशेषताएँ',

  /* ── Dashboard: pipeline explainer ─────────────────────────────────── */
  'How a window is scored': 'विंडो का स्कोर कैसे बनता है',
  'Watermark check': 'वॉटरमार्क जाँच',
  'A 4096-point FFT scans 7.0–7.5 kHz for the enterprise pilot tone. A verified caller short-circuits the pipeline with a score of zero.':
    '4096-बिंदु FFT एंटरप्राइज़ पायलट टोन के लिए 7.0–7.5 kHz स्कैन करता है। सत्यापित कॉलर का स्कोर सीधे शून्य कर दिया जाता है।',
  'Acoustic model': 'एकॉस्टिक मॉडल',
  'AASIST-L — a spectro-temporal graph attention network — classifies synthesis artifacts in the log-mel spectrogram.':
    'AASIST-L — एक स्पेक्ट्रो-टेम्पोरल ग्राफ़ अटेंशन नेटवर्क — log-mel स्पेक्ट्रोग्राम में संश्लेषण की कलाकृतियाँ पहचानता है।',
  'Prosodic XAI': 'प्रोज़ोडिक XAI',
  'Glottal-cycle jitter and shimmer plus inter-frame phase continuity expose the unnatural regularity of neural speech.':
    'ग्लोटल-साइकल जिटर, शिमर और इंटर-फ्रेम फ़ेज़ निरंतरता न्यूरल भाषण की अप्राकृतिक एकरसता उजागर करते हैं।',

  /* ── Dashboard: threshold reference ────────────────────────────────── */
  'Mitigation thresholds': 'उपायों की सीमाएँ (थ्रेशोल्ड)',
  Scenario: 'परिदृश्य',
  Trigger: 'ट्रिगर',
  Response: 'प्रतिक्रिया',
  'Child-safety calls': 'बच्चों से जुड़ी कॉलें',
  'Score ≥ 70%': 'स्कोर ≥ 70%',
  'Immediate guardian alert, block sensitive actions': 'अभिभावक को तुरंत अलर्ट, संवेदनशील कार्रवाइयाँ रोकें',
  'Adult / enterprise calls': 'वयस्क / एंटरप्राइज़ कॉलें',
  'Score ≥ 85%': 'स्कोर ≥ 85%',
  'Hold transaction, require call-back or MFA': 'लेन-देन रोकें, कॉल-बैक या MFA माँगें',
  'Elevated suspicion': 'बढ़ा संदेह',
  'Score ≥ 35%': 'स्कोर ≥ 35%',
  'Warning banner, recommend secondary verification': 'चेतावनी बैनर, दूसरे स्तर का सत्यापन सुझाएँ',
  'Enterprise watermark': 'एंटरप्राइज़ वॉटरमार्क',
  'Pilot tone 12× noise floor': 'Pilot tone 12× noise floor',
  'Verified caller — score forced to 0.0': 'सत्यापित कॉलर — स्कोर 0.0 कर दिया गया',

  /* ── Dashboard: quick check ────────────────────────────────────────── */
  'Quick check': 'त्वरित जाँच',
  'Run a 30-second check from this page — or open the': 'इसी पेज से 30 सेकंड की जाँच चलाएँ — या खोलें',
  'full live monitor': 'पूरा लाइव मॉनिटर',

  /* ── Dashboard: live panel ─────────────────────────────────────────── */
  'Session setup': 'सत्र सेटअप',
  Role: 'भूमिका',
  Language: 'भाषा',
  'Enrolled speaker (optional)': 'पंजीकृत स्पीकर (वैकल्पिक)',
  'e.g. manager_rajesh': 'जैसे manager_rajesh',
  'Shielded — mic paused': 'शील्ड सक्रिय — माइक रोका गया',
  'Microphone live': 'माइक चालू',
  Connected: 'कनेक्टेड',
  Offline: 'ऑफ़लाइन',
  'Score timeline': 'स्कोर टाइमलाइन',
  'peak {p}% · {n} windows · latency {l} ms': 'पीक {p}% · {n} विंडो · विलंबता {l} ms',
  'Model P': 'Model P',
  'XAI risk': 'XAI risk',
  Verdict: 'वर्डिक्ट',
  'NF drops': 'NF drops',
  'XAI breakdown': 'XAI विश्लेषण',
  'Latest window': 'नवीनतम विंडो',
  'Speaker mismatch — possible impersonation.': 'स्पीकर मेल नहीं खाता — नक़ल हो सकती है।',
  'Consistent with the enrolled voice.': 'पंजीकृत आवाज़ से मेल खाता है।',
  Mitigation: 'उपाय',
  'Role-aware response (child ≥ 70% / adult ≥ 85%)': 'रोल-अवेयर प्रतिक्रिया (बच्चा ≥ 70% / वयस्क ≥ 85%)',
  'Monitoring live — no mitigation triggered yet.': 'लाइव निगरानी चल रही है — अभी कोई उपाय लागू नहीं हुआ।',
  'Start a session to see role-aware mitigation.': 'रोल-अवेयर उपाय देखने के लिए सत्र शुरू करें।',

  /* ── Dashboard: verdicts / roles ───────────────────────────────────── */
  'v.bonafide': 'असली आवाज़',
  'v.synthetic': 'अशुद्ध/कृत्रिम',
  'v.verified_enterprise': 'सत्यापित एंटरप्राइज़',
  'v.suspicious': 'संदिग्ध',
  'v.synthetic+speaker_mismatch': 'अशुद्ध + स्पीकर बेमेल',
  'role.adult': 'वयस्क',
  'role.child': 'बच्चा',

  /* ── Live hook errors ──────────────────────────────────────────────── */
  'WebSocket error — is the backend running on :8000?': 'WebSocket त्रुटि — क्या बैकएंड :8000 पर चल रहा है?',
  'Microphone context could not start — allow mic permission and retry.': 'माइक शुरू नहीं हो सका — माइक की अनुमति दें और फिर कोशिश करें।',
  'Microphone unavailable — {e}': 'माइक उपलब्ध नहीं — {e}',
  'Audio init failed — {e}': 'ऑडियो शुरू करने में विफल — {e}',

  /* ── Incidents ─────────────────────────────────────────────────────── */
  'Threshold crossings are recorded as incidents with severity, triggers and a forensic I4C report. Acknowledge incidents once they’ve been reviewed.':
    'सीमा पार होने की घटनाएँ गंभीरता, ट्रिगर और फोरेंसिक I4C रिपोर्ट के साथ दर्ज होती हैं। समीक्षा के बाद घटनाओं को स्वीकार करें।',
  'Loading…': 'लोड हो रहा है…',
  Refresh: 'रीफ़्रेश',
  'No incidents recorded yet. Run a live monitor session or upload a recording to see incidents here.':
    'अभी कोई घटना दर्ज नहीं है। यहाँ घटनाएँ देखने के लिए लाइव मॉनिटर सत्र चलाएँ या कोई रिकॉर्डिंग अपलोड करें।',
  'sev.critical': 'गंभीर',
  'sev.high': 'उच्च',
  'sev.medium': 'मध्यम',
  'sev.low': 'कम',
  'I4C report': 'I4C report',
  Acknowledged: 'स्वीकृत',
  Acknowledge: 'स्वीकारें',
  'Ack…': 'स्वीकार…',
  'role {r}': 'रोल {r}',
  'lang {l}': 'lang {l}',
  'speaker mismatch': 'स्पीकर बेमेल',
  'triggers: {t}': 'ट्रिगर: {t}',

  /* ── Reports ───────────────────────────────────────────────────────── */
  'Reconstruct any monitored call window-by-window, run batch analysis on recordings, or enroll trusted voices for cross-session identity checks.':
    'किसी भी निगरानी की गई कॉल को विंडो-दर-विंडो रीकंस्ट्रक्ट करें, रिकॉर्डिंग का बैच विश्लेषण चलाएँ, या क्रॉस-सेशन पहचान जाँच के लिए भरोसेमंद आवाज़ें पंजीकृत करें।',
  'No sessions recorded yet — run a live monitor session first.':
    'अभी कोई सत्र दर्ज नहीं है — पहले लाइव मॉनिटर सत्र चलाएँ।',
  'Window timeline': 'विंडो टाइमलाइन',
  'Download report': 'रिपोर्ट डाउनलोड करें',
  Score: 'स्कोर',
  'No windows persisted for this session.': 'इस सत्र के लिए कोई विंडो सहेजी नहीं गई।',
  'Select a session on the left to reconstruct its full per-window analysis timeline.':
    'पूरा विंडो-वार विश्लेषण टाइमलाइन देखने के लिए बाईं ओर कोई सत्र चुनें।',

  /* ── Reports: blockchain ───────────────────────────────────────────── */
  'Report blockchain': 'रिपोर्ट blockchain',
  'Every forensic PDF is anchored via SHA-256 + proof-of-work to an append-only hash chain. Each block commits the report hash and a Merkle root of the session score timeline, linked to its predecessor — so any modification after the fact is cryptographically detectable.':
    'हर फोरेंसिक PDF SHA-256 + proof-of-work की मदद से append-only hash chain में दर्ज होती है। हर ब्लॉक रिपोर्ट का हैश और सत्र स्कोर टाइमलाइन का Merkle root सहेजता है, जो पिछले ब्लॉक से जुड़ा होता है — इसलिए बाद में कोई भी बदलाव क्रिप्टोग्राफ़िक रूप से पकड़ा जा सकता है।',
  'chain OK · height {h}': 'चेन ठीक · ऊँचाई {h}',
  'chain INVALID': 'चेन अमान्य',
  Height: 'ऊँचाई',
  Difficulty: 'डिफ़िकल्टी',
  'No reports anchored yet — download a forensic report to mint the genesis block.':
    'अभी कोई रिपोर्ट दर्ज नहीं — genesis ब्लॉक बनाने के लिए कोई फोरेंसिक रिपोर्ट डाउनलोड करें।',
  'Verifying…': 'सत्यापन हो रहा है…',
  Verify: 'सत्यापित करें',
  'verification failed': 'सत्यापन विफल',
  'error.verification failed': 'सत्यापन विफल',
  'On-disk report hash matches the anchored hash; chain linkage intact.':
    'डिस्क पर मौजूद रिपोर्ट का हैश दर्ज हैश से मेल खाता है; चेन की कड़ियाँ सही हैं।',

  /* ── Reports: analyze ──────────────────────────────────────────────── */
  'Analyze a recording': 'रिकॉर्डिंग का विश्लेषण',
  'Upload a call recording (wav, mp3, flac). VoiceShield resamples to 16 kHz, slides a window across the file (3 s window / 1 s hop with Dhwani; 300 ms / 100 ms legacy fallback), and returns the full per-window XAI breakdown.':
    'कॉल रिकॉर्डिंग अपलोड करें (wav, mp3, flac)। VoiceShield उसे 16 kHz पर रीसैंपल करता है, फ़ाइल पर एक विंडो चलाता है (Dhwani के साथ 3 s विंडो / 1 s हॉप; अन्यथा 300 ms / 100 ms लेगेसी), और हर विंडो का पूरा XAI विश्लेषण देता है।',
  'Analyzing…': 'विश्लेषण हो रहा है…',
  Analyze: 'विश्लेषण करें',
  'error.Analysis failed — is the backend reachable?': 'विश्लेषण विफल — क्या बैकएंड उपलब्ध है?',
  'Peak score': 'पीक स्कोर',
  'Risk band': 'रिस्क बैंड',
  'Windows analyzed': 'विश्लेषित विंडो',

  /* ── Reports: speakers ─────────────────────────────────────────────── */
  'Enroll a trusted speaker': 'भरोसेमंद स्पीकर पंजीकृत करें',
  'Upload about ten seconds of genuine speech per person. Live sessions tagged with this label are compared against the stored embedding; a mismatch adds +0.15 to the fused risk score.':
    'हर व्यक्ति की लगभग दस सेकंड की असली आवाज़ अपलोड करें। इस लेबल वाले लाइव सत्रों की तुलना सहेजे गए embedding से होती है; बेमेल होने पर fused risk score में +0.15 जुड़ता है।',
  'Speaker label': 'स्पीकर लेबल',
  Enroll: 'पंजीकरण',
  'msg.Provide a label and a genuine voice sample.': 'लेबल और असली आवाज़ का नमूना दें।',
  'msg.Enrolled "{label}" — cross-session consistency checks are now active for this voice.':
    '"{label}" पंजीकृत हो गया — इस आवाज़ के लिए क्रॉस-सेशन स्थिरता जाँच अब सक्रिय है।',
  'msg.Error: {d}': 'त्रुटि: {d}',

  /* ── RiskGauge / Radar ─────────────────────────────────────────────── */
  'SYNTHETIC SCORE': 'सिंथेटिक स्कोर',
  '{band} risk': '{band} रिस्क',
  'band.low': 'कम',
  'band.medium': 'मध्यम',
  'band.high': 'उच्च',
  'band.critical': 'गंभीर',
  'Model P(synthetic)': 'Model P(synthetic)',
  'XAI risk (fused)': 'XAI risk (fused)',
  'Phase discontinuity': 'फ़ेज़ अस्थिरता',
  Jitter: 'जिटर',
  Shimmer: 'शिमर',
  'Pitch Stability': 'पिच स्थिरता',
  'Phase Continuity': 'फ़ेज़ निरंतरता',
  'NF Dropouts': 'NF Dropouts',

  /* ── ShieldBanner ──────────────────────────────────────────────────── */
  'Call paused': 'कॉल रोक दी गई',
  'A potential AI-cloned voice was detected. A trusted guardian should verify the caller before continuing.':
    'संभावित AI-क्लोन की गई आवाज़ मिली है। आगे बढ़ने से पहले भरोसेमंद अभिभावक कॉलर की पुष्टि करें।',
  Dismiss: 'हटाएँ',
  'synthetic score': 'synthetic score',
  'threshold {t}%': 'threshold {t}%',
  '{p}% synthetic': '{p}% synthetic',

  /* ── SessionCard ───────────────────────────────────────────────────── */
  '{n} windows': '{n} विंडो',
  enterprise: 'एंटरप्राइज़',
  live: 'लाइव',
}

const kn: Record<string, string> = {
  /* ── Top bar / sidebar ─────────────────────────────────────────────── */
  'Live Monitor': 'ಲೈವ್ ಮಾನಿಟರ್',
  Incidents: 'ಘಟನೆಗಳು',
  Forensics: 'ಫೋರೆನ್ಸಿಕ್ಸ್',
  Monitoring: 'ನಿಗಾ',
  Overview: 'ಅವಲೋಕನ',
  'Live call monitor': 'ಲೈವ್ ಕರೆ ಮಾನಿಟರ್',
  'Risk & incidents': 'ಅಪಾಯ ಮತ್ತು ಘಟನೆಗಳು',
  'Incident log': 'ಘಟನೆ ದಾಖಲೆ',
  'Session forensics': 'ಸೆಷನ್ ಫೋರೆನ್ಸಿಕ್ಸ್',
  'File analysis': 'ಫೈಲ್ ವಿಶ್ಲೇಷಣೆ',
  Identity: 'ಗುರುತು',
  'Speaker enrollment': 'ಸ್ಪೀಕರ್ ನೋಂದಣಿ',

  /* ── Footer ────────────────────────────────────────────────────────── */
  'VoiceShield AI — real-time voice integrity verification · AASIST-L inference, prosodic XAI, watermark verification · API served from {base}':
    'VoiceShield AI — ನೈಜ-ಸಮಯದ ಧ್ವನಿ ಸಮಗ್ರತೆ ಪರಿಶೀಲನೆ · AASIST-L inference, prosodic XAI, watermark verification · API {base} ನಿಂದ ಲಭ್ಯ',
  'this origin': 'ಈ ಒರಿಜಿನ್‌ನಿಂದ',

  /* ── Dashboard: header ─────────────────────────────────────────────── */
  'Back to overview': 'ಅವಲೋಕನಕ್ಕೆ ಹಿಂತಿರುಗಿ',
  'Start session': 'ಸೆಷನ್ ಪ್ರಾರಂಭಿಸಿ',
  'End session': 'ಸೆಷನ್ ಮುಗಿಸಿ',
  'Voice integrity, verified in real time.': 'ಧ್ವನಿಯ ನೈಜತೆ, ನೈಜ-ಸಮಯದಲ್ಲಿ ಪರಿಶೀಲಿಸಲಾಗಿದೆ.',
  'VoiceShield analyzes live call audio for AI-generated speech — acoustic model, prosodic evidence and enterprise watermarking, fused into a single actionable score.':
    'VoiceShield ಲೈವ್ ಕರೆ ಆಡಿಯೊದಲ್ಲಿ AI-ರಚಿತ ಧ್ವನಿಯನ್ನು ವಿಶ್ಲೇಷಿಸುತ್ತದೆ — ಅಕೌಸ್ಟಿಕ್ ಮಾಡೆಲ್, ಪ್ರಾಸೊಡಿಕ್ ಸಾಕ್ಷ್ಯ ಮತ್ತು ಎಂಟರ್ಪ್ರೈಸ್ ವಾಟರ್ಮಾರ್ಕಿಂಗ್, ಎಲ್ಲವನ್ನು ಒಂದೇ actionable ಸ್ಕೋರ್‌ಗೆ ಸೇರಿಸಿ.',
  'View forensics': 'ಫೋರೆನ್ಸಿಕ್ಸ್ ನೋಡಿ',
  'Start live session': 'ಲೈವ್ ಸೆಷನ್ ಪ್ರಾರಂಭಿಸಿ',

  /* ── Dashboard: intro paragraphs ───────────────────────────────────── */
  'Every 300 milliseconds, VoiceShield extracts a fresh window from the call stream and runs it through three independent checks: a graph-attention acoustic model (AASIST-L), sub-phonemic prosodic analysis — jitter, shimmer and spectral phase continuity — and a watermark verifier that recognizes authorized enterprise callers instantly.':
    'ಪ್ರತಿ 300 ಮಿಲಿಸೆಕೆಂಡ್‌ಗೆ VoiceShield ಕರೆ ಸ್ಟ್ರೀಮ್‌ನಿಂದ ಹೊಸ ವಿಂಡೋ ತೆಗೆದು ಅದನ್ನು ಮೂರು ಸ್ವತಂತ್ರ ಪರೀಕ್ಷೆಗಳ ಮೂಲಕ ಸಾಗಿಸುತ್ತದೆ: ಗ್ರಾಫ್-ಅಟೆನ್ಶನ್ ಅಕೌಸ್ಟಿಕ್ ಮಾಡೆಲ್ (AASIST-L), ಸಬ್-ಫೋನೆಮಿಕ್ ಪ್ರಾಸೊಡಿಕ್ ವಿಶ್ಲೇಷಣೆ — ಜಿಟರ್, ಶಿಮರ್ ಮತ್ತು ಸ್ಪೆಕ್ಟ್ರಲ್ ಫೇಸ್ ನಿರಂತರತೆ — ಮತ್ತು ಮಾನ್ಯ ಎಂಟರ್ಪ್ರೈಸ್ ಕರೆದಾರರನ್ನು ತಕ್ಷಣ ಗುರುತಿಸುವ ವಾಟರ್ಮಾರ್ಕ್ ಪರಿಶೀಲಕ.',
  'The results are fused into a single synthetic score. Crossings trigger role-aware mitigation: 70% for calls involving children, 85% for adults, with alerts dispatched to Telegram, email, SMS and webhooks, and an I4C-ready forensic PDF generated for every incident.':
    'ಈ ಫಲಿತಾಂಶಗಳನ್ನು ಒಂದೇ synthetic score ಆಗಿ ವಿಲೀನಗೊಳಿಸಲಾಗುತ್ತದೆ. ಮಿತಿ ದಾಟಿದರೆ ಪಾತ್ರ-ಆಧಾರಿತ ಕ್ರಮ ಜಾರಿಯಾಗುತ್ತದೆ: ಮಕ್ಕಳ ಕರೆಗಳಿಗೆ 70%, ವಯಸ್ಕರಿಗೆ 85%. ಟೆಲಿಗ್ರಾಮ್, ಇಮೇಲ್, SMS ಮತ್ತು ವೆಬ್‌ಹುಕ್‌ಗೆ ಎಚ್ಚರಿಕೆಗಳನ್ನು ಕಳುಹಿಸಲಾಗುತ್ತದೆ, ಮತ್ತು ಪ್ರತಿ ಘಟನೆಗೆ I4C-ಸಿದ್ಧ ಫೋರೆನ್ಸಿಕ್ PDF ರಚಿಸಲಾಗುತ್ತದೆ.',

  /* ── Dashboard: stat cards ─────────────────────────────────────────── */
  'Detection latency': 'ಪತ್ತೆ ವಿಳಂಬ',
  'Window cadence': 'ವಿಂಡೋ ವೇಗ',
  Languages: 'ಭಾಷೆಗಳು',
  'per-window design budget, ONNX, 2 CPU threads': 'ಪ್ರತಿ-ವಿಂಡೋ ವಿನ್ಯಾಸ ಬಜೆಟ್, ONNX, 2 CPU ಥ್ರೆಡ್',
  'Dhwani window / hop · 300 ms / 100 ms legacy fallback': 'Dhwani ವಿಂಡೋ / ಹಾಪ್ · 300 ms / 100 ms ಲೆಗಸಿ ಫಾಲ್‌ಬ್ಯಾಕ್',
  'accent-invariant features': 'ಉಚ್ಚಾರ-ಸ್ವತಂತ್ರ ವೈಶಿಷ್ಟ್ಯಗಳು',

  /* ── Dashboard: pipeline explainer ─────────────────────────────────── */
  'How a window is scored': 'ವಿಂಡೋವನ್ನು ಹೇಗೆ ಅಂಕಿಸಲಾಗುತ್ತದೆ',
  'Watermark check': 'ವಾಟರ್ಮಾರ್ಕ್ ಪರೀಕ್ಷೆ',
  'A 4096-point FFT scans 7.0–7.5 kHz for the enterprise pilot tone. A verified caller short-circuits the pipeline with a score of zero.':
    '4096-ಪಾಯಿಂಟ್ FFT ಎಂಟರ್ಪ್ರೈಸ್ ಪೈಲಟ್ ಟೋನ್‌ಗಾಗಿ 7.0–7.5 kHz ಸ್ಕ್ಯಾನ್ ಮಾಡುತ್ತದೆ. ಪರಿಶೀಲಿತ ಕರೆದಾರರ ಸ್ಕೋರ್ ನೇರವಾಗಿ ಶೂನ್ಯವಾಗುತ್ತದೆ.',
  'Acoustic model': 'ಅಕೌಸ್ಟಿಕ್ ಮಾಡೆಲ್',
  'AASIST-L — a spectro-temporal graph attention network — classifies synthesis artifacts in the log-mel spectrogram.':
    'AASIST-L — ಸ್ಪೆಕ್ಟ್ರೋ-ಟೆಂಪೊರಲ್ ಗ್ರಾಫ್ ಅಟೆನ್ಶನ್ ನೆಟ್‌ವರ್ಕ್ — log-mel ಸ್ಪೆಕ್ಟ್ರೋಗ್ರಾಮ್‌ನಲ್ಲಿ ಸಂಶ್ಲೇಷಣೆಯ ಅಂಶಗಳನ್ನು ಗುರುತಿಸುತ್ತದೆ.',
  'Prosodic XAI': 'ಪ್ರಾಸೊಡಿಕ್ XAI',
  'Glottal-cycle jitter and shimmer plus inter-frame phase continuity expose the unnatural regularity of neural speech.':
    'ಗ್ಲೋಟಲ್-ಸೈಕಲ್ ಜಿಟರ್, ಶಿಮರ್ ಮತ್ತು ಅಂತರ-ಫ್ರೇಮ್ ಫೇಸ್ ನಿರಂತರತೆ ನ್ಯೂರಲ್ ಧ್ವನಿಯ ಅಸ್ವಾಭಾವಿಕ ಸ್ಥಿರತೆಯನ್ನು ಬಯಲು ಮಾಡುತ್ತದೆ.',

  /* ── Dashboard: threshold reference ────────────────────────────────── */
  'Mitigation thresholds': 'ಕ್ರಮದ ಮಿತಿಗಳು (ಥ್ರೆಶೋಲ್ಡ್)',
  Scenario: 'ಸನ್ನಿವೇಶ',
  Trigger: 'ಟ್ರಿಗರ್',
  Response: 'ಪ್ರತಿಕ್ರಿಯೆ',
  'Child-safety calls': 'ಮಕ್ಕಳ ಸುರಕ್ಷತೆ ಕರೆಗಳು',
  'Score ≥ 70%': 'ಸ್ಕೋರ್ ≥ 70%',
  'Immediate guardian alert, block sensitive actions': 'ತಕ್ಷಣ ಪಾಲಕರಿಗೆ ಎಚ್ಚರಿಕೆ, ಸೂಕ್ಷ್ಮ ಕ್ರಿಯೆಗಳನ್ನು ನಿರ್ಬಂಧಿಸಿ',
  'Adult / enterprise calls': 'ವಯಸ್ಕ / ಎಂಟರ್ಪ್ರೈಸ್ ಕರೆಗಳು',
  'Score ≥ 85%': 'ಸ್ಕೋರ್ ≥ 85%',
  'Hold transaction, require call-back or MFA': 'ವ್ಯವಹಾರ ತಡೆಹಿಡಿ, ಕಾಲ್-ಬ್ಯಾಕ್ ಅಥವಾ MFA ಕೇಳಿ',
  'Elevated suspicion': 'ಹೆಚ್ಚಿದ ಅನುಮಾನ',
  'Score ≥ 35%': 'ಸ್ಕೋರ್ ≥ 35%',
  'Warning banner, recommend secondary verification': 'ಎಚ್ಚರಿಕೆ ಬ್ಯಾನರ್, ದ್ವಿತೀಯಕ ಪರಿಶೀಲನೆ ಸೂಚಿಸಿ',
  'Enterprise watermark': 'ಎಂಟರ್ಪ್ರೈಸ್ ವಾಟರ್ಮಾರ್ಕ್',
  'Pilot tone 12× noise floor': 'Pilot tone 12× noise floor',
  'Verified caller — score forced to 0.0': 'ಪರಿಶೀಲಿತ ಕರೆದಾರ — ಸ್ಕೋರ್ 0.0 ಗೆ ಹೊಂದಿಸಲಾಗಿದೆ',

  /* ── Dashboard: quick check ────────────────────────────────────────── */
  'Quick check': 'ಶೀಘ್ರ ಪರೀಕ್ಷೆ',
  'Run a 30-second check from this page — or open the': 'ಈ ಪುಟದಿಂದಲೇ 30 ಸೆಕೆಂಡ್ ಪರೀಕ್ಷೆ ನಡೆಸಿ — ಅಥವಾ ತೆರೆಯಿರಿ',
  'full live monitor': 'ಪೂರ್ಣ ಲೈವ್ ಮಾನಿಟರ್',

  /* ── Dashboard: live panel ─────────────────────────────────────────── */
  'Session setup': 'ಸೆಷನ್ ಸೆಟಪ್',
  Role: 'ಪಾತ್ರ',
  Language: 'ಭಾಷೆ',
  'Enrolled speaker (optional)': 'ನೋಂದಾಯಿತ ಸ್ಪೀಕರ್ (ಐಚ್ಛಿಕ)',
  'e.g. manager_rajesh': 'ಉದಾ. manager_rajesh',
  'Shielded — mic paused': 'ಶೀಲ್ಡ್ ಸಕ್ರಿಯ — ಮೈಕ್ ನಿಂತಿದೆ',
  'Microphone live': 'ಮೈಕ್ ಆನ್ ಆಗಿದೆ',
  Connected: 'ಸಂಪರ್ಕಿತ',
  Offline: 'ಆಫ್‌ಲೈನ್',
  'Score timeline': 'ಸ್ಕೋರ್ ಕಾಲಾನುಕ್ರಮ',
  'peak {p}% · {n} windows · latency {l} ms': 'ಗರಿಷ್ಠ {p}% · {n} ವಿಂಡೋ · ವಿಳಂಬ {l} ms',
  'Model P': 'Model P',
  'XAI risk': 'XAI risk',
  Verdict: 'ತೀರ್ಪು',
  'NF drops': 'NF drops',
  'XAI breakdown': 'XAI ವಿಭಜನೆ',
  'Latest window': 'ಇತ್ತೀಚಿನ ವಿಂಡೋ',
  'Speaker mismatch — possible impersonation.': 'ಸ್ಪೀಕರ್ ಹೊಂದಾಣಿಕೆ ಇಲ್ಲ — ಸಂಭಾವ್ಯ ನಕಲಿ.',
  'Consistent with the enrolled voice.': 'ನೋಂದಾಯಿತ ಧ್ವನಿಯೊಂದಿಗೆ ಹೊಂದಿಕೊಳ್ಳುತ್ತದೆ.',
  Mitigation: 'ಕ್ರಮ',
  'Role-aware response (child ≥ 70% / adult ≥ 85%)': 'ಪಾತ್ರ-ಆಧಾರಿತ ಪ್ರತಿಕ್ರಿಯೆ (ಮಗು ≥ 70% / ವಯಸ್ಕ ≥ 85%)',
  'Monitoring live — no mitigation triggered yet.': 'ಲೈವ್ ನಿಗಾ ನಡೆಯುತ್ತಿದೆ — ಇನ್ನೂ ಕ್ರಮ ಪ್ರಚೋದಿತವಾಗಿಲ್ಲ.',
  'Start a session to see role-aware mitigation.': 'ಪಾತ್ರ-ಆಧಾರಿತ ಕ್ರಮ ನೋಡಲು ಸೆಷನ್ ಪ್ರಾರಂಭಿಸಿ.',

  /* ── Dashboard: verdicts / roles ───────────────────────────────────── */
  'v.bonafide': 'ನೈಜ ಧ್ವನಿ',
  'v.synthetic': 'ಕೃತಕ',
  'v.verified_enterprise': 'ಪರಿಶೀಲಿತ ಎಂಟರ್ಪ್ರೈಸ್',
  'v.suspicious': 'ಅನುಮಾನಾಸ್ಪದ',
  'v.synthetic+speaker_mismatch': 'ಕೃತಕ + ಸ್ಪೀಕರ್ ಹೊಂದಾಣಿಕೆ ಇಲ್ಲ',
  'role.adult': 'ವಯಸ್ಕ',
  'role.child': 'ಮಗು',

  /* ── Live hook errors ──────────────────────────────────────────────── */
  'WebSocket error — is the backend running on :8000?': 'WebSocket ದೋಷ — ಬ್ಯಾಕೆಂಡ್ :8000 ರಲ್ಲಿ ಚಾಲನೆಯಲ್ಲಿದೆಯೇ?',
  'Microphone context could not start — allow mic permission and retry.': 'ಮೈಕ್ ಪ್ರಾರಂಭವಾಗಲಿಲ್ಲ — ಮೈಕ್ ಅನುಮತಿ ನೀಡಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
  'Microphone unavailable — {e}': 'ಮೈಕ್ ಲಭ್ಯವಿಲ್ಲ — {e}',
  'Audio init failed — {e}': 'ಆಡಿಯೊ ಪ್ರಾರಂಭ ವಿಫಲ — {e}',

  /* ── Incidents ─────────────────────────────────────────────────────── */
  'Threshold crossings are recorded as incidents with severity, triggers and a forensic I4C report. Acknowledge incidents once they’ve been reviewed.':
    'ಮಿತಿ ದಾಟುವಿಕೆಗಳನ್ನು ಗಂಭೀರತೆ, ಟ್ರಿಗರ್ ಮತ್ತು ಫೋರೆನ್ಸಿಕ್ I4C ವರದಿಯೊಂದಿಗೆ ಘಟನೆಗಳಾಗಿ ದಾಖಲಿಸಲಾಗುತ್ತದೆ. ಪರಿಶೀಲಿಸಿದ ನಂತರ ಘಟನೆಗಳನ್ನು ಅಂಗೀಕರಿಸಿ.',
  'Loading…': 'ಲೋಡ್ ಆಗುತ್ತಿದೆ…',
  Refresh: 'ರಿಫ್ರೆಶ್',
  'No incidents recorded yet. Run a live monitor session or upload a recording to see incidents here.':
    'ಇನ್ನೂ ಯಾವುದೇ ಘಟನೆಗಳು ದಾಖಲಾಗಿಲ್ಲ. ಇಲ್ಲಿ ಘಟನೆಗಳನ್ನು ನೋಡಲು ಲೈವ್ ಮಾನಿಟರ್ ಸೆಷನ್ ನಡೆಸಿ ಅಥವಾ ರೆಕಾರ್ಡಿಂಗ್ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.',
  'sev.critical': 'ಗಂಭೀರ',
  'sev.high': 'ಹೆಚ್ಚು',
  'sev.medium': 'ಮಧ್ಯಮ',
  'sev.low': 'ಕಡಿಮೆ',
  'I4C report': 'I4C report',
  Acknowledged: 'ಅಂಗೀಕರಿಸಲಾಗಿದೆ',
  Acknowledge: 'ಅಂಗೀಕರಿಸಿ',
  'Ack…': 'ಅಂಗೀಕಾರ…',
  'role {r}': 'ಪಾತ್ರ {r}',
  'lang {l}': 'lang {l}',
  'speaker mismatch': 'ಸ್ಪೀಕರ್ ಹೊಂದಾಣಿಕೆ ಇಲ್ಲ',
  'triggers: {t}': 'ಟ್ರಿಗರ್: {t}',

  /* ── Reports ───────────────────────────────────────────────────────── */
  'Reconstruct any monitored call window-by-window, run batch analysis on recordings, or enroll trusted voices for cross-session identity checks.':
    'ಯಾವುದೇ ಮೇಲ್ವಿಚಾರಣೆಯ ಕರೆಯನ್ನು ವಿಂಡೋ-ವಾರು ಪುನರ್ರಚಿಸಿ, ರೆಕಾರ್ಡಿಂಗ್‌ಗಳ ಬ್ಯಾಚ್ ವಿಶ್ಲೇಷಣೆ ನಡೆಸಿ, ಅಥವಾ ಅಡ್ಡ-ಸೆಷನ್ ಗುರುತು ಪರಿಶೀಲನೆಗಾಗಿ ವಿಶ್ವಾಸಾರ್ಹ ಧ್ವನಿಗಳನ್ನು ನೋಂದಾಯಿಸಿ.',
  'No sessions recorded yet — run a live monitor session first.':
    'ಇನ್ನೂ ಯಾವುದೇ ಸೆಷನ್‌ಗಳು ದಾಖಲಾಗಿಲ್ಲ — ಮೊದಲು ಲೈವ್ ಮಾನಿಟರ್ ಸೆಷನ್ ನಡೆಸಿ.',
  'Window timeline': 'ವಿಂಡೋ ಕಾಲಾನುಕ್ರಮ',
  'Download report': 'ವರದಿ ಡೌನ್‌ಲೋಡ್',
  Score: 'ಸ್ಕೋರ್',
  'No windows persisted for this session.': 'ಈ ಸೆಷನ್‌ಗೆ ಯಾವುದೇ ವಿಂಡೋ ಉಳಿಸಿಲ್ಲ.',
  'Select a session on the left to reconstruct its full per-window analysis timeline.':
    'ಸಂಪೂರ್ಣ ವಿಂಡೋ-ವಾರು ವಿಶ್ಲೇಷಣೆ ಕಾಲಾನುಕ್ರಮವನ್ನು ಪುನರ್ರಚಿಸಲು ಎಡಭಾಗದಲ್ಲಿ ಒಂದು ಸೆಷನ್ ಆಯ್ಕೆಮಾಡಿ.',

  /* ── Reports: blockchain ───────────────────────────────────────────── */
  'Report blockchain': 'ವರದಿ blockchain',
  'Every forensic PDF is anchored via SHA-256 + proof-of-work to an append-only hash chain. Each block commits the report hash and a Merkle root of the session score timeline, linked to its predecessor — so any modification after the fact is cryptographically detectable.':
    'ಪ್ರತಿ ಫೋರೆನ್ಸಿಕ್ PDF SHA-256 + proof-of-work ಮೂಲಕ append-only hash chain ನಲ್ಲಿ ದಾಖಲಾಗುತ್ತದೆ. ಪ್ರತಿ ಬ್ಲಾಕ್ ವರದಿಯ ಹ್ಯಾಶ್ ಮತ್ತು ಸೆಷನ್ ಸ್ಕೋರ್ ಕಾಲಾನುಕ್ರಮದ Merkle root ಹೊಂದಿಸಿ, ಹಿಂದಿನ ಬ್ಲಾಕ್‌ಗೆ ಜೋಡಿಸುತ್ತದೆ — ಆದ್ದರಿಂದ ನಂತರದ ಯಾವುದೇ ಬದಲಾವಣೆ ಕ್ರಿಪ್ಟೋಗ್ರಾಫಿಕ್ ಆಗಿ ಪತ್ತೆಯಾಗುತ್ತದೆ.',
  'chain OK · height {h}': 'ಚೈನ್ ಸರಿ · ಎತ್ತರ {h}',
  'chain INVALID': 'ಚೈನ್ ಅಮಾನ್ಯ',
  Height: 'ಎತ್ತರ',
  Difficulty: 'ಡಿಫಿಕಲ್ಟಿ',
  'No reports anchored yet — download a forensic report to mint the genesis block.':
    'ಇನ್ನೂ ವರದಿಗಳು ದಾಖಲಾಗಿಲ್ಲ — genesis ಬ್ಲಾಕ್ ರಚಿಸಲು ಫೋರೆನ್ಸಿಕ್ ವರದಿಯನ್ನು ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ.',
  'Verifying…': 'ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…',
  Verify: 'ಪರಿಶೀಲಿಸಿ',
  'verification failed': 'ಪರಿಶೀಲನೆ ವಿಫಲವಾಗಿದೆ',
  'error.verification failed': 'ಪರಿಶೀಲನೆ ವಿಫಲವಾಗಿದೆ',
  'On-disk report hash matches the anchored hash; chain linkage intact.':
    'ಡಿಸ್ಕ್‌ನಲ್ಲಿರುವ ವರದಿಯ ಹ್ಯಾಶ್ ದಾಖಲಾದ ಹ್ಯಾಶ್‌ಗೆ ಹೊಂದುತ್ತದೆ; ಚೈನ್ ಸಂಪರ್ಕ ಸರಿಯಾಗಿದೆ.',

  /* ── Reports: analyze ──────────────────────────────────────────────── */
  'Analyze a recording': 'ರೆಕಾರ್ಡಿಂಗ್ ವಿಶ್ಲೇಷಣೆ',
  'Upload a call recording (wav, mp3, flac). VoiceShield resamples to 16 kHz, slides a window across the file (3 s window / 1 s hop with Dhwani; 300 ms / 100 ms legacy fallback), and returns the full per-window XAI breakdown.':
    'ಕರೆ ರೆಕಾರ್ಡಿಂಗ್ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ (wav, mp3, flac). VoiceShield ಅದನ್ನು 16 kHz ಗೆ ಮರುಮಾದರಿ ಮಾಡಿ, ಫೈಲ್‌ನಾದ್ಯಂತ ವಿಂಡೋ ಸರಿಸಿ (Dhwani ಜೊತೆ 3 s ವಿಂಡೋ / 1 s ಹಾಪ್; ಇಲ್ಲದಿದ್ದರೆ 300 ms / 100 ms ಲೆಗಸಿ), ಪ್ರತಿ ವಿಂಡೋದ ಸಂಪೂರ್ಣ XAI ವಿಭಜನೆಯನ್ನು ನೀಡುತ್ತದೆ.',
  'Analyzing…': 'ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ…',
  Analyze: 'ವಿಶ್ಲೇಷಿಸಿ',
  'error.Analysis failed — is the backend reachable?': 'ವಿಶ್ಲೇಷಣೆ ವಿಫಲ — ಬ್ಯಾಕೆಂಡ್ ಲಭ್ಯವಿದೆಯೇ?',
  'Peak score': 'ಗರಿಷ್ಠ ಸ್ಕೋರ್',
  'Risk band': 'ಅಪಾಯ ಮಟ್ಟ',
  'Windows analyzed': 'ವಿಶ್ಲೇಷಿಸಿದ ವಿಂಡೋಗಳು',

  /* ── Reports: speakers ─────────────────────────────────────────────── */
  'Enroll a trusted speaker': 'ವಿಶ್ವಾಸಾರ್ಹ ಸ್ಪೀಕರ್ ನೋಂದಾಯಿಸಿ',
  'Upload about ten seconds of genuine speech per person. Live sessions tagged with this label are compared against the stored embedding; a mismatch adds +0.15 to the fused risk score.':
    'ಪ್ರತಿ ವ್ಯಕ್ತಿಯ ಸುಮಾರು ಹತ್ತು ಸೆಕೆಂಡ್ ನಿಜವಾದ ಧ್ವನಿ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ. ಈ ಲೇಬಲ್ ಇರುವ ಲೈವ್ ಸೆಷನ್‌ಗಳನ್ನು ಸಂಗ್ರಹಿಸಿದ embedding ನೊಂದಿಗೆ ಹೋಲಿಸಲಾಗುತ್ತದೆ; ಹೊಂದಾಣಿಕೆ ಇಲ್ಲದಿದ್ದರೆ fused risk score ಗೆ +0.15 ಸೇರುತ್ತದೆ.',
  'Speaker label': 'ಸ್ಪೀಕರ್ ಲೇಬಲ್',
  Enroll: 'ನೋಂದಾಯಿಸಿ',
  'msg.Provide a label and a genuine voice sample.': 'ಲೇಬಲ್ ಮತ್ತು ನಿಜವಾದ ಧ್ವನಿ ಮಾದರಿ ನೀಡಿ.',
  'msg.Enrolled "{label}" — cross-session consistency checks are now active for this voice.':
    '"{label}" ನೋಂದಾಯಿತವಾಗಿದೆ — ಈ ಧ್ವನಿಗೆ ಅಡ್ಡ-ಸೆಷನ್ ಸ್ಥಿರತೆ ಪರೀಕ್ಷೆಗಳು ಈಗ ಸಕ್ರಿಯವಾಗಿವೆ.',
  'msg.Error: {d}': 'ದೋಷ: {d}',

  /* ── RiskGauge / Radar ─────────────────────────────────────────────── */
  'SYNTHETIC SCORE': 'ಸಿಂಥೆಟಿಕ್ ಸ್ಕೋರ್',
  '{band} risk': '{band} ಅಪಾಯ',
  'band.low': 'ಕಡಿಮೆ',
  'band.medium': 'ಮಧ್ಯಮ',
  'band.high': 'ಹೆಚ್ಚು',
  'band.critical': 'ಗಂಭೀರ',
  'Model P(synthetic)': 'Model P(synthetic)',
  'XAI risk (fused)': 'XAI risk (fused)',
  'Phase discontinuity': 'ಫೇಸ್ ಅಸಂಗತತೆ',
  Jitter: 'ಜಿಟರ್',
  Shimmer: 'ಶಿಮರ್',
  'Pitch Stability': 'ಪಿಚ್ ಸ್ಥಿರತೆ',
  'Phase Continuity': 'ಫೇಸ್ ನಿರಂತರತೆ',
  'NF Dropouts': 'NF Dropouts',

  /* ── ShieldBanner ──────────────────────────────────────────────────── */
  'Call paused': 'ಕರೆ ವಿರಾಮಗೊಳಿಸಲಾಗಿದೆ',
  'A potential AI-cloned voice was detected. A trusted guardian should verify the caller before continuing.':
    'ಸಂಭಾವ್ಯ AI-ಕ್ಲೋನ್ ಧ್ವನಿ ಪತ್ತೆಯಾಗಿದೆ. ಮುಂದುವರಿಯುವ ಮೊದಲು ವಿಶ್ವಾಸಾರ್ಹ ಪಾಲಕರು ಕರೆದಾರರನ್ನು ಪರಿಶೀಲಿಸಬೇಕು.',
  Dismiss: 'ತೆಗೆದುಹಾಕಿ',
  'synthetic score': 'synthetic score',
  'threshold {t}%': 'threshold {t}%',
  '{p}% synthetic': '{p}% synthetic',

  /* ── SessionCard ───────────────────────────────────────────────────── */
  '{n} windows': '{n} ವಿಂಡೋ',
  enterprise: 'ಎಂಟರ್ಪ್ರೈಸ್',
  live: 'ಲೈವ್',
}

/**
 * English is the source language: natural-language keys fall back to the key
 * itself, so only the coded keys need explicit labels here (they would
 * otherwise render as raw identifiers like `role.adult` or `sev.critical`).
 */
const en: Record<string, string> = {
  'v.bonafide': 'Genuine voice',
  'v.synthetic': 'Synthetic',
  'v.verified_enterprise': 'Verified enterprise',
  'v.suspicious': 'Suspicious',
  'v.synthetic+speaker_mismatch': 'Synthetic + speaker mismatch',
  'role.adult': 'Adult',
  'role.child': 'Child',
  'sev.critical': 'Critical',
  'sev.high': 'High',
  'sev.medium': 'Medium',
  'sev.low': 'Low',
  'band.low': 'Low',
  'band.medium': 'Medium',
  'band.high': 'High',
  'band.critical': 'Critical',
  'error.verification failed': 'Verification failed',
  'error.Analysis failed — is the backend reachable?': 'Analysis failed — is the backend reachable?',
  'error.undefined': 'Something went wrong.',
  'Error: {e}': 'Error: {e}',
  'Failed to load incidents': 'Failed to load incidents',
  'Failed to acknowledge incident': 'Failed to acknowledge incident',
  'External anchor (NBF-Fabric)': 'External anchor (NBF-Fabric)',
  'demo / offline': 'demo / offline',
}

const dict: Record<Lang, Record<string, string>> = { en, hi, kn }

type T = (key: string, vars?: Record<string, string | number>) => string

type Ctx = {
  lang: Lang
  setLang: (l: Lang) => void
  t: T
  tVerdict: (v: string) => string
}

const I18nContext = createContext<Ctx>({
  lang: 'en',
  setLang: () => {},
  t: (k) => k,
  tVerdict: (v) => v,
})

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => {
    const stored = localStorage.getItem('vs-lang')
    return stored === 'hi' || stored === 'kn' ? stored : 'en'
  })

  useEffect(() => {
    localStorage.setItem('vs-lang', lang)
    document.documentElement.lang = lang
  }, [lang])

  const t: T = (key, vars) => {
    let s = dict[lang][key] ?? key
    if (vars) {
      for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v))
    }
    return s
  }

  const tVerdict = (v: string): string => {
    const key = `v.${v}`
    return key in dict[lang] ? dict[lang][key] : v
  }

  return <I18nContext.Provider value={{ lang, setLang, t, tVerdict }}>{children}</I18nContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useI18n() {
  return useContext(I18nContext)
}

// eslint-disable-next-line react-refresh/only-export-components
export function useT(): T {
  return useContext(I18nContext).t
}