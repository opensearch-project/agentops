import {
  printHeader, printStep, printInfo, printSubStep, printWarning,
  createSpinner, theme, GoBack, eSelect, eInput, eCheckbox,
  saveCursor, clearFromCursor,
} from './ui.mjs';
import { createDefaultConfig, DEFAULTS, DEFAULT_REGION } from './config.mjs';
import { EngineMode, OPTIMIZED_FAMILY_CHOICES, DEFAULT_GENERAL_INSTANCE_TYPE, optimizedInstanceType, isNvmeOnlyInstanceType } from './engine.mjs';
import { listDomains, listCollections, listWorkspaces, listApplications, listVpcs, listSubnets, listSecurityGroups } from './aws.mjs';

const CUSTOM_INPUT = Symbol('custom');

/**
 * Fetch resources with a spinner, returning [] on failure.
 */
async function fetchWithSpinner(label, fn) {
  const spinner = createSpinner(label);
  spinner.start();
  try {
    const result = await fn();
    spinner.succeed(`${label} (${result.length} found)`);
    return result;
  } catch (err) {
    spinner.warn(`Could not list resources: ${err.message}`);
    return [];
  }
}

// ── Step functions ────────────────────────────────────────────────────────────

async function stepMode(cfg) {
  printStep('Select mode');
  console.error();

  const mode = await eSelect({
    message: 'Mode',
    choices: [
      { name: `Quick    ${theme.muted('\u2014 creates all resources with defaults')}`, value: 'quick' },
      { name: `Advanced ${theme.muted('\u2014 create new or reuse existing resources; tune pipeline settings')}`, value: 'advanced' },
    ],
    default: cfg.mode || 'quick',
  });
  if (mode === GoBack) return GoBack;
  cfg.mode = mode;
  console.error();
}

async function stepCore(cfg, session) {
  printStep('Core settings');
  console.error();

  const name = await eInput({
    message: 'Pipeline name',
    default: cfg.pipelineName || DEFAULTS.pipelineName,
    validate: (v) => v.trim().length > 0 || 'Pipeline name is required',
  });
  if (name === GoBack) return GoBack;
  cfg.pipelineName = name;

  if (session) {
    cfg.region = session.region;
    cfg.accountId = session.accountId;
    printSubStep(`Region: ${theme.accent(cfg.region)}`);
  } else {
    const region = await eInput({
      message: 'AWS region',
      default: cfg.region || DEFAULT_REGION,
      validate: (v) => /^[a-z]{2}-[a-z]+-\d+$/.test(v) || 'Expected format: us-east-1',
    });
    if (region === GoBack) return GoBack;
    cfg.region = region;
  }

  // OpenSearch backend type
  const osType = await eSelect({
    message: 'OpenSearch backend',
    choices: [
      { name: `Managed domain    ${theme.muted('— provisioned cluster with FGAC')}`, value: 'managed' },
      { name: `Serverless (AOSS) ${theme.muted('— auto-scaling, IAM-only auth')}`, value: 'serverless' },
    ],
    default: cfg.opensearchType || 'managed',
  });
  if (osType === GoBack) return GoBack;
  cfg.opensearchType = osType;

  // Quick mode: auto-derive all resources from pipeline name
  if (cfg.mode === 'quick') {
    cfg.osAction = 'create';
    if (cfg.opensearchType === 'serverless') {
      cfg.aossCollectionName = cfg.pipelineName;
    } else {
      cfg.osDomainName = cfg.pipelineName;
    }
    cfg.iamAction = 'create';
    cfg.iamRoleName = `${cfg.pipelineName}-osi-role`;
    cfg.apsAction = 'create';
    cfg.apsWorkspaceAlias = cfg.pipelineName;
    cfg.dashboardsAction = 'create';
    cfg.connectedDataSourceRoleName = `${cfg.pipelineName}-connected-data-source-prometheus-role`;
    cfg.connectedDataSourceName = `${cfg.pipelineName.replace(/-/g, '_')}_prometheus`;
    cfg.appName = cfg.pipelineName;
    console.error();
    printInfo(`Will create:`);
    if (cfg.opensearchType === 'serverless') {
      printSubStep(`AOSS collection: ${theme.accent(cfg.aossCollectionName)}`);
    } else {
      printSubStep(`OpenSearch domain: ${theme.accent(cfg.osDomainName)}`);
    }
    printSubStep(`IAM role: ${theme.accent(cfg.iamRoleName)}`);
    printSubStep(`APS workspace: ${theme.accent(cfg.apsWorkspaceAlias)}`);
    printSubStep(`Connected Data Source role: ${theme.accent(cfg.connectedDataSourceRoleName)}`);
    printSubStep(`Connected Data Source: ${theme.accent(cfg.connectedDataSourceName)}`);
    printSubStep(`OpenSearch Application: ${theme.accent(cfg.appName)}`);
  }
}

