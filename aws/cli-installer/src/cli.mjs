import { Command } from 'commander';
import { createRequire } from 'node:module';
import { DEFAULTS } from './config.mjs';
import { EngineMode, isOptimizedInstanceType, isNvmeOnlyInstanceType, OPTIMIZED_MIN_VERSION, DEFAULT_GENERAL_INSTANCE_TYPE } from './engine.mjs';

/**
 * Normalize an engine-mode flag value (case-insensitive) to an EngineMode
 * constant. Returns '' for an unrecognized value so validateConfig can flag it.
 */
export function normalizeEngineMode(value) {
  const v = String(value || '').trim().toUpperCase();
  if (v === EngineMode.OPTIMIZED || v === EngineMode.GENERAL) return v;
  return '';
}

const require = createRequire(import.meta.url);
const { version: PKG_VERSION } = require('../package.json');

/**
 * Parse CLI arguments into a config object.
 * Returns null when no flags were given (triggers interactive mode).
 */
export function parseCli(argv) {
  // No args → interactive REPL
  if (argv.length <= 2) return null;

  // Demo subcommand — separate parser to avoid option conflicts
  if (argv[2] === 'destroy') return parseDestroyArgs(argv);

  const program = new Command()
    .name('observability-stack-aws-cli')
    .description(
      'Create and manage your observability stack on AWS:\n' +
      'OpenSearch, Prometheus, IAM roles, and ingestion pipelines.'
    )
    .version(PKG_VERSION);

  // Mode
  program
    .option('--quick', 'Minimal input — auto-creates all resources with defaults')
    .option('--advanced', 'More options — create new or reuse existing resources');

  // Core
  program
    .option('--pipeline-name <name>', 'Pipeline name and resource prefix', DEFAULTS.pipelineName)
    .option('--region <region>', 'AWS region (e.g. us-east-1)');

  // OpenSearch backend type
  program
    .option('--serverless', 'Use OpenSearch Serverless (AOSS) instead of a managed domain')
    .option('--aoss-collection-name <name>', 'Collection name for OpenSearch Serverless');

  // OpenSearch — reuse
  program
    .option('--opensearch-endpoint <url>', 'Reuse an existing OpenSearch endpoint')
    .option('--opensearch-user <user>', 'OpenSearch master username', 'admin')
    .option('--opensearch-password <password>', 'Master password for existing OpenSearch domain (for FGAC mapping)');
  // OpenSearch — create (managed domain)
  program
    .option('--os-domain-name <name>', 'Domain name for new OpenSearch domain')
    .option('--engine-mode <mode>', 'Engine mode: general or optimized (OR1/OR2/OM2/OI2 instances)', DEFAULTS.engineMode)
    .option('--os-instance-type <type>', 'Instance type', DEFAULTS.osInstanceType)
    .option('--os-instance-count <n>', 'Number of data nodes', DEFAULTS.osInstanceCount)
    .option('--os-volume-size <gb>', 'EBS volume size in GB', DEFAULTS.osVolumeSize)
    .option('--os-engine-version <ver>', 'Engine version', DEFAULTS.osEngineVersion)
    .option('--managed', 'Target is OpenSearch managed domain');

  // Network topology — deploy into a VPC instead of public endpoints
  program
    .option('--vpc-id <id>', 'Deploy the domain, pipeline, and demo into this VPC (private endpoints)')
    .option('--subnet-ids <ids>', 'Comma-separated subnet IDs for VPC deployment')
    .option('--security-group-ids <ids>', 'Comma-separated security group IDs for VPC deployment');

  // IAM
  program
    .option('--iam-role-arn <arn>', 'Reuse an existing IAM role')
    .option('--iam-role-name <name>', 'Name for new IAM role');

  // APS
  program
    .option('--prometheus-url <url>', 'Reuse an existing APS remote-write URL')
    .option('--aps-workspace-alias <name>', 'Alias for new APS workspace');

  // Connected Data Source
  program
    .option('--connected-data-source-role-arn <arn>', 'Reuse an existing Connected Data Source Prometheus IAM role')
    .option('--connected-data-source-role-name <name>', 'Name for new Connected Data Source Prometheus IAM role')
    .option('--connected-data-source-name <name>', 'Name for the Connected Data Source');

  // Dashboards / Application
  program
    .option('--dashboards-url <url>', 'Reuse an existing OpenSearch UI URL')
    .option('--app-name <name>', 'Name for new OpenSearch Application');

  // Pipeline tuning
  program
    .option('--min-ocu <n>', 'Minimum OCUs', DEFAULTS.minOcu)
    .option('--max-ocu <n>', 'Maximum OCUs', DEFAULTS.maxOcu)
    .option('--service-map-window <dur>', 'Service-map window duration', DEFAULTS.serviceMapWindow);

  // Output
  program
    .option('-o, --output <file>', 'Write pipeline YAML to file instead of stdout')
    .option('--dry-run', 'Generate config only; do not create AWS resources')
    .option('--skip-demo', 'Skip launching EC2 demo workloads');

  program.parse(argv);

  const cfg = optsToConfig(program.opts());
  // Whether --os-volume-size was passed explicitly (vs. the default). Used to
  // reject an OI2 type combined with an explicit EBS volume size.
  cfg.osVolumeSizeExplicit = program.getOptionValueSource('osVolumeSize') === 'cli';
  // The default instance type is optimized (OR2). If the user selects general mode
  // without naming a type, fall back to a standard type so the two agree.
  if (cfg.engineMode === EngineMode.GENERAL && program.getOptionValueSource('osInstanceType') !== 'cli') {
    cfg.osInstanceType = DEFAULT_GENERAL_INSTANCE_TYPE;
  }
  return cfg;
}

