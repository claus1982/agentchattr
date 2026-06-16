# Architecture Decision Records (ADR)

Questa cartella raccoglie le **decisioni architetturali** di JamMate: cosa
abbiamo scelto, perché, quali alternative abbiamo scartato e con quali
conseguenze. Servono a non ri‑discutere le stesse scelte e a spiegare il
"perché" a chi entra dopo.

Formato (leggero, stile Nygard): **Contesto → Decisione → Conseguenze → Alternative**.
Ogni ADR ha uno **stato**: `Proposto`, `Accettato`, `Sostituito da ...`, `Deprecato`.

## Indice
| # | Decisione | Stato |
|---|---|---|
| [0001](0001-piattaforma-cloud-azure.md) | Piattaforma cloud: **Azure** | Accettato |
| [0002](0002-compute-azure-functions.md) | Compute: **Azure Functions** (serverless) | Accettato |
| [0003](0003-database-postgresql.md) | Database: **PostgreSQL** (relazionale) | Accettato |
| [0004](0004-auth-entra-external-id.md) | Identità: **Microsoft Entra External ID** | Accettato |
| [0005](0005-data-layer-seam-frontend.md) | Frontend: **data layer sostituibile** (`storage.js`) | Accettato |
| [0006](0006-pagamenti-stripe.md) | Pagamenti: **Stripe** (Connect + escrow) | Accettato |
| [0007](0007-realtime-web-pubsub.md) | Chat realtime: **Azure Web PubSub** | Proposto |
| [0008](0008-residenza-dati-ue-gdpr.md) | Residenza dati: **regione UE** (GDPR) | Accettato |
| [0009](0009-contract-first-openapi.md) | Approccio **contract‑first** (OpenAPI) | Accettato |
| [0010](0010-media-blob-storage.md) | Media/foto: **Azure Blob Storage** | Accettato |