async function stepOpenSearch(cfg) {
  if (cfg.mode !== 'advanced') return 'skip';

  const isServerless = cfg.opensearchType === 'serverless';
  printStep(isServerless ? 'OpenSearch Serverless' : 'OpenSearch');
  console.error();

  while (true) {
    saveCursor();
    const osChoice = await eSelect({
      message: 'Create new or reuse existing?',
      choices: [
        { name: 'Create new', value: 'create' },
        { name: 'Reuse existing', value: 'reuse' },
      ],
      default: cfg.osAction || 'create',
    });
    if (osChoice === GoBack) return GoBack;

    if (osChoice === 'reuse') {
      cfg.osAction = 'reuse';

      if (isServerless) {
        // Serverless reuse path
        const collections = await fetchWithSpinner(
          'Loading AOSS collections',
          () => listCollections(cfg.region),
        );

        if (collections.length > 0) {
          const choices = collections.map((c) => ({
            name: c.status === 'ACTIVE'
              ? `${c.name} ${theme.muted(`— ${c.endpoint}`)}`
              : `${c.name} ${theme.muted(`— ${c.status}`)}`,
            value: { endpoint: c.endpoint, id: c.id, name: c.name },
            disabled: c.status !== 'ACTIVE' ? `(${c.status})` : false,
          }));
          choices.push({ name: theme.accent('Enter manually...'), value: CUSTOM_INPUT });

          const selected = await eSelect({ message: 'Select collection', choices });
          if (selected === GoBack) { clearFromCursor(); continue; }
          if (selected === CUSTOM_INPUT) {
            const ep = await promptEndpoint();
            if (ep === GoBack) { clearFromCursor(); continue; }
            cfg.opensearchEndpoint = ep;
            const collName = await eInput({ message: 'Collection name', validate: (v) => v.trim().length > 0 || 'Collection name is required' });
            if (collName === GoBack) { clearFromCursor(); continue; }
            cfg.aossCollectionName = collName;
          } else {
            cfg.opensearchEndpoint = selected.endpoint;
            cfg.collectionId = selected.id;
            cfg.aossCollectionName = selected.name;
          }
        } else {
          printInfo('No collections found — enter endpoint manually');
          const ep = await promptEndpoint();
          if (ep === GoBack) { clearFromCursor(); continue; }
          cfg.opensearchEndpoint = ep;
          const collName = await eInput({ message: 'Collection name', validate: (v) => v.trim().length > 0 || 'Collection name is required' });
          if (collName === GoBack) { clearFromCursor(); continue; }
          cfg.aossCollectionName = collName;
        }
      } else {
      // Managed domain reuse path
      const domains = await fetchWithSpinner(
        'Loading OpenSearch domains',
        () => listDomains(cfg.region),
      );

      if (domains.length > 0) {
        const choices = domains.map((d) => ({
          name: d.endpoint
            ? `${d.name} ${theme.muted(`\u2014 ${d.endpoint} (${d.engineVersion})`)}`
            : `${d.name} ${theme.muted(`\u2014 provisioning... (${d.engineVersion})`)}`,
          value: { endpoint: d.endpoint },
          disabled: !d.endpoint ? '(no endpoint yet)' : false,
        }));
        choices.push({ name: theme.accent('Enter manually...'), value: CUSTOM_INPUT });

        const selected = await eSelect({ message: 'Select domain', choices });
        if (selected === GoBack) { clearFromCursor(); continue; }
        if (selected === CUSTOM_INPUT) {
          const ep = await promptEndpoint();
          if (ep === GoBack) { clearFromCursor(); continue; }
          cfg.opensearchEndpoint = ep;
        } else {
          cfg.opensearchEndpoint = selected.endpoint;
        }
      } else {
        printInfo('No domains found \u2014 enter endpoint manually');
        const ep = await promptEndpoint();
        if (ep === GoBack) { clearFromCursor(); continue; }
        cfg.opensearchEndpoint = ep;
      }

      // Try Secrets Manager first — skip prompts if password already stored
      let smPass;
      try { smPass = await getMasterPassword(cfg.region, cfg.pipelineName); } catch {}
      if (smPass) {
        cfg.opensearchUser = cfg.opensearchUser || 'admin';
        cfg.opensearchPassword = smPass;
        printInfo('Master password found in Secrets Manager — skipping credential prompts');
      } else {
        const user = await eInput({
          message: 'OpenSearch master username',
          default: cfg.opensearchUser || 'admin',
        });
        if (user === GoBack) { clearFromCursor(); continue; }
        cfg.opensearchUser = user;

        const pass = await eInput({
          message: 'OpenSearch master password (for FGAC role mapping)',
          validate: (v) => v.trim().length > 0 || 'Password is required to configure access',
        });
        if (pass === GoBack) { clearFromCursor(); continue; }
        cfg.opensearchPassword = pass;
      }
      } // end managed reuse else
    } else {
      cfg.osAction = 'create';

      if (isServerless) {
        const collName = await eInput({ message: 'Collection name', default: cfg.aossCollectionName || cfg.pipelineName });
        if (collName === GoBack) { clearFromCursor(); continue; }
        cfg.aossCollectionName = collName;
      } else {
      const domainName = await eInput({ message: 'Domain name', default: cfg.osDomainName || cfg.pipelineName });
      if (domainName === GoBack) { clearFromCursor(); continue; }
      cfg.osDomainName = domainName;

      const engineMode = await eSelect({
        message: 'Engine mode',
        choices: [
          { name: `Optimized ${theme.muted('— OR2/OM2/OI2, recommended for log analytics/observability')}`, value: EngineMode.OPTIMIZED },
          { name: `General  ${theme.muted('— standard instances (e.g. r6g), EBS storage')}`, value: EngineMode.GENERAL },
        ],
        default: cfg.engineMode || DEFAULTS.engineMode,
      });
      if (engineMode === GoBack) { clearFromCursor(); continue; }
      cfg.engineMode = engineMode;

      let instType;
      if (engineMode === EngineMode.OPTIMIZED) {
        // Select a family, then a size, and compose the instance type.
        const family = await eSelect({
          message: 'Optimized instance family',
          choices: OPTIMIZED_FAMILY_CHOICES.map((f) => ({ name: f.label, value: f.family })),
          default: OPTIMIZED_FAMILY_CHOICES[0].family,
        });
        if (family === GoBack) { clearFromCursor(); continue; }
        const sizes = OPTIMIZED_FAMILY_CHOICES.find((f) => f.family === family).sizes;
        const size = await eSelect({
          message: 'Instance size',
          choices: sizes.map((s) => ({ name: s, value: s })),
          default: sizes[0],
        });
        if (size === GoBack) { clearFromCursor(); continue; }
        instType = optimizedInstanceType(family, size);
      } else {
        instType = await eInput({ message: 'Instance type', default: DEFAULT_GENERAL_INSTANCE_TYPE });
      }
      if (instType === GoBack) { clearFromCursor(); continue; }
      cfg.osInstanceType = instType;

      const instCount = await eInput({
        message: 'Instance count',
        default: String(cfg.osInstanceCount || DEFAULTS.osInstanceCount),
        validate: (v) => /^\d+$/.test(v.trim()) && Number(v) >= 1 || 'Must be a positive integer',
      });
      if (instCount === GoBack) { clearFromCursor(); continue; }
      cfg.osInstanceCount = Number(instCount);

      // OI2 uses local NVMe and takes no EBS volume, so skip the size prompt.
      if (isNvmeOnlyInstanceType(cfg.osInstanceType)) {
        cfg.osVolumeSize = 0;
      } else {
        const volSize = await eInput({
          message: 'EBS volume size (GB)',
          default: String(cfg.osVolumeSize || DEFAULTS.osVolumeSize),
          validate: (v) => /^\d+$/.test(v.trim()) && Number(v) >= 10 || 'Must be at least 10 GB',
        });
        if (volSize === GoBack) { clearFromCursor(); continue; }
        cfg.osVolumeSize = Number(volSize);
      }

      const engineVer = await eInput({ message: 'Engine version', default: cfg.osEngineVersion || DEFAULTS.osEngineVersion });
      if (engineVer === GoBack) { clearFromCursor(); continue; }
      cfg.osEngineVersion = engineVer;
      } // end managed create else
    }
    return;
  }
}