function parseDestroyArgs(argv) {
  const program = new Command()
    .name('observability-stack-aws-cli destroy')
    .description('Tear down all AWS resources created by the CLI for a given pipeline name')
    .requiredOption('--pipeline-name <name>', 'Pipeline name used during creation')
    .option('--region <region>', 'AWS region', process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION)
    .option('--opensearch-password <password>', 'Master password (if domain was not created by CLI)')
    .option('--aoss-collection-name <name>', 'Collection name if it differs from the pipeline name');

  program.parse(argv.slice(1));
  return { _command: 'destroy', ...program.opts() };
}

/**
 * Parse a comma-separated list of IDs into a trimmed, de-duplicated array.
 * Returns [] for empty/undefined input.
 */
function parseIdList(value) {
  if (!value) return [];
  return [...new Set(value.split(',').map((s) => s.trim()).filter(Boolean))];
}

/**
 * Convert commander opts to our normalized config shape.
 */
function optsToConfig(opts) {
  const mode = opts.advanced ? 'advanced' : 'quick';
  const opensearchType = opts.serverless ? 'serverless' : 'managed';

  // Determine actions based on which flags were provided
  let osAction = '';
  if (opts.opensearchEndpoint) osAction = 'reuse';
  else if (opts.osDomainName || opts.aossCollectionName) osAction = 'create';

  let iamAction = '';
  if (opts.iamRoleArn) iamAction = 'reuse';
  else if (opts.iamRoleName) iamAction = 'create';

  let apsAction = '';
  if (opts.prometheusUrl) apsAction = 'reuse';
  else if (opts.apsWorkspaceAlias) apsAction = 'create';

  let dashboardsAction = '';
  if (opts.dashboardsUrl) dashboardsAction = 'reuse';
  else dashboardsAction = 'create';

  return {
    mode,
    pipelineName: opts.pipelineName,
    region: opts.region || '',
    opensearchType,
    osAction,
    aossCollectionName: opts.aossCollectionName || '',
    opensearchEndpoint: opts.opensearchEndpoint || '',
    opensearchUser: opts.opensearchUser || 'admin',
    opensearchPassword: opts.opensearchPassword || '',
    osDomainName: opts.osDomainName || '',
    engineMode: normalizeEngineMode(opts.engineMode),
    osInstanceType: opts.osInstanceType,
    osInstanceCount: Number(opts.osInstanceCount),
    osVolumeSize: Number(opts.osVolumeSize),
    osEngineVersion: opts.osEngineVersion,
    vpcId: opts.vpcId || '',
    subnetIds: parseIdList(opts.subnetIds),
    securityGroupIds: parseIdList(opts.securityGroupIds),
    iamAction,
    iamRoleArn: opts.iamRoleArn || '',
    iamRoleName: opts.iamRoleName || '',
    apsAction,
    prometheusUrl: opts.prometheusUrl || '',
    apsWorkspaceAlias: opts.apsWorkspaceAlias || '',
    apsWorkspaceId: '',
    minOcu: Number(opts.minOcu),
    maxOcu: Number(opts.maxOcu),
    serviceMapWindow: opts.serviceMapWindow,
    dashboardsAction,
    dashboardsUrl: opts.dashboardsUrl || '',
    connectedDataSourceRoleName: opts.connectedDataSourceRoleName || '',
    connectedDataSourceRoleArn: opts.connectedDataSourceRoleArn || '',
    connectedDataSourceName: opts.connectedDataSourceName || '',
    connectedDataSourceArn: '',
    appName: opts.appName || '',
    appId: '',
    appEndpoint: '',
    outputFile: opts.output || '',
    dryRun: opts.dryRun || false,
    skipDemo: opts.skipDemo || false,
    accountId: '',
  };
}

