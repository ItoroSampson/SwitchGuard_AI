SwitchGuard AI
An Event-Driven, Real-Time Payment Route Anomaly Engine for POS Merchants.SwitchGuard AI bridges the gap between official channel stability dashboards and actual merchant checkout realities. Rather than relying solely on high-level provider status pages—which often suffer from false positives and miss micro-outages—SwitchGuard AI evaluates live terminal metrics to detect hidden route degradation, issuer-specific failures, and high-risk "Ghost Debits" in real time.

 The Problem
 In emerging fintech ecosystems, merchants face three main checkout risks:
 False Alarms: Standard channel stability monitors treat soft user errors (e.g., Wrong PIN, Insufficient Funds) as network failures, triggering unnecessary channel switches.
 Invisible Micro-Outages: A payment switch might report $100\%$ operational uptime overall while an underlying bank endpoint is completely offline.
 Ghost Debits: Transactions that linger past 7–10 seconds without a definitive response often result in unconfirmed customer debits with no printed receipt, causing severe counter disputes and financial risk. 
 
 Core Features & Engine Signals
 SwitchGuard AI uses a 7-Signal Evaluation Engine with time-decayed metrics to evaluate incoming transaction streams:
 Time-Decayed Failure Weighting: Uses exponential decay ($\lambda$) to prioritize recent failures over older transactions within a moving sample window.
 Soft User Error Filtering: Automatically excludes consumer-side errors (Code 51: Insufficient Funds, Code 55: Wrong PIN) to prevent false positive alarms.
 Ghost Debit Risk Heuristics: Detects hanging high-latency transactions ($>7,000\text{ ms}$) prone to unconfirmed debits.
 Issuer-Specific Isolation: Identifies whether an outage stems from a specific card issuer endpoint rather than the payment switch itself.
 Route Recovery Probing: Monitors degraded routes for automatic recovery once failure rates and latencies normalize.
 
  Architecture & Pipeline Overview
  [ POS Terminal Logs ]
         │
         ▼
[ PostgreSQL Database ] ──► [ Seed & Inspect Utilities ]
         │
         ▼
[ SwitchGuard Engine ] ──► Evaluates 7 Signals (Decay, Latency, Ghost Debits)
         │
         ▼
[ LLM Alert Agent ] ────► Translates JSON Signals into Plain-English Advice (In Progress)
         │
         ▼
[ Telegram Merchant Bot ] ─► Real-Time Route Instructions (e.g., "SWITCH_PROVIDER")


 Repository Structure.
├── src/
│   └── anomaly_detector.py   # SwitchGuardEngine with decay logic & heuristics
├── run_pipeline.py           # Ingestion, pipeline execution & dispatch logging
├── seed_postgresql.py        # Database seeding utility for mock POS logs
├── inspect_db.py             # Database inspection & route validation script
├── switchguard.py            # Core engine entrypoint and routing evaluation
├── README.md                 # Project documentation
└── requirements.txt          # Python dependencies


 Getting Started
 Prerequisite: Python 3.10+PostgreSQL running locally or via Docker1. 
 Installation: Clone the repository and install the dependencies:
 Bash  git clone https://github.com/your-username/switchguard-ai.git
cd switchguard-ai
pip install -r requirements.txt
2. Configure Database Environment :Set up your PostgreSQL database connection in environment variables or configuration file:Bashexport DATABASE_URL="postgresql://user:password@localhost:5432/switchguard_db"
3. Seed Mock Transactions:Populate your database with realistic merchant transaction scenarios (Moniepoint, Opay, Palmpay):Bashpython seed_postgresql.py
4. Run the Pipeline & Inspection :Execute the anomaly detector against live database logs:
Bash :python run_pipeline.py
Inspect detailed channel signal breakdown:Bash python inspect_db.py


 Sample Pipeline Output================ OPAY ROUTE STATUS ================
ALERT MERCHANTS (SWITCH_PROVIDER): 
HIGH NETWORK FAILURE RATE (46.2%) | GHOST DEBIT RISK: 6 delayed transactions flagged.

Advanced Network Signals Evaluated:
 - Time-Decayed Hard Failure Rate: 46.2%
 - Average Response Latency:       3330 ms
 - Ghost Debit Risk Count:         6

 [DISPATCH]: 'ATTENTION (Opay): HIGH NETWORK FAILURE RATE (46.2%) | Recommended Action: SWITCH_PROVIDER.'
===================================================
 Roadmap & Next Steps
 [x] Phase 1: Core Detection EngineExponential time-decay metric implementationSoft error noise filteringGhost debit heuristics & high-latency detectionPostgreSQL seeding & validation tooling[ ] Phase 2: LLM Alert Translation AgentIntegrate an LLM provider to convert structured JSON alerts into concise, contextual advice.
 [ ] Phase 3: Telegram Merchant GatewayAsynchronous Telegram bot dispatcher for instant merchant broadcast.Interactive /status command for merchant query handling.
 
 📜 LicenseDistributed under the MIT License. See LICENSE for more information.