async function stepVpc(cfg) {
  if (cfg.mode !== 'advanced') return 'skip';
  // VPC options only apply when creating a new domain (not reusing an endpoint).
  if (cfg.osAction === 'reuse') return 'skip';

  printStep('Network topology');
  printInfo('Deploy the domain, ingestion pipeline, and demo into a VPC for private endpoints,');
  printInfo('or use public endpoints (default).');
  console.error();

  while (true) {
    const netChoice = await eSelect({
      message: 'Deployment network',
      choices: [
        { name: `Public endpoints ${theme.muted('— default, reachable over the internet')}`, value: 'public' },
        { name: `VPC ${theme.muted('— private endpoints inside a VPC (EKS/ECS workloads)')}`, value: 'vpc' },
      ],
      default: cfg.vpcId ? 'vpc' : 'public',
    });
    if (netChoice === GoBack) return GoBack;

    if (netChoice === 'public') {
      cfg.vpcId = '';
      cfg.subnetIds = [];
      cfg.securityGroupIds = [];
      return;
    }

    // VPC selection
    const vpcs = await fetchWithSpinner('Loading VPCs', () => listVpcs(cfg.region));
    if (!vpcs.length) {
      printWarning('No VPCs found in this region — falling back to public endpoints.');
      cfg.vpcId = '';
      return;
    }
    const vpcChoices = vpcs.map((v) => ({
      name: `${v.id} ${theme.muted(`— ${v.cidr}${v.name ? ` (${v.name})` : ''}${v.isDefault ? ' [default]' : ''}`)}`,
      value: v.id,
    }));
    const selectedVpc = await eSelect({ message: 'Select VPC', choices: vpcChoices });
    if (selectedVpc === GoBack) continue;
    cfg.vpcId = selectedVpc;

    // Subnet selection (multi-select, at most 3 for the domain)
    const subnets = await fetchWithSpinner('Loading subnets', () => listSubnets(cfg.region, cfg.vpcId));
    if (!subnets.length) {
      printWarning('No subnets found in that VPC — pick another VPC or use public endpoints.');
      continue;
    }
    const subnetChoices = subnets.map((s) => ({
      name: `${s.id} ${theme.muted(`— ${s.az} ${s.cidr}${s.name ? ` (${s.name})` : ''}`)}`,
      value: s.id,
    }));
    const selectedSubnets = await eCheckbox({
      message: 'Select subnets (1-3, ideally one per AZ)',
      choices: subnetChoices,
      required: true,
    });
    if (selectedSubnets === GoBack) continue;
    if (!selectedSubnets.length) {
      printWarning('Select at least one subnet.');
      continue;
    }
    if (selectedSubnets.length > 3) {
      printWarning('An OpenSearch domain supports at most 3 subnets — select 3 or fewer.');
      continue;
    }
    cfg.subnetIds = selectedSubnets;

    // Security group selection (multi-select)
    const sgs = await fetchWithSpinner('Loading security groups', () => listSecurityGroups(cfg.region, cfg.vpcId));
    if (!sgs.length) {
      printWarning('No security groups found in that VPC — pick another VPC or use public endpoints.');
      continue;
    }
    const sgChoices = sgs.map((g) => ({
      name: `${g.id} ${theme.muted(`— ${g.name}${g.description ? ` (${g.description})` : ''}`)}`,
      value: g.id,
    }));
    const selectedSgs = await eCheckbox({
      message: 'Select security groups',
      choices: sgChoices,
      required: true,
    });
    if (selectedSgs === GoBack) continue;
    if (!selectedSgs.length) {
      printWarning('Select at least one security group.');
      continue;
    }
    cfg.securityGroupIds = selectedSgs;

    printInfo('The pipeline and demo instance will be placed in this VPC too.');
    printInfo("Your IAM principal will be the domain's master user; FGAC mapping and UI setup run through the managed OpenSearch UI, so you can run this from anywhere.");
    return;
  }
}

