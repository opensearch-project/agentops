# Observability Stack AWS CLI

Deploy the [Observability Stack](https://github.com/opensearch-project/observability-stack) on AWS managed services with a single command. Creates an OpenSearch domain (or serverless collection), OSIS ingestion pipeline, Amazon Managed Prometheus workspace, and a fully configured OpenSearch UI with dashboards — plus an EC2 instance running demo workloads that generate telemetry out of the box.

## Quick Start

**Managed domain (default):**
```bash
npx @opensearch-project/observability-stack
```

**Serverless collection (AOSS):**
```bash
npx @opensearch-project/observability-stack --serverless
```

Takes ~15 minutes for managed, ~5 minutes for serverless. When complete, the CLI prints a dashboard URL — open it and you're in.

## What Gets Created

| Resource | Description |
|---|---|
| OpenSearch domain **or** serverless collection | Stores logs, traces, and service map data |
| OSIS pipeline | Ingests OTLP data (logs, traces, metrics) via SigV4 |
| Amazon Managed Prometheus | Stores time-series metrics |
| Connected Data Source (Prometheus) | Connects AMP to OpenSearch for metric queries |
| OpenSearch Application | UI with workspace, index patterns, correlations, dashboards |
| IAM roles | Pipeline role (OSIS → OpenSearch + AMP) and Connected Data Source role |
| EC2 instance (t3.xlarge) | Runs OTel Demo + example agents (29 containers generating telemetry) |

All resources are tagged with `observability-stack:pipeline-name` for identification and cleanup.

## Usage

**Create a managed domain deployment from scratch:**
```bash
node bin/cli-installer.mjs --managed \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1
```

By default this creates an optimized-engine domain (`or2.large.search`), recommended
for log-analytics/observability workloads. Optimized domains require OpenSearch 3.5 or
later. Pick a different optimized type with `--os-instance-type` (OR2/OM2 take an EBS
volume via `--os-volume-size`; OI2 uses local NVMe and takes none):
```bash
node bin/cli-installer.mjs --managed \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1 \
  --engine-mode optimized --os-instance-type om2.xlarge.search
```

For a standard (non-optimized) domain, pass `--engine-mode general`:
```bash
node bin/cli-installer.mjs --managed \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1 \
  --engine-mode general --os-instance-type r6g.large.search
```

**Create a serverless (AOSS) deployment from scratch:**
```bash
node bin/cli-installer.mjs --serverless \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1
```

**Reuse existing OpenSearch domain / AMP workspace:**
```bash
node bin/cli-installer.mjs --managed \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1 \
  --opensearch-endpoint https://search-your-domain-xxx.us-east-1.es.amazonaws.com \
  --prometheus-url https://aps-workspaces.us-east-1.amazonaws.com/workspaces/ws-xxx/api/v1/remote_write
```

**Skip EC2 demo** (just pipeline + UI, no demo workloads):
```bash
node bin/cli-installer.mjs --managed \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1 \
  --skip-demo
```

**Launch demo workload against an existing pipeline:**
```bash
node bin/launch-demo.mjs \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1
```

**Deploy into a VPC** (private endpoints):
```bash
node bin/cli-installer.mjs --advanced --managed \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1 \
  --os-domain-name obs-stack-<your-alias> \
  --vpc-id vpc-xxxxxxxx \
  --subnet-ids subnet-aaaa,subnet-bbbb \
  --security-group-ids sg-xxxxxxxx
```

The domain, OSIS ingestion pipeline, and EC2 demo instance are all placed in the
selected VPC. Use this when your telemetry sources (EKS, ECS, EC2) run inside a VPC
and you want the OpenSearch stack in the same network boundary.

- Pass **1-3 subnets** (each in a distinct AZ). With more than one subnet the domain
  is created zone-aware; the pipeline attaches to the first two.
- Security groups must allow the intra-VPC traffic between the pipeline, domain, and
  demo instance (a single group that allows traffic from itself works well).
- Omitting `--vpc-id` keeps the default behavior: public endpoints.

> **You can run this from anywhere** — you do not need to be inside the VPC. A
> VPC-private domain's endpoint isn't reachable from your machine, but the managed
> OpenSearch UI (Application) endpoint is public and proxies to the domain over the
> AWS-internal network. For VPC domains the installer:
> - sets your IAM principal as the domain's master user,
> - authorizes the OpenSearch UI service (`application.opensearchservice.amazonaws.com`)
>   to reach the domain through its VPC endpoint, and
> - performs all FGAC role mapping and UI setup through that reachable Application
>   endpoint.
>
> So no bastion or VPN is required. (If you deploy a VPC domain by other means, run
> `aws opensearch authorize-vpc-endpoint-access --domain-name <name> --service
> application.opensearchservice.amazonaws.com` yourself, or the UI cannot connect.)

**Interactive mode** (TUI wizard):
```bash
node bin/cli-installer.mjs
```

Advanced mode adds a **Network topology** step where you pick public endpoints or a
VPC, then select subnets and security groups from your account.

## Destroy

```bash
node bin/cli-installer.mjs destroy \
  --pipeline-name obs-stack-<your-alias> \
  --region us-east-1
```

Deletes: EC2 instance, OpenSearch Application, Connected Data Source, OSIS pipeline, IAM roles. OpenSearch domain and AMP workspace are preserved (shared resources).

## Prerequisites

- Node.js 18+
- AWS credentials configured (`aws sts get-caller-identity` should succeed)
- IAM permissions: OSIS, OpenSearch, AMP, IAM role creation, EC2, SSM

## Known Limitations

- **Index pattern fields need manual refresh** — After data starts flowing, go to Management → Index Patterns → select pattern → click 🔄 to pick up new fields.
- **Demo data takes 10-15 minutes** — The EC2 instance needs time to bootstrap Docker, pull images, and start sending telemetry.
- **Idempotent but not updateable** — Running twice safely no-ops, but won't update existing resources with new config.
- **VPC mode maps FGAC through the OpenSearch UI** — for VPC-private domains your IAM principal is the domain's master user and role mapping runs through the managed OpenSearch UI (Application) endpoint, so the CLI does not need to be inside the VPC. VPC options apply only to newly created domains, not reused endpoints.

## Development

### Repository Layout

```
aws/cli-installer/
├── bin/
│   ├── cli-installer.mjs         # Entry point (full pipeline)
│   └── launch-demo.mjs           # Standalone EC2 demo launcher against an existing pipeline
├── src/
│   ├── main.mjs                # CLI orchestration + executePipeline flow
│   ├── cli.mjs                 # Argument parsing + config
│   ├── aws.mjs                 # AWS resource creation (IAM, OSIS, Connected Data Source, Application)
│   ├── render.mjs              # OSIS pipeline YAML generation
│   ├── opensearch-ui-init.mjs  # OpenSearch UI setup (SigV4, workspace, dashboards)
│   ├── ec2-demo.mjs            # EC2 demo workload launcher
│   ├── destroy.mjs             # Resource teardown
│   ├── interactive.mjs         # TUI wizard
│   ├── config.mjs              # Defaults
│   ├── ui.mjs                  # Terminal UI helpers (spinners, boxes, theme)
│   ├── arch-image.mjs          # Base64 architecture image for dashboard
│   └── commands/               # REPL commands (create, list, describe)
└── test/
    └── unit.test.mjs           # Unit tests (16 tests, 6 suites)
```

### Running Tests

```bash
cd aws/cli-installer
node --test test/unit.test.mjs
```

### Key Patterns

- **SigV4 signing** — `opensearch-ui-init.mjs` uses `@aws-sdk/signature-v4` with service `opensearch`. Query params must be in the `query` property of `HttpRequest`, not embedded in the path.
- **Idempotency** — Every resource creation checks for existence first. Correlations use find-before-create; saved objects with fixed IDs are upserted.
- **EC2 demo** — User data script installs Docker + Compose, clones the repo, writes a managed-mode collector config, and starts workload services via `docker-compose.managed.yml`.