/**
 * Apply quick-mode defaults: fill in blanks so every field has a value.
 */
export function applyQuickDefaults(cfg) {
  if (!cfg.osAction) cfg.osAction = 'create';
  if (cfg.opensearchType === 'serverless') {
    if (!cfg.aossCollectionName) cfg.aossCollectionName = cfg.pipelineName;
  } else {
    if (!cfg.osDomainName) cfg.osDomainName = cfg.pipelineName;
  }
  if (!cfg.iamAction) cfg.iamAction = 'create';
  if (!cfg.iamRoleName) cfg.iamRoleName = `${cfg.pipelineName}-osi-role`;
  if (!cfg.apsAction) cfg.apsAction = 'create';
  if (!cfg.apsWorkspaceAlias) cfg.apsWorkspaceAlias = cfg.pipelineName;
  if (!cfg.dashboardsAction) cfg.dashboardsAction = 'create';
  if (!cfg.connectedDataSourceRoleName) cfg.connectedDataSourceRoleName = `${cfg.pipelineName}-connected-data-source-prometheus-role`;
  if (!cfg.connectedDataSourceName) cfg.connectedDataSourceName = `${cfg.pipelineName.replace(/-/g, '_')}_prometheus`;
  if (!cfg.appName) cfg.appName = cfg.pipelineName;
}

/**
 * Fill in placeholder values for resources that would be created in dry-run mode.
 */
export function fillDryRunPlaceholders(cfg) {
  if (cfg.osAction === 'create' && !cfg.opensearchEndpoint) {
    if (cfg.opensearchType === 'serverless') {
      cfg.opensearchEndpoint = `https://${cfg.aossCollectionName}.${cfg.region}.aoss.amazonaws.com`;
    } else {
      cfg.opensearchEndpoint = `https://search-${cfg.osDomainName}.${cfg.region}.es.amazonaws.com`;
    }
  }
  if (cfg.iamAction === 'create' && !cfg.iamRoleArn) {
    cfg.iamRoleArn = `arn:aws:iam::${cfg.accountId || '123456789012'}:role/${cfg.iamRoleName}`;
  }
  if (cfg.apsAction === 'create' && !cfg.prometheusUrl) {
    cfg.prometheusUrl = `https://aps-workspaces.${cfg.region}.amazonaws.com/workspaces/<workspace-id>/api/v1/remote_write`;
  }
  if (!cfg.connectedDataSourceRoleArn && cfg.connectedDataSourceRoleName) {
    cfg.connectedDataSourceRoleArn = `arn:aws:iam::${cfg.accountId || '123456789012'}:role/${cfg.connectedDataSourceRoleName}`;
  }
  if (!cfg.connectedDataSourceArn && cfg.connectedDataSourceName) {
    cfg.connectedDataSourceArn = `arn:aws:opensearch:${cfg.region}:${cfg.accountId || '123456789012'}:datasource/${cfg.connectedDataSourceName}`;
  }
  if (!cfg.appEndpoint) {
    cfg.appEndpoint = `https://<app-id>.${cfg.region}.opensearch.amazonaws.com`;
  }
}