async function stepIam(cfg) {
  if (cfg.mode !== 'advanced') return 'skip';

  printStep('IAM role for OSI pipeline');
  printInfo('This role allows the ingestion pipeline to write to OpenSearch and Prometheus');
  console.error();

  while (true) {
    saveCursor();
    const iamChoice = await eSelect({
      message: 'Create new or reuse existing?',
      choices: [
        { name: 'Create new', value: 'create' },
        { name: 'Reuse existing', value: 'reuse' },
      ],
      default: cfg.iamAction || 'create',
    });
    if (iamChoice === GoBack) return GoBack;

    if (iamChoice === 'reuse') {
      cfg.iamAction = 'reuse';
      const arn = await promptArn('IAM role ARN');
      if (arn === GoBack) { clearFromCursor(); continue; }
      cfg.iamRoleArn = arn;
    } else {
      cfg.iamAction = 'create';
      const roleName = await eInput({ message: 'Role name', default: cfg.iamRoleName || `${cfg.pipelineName}-osi-role` });
      if (roleName === GoBack) { clearFromCursor(); continue; }
      cfg.iamRoleName = roleName;
    }
    return;
  }
}

async function stepAps(cfg) {
  if (cfg.mode !== 'advanced') return 'skip';

  printStep('Amazon Managed Prometheus (APS) workspace');
  console.error();

  while (true) {
    saveCursor();
    const apsChoice = await eSelect({
      message: 'Create new or reuse existing?',
      choices: [
        { name: 'Create new', value: 'create' },
        { name: 'Reuse existing', value: 'reuse' },
      ],
      default: cfg.apsAction || 'create',
    });
    if (apsChoice === GoBack) return GoBack;

    if (apsChoice === 'reuse') {
      cfg.apsAction = 'reuse';

      const workspaces = await fetchWithSpinner(
        'Loading APS workspaces',
        () => listWorkspaces(cfg.region),
      );

      if (workspaces.length > 0) {
        const choices = workspaces.map((w) => ({
          name: w.alias
            ? `${w.alias} ${theme.muted(`\u2014 ${w.id}`)}`
            : `${w.id} ${theme.muted('(no alias)')}`,
          value: w.url,
        }));
        choices.push({ name: theme.accent('Enter URL manually...'), value: CUSTOM_INPUT });

        const selected = await eSelect({ message: 'Select workspace', choices });
        if (selected === GoBack) { clearFromCursor(); continue; }
        if (selected === CUSTOM_INPUT) {
          const url = await promptUrl('Prometheus remote-write URL');
          if (url === GoBack) { clearFromCursor(); continue; }
          cfg.prometheusUrl = url;
        } else {
          cfg.prometheusUrl = selected;
        }
      } else {
        printInfo('No workspaces found \u2014 enter URL manually');
        const url = await promptUrl('Prometheus remote-write URL');
        if (url === GoBack) { clearFromCursor(); continue; }
        cfg.prometheusUrl = url;
      }
    } else {
      cfg.apsAction = 'create';
      const alias = await eInput({ message: 'Workspace alias', default: cfg.apsWorkspaceAlias || cfg.pipelineName });
      if (alias === GoBack) { clearFromCursor(); continue; }
      cfg.apsWorkspaceAlias = alias;
    }
    return;
  }
}

