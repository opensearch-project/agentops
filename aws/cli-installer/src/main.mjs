import { writeFileSync } from 'node:fs';
import { configureAwsProfile } from './aws-profile.mjs';
import { parseCli, applyQuickDefaults, validateConfig, fillDryRunPlaceholders } from './cli.mjs';
import { renderPipeline } from './render.mjs';
import {
  checkRequirements,
  createOpenSearch,
  createIamRole,
  createApsWorkspace,
  createOsiPipeline,
  mapOsiRoleInDomain,
  mapOsiRoleViaOpenSearchUI,
  createAossDataAccessPolicy,
  setupDashboards,
  createConnectedDataSourceRole,
  createConnectedDataSource,
  createOpenSearchApplication,
  validateVpcTopology,
  checkSecurityGroupRules,
} from './aws.mjs';
import {
  printError,
  printSuccess,
  printStep,
  printWarning,
  printPanel,
  printBox,
  STAR,
  theme,
  link,
} from './ui.mjs';

export async function run() {
  try {
    // Parse CLI or run interactive REPL
    let cfg = parseCli(process.argv);
    configureAwsProfile(cfg?.profile);
    if (!cfg || cfg._command === 'repl') {
      const { startRepl } = await import('./repl.mjs');
      return startRepl();
    }

    // Destroy subcommand
    if (cfg._command === 'destroy') {
      const { destroy } = await import('./destroy.mjs');
      await destroy(cfg);
      return;
    }

    // Apply quick-mode defaults for anything not explicitly set
    if (!cfg.mode) cfg.mode = 'quick';
    if (cfg.mode === 'quick') applyQuickDefaults(cfg);

    // Validate
    const errors = validateConfig(cfg);
    if (errors.length) {
      for (const e of errors) printError(e);
      console.error('Run with --help for usage information.');
      process.exit(1);
    }

    // ── Dry-run path ──────────────────────────────────────────────────────
    if (cfg.dryRun) {
      printSummary(cfg);
      fillDryRunPlaceholders(cfg);

      const yaml = renderPipeline(cfg);

      if (cfg.outputFile) {
        writeFileSync(cfg.outputFile, yaml + '\n');
        printSuccess(`Pipeline YAML written to ${cfg.outputFile}`);
      } else {
        if (process.stdout.isTTY) {
          console.error(`  ${theme.muted('\u2500'.repeat(43))}`);
        }
        process.stdout.write(yaml);
      }
      process.exit(0);
    }

    // ── Live path ─────────────────────────────────────────────────────────
    await executePipeline(cfg);

  } catch (err) {
    if (err.name === 'ExitPromptError') {
      // User pressed Ctrl+C during a prompt
      console.error();
      process.exit(130);
    }
    printError(err.message);
    process.exit(1);
  }
}

/**
 * Execute the full pipeline creation flow.
 * Shared by the CLI path (main.mjs) and the REPL create command.
 */