/**
 * Validate the config. Returns an array of error strings (empty = valid).
 */
export function validateConfig(cfg) {
  const errors = [];

  if (!cfg.pipelineName) errors.push('--pipeline-name is required');
  if (cfg.pipelineName && cfg.pipelineName.length > 28) {
    errors.push(`--pipeline-name must be 28 characters or fewer (got ${cfg.pipelineName.length}). This limit is imposed by OSIS pipeline naming.`);
  }
  if (cfg.pipelineName && !/^[a-z][a-z0-9-]*$/.test(cfg.pipelineName)) {
    errors.push('--pipeline-name must start with a lowercase letter and contain only lowercase letters, numbers, and hyphens');
  }
  if (!cfg.region) errors.push('--region is required');

  // OpenSearch backend must be resolved to either create or reuse. In advanced
  // mode with no OpenSearch flags, osAction stays empty and the domain step is
  // silently skipped — the run then fails deep in pipeline creation with an empty
  // endpoint. Catch it up front so the CLI fails fast with a clear message.
  if (!cfg.osAction) {
    errors.push('No OpenSearch backend specified. Pass --os-domain-name (create a managed domain), --aoss-collection-name (create a serverless collection), or --opensearch-endpoint (reuse an existing one). Or run with --quick to auto-create defaults.');
  }
  if (cfg.osAction === 'reuse' && !cfg.opensearchEndpoint) {
    errors.push('--opensearch-endpoint required when reusing OpenSearch');
  }
  if (cfg.osAction === 'reuse' && cfg.opensearchType !== 'serverless' && !cfg.opensearchPassword) {
    errors.push('--opensearch-password required when reusing an existing OpenSearch domain (needed for FGAC mapping)');
  }
  // The OSI pipeline cannot be created without a role. In advanced mode with no
  // IAM flags, iamAction stays empty and the role step is silently skipped — the
  // run then reaches OSIS CreatePipeline with an empty PipelineRoleArn and fails
  // ~11 min later (after the domain is built) with a cryptic cross-account/pass-role
  // error. Catch it up front, symmetric to the osAction guard above.
  if (!cfg.iamAction) {
    errors.push('No OSI pipeline role specified. Pass --iam-role-name (create one) or --iam-role-arn (reuse an existing one). Or run with --quick to auto-create defaults.');
  }
  if (cfg.iamAction === 'reuse' && !cfg.iamRoleArn) {
    errors.push('--iam-role-arn required when reusing IAM role');
  }
  if (cfg.apsAction === 'reuse' && !cfg.prometheusUrl) {
    errors.push('--prometheus-url required when reusing APS workspace');
  }
  if (cfg.dashboardsAction === 'reuse' && !cfg.dashboardsUrl) {
    errors.push('--dashboards-url required when reusing OpenSearch UI');
  }

  // Format checks
  if (cfg.region && !/^[a-z]{2}-[a-z]+-\d+$/.test(cfg.region)) {
    errors.push(`Region format looks wrong: ${cfg.region} (expected e.g. us-east-1)`);
  }
  if (cfg.osAction === 'reuse' && cfg.opensearchEndpoint && !/^https?:\/\//.test(cfg.opensearchEndpoint)) {
    errors.push('OpenSearch endpoint must start with http:// or https://');
  }
  if (cfg.iamAction === 'reuse' && cfg.iamRoleArn && !cfg.iamRoleArn.startsWith('arn:aws:iam:')) {
    errors.push('IAM role ARN must start with arn:aws:iam:');
  }
  if (cfg.apsAction === 'reuse' && cfg.prometheusUrl && !/^https?:\/\//.test(cfg.prometheusUrl)) {
    errors.push('Prometheus URL must start with http:// or https://');
  }

  // VPC deployment: all three (vpc/subnets/SGs) must be present together and well-formed.
  const wantsVpc = cfg.vpcId || cfg.subnetIds?.length || cfg.securityGroupIds?.length;
  if (wantsVpc) {
    if (!cfg.vpcId) errors.push('--vpc-id is required when configuring subnets or security groups');
    if (!cfg.subnetIds?.length) errors.push('--subnet-ids is required for VPC deployment (at least one subnet)');
    if (!cfg.securityGroupIds?.length) errors.push('--security-group-ids is required for VPC deployment (at least one security group)');

    if (cfg.vpcId && !/^vpc-[0-9a-f]+$/.test(cfg.vpcId)) {
      errors.push(`--vpc-id must look like vpc-xxxxxxxx (got ${cfg.vpcId})`);
    }
    for (const id of cfg.subnetIds || []) {
      if (!/^subnet-[0-9a-f]+$/.test(id)) errors.push(`Invalid subnet ID: ${id} (expected subnet-xxxxxxxx)`);
    }
    for (const id of cfg.securityGroupIds || []) {
      if (!/^sg-[0-9a-f]+$/.test(id)) errors.push(`Invalid security group ID: ${id} (expected sg-xxxxxxxx)`);
    }
    // OpenSearch domains support at most 3 subnets (one per AZ, zone-awareness limit).
    if (cfg.subnetIds?.length > 3) {
      errors.push(`--subnet-ids accepts at most 3 subnets for an OpenSearch domain (got ${cfg.subnetIds.length})`);
    }
    // A VPC domain cannot be reused via a public endpoint reference; VPC only applies to newly created domains.
    if (cfg.osAction === 'reuse') {
      errors.push('VPC options apply only when creating a new OpenSearch domain; omit --vpc-id when reusing an existing endpoint');
    }
  }

  // Engine mode / optimized instance family checks (only when creating a domain).
  if (cfg.osAction === 'create' && cfg.opensearchType !== 'serverless') {
    if (cfg.engineMode !== EngineMode.GENERAL && cfg.engineMode !== EngineMode.OPTIMIZED) {
      errors.push(`--engine-mode must be 'general' or 'optimized' (got ${cfg.engineMode || '(empty)'})`);
    }
    const typeIsOptimized = isOptimizedInstanceType(cfg.osInstanceType);
    // The engine mode and the instance family must agree: the optimized engine
    // runs only on OR1/OR2/OM2/OI2; the general engine runs only on standard types.
    if (cfg.engineMode === EngineMode.OPTIMIZED && cfg.osInstanceType && !typeIsOptimized) {
      errors.push(`--engine-mode optimized requires an optimized instance type (OR2/OM2/OI2), got ${cfg.osInstanceType}`);
    }
    if (cfg.engineMode === EngineMode.GENERAL && typeIsOptimized) {
      errors.push(`Instance type ${cfg.osInstanceType} is an optimized type; pass --engine-mode optimized to use it`);
    }
    // OI2 uses local NVMe and takes no EBS configuration. Only reject an EBS
    // volume the user set explicitly; the default is ignored (EBS is omitted for OI2).
    if (isNvmeOnlyInstanceType(cfg.osInstanceType) && cfg.osVolumeSizeExplicit) {
      errors.push(`Instance type ${cfg.osInstanceType} uses local NVMe storage and cannot take an EBS volume; omit --os-volume-size`);
    }
    // Optimized domains require encryption at rest (always enabled here) and
    // OpenSearch 3.5 or newer (verified against CreateDomain; the developer guide
    // still lists 2.11). https://docs.aws.amazon.com/opensearch-service/latest/developerguide/or1.html
    const optimized = cfg.engineMode === EngineMode.OPTIMIZED || typeIsOptimized;
    if (optimized) {
      const { major: minMajor, minor: minMinor } = OPTIMIZED_MIN_VERSION;
      const m = /^OpenSearch_(\d+)\.(\d+)$/.exec(cfg.osEngineVersion || '');
      const tooOld = m
        ? (Number(m[1]) < minMajor || (Number(m[1]) === minMajor && Number(m[2]) < minMinor))
        : Boolean(cfg.osEngineVersion);
      if (tooOld) {
        errors.push(`Optimized domains require OpenSearch ${minMajor}.${minMinor} or newer (got ${cfg.osEngineVersion})`);
      }
    }
  }

  return errors;
}