async function stepConnectedDataSourceRole(cfg) {
  if (cfg.mode !== 'advanced') return 'skip';

  printStep('Connected Data Source IAM role');
  printInfo('This role allows OpenSearch to query Prometheus metrics via Connected Data Source');
  console.error();

  while (true) {
    saveCursor();
    const choice = await eSelect({
      message: 'Create new or reuse existing?',
      choices: [
        { name: 'Create new', value: 'create' },
        { name: 'Reuse existing', value: 'reuse' },
      ],
      default: 'create',
    });
    if (choice === GoBack) return GoBack;

    if (choice === 'reuse') {
      const arn = await promptArn('Connected Data Source role ARN');
      if (arn === GoBack) { clearFromCursor(); continue; }
      cfg.connectedDataSourceRoleArn = arn;
      cfg.connectedDataSourceRoleName = '';
    } else {
      const roleName = await eInput({
        message: 'Connected Data Source role name',
        default: cfg.connectedDataSourceRoleName || `${cfg.pipelineName}-connected-data-source-prometheus-role`,
      });
      if (roleName === GoBack) { clearFromCursor(); continue; }
      cfg.connectedDataSourceRoleName = roleName;
    }
    return;
  }
}

async function stepConnectedDataSource(cfg) {
  if (cfg.mode !== 'advanced') return 'skip';
  // Skip if no Connected Data Source role was configured
  if (!cfg.connectedDataSourceRoleName && !cfg.connectedDataSourceRoleArn) return 'skip';

  printStep('Connected Data Source');
  printInfo('Connects OpenSearch to Prometheus so you can query metrics from OpenSearch UI');
  console.error();

  const dsName = await eInput({
    message: 'Data source name',
    default: cfg.connectedDataSourceName || `${cfg.pipelineName.replace(/-/g, '_')}_prometheus`,
    validate: (v) => /^[a-z][a-z0-9_]+$/.test(v.trim()) || 'Must match [a-z][a-z0-9_]+ (lowercase, underscores only)',
  });
  if (dsName === GoBack) return GoBack;
  cfg.connectedDataSourceName = dsName;
}

