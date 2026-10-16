# Data flow and control points

Solid boxes are built and tested in the repository. Items marked BLOCKED need an
operator, vendor, or live authority.

```mermaid
flowchart LR
  subgraph Sources
    G[Guesty API<br/>read credential]
    WH[Guesty webhooks<br/>Svix-signed — BLOCKED: no subscription]
    ST[Owner statements / channel settlements<br/>BLOCKED: no export]
    OPS[Turno / Breezeway / Guesty Tasks<br/>BLOCKED: no account]
    COMP[Comp scrape / vendor<br/>price basis required]
  end

  WH -->|verify signature first| ING[webhook_ingress<br/>receipt · dedupe · dead letter]
  ING -->|bounded refetch request| G
  G --> SYNC[pms.sync<br/>scope audit at sync]
  SYNC --> LEGACY[(legacy tables<br/>nightly_inventory · reservations)]
  G -. contract .-> SPINE
  ST -. contract .-> SPINE
  OPS --> OPSA[ops.constraint_adapter<br/>restrict-only]
  OPSA --> SPINE
  COMP -. contract .-> SPINE

  SPINE[(data spine<br/>append-only facts<br/>quarantine)] --> NET[owner_net · reconcile · trace]
  LEGACY --> REC[recommendation engine]
  REC --> REV[review queue<br/>hash-chained actions]
  REV --> DEC[fact_price_decision]
  DEC --> SPINE

  REC --> PUSH[push_recommendations<br/>scope · kill switch · floor · caps]
  REV --> CAN[canary controller<br/>INACTIVE]
  PUSH --> SR[GuestyClient.set_rate<br/>scope · write credential · env · permit · KILL]
  CAN --> SR
  SR -->|BLOCKED: no permit, no write credential| GW[Guesty write]

  ORCH[orchestration<br/>locks · deadlines · receipts] -.drives.-> SYNC & REC & REV
  ORCH --> OBS[observability<br/>autonomy ceiling · incidents · alerts]
```

Control points, in order of a live write: portfolio scope → data health
(`handle`) → operational readiness → human review → canary authorization →
final boundary (floor, caps, dates) → `set_rate` gate (scope, separate write
credential, production environment, unexpired permit, no `KILL`) → read-back →
rollback on any mismatch.