export async function executePipeline(cfg) {
  await checkRequirements(cfg);

  // Live VPC validation — verify the VPC/subnets/SGs exist, belong together, and
  // satisfy zone-awareness before creating any OpenSearch resources. Fails fast
  // so we don't leave a half-built stack when the network inputs are wrong.
  if (cfg.vpcId) {
    printStep('Validating VPC network configuration...');
    const vpcErrors = await validateVpcTopology(cfg);
    if (vpcErrors.length) {
      console.error();
      for (const e of vpcErrors) printError(e);
      throw new Error('VPC configuration is invalid; no resources were created.');
    }
    printSuccess('VPC, subnets, and security groups validated');

    // Topology validation proves the SGs exist and belong to the VPC, not that
    // their rules permit the 443 data path. Warn before the ~30-min build.
    const sgWarnings = await checkSecurityGroupRules(cfg);
    for (const w of sgWarnings) printWarning(w);
    console.error();
  }

  printSummary(cfg);
  console.error();

  // Create resources — OpenSearch first (slow), then IAM & APS
  if (cfg.osAction === 'create') {
    await createOpenSearch(cfg);
    console.error();
  }

  if (cfg.iamAction === 'create') {
    await createIamRole(cfg);
    console.error();
  }

  if (cfg.apsAction === 'create') {
    await createApsWorkspace(cfg);
    console.error();
  }

  // Map OSI role in managed domain FGAC (skip for serverless — IAM-only)
  if (cfg.opensearchType !== 'serverless' && cfg.opensearchEndpoint && cfg.iamRoleArn) {
    await mapOsiRoleInDomain(cfg);
    console.error();
  }

  // Create AOSS data access policy (serverless only, after IAM role exists)
  if (cfg.opensearchType === 'serverless' && cfg.aossCollectionName && cfg.iamRoleArn) {
    await createAossDataAccessPolicy(cfg);
    console.error();
  }

  // Extract apsWorkspaceId from prometheusUrl if not already set
  if (!cfg.apsWorkspaceId && cfg.prometheusUrl) {
    const m = cfg.prometheusUrl.match(/\/workspaces\/(ws-[^/]+)\//);
    if (m) cfg.apsWorkspaceId = m[1];
  }

  // Create Connected Data Source role and data source (connects AMP to OpenSearch)
  if (cfg.apsWorkspaceId && cfg.connectedDataSourceRoleName) {
    await createConnectedDataSourceRole(cfg);
    console.error();

    await createConnectedDataSource(cfg);
    console.error();
  }

  // Create OpenSearch Application and associate data sources
  if (cfg.appName) {
    await createOpenSearchApplication(cfg);
    console.error();
  }

  // For VPC-private domains, FGAC role mapping is deferred until the managed
  // OpenSearch UI (Application) exists, since the UI proxies to the domain over
  // the AWS-internal path — no in-VPC network access needed from this host.
  if (cfg.deferFgacToUi) {
    await mapOsiRoleViaOpenSearchUI(cfg);
    console.error();
  }

  // Generate pipeline YAML
  const pipelineYaml = renderPipeline(cfg);

  if (cfg.outputFile) {
    writeFileSync(cfg.outputFile, pipelineYaml + '\n');
    printSuccess(`Pipeline YAML saved to ${cfg.outputFile}`);
    console.error();
  }

  // Create the OSI pipeline
  await createOsiPipeline(cfg, pipelineYaml);
  console.error();

  // Set up OpenSearch UI and create Observability workspace
  await setupDashboards(cfg);

  // Initialize OpenSearch UI (workspaces, index patterns, correlations, dashboards)
  const { initOpenSearchUI } = await import('./opensearch-ui-init.mjs');
  await initOpenSearchUI(cfg);

  // Launch EC2 demo workloads (unless --skip-demo)
  if (!cfg.skipDemo && cfg.ingestEndpoints?.length) {
    const { launchDemoInstance } = await import('./ec2-demo.mjs');
    await launchDemoInstance(cfg);
  }

  // ── Final summary ───────────────────────────────────────────────────
  console.error();
  const pad = (l) => l.padEnd(35);
  const osiUrl = cfg.ingestEndpoints?.length ? `https://${cfg.ingestEndpoints[0]}` : null;
  printBox([
    '',
    `${theme.success.bold(`${STAR} Open Stack Setup Complete! ${STAR}`)}`,
    '',
    `${theme.label(pad('OSI Pipeline:'))} ${osiUrl ? link(osiUrl) : cfg.pipelineName}`,
    `${theme.label(pad('OSI Pipeline Role:'))} ${cfg.iamRoleArn}`,
    `${theme.label(pad('OpenSearch:'))} ${link(cfg.opensearchEndpoint)}`,
    ...(cfg.opensearchType !== 'serverless' ? [
      cfg.iamMasterArn
        ? `${theme.label(pad('OpenSearch Master:'))} IAM principal ${cfg.iamMasterArn}`
        : `${theme.label(pad('OpenSearch Master Password:'))} Secrets Manager: observability-stack/${cfg.pipelineName}/master-password`,
    ] : []),
    `${theme.label(pad('OpenSearch UI:'))} ${link(cfg.dashboardsUrl)}`,
    `${theme.label(pad('Prometheus:'))} ${link(cfg.prometheusUrl)}`,
    `${theme.label(pad('Connected Data Source:'))} ${cfg.connectedDataSourceArn || 'n/a'}`,
    `${theme.label(pad('Connected Data Source Role:'))} ${cfg.connectedDataSourceRoleArn || 'n/a'}`,
    ...(cfg.demoInstanceId ? [
      `${theme.label(pad('Demo EC2 Instance:'))} ${cfg.demoInstanceId}`,
      `${pad('')} ${theme.muted(`└─ Connect: aws ssm start-session --target ${cfg.demoInstanceId} --region ${cfg.region}`)}`,
    ] : []),
    '',
    `${theme.success.bold('→ Open your dashboards')} ${theme.muted('(requires signing into your AWS account)')}`,
    `  ${link(cfg.dashboardsUrl)}`,
    ...(cfg.demoInstanceId ? [``, `  ${theme.muted('Demo data may take 10-15 minutes to appear.')}`] : []),
    '',
  ], { color: 'primary', padding: 2 });

}

// ── Summary ─────────────────────────────────────────────────────────────────

function printSummary(cfg) {
  console.error();

  // Core info
  const coreEntries = [
    ['Mode', cfg.mode],
    ['Pipeline name', cfg.pipelineName],
    ['Region', cfg.region],
  ];

  // OpenSearch
  const osEntries = [];
  if (cfg.opensearchType === 'serverless') {
    osEntries.push(['Type', 'Serverless (AOSS)']);
    if (cfg.osAction === 'reuse') {
      osEntries.push(['Action', 'reuse existing collection']);
      osEntries.push(['Endpoint', cfg.opensearchEndpoint]);
    } else {
      osEntries.push(['Action', 'create new AOSS collection']);
      osEntries.push(['Collection name', cfg.aossCollectionName]);
    }
  } else if (cfg.osAction === 'reuse') {
    osEntries.push(['Action', 'reuse existing']);
    osEntries.push(['Endpoint', cfg.opensearchEndpoint]);
    osEntries.push(['Type', 'Managed domain']);
  } else {
    osEntries.push(['Action', 'create new managed domain']);
    osEntries.push(['Domain name', cfg.osDomainName]);
    osEntries.push(['Instance type', cfg.osInstanceType]);
    osEntries.push(['Instance count', String(cfg.osInstanceCount)]);
    osEntries.push(['Volume size', `${cfg.osVolumeSize} GB`]);
    osEntries.push(['Engine version', cfg.osEngineVersion]);
    if (cfg.vpcId) {
      osEntries.push(['Network', `VPC ${cfg.vpcId}`]);
      osEntries.push(['Subnets', cfg.subnetIds.join(', ')]);
      osEntries.push(['Security groups', cfg.securityGroupIds.join(', ')]);
    } else {
      osEntries.push(['Network', 'public endpoint']);
    }
  }

  // IAM
  const iamEntries = [];
  if (cfg.iamAction === 'reuse') {
    iamEntries.push(['Pipeline role ARN', cfg.iamRoleArn]);
  } else {
    iamEntries.push(['Pipeline role', cfg.iamRoleName]);
  }

  // APS
  const apsEntries = [];
  if (cfg.apsAction === 'reuse') {
    apsEntries.push(['Action', 'reuse existing']);
    apsEntries.push(['Remote write URL', cfg.prometheusUrl]);
  } else {
    apsEntries.push(['Action', 'create new']);
    apsEntries.push(['Workspace alias', cfg.apsWorkspaceAlias]);
  }

  // Dashboards
  const dashEntries = [];
  if (cfg.dashboardsAction === 'reuse') {
    dashEntries.push(['Action', 'reuse existing']);
    dashEntries.push(['URL', cfg.dashboardsUrl]);
  } else {
    dashEntries.push(['Action', 'create new Observability workspace']);
  }
  if (cfg.appName) dashEntries.push(['Application name', cfg.appName]);

  // Connected Data Source
  const dqEntries = [];
  if (cfg.connectedDataSourceRoleName) dqEntries.push(['Connected Data Source role', cfg.connectedDataSourceRoleName]);
  else if (cfg.connectedDataSourceRoleArn) dqEntries.push(['Connected Data Source role ARN', cfg.connectedDataSourceRoleArn]);
  if (cfg.connectedDataSourceName) dqEntries.push(['Data source name', cfg.connectedDataSourceName]);

  // Pipeline settings
  const tuneEntries = [
    ['Min OCU', String(cfg.minOcu)],
    ['Max OCU', String(cfg.maxOcu)],
    ['Service-map window', cfg.serviceMapWindow],
  ];

  printPanel(`${STAR} Configuration Summary`, [
    ...coreEntries,
    ['', ''],
    ['', theme.accentBold('OpenSearch')],
    ...osEntries,
    ['', ''],
    ['', theme.accentBold('OpenSearch UI')],
    ...dashEntries,
    ['', ''],
    ['', theme.accentBold('Amazon Managed Prometheus')],
    ...apsEntries,
    ['', ''],
    ['', theme.accentBold('Connected Data Source')],
    ...dqEntries,
    ['', ''],
    ['', theme.accentBold('Ingestion Pipeline')],
    ...iamEntries,
    ...tuneEntries,
  ]);

  if (cfg.dryRun) {
    console.error();
    console.error(`  ${theme.warn('DRY RUN')} ${theme.muted('\u2014 will generate config only, no AWS resources created')}`);
  }

  console.error();
}