async function stepApp(cfg) {
  if (cfg.mode !== 'advanced') return 'skip';

  printStep('OpenSearch UI');
  printInfo('The OpenSearch Application provides a unified dashboard for your observability data');
  console.error();

  while (true) {
    saveCursor();
    const choice = await eSelect({
      message: 'Create new or reuse existing?',
      choices: [
        { name: `Create new ${theme.muted('\u2014 creates an OpenSearch Application with data sources')}`, value: 'create' },
        { name: 'Reuse existing', value: 'reuse' },
      ],
      default: cfg.dashboardsAction || 'create',
    });
    if (choice === GoBack) return GoBack;

    if (choice === 'reuse') {
      cfg.dashboardsAction = 'reuse';

      const apps = await fetchWithSpinner(
        'Loading OpenSearch Applications',
        () => listApplications(cfg.region),
      );

      if (apps.length > 0) {
        const choices = apps.map((a) => ({
          name: a.endpoint
            ? `${a.name} ${theme.muted(`\u2014 ${a.endpoint}`)}`
            : `${a.name} ${theme.muted(`(${a.id})`)}`,
          value: a.endpoint || a.id,
        }));
        choices.push({ name: theme.accent('Enter URL manually...'), value: CUSTOM_INPUT });

        const selected = await eSelect({ message: 'Select application', choices });
        if (selected === GoBack) { clearFromCursor(); continue; }
        if (selected === CUSTOM_INPUT) {
          const url = await promptUrl('OpenSearch UI URL');
          if (url === GoBack) { clearFromCursor(); continue; }
          cfg.dashboardsUrl = url;
        } else {
          cfg.dashboardsUrl = selected;
        }
      } else {
        printInfo('No applications found \u2014 enter URL manually');
        const url = await promptUrl('OpenSearch UI URL');
        if (url === GoBack) { clearFromCursor(); continue; }
        cfg.dashboardsUrl = url;
      }
      cfg.appName = '';
    } else {
      cfg.dashboardsAction = 'create';
      const appName = await eInput({
        message: 'Application name',
        default: cfg.appName || cfg.pipelineName,
      });
      if (appName === GoBack) { clearFromCursor(); continue; }
      cfg.appName = appName;
    }
    return;
  }
}

async function stepTuning(cfg) {
  if (cfg.mode !== 'advanced') return 'skip';

  printStep('Pipeline tuning');
  console.error();

  const minOcu = await eInput({
    message: 'Minimum OCUs',
    default: String(cfg.minOcu ?? DEFAULTS.minOcu),
    validate: (v) => /^\d+$/.test(v.trim()) && Number(v) >= 1 || 'Must be a positive integer',
  });
  if (minOcu === GoBack) return GoBack;
  cfg.minOcu = Number(minOcu);

  const maxOcu = await eInput({
    message: 'Maximum OCUs',
    default: String(cfg.maxOcu ?? DEFAULTS.maxOcu),
    validate: (v) => /^\d+$/.test(v.trim()) && Number(v) >= 1 || 'Must be a positive integer',
  });
  if (maxOcu === GoBack) return GoBack;
  cfg.maxOcu = Number(maxOcu);

  const window = await eInput({ message: 'Service-map window duration', default: cfg.serviceMapWindow || DEFAULTS.serviceMapWindow });
  if (window === GoBack) return GoBack;
  cfg.serviceMapWindow = window;
}

async function stepDemo(cfg) {
  printStep('Demo workloads');
  console.error();

  const demo = await eSelect({
    message: 'Launch EC2 demo instance with sample logs, traces & metrics?',
    choices: [
      { name: `Yes ${theme.muted('— sends demo telemetry to the pipeline')}`, value: true },
      { name: 'No', value: false },
    ],
    default: false,
  });
  if (demo === GoBack) return GoBack;
  cfg.skipDemo = !demo;
}

// ── Main wizard ──────────────────────────────────────────────────────────────

/**
 * Run the interactive create wizard. Returns a fully populated config object.
 * Supports Escape to go back to the previous step.
 * @param {Object} [session] - Optional session with pre-filled { region, accountId }
 */
export async function runCreateWizard(session = null) {
  const cfg = createDefaultConfig();

  if (!session) printHeader();

  const steps = [stepMode, stepCore, stepOpenSearch, stepVpc, stepIam, stepAps, stepConnectedDataSourceRole, stepConnectedDataSource, stepApp, stepTuning, stepDemo];
  const visited = [];
  let i = 0;

  while (i < steps.length) {
    saveCursor();
    const result = await steps[i](cfg, session);

    if (result === GoBack) {
      clearFromCursor();
      if (visited.length === 0) {
        // Escape at first step → return to menu
        return GoBack;
      }
      i = visited.pop();
    } else if (result === 'skip') {
      i++;
    } else {
      visited.push(i);
      i++;
    }
  }

  return cfg;
}

// ── Prompt helpers for manual input fallback ────────────────────────────────────

function promptEndpoint() {
  return eInput({
    message: 'OpenSearch endpoint URL',
    validate: (v) => {
      if (!v.trim()) return 'Endpoint is required';
      if (!/^https?:\/\//.test(v)) return 'Must start with http:// or https://';
      return true;
    },
  });
}

function promptArn(message) {
  return eInput({
    message,
    validate: (v) => {
      if (!v.trim()) return 'ARN is required';
      if (!v.startsWith('arn:aws:iam:')) return 'Must start with arn:aws:iam:';
      return true;
    },
  });
}

function promptUrl(message) {
  return eInput({
    message,
    validate: (v) => {
      if (!v.trim()) return 'URL is required';
      if (!/^https?:\/\//.test(v)) return 'Must start with http:// or https://';
      return true;
    },
  });
}


