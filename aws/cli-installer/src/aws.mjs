import { STSClient, GetCallerIdentityCommand } from '@aws-sdk/client-sts';
import {
  OpenSearchClient,
  CreateDomainCommand,
  DescribeDomainCommand,
  DescribeDomainChangeProgressCommand,
  ListDomainNamesCommand,
  DescribeDomainsCommand,
  AddDirectQueryDataSourceCommand,
  GetDirectQueryDataSourceCommand,
  CreateApplicationCommand,
  GetApplicationCommand,
  UpdateApplicationCommand,
  ListApplicationsCommand,
  AuthorizeVpcEndpointAccessCommand,
} from '@aws-sdk/client-opensearch';
import {
  IAMClient,
  GetRoleCommand,
  CreateRoleCommand,
  PutRolePolicyCommand,
  ListRolesCommand,
} from '@aws-sdk/client-iam';
import {
  AmpClient,
  ListWorkspacesCommand,
  CreateWorkspaceCommand,
  DescribeWorkspaceCommand,
} from '@aws-sdk/client-amp';
import {
  OSISClient,
  ListPipelinesCommand,
  CreatePipelineCommand,
  GetPipelineCommand,
  GetPipelineChangeProgressCommand,
} from '@aws-sdk/client-osis';
import {
  ResourceGroupsTaggingAPIClient,
  GetResourcesCommand,
  TagResourcesCommand,
} from '@aws-sdk/client-resource-groups-tagging-api';
import {
  OpenSearchServerlessClient,
  CreateCollectionCommand as CreateAossCollectionCommand,
  BatchGetCollectionCommand,
  CreateSecurityPolicyCommand,
  CreateAccessPolicyCommand,
  ListCollectionsCommand,
} from '@aws-sdk/client-opensearchserverless';
import {
  printStep,
  printSuccess,
  printError,
  printWarning,
  printInfo,
  createSpinner,
  createAsciiAnimation,
} from './ui.mjs';
import { SignatureV4 } from '@aws-sdk/signature-v4';
import { Sha256 } from '@aws-crypto/sha256-js';
import { HttpRequest } from '@smithy/protocol-http';
import { defaultProvider } from '@aws-sdk/credential-provider-node';
import chalk from 'chalk';
import { randomBytes, createHash } from 'node:crypto';
import {
  SecretsManagerClient,
  CreateSecretCommand,
  GetSecretValueCommand,
  DeleteSecretCommand,
} from '@aws-sdk/client-secrets-manager';

// ── Tagging ─────────────────────────────────────────────────────────────────

const SECRET_PREFIX = 'observability-stack';

function generatePassword() {
  return randomBytes(16).toString('base64url') + '!A1';
}

async function storeMasterPassword(region, pipelineName, password) {
  const sm = new SecretsManagerClient({ region });
  const secretName = `${SECRET_PREFIX}/${pipelineName}/master-password`;
  try {
    await sm.send(new CreateSecretCommand({
      Name: secretName,
      SecretString: password,
      Description: `OpenSearch master password for ${pipelineName}`,
    }));
    printSuccess(`Master password stored in Secrets Manager (${secretName})`);
  } catch (e) {
    if (e.name === 'ResourceExistsException') {
      const { PutSecretValueCommand } = await import('@aws-sdk/client-secrets-manager');
      await sm.send(new PutSecretValueCommand({ SecretId: secretName, SecretString: password }));
      printSuccess(`Master password updated in Secrets Manager (${secretName})`);
    } else throw e;
  }
}

async function getMasterPassword(region, pipelineName) {
  const sm = new SecretsManagerClient({ region });
  const { SecretString } = await sm.send(new GetSecretValueCommand({
    SecretId: `${SECRET_PREFIX}/${pipelineName}/master-password`,
  }));
  return SecretString;
}

const TAG_KEY = 'observability-stack';

function stackTags(stackName) {
  return [{ Key: TAG_KEY, Value: stackName }];
}

// ── Prerequisites ───────────────────────────────────────────────────────────

export async function checkRequirements(cfg) {
  printStep('Checking prerequisites...');
  console.error();

  // 1. Credentials + account ID
  const sts = new STSClient({ region: cfg.region });
  let identity;
  try {
    identity = await sts.send(new GetCallerIdentityCommand({}));
  } catch (err) {
    printError('AWS credentials are not configured or have expired');
    console.error();
    if (/unable to locate credentials|no credentials/i.test(err.message)) {
      console.error(`  ${chalk.bold('No credentials found. Set up AWS access:')}`);
      console.error();
      console.error(`  ${chalk.dim('Option A — Configure long-term credentials:')}`);
      console.error(`     ${chalk.bold('aws configure')}`);
      console.error();
      console.error(`  ${chalk.dim('Option B — Use IAM Identity Center (SSO):')}`);
      console.error(`     ${chalk.bold('aws configure sso')}`);
      console.error(`     ${chalk.bold('aws sso login --profile <your-profile>')}`);
      console.error();
      console.error(`  ${chalk.dim('Option C — Export temporary credentials:')}`);
      console.error(`     ${chalk.bold('export AWS_ACCESS_KEY_ID=<key>')}`);
      console.error(`     ${chalk.bold('export AWS_SECRET_ACCESS_KEY=<secret>')}`);
      console.error(`     ${chalk.bold('export AWS_SESSION_TOKEN=<token>')}  ${chalk.dim('(if using temporary creds)')}`);
      console.error();
      console.error(`  ${chalk.dim('Docs:')} ${chalk.underline('https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html#getting-started-quickstart-new-command')}`);
    } else if (/expired|ExpiredToken/i.test(err.message)) {
      console.error(`  ${chalk.bold('Your session has expired. Refresh credentials:')}`);
      console.error();
      console.error(`  ${chalk.dim('If using SSO:')}         ${chalk.bold('aws sso login')}`);
      console.error(`  ${chalk.dim('If using profiles:')}    ${chalk.bold('aws sts get-session-token')}`);
      console.error(`  ${chalk.dim('If using assume-role:')} re-run your assume-role command`);
    } else {
      console.error(`  ${chalk.bold('Authentication failed:')}`);
      console.error(`  ${chalk.dim(err.message)}`);
      console.error();
      console.error(`  ${chalk.bold('Try:')}`);
      console.error(`     ${chalk.bold('aws configure')}        ${chalk.dim('— set up credentials')}`);
      console.error(`     ${chalk.bold('aws sso login')}        ${chalk.dim('— refresh SSO session')}`);
      console.error();
      console.error(`  ${chalk.dim('Docs:')} ${chalk.underline('https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html#getting-started-quickstart-new-command')}`);
    }
    console.error();
    throw new Error('AWS credentials are not configured or have expired');
  }

  cfg.accountId = identity.Account;
  // Extract the caller's IAM principal for FGAC mapping.
  // Handles: assumed-role, IAM user, federated user, and root.
  const arn = identity.Arn;
  const assumedMatch = arn.match(/assumed-role\/([^/]+)\//);
  const userMatch = arn.match(/:user\/(.+)$/);
  const fedMatch = arn.match(/:federated-user\/(.+)$/);
  if (assumedMatch) {
    cfg.callerPrincipal = { arn: `arn:aws:iam::${cfg.accountId}:role/${assumedMatch[1]}`, type: 'role' };
  } else if (userMatch) {
    cfg.callerPrincipal = { arn, type: 'user' };
  } else if (fedMatch) {
    cfg.callerPrincipal = { arn, type: 'user' };
  } else if (arn.endsWith(':root')) {
    cfg.callerPrincipal = { arn, type: 'user' };
  }
  printSuccess(`Authenticated — account ${cfg.accountId}`);
  printInfo(`Identity: ${identity.Arn}`);

  // 2. Quick OSIS access check
  const osis = new OSISClient({ region: cfg.region });
  try {
    await osis.send(new ListPipelinesCommand({ MaxResults: 1 }));
    printSuccess(`OSI service accessible in ${cfg.region}`);
  } catch {
    printWarning(`Cannot list OSI pipelines in ${cfg.region} — you may lack osis:* permissions`);
    printInfo('The script will attempt to proceed, but resource creation may fail.');
    printInfo('Required IAM actions: es:*, iam:CreateRole, iam:PutRolePolicy, aps:*, osis:*');
  }

  console.error();
}

// ── OpenSearch (managed domain) ─────────────────────────────────────────────

export async function createOpenSearch(cfg) {
  if (cfg.opensearchType === 'serverless') return createServerlessCollection(cfg);
  return createManagedDomain(cfg);
}

/**
 * Extract the reachable endpoint from a DomainStatus, supporting both public
 * (top-level Endpoint) and VPC domains (Endpoints.vpc map).
 */
function domainEndpoint(status) {
  if (!status) return '';
  if (status.Endpoint) return status.Endpoint;
  return status.Endpoints?.vpc || '';
}

// Managed OpenSearch UI reaches a VPC-private domain over the domain's VPC
// endpoint, which the domain owner must authorize for the UI service principal.
// Idempotent: a re-authorize just no-ops.
const OPENSEARCH_UI_SERVICE = 'application.opensearchservice.amazonaws.com';

async function authorizeOpenSearchUiVpcAccess(cfg, client) {
  try {
    await client.send(new AuthorizeVpcEndpointAccessCommand({
      DomainName: cfg.osDomainName,
      Service: OPENSEARCH_UI_SERVICE,
    }));
    printSuccess('Authorized OpenSearch UI to reach the VPC-private domain');
  } catch (err) {
    // Already authorized is fine; anything else is a warning, not fatal.
    if (/already|Conflict|LimitExceeded/i.test(err.message)) {
      printInfo('OpenSearch UI VPC access already authorized');
    } else {
      printWarning(`Could not authorize OpenSearch UI VPC access: ${err.message}`);
      printInfo(`Authorize it manually: aws opensearch authorize-vpc-endpoint-access --domain-name ${cfg.osDomainName} --service ${OPENSEARCH_UI_SERVICE} --region ${cfg.region}`);
    }
  }
}

async function createManagedDomain(cfg) {
  const inVpc = Boolean(cfg.vpcId);
  printStep(`Creating OpenSearch domain '${cfg.osDomainName}'${inVpc ? ' (VPC)' : ''}...`);
  console.error();

  const client = new OpenSearchClient({ region: cfg.region });

  // Check if domain already exists
  try {
    const desc = await client.send(new DescribeDomainCommand({ DomainName: cfg.osDomainName }));
    const status = desc.DomainStatus || {};
    const endpoint = domainEndpoint(status);
    // Only short-circuit if the pre-existing domain is fully active. A domain
    // still Processing (e.g. a prior interrupted run) must fall through to the
    // wait loop, or downstream security-API calls race an unready cluster.
    if (endpoint && !status.Processing && !status.UpgradeProcessing) {
      cfg.opensearchEndpoint = `https://${endpoint}`;
      printSuccess(`Domain '${cfg.osDomainName}' already exists: ${cfg.opensearchEndpoint}`);
      if (inVpc) await authorizeOpenSearchUiVpcAccess(cfg, client);
      return;
    }
    printSuccess(`Domain '${cfg.osDomainName}' already exists — waiting for it to become active`);
  } catch (err) {
    if (err.name !== 'ResourceNotFoundException') throw err;

    // Open access policy — FGAC (fine-grained access control) handles authorization.
    // A scoped Principal (e.g. account root) blocks basic auth requests, which
    // prevents the Security API from working for FGAC role mapping.
    const accessPolicy = JSON.stringify({
      Version: '2012-10-17',
      Statement: [{
        Effect: 'Allow',
        Principal: { AWS: '*' },
        Action: 'es:*',
        Resource: `arn:aws:es:${cfg.region}:${cfg.accountId}:domain/${cfg.osDomainName}/*`,
      }],
    });

    // Build cluster config; enable zone awareness when spanning multiple VPC subnets (AZs).
    const clusterConfig = {
      InstanceType: cfg.osInstanceType,
      InstanceCount: cfg.osInstanceCount,
    };
    if (inVpc && cfg.subnetIds.length > 1) {
      // Zone awareness supports 2 or 3 AZs, and the data node count must be a
      // multiple of the AZ count. Round the requested count up to the next multiple.
      const azCount = Math.min(cfg.subnetIds.length, 3);
      const nodeCount = Math.max(azCount, Math.ceil(cfg.osInstanceCount / azCount) * azCount);
      if (nodeCount !== cfg.osInstanceCount) {
        printInfo(`Zone-aware domain across ${azCount} AZs requires the data node count to be a multiple of ${azCount}; using ${nodeCount} data nodes.`);
        cfg.osInstanceCount = nodeCount;
      }
      clusterConfig.InstanceCount = nodeCount;
      clusterConfig.ZoneAwarenessEnabled = true;
      clusterConfig.ZoneAwarenessConfig = { AvailabilityZoneCount: azCount };
    }

    // Master user: for VPC-private domains the domain's Security API is only
    // reachable from inside the VPC, so an internal (username/password) master
    // user can't be used to bootstrap role mappings from outside. Instead, make
    // the caller's IAM principal the master user — it can then drive role mapping
    // through the reachable managed OpenSearch UI (which proxies to the domain over
    // the AWS-internal path) via SigV4, no in-VPC network access required. Public
    // domains keep the internal-database master user (username/password).
    const iamMaster = inVpc && Boolean(cfg.callerPrincipal?.arn);
    const advancedSecurity = iamMaster
      ? {
          Enabled: true,
          InternalUserDatabaseEnabled: false,
          MasterUserOptions: { MasterUserARN: cfg.callerPrincipal.arn },
        }
      : {
          Enabled: true,
          InternalUserDatabaseEnabled: true,
          MasterUserOptions: {
            MasterUserName: cfg.opensearchUser || 'admin',
            MasterUserPassword: (cfg._masterPassword = generatePassword()),
          },
        };

    try {
      await client.send(new CreateDomainCommand({
        DomainName: cfg.osDomainName,
        EngineVersion: cfg.osEngineVersion,
        ClusterConfig: clusterConfig,
        EBSOptions: {
          EBSEnabled: true,
          VolumeType: 'gp3',
          VolumeSize: cfg.osVolumeSize,
        },
        // VPCOptions places the domain inside the selected subnets/SGs (private endpoint).
        // Omitting it leaves the domain on a public endpoint (default behavior).
        ...(inVpc ? {
          VPCOptions: {
            SubnetIds: cfg.subnetIds,
            SecurityGroupIds: cfg.securityGroupIds,
          },
        } : {}),
        NodeToNodeEncryptionOptions: { Enabled: true },
        EncryptionAtRestOptions: { Enabled: true },
        DomainEndpointOptions: { EnforceHTTPS: true },
        AdvancedSecurityOptions: advancedSecurity,
        AccessPolicies: accessPolicy,
        TagList: stackTags(cfg.pipelineName),
      }));
      printSuccess(`Domain creation initiated${inVpc ? ` in VPC ${cfg.vpcId}` : ''} — waiting for endpoint`);
      if (iamMaster) {
        cfg.iamMasterArn = cfg.callerPrincipal.arn;
        printInfo(`Master user: IAM principal ${cfg.iamMasterArn} (role mapping via OpenSearch UI)`);
      } else {
        await storeMasterPassword(cfg.region, cfg.pipelineName, cfg._masterPassword);
      }
    } catch (createErr) {
      printError('Failed to create OpenSearch domain');
      console.error();
      if (/AccessDeniedException|not authorized/i.test(createErr.message)) {
        console.error(`  ${chalk.bold('Permission denied.')} Your IAM identity needs the ${chalk.bold('es:CreateDomain')} action.`);
      } else {
        console.error(`  ${chalk.dim(createErr.message)}`);
      }
      console.error();
      throw new Error('Failed to create OpenSearch domain');
    }
  }

  // Poll for endpoint
  const spinner = createSpinner('Provisioning OpenSearch domain (20-30 min)...');
  spinner.start();
  const anim = createAsciiAnimation('opensearch');
  anim.start(spinner);
  const maxWait = 1800_000; // 30 min
  const interval = 10_000;
  const start = Date.now();
  anim.setStatus(() => `Provisioning OpenSearch domain... (${fmtElapsed(Math.round((Date.now() - start) / 1000))} elapsed)`);

  while (Date.now() - start < maxWait) {
    try {
      const desc = await client.send(new DescribeDomainCommand({ DomainName: cfg.osDomainName }));
      const ds = desc.DomainStatus || {};
      const endpoint = domainEndpoint(ds);

      // Feed real stage progress into the owl animation
      try {
        const cp = await client.send(new DescribeDomainChangeProgressCommand({ DomainName: cfg.osDomainName }));
        const stages = cp.ChangeProgressStatus?.ChangeProgressStages || [];
        const current = stages.find((s) => s.Status === 'IN_PROGRESS') || stages.findLast((s) => s.Status === 'COMPLETED');
        anim.setDomainStatus(current?.Description || current?.Name || 'Initializing...');
      } catch { /* change progress may not be available yet */ }

      // Gate on the endpoint being present AND the domain no longer processing.
      // The endpoint URL is published while the cluster is still initializing, so
      // returning on endpoint alone races the immediately-following security-API
      // calls (FGAC mapping / UI→domain connection), which then hit a cluster that
      // is not yet serving. Waiting for Processing to clear removes that race.
      const active = !ds.Processing && !ds.UpgradeProcessing;
      if (endpoint && active) {
        cfg.opensearchEndpoint = `https://${endpoint}`;
        anim.stop();
        spinner.succeed(`Domain ready: ${cfg.opensearchEndpoint} (${fmtElapsed(Math.round((Date.now() - start) / 1000))})`);
        // For VPC-private domains, authorize the managed OpenSearch UI service to
        // reach the domain through its VPC endpoint. Without this the UI cannot
        // connect to the domain ("No living connections"), so FGAC mapping and UI
        // setup — which we route through the UI — would fail.
        if (inVpc) await authorizeOpenSearchUiVpcAccess(cfg, client);
        return;
      }
    } catch { /* keep polling */ }
    await sleep(interval);
  }

  anim.stop();
  spinner.fail(`Timed out waiting for OpenSearch domain (${fmtElapsed(Math.round((Date.now() - start) / 1000))})`);
  throw new Error('Timed out waiting for OpenSearch domain');
}

// ── OpenSearch Serverless (AOSS) collection ────────────────────────────────

async function createServerlessCollection(cfg) {
  const collectionName = cfg.aossCollectionName;
  printStep(`Creating AOSS collection '${collectionName}'...`);
  console.error();

  const client = new OpenSearchServerlessClient({ region: cfg.region });

  // Check if collection already exists
  try {
    const list = await client.send(new ListCollectionsCommand({
      collectionFilters: { name: collectionName },
    }));
    const existing = list.collectionSummaries?.find((c) => c.name === collectionName);
    if (existing) {
      if (existing.status === 'ACTIVE') {
        cfg.collectionId = existing.id;
        cfg.opensearchEndpoint = `https://${existing.id}.${cfg.region}.aoss.amazonaws.com`;
        printSuccess(`Collection '${collectionName}' already exists: ${cfg.opensearchEndpoint}`);
        return;
      }
      if (existing.status === 'CREATING') {
        cfg.collectionId = existing.id;
        printInfo(`Collection '${collectionName}' is being created — waiting...`);
      }
    }
  } catch { /* proceed to create */ }

  if (!cfg.collectionId) {
    // Encryption policy (required before collection creation)
    const encPolicyName = `${collectionName}-enc`;
    try {
      await client.send(new CreateSecurityPolicyCommand({
        name: encPolicyName,
        type: 'encryption',
        policy: JSON.stringify({
          Rules: [{ ResourceType: 'collection', Resource: [`collection/${collectionName}`] }],
          AWSOwnedKey: true,
        }),
      }));
      printSuccess(`Encryption policy '${encPolicyName}' created`);
    } catch (e) {
      if (/ConflictException|already exists/i.test(e.message)) {
        printSuccess(`Encryption policy '${encPolicyName}' already exists`);
      } else throw e;
    }

    // Network policy (public access)
    const netPolicyName = `${collectionName}-net`;
    try {
      await client.send(new CreateSecurityPolicyCommand({
        name: netPolicyName,
        type: 'network',
        policy: JSON.stringify([{
          Rules: [
            { ResourceType: 'collection', Resource: [`collection/${collectionName}`] },
            { ResourceType: 'dashboard', Resource: [`collection/${collectionName}`] },
          ],
          AllowFromPublic: true,
        }]),
      }));
      printSuccess(`Network policy '${netPolicyName}' created`);
    } catch (e) {
      if (/ConflictException|already exists/i.test(e.message)) {
        printSuccess(`Network policy '${netPolicyName}' already exists`);
      } else throw e;
    }

    // Create collection
    try {
      const result = await client.send(new CreateAossCollectionCommand({
        name: collectionName,
        type: 'SEARCH',
        tags: [{ key: TAG_KEY, value: cfg.pipelineName }],
      }));
      cfg.collectionId = result.createCollectionDetail?.id;
      printSuccess(`Collection creation initiated (id: ${cfg.collectionId})`);
    } catch (e) {
      if (/ConflictException|already exists/i.test(e.message)) {
        const list = await client.send(new ListCollectionsCommand({
          collectionFilters: { name: collectionName },
        }));
        const existing = list.collectionSummaries?.find((c) => c.name === collectionName);
        if (existing) {
          cfg.collectionId = existing.id;
          printSuccess(`Collection '${collectionName}' already exists`);
        }
      } else {
        printError('Failed to create AOSS collection');
        console.error(`  ${chalk.dim(e.message)}`);
        throw new Error('Failed to create AOSS collection');
      }
    }
  }

  // Poll until ACTIVE
  const spinner = createSpinner('Waiting for AOSS collection (2-5 min)...');
  spinner.start();
  const maxWait = 600_000; // 10 min
  const interval = 10_000;
  const start = Date.now();

  while (Date.now() - start < maxWait) {
    try {
      const resp = await client.send(new BatchGetCollectionCommand({
        ids: [cfg.collectionId],
      }));
      const detail = resp.collectionDetails?.[0];
      if (detail?.status === 'ACTIVE') {
        cfg.opensearchEndpoint = detail.collectionEndpoint;
        spinner.succeed(`Collection ready: ${cfg.opensearchEndpoint} (${fmtElapsed(Math.round((Date.now() - start) / 1000))})`);
        break;
      }
      if (detail?.status === 'FAILED') {
        spinner.fail('Collection creation failed');
        throw new Error('AOSS collection creation failed');
      }
    } catch (err) {
      if (err.message?.includes('creation failed')) throw err;
    }
    await sleep(interval);
  }

  if (!cfg.opensearchEndpoint) {
    spinner.fail('Timed out waiting for AOSS collection');
    throw new Error('Timed out waiting for AOSS collection');
  }
}

/**
 * Create the AOSS data access policy after the IAM role exists.
 * Grants the pipeline role and the caller index/collection permissions.
 */
export async function createAossDataAccessPolicy(cfg) {
  const collectionName = cfg.aossCollectionName;
  const policyName = `${collectionName}-access`;
  printStep(`Creating AOSS data access policy '${policyName}'...`);

  const principals = [cfg.iamRoleArn];
  if (cfg.callerPrincipal?.arn && cfg.callerPrincipal.arn !== cfg.iamRoleArn) {
    principals.push(cfg.callerPrincipal.arn);
  }

  const client = new OpenSearchServerlessClient({ region: cfg.region });
  try {
    await client.send(new CreateAccessPolicyCommand({
      name: policyName,
      type: 'data',
      policy: JSON.stringify([{
        Rules: [
          {
            ResourceType: 'index',
            Resource: [`index/${collectionName}/*`],
            Permission: [
              'aoss:CreateIndex', 'aoss:UpdateIndex', 'aoss:DescribeIndex',
              'aoss:ReadDocument', 'aoss:WriteDocument',
            ],
          },
          {
            ResourceType: 'collection',
            Resource: [`collection/${collectionName}`],
            Permission: [
              'aoss:CreateCollectionItems', 'aoss:DeleteCollectionItems',
              'aoss:UpdateCollectionItems', 'aoss:DescribeCollectionItems',
            ],
          },
        ],
        Principal: principals,
      }]),
    }));
    printSuccess(`Data access policy created`);
  } catch (e) {
    if (/ConflictException|already exists/i.test(e.message)) {
      printSuccess(`Data access policy '${policyName}' already exists`);
    } else {
      printWarning(`Could not create data access policy: ${e.message}`);
    }
  }
}

// ── FGAC role mapping for managed domains ────────────────────────────────

// Roles mapped on create for full OpenSearch UI + PPL access. Exported so
// destroy strips the same set — mapping any role here without removing it on
// teardown leaks it on shared domains.
export const FGAC_ROLES = ['all_access', 'security_manager'];

/**
 * Backend roles and users to add to the domain's FGAC role mappings: the OSI
 * pipeline role (so ingestion can write) plus the caller's principal (so the
 * caller can use the OpenSearch UI). Returns { backendRoles, users }.
 */
export function fgacPrincipals(cfg) {
  const backendRoles = [cfg.iamRoleArn];
  const users = [];
  const p = cfg.callerPrincipal;
  if (p && p.arn !== cfg.iamRoleArn) {
    if (p.type === 'role') backendRoles.push(p.arn);
    else users.push(p.arn);
  }
  return { backendRoles, users };
}

export async function mapOsiRoleInDomain(cfg) {
  if (cfg.opensearchType === 'serverless') return;
  if (!cfg.opensearchEndpoint || !cfg.iamRoleArn) return;

  // VPC-private domains: the domain's Security API is only reachable from inside
  // the VPC, so we can't map roles by calling the domain directly from here.
  // Instead the caller is the IAM master user, and role mapping is done through the
  // reachable managed OpenSearch UI once the Application exists (see
  // mapOsiRoleViaOpenSearchUI, called from executePipeline after the app is up).
  if (cfg.vpcId) {
    cfg.deferFgacToUi = true;
    printInfo('VPC domain — FGAC role mapping will run through the OpenSearch UI after the Application is created.');
    return;
  }

  printStep('Mapping roles in OpenSearch FGAC...');

  // Retrieve master password — from flag (reuse) or Secrets Manager (created by CLI)
  let masterPass = cfg.opensearchPassword || '';
  if (!masterPass) {
    try {
      masterPass = await getMasterPassword(cfg.region, cfg.pipelineName);
    } catch (e) {
      printError('No master password available.');
      printInfo('Provide --opensearch-password to supply the domain master password.');
      throw new Error('FGAC mapping requires a master password. Cannot continue.');
    }
  }

  const url = `${cfg.opensearchEndpoint}/_plugins/_security/api/rolesmapping`;
  const auth = Buffer.from(`${cfg.opensearchUser || 'admin'}:${masterPass}`).toString('base64');

  const { backendRoles: newBackendRoles, users: newUsers } = fgacPrincipals(cfg);
  const headers = { 'Content-Type': 'application/json', 'Authorization': `Basic ${auth}` };

  // Map one role, retrying transient failures. The security plugin can briefly
  // return 5xx/connection errors right after the cluster becomes active, and a
  // silent miss here leaves the OSI role unmapped — the pipeline then goes ACTIVE
  // but can't write. So retry, and treat a persistent failure as fatal.
  async function mapRole(role) {
    const roleUrl = `${url}/${role}`;
    await withRetry(async () => {
      const getResp = await fetch(roleUrl, { headers });
      let existingBackendRoles = [];
      let existingUsers = [];
      if (getResp.ok) {
        const data = await getResp.json();
        existingBackendRoles = data?.[role]?.backend_roles || [];
        existingUsers = data?.[role]?.users || [];
      } else if (getResp.status >= 500) {
        throw new Error(`security API GET ${role} returned ${getResp.status} (cluster warming up)`);
      }
      const mergedBackendRoles = [...new Set([...existingBackendRoles, ...newBackendRoles])];
      const mergedUsers = [...new Set([...existingUsers, ...newUsers])];

      const ops = [{ op: 'add', path: '/backend_roles', value: mergedBackendRoles }];
      if (newUsers.length) ops.push({ op: 'add', path: '/users', value: mergedUsers });

      const resp = await fetch(roleUrl, { method: 'PATCH', headers, body: JSON.stringify(ops) });
      if (!resp.ok) {
        const body = await resp.text();
        // 5xx and 401/403 right after provisioning are transient; retry. A stable
        // 4xx (e.g. malformed) would exhaust retries and surface below.
        throw new Error(`security API PATCH ${role} returned ${resp.status}: ${body}`);
      }
    }, {
      shouldRetry: (e) => isTransientHttpError(e) || /returned (401|403|5\d\d)/.test(e.message),
      onRetry: (e, i) => printInfo(`FGAC mapping for ${role} not ready yet (attempt ${i + 1}) — retrying`),
    });
  }

  try {
    for (const role of FGAC_ROLES) await mapRole(role);
    printSuccess('Roles mapped to all_access and security_manager in OpenSearch');
  } catch (err) {
    printError(`Could not map the OSI role in OpenSearch FGAC: ${err.message}`);
    printInfo('The pipeline cannot write to OpenSearch until this role is mapped.');
    printInfo('Map it manually in OpenSearch UI → Security → Roles, or re-run the installer.');
    throw new Error('FGAC role mapping failed — pipeline would not be able to write to OpenSearch');
  }
}

// ── SigV4 request against the managed OpenSearch UI Application endpoint ──────
// The managed UI proxies the domain's Security API over the AWS-internal path,
// so this reaches a VPC-private domain from anywhere the app endpoint resolves.

async function osuiSecurityRequest(method, url, body) {
  const isGet = method === 'GET' || method === 'DELETE';
  const bodyBytes = (!isGet && body) ? JSON.stringify(body) : '';
  const bodyHash = createHash('sha256').update(bodyBytes).digest('hex');
  const parsed = new URL(url);
  const query = {};
  parsed.searchParams.forEach((v, k) => { query[k] = v; });

  const request = new HttpRequest({
    method,
    protocol: parsed.protocol,
    hostname: parsed.hostname,
    port: parsed.port ? Number(parsed.port) : undefined,
    path: parsed.pathname,
    query,
    headers: {
      host: parsed.hostname,
      'Content-Type': 'application/json',
      'osd-xsrf': 'osd-fetch',
      'x-amz-content-sha256': bodyHash,
    },
    body: bodyBytes || undefined,
  });

  const signer = new SignatureV4({
    credentials: defaultProvider(),
    region: parsed.hostname.split('.')[1] || 'us-east-1',
    service: 'opensearch',
    sha256: Sha256,
  });
  const signed = await signer.sign(request);
  const resp = await fetch(url, { method, headers: signed.headers, body: isGet ? undefined : bodyBytes });
  const text = await resp.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  return { status: resp.status, data };
}

/**
 * Discover the data-source id the managed OpenSearch UI created for the domain.
 * The Security API proxy is keyed by this id (?dataSourceId=...).
 */
// The UI connects the domain data source only after its VPC endpoint warms up,
// which routinely takes 10-15 min for a fresh VPC-private domain. Poll up to
// ~18 min so a healthy-but-slow warm-up isn't misread as a missing data source.
async function findAppDataSourceId(appEndpoint) {
  for (let attempt = 0; attempt < 108; attempt++) {
    const r = await osuiSecurityRequest('GET', `${appEndpoint}/api/saved_objects/_find?type=data-source&per_page=10`);
    const id = r.data?.saved_objects?.[0]?.id;
    if (id) return id;
    await new Promise((res) => setTimeout(res, 10_000));
  }
  return null;
}

/**
 * Map the OSI pipeline role (and caller principal) into the domain's FGAC roles
 * through the reachable managed OpenSearch UI. Used for VPC-private domains,
 * where the domain's own Security API is not reachable from this host.
 */
export async function mapOsiRoleViaOpenSearchUI(cfg) {
  if (!cfg.deferFgacToUi) return;
  const appEndpoint = cfg.appEndpoint;
  if (!appEndpoint) {
    printError('No OpenSearch UI endpoint — cannot map FGAC roles for the VPC domain.');
    printInfo('Map the OSI role manually in OpenSearch UI → Security → Roles once the UI is reachable.');
    throw new Error('FGAC role mapping via OpenSearch UI failed — no app endpoint; pipeline would not be able to write to OpenSearch');
  }

  printStep('Mapping roles in OpenSearch FGAC (via OpenSearch UI)...');

  const dsId = await findAppDataSourceId(appEndpoint);
  if (!dsId) {
    printError('OpenSearch UI has not connected the domain data source yet — cannot map FGAC roles.');
    printInfo('Re-run the installer, or map the OSI role manually in OpenSearch UI → Security → Roles.');
    throw new Error('FGAC role mapping via OpenSearch UI failed — data source not ready; pipeline would not be able to write to OpenSearch');
  }

  const { backendRoles: newBackendRoles, users: newUsers } = fgacPrincipals(cfg);

  // A VPC-private domain returns "No Living connections" through the UI until the
  // UI→domain VPC endpoint connection is live, which lags the data-source object
  // by a bit. So retry each role until the proxy actually reaches the domain.
  const looksUnreachable = (data) => /no living connections|data source error|not ready|unavailable/i.test(
    typeof data === 'string' ? data : JSON.stringify(data || ''),
  );

  async function mapRoleViaUi(role) {
    const base = `${appEndpoint}/api/v1/configuration/rolesmapping/${role}?dataSourceId=${dsId}`;
    await withRetry(async () => {
      const getResp = await osuiSecurityRequest('GET', base);
      if (getResp.status >= 500 || looksUnreachable(getResp.data)) {
        throw new Error(`UI security API GET ${role}: ${getResp.status} ${JSON.stringify(getResp.data).slice(0, 160)}`);
      }
      const cur = (getResp.status === 200 && typeof getResp.data === 'object') ? getResp.data : {};
      const mergedBackendRoles = [...new Set([...(cur.backend_roles || []), ...newBackendRoles])];
      const mergedUsers = [...new Set([...(cur.users || []), ...newUsers])];

      // The UI security API replaces the mapping wholesale, so send the merged set.
      const resp = await osuiSecurityRequest('POST', base, {
        backend_roles: mergedBackendRoles,
        hosts: cur.hosts || [],
        users: mergedUsers,
      });
      if (resp.status !== 200 || looksUnreachable(resp.data)) {
        throw new Error(`UI security API POST ${role}: ${resp.status} ${JSON.stringify(resp.data).slice(0, 160)}`);
      }
    }, {
      shouldRetry: (e) => isTransientHttpError(e) || looksUnreachable(e.message) || /: (5\d\d|4\d\d) /.test(e.message),
      onRetry: (e, i) => printInfo(`OpenSearch UI not connected to the VPC domain yet (attempt ${i + 1}) — retrying`),
    });
  }

  try {
    for (const role of FGAC_ROLES) await mapRoleViaUi(role);
    printSuccess('Roles mapped to all_access and security_manager via OpenSearch UI');
  } catch (err) {
    printError(`Could not map the OSI role via OpenSearch UI: ${err.message}`);
    printInfo('The pipeline cannot write to the VPC-private domain until this role is mapped.');
    printInfo('Map the OSI role manually in OpenSearch UI → Security → Roles, or re-run the installer.');
    throw new Error('FGAC role mapping via OpenSearch UI failed — pipeline would not be able to write to OpenSearch');
  }
}

// ── IAM role ────────────────────────────────────────────────────────────────

export async function createIamRole(cfg) {
  printStep(`Creating IAM role '${cfg.iamRoleName}'...`);

  const client = new IAMClient({ region: cfg.region });

  // Check if role already exists
  try {
    const existing = await client.send(new GetRoleCommand({ RoleName: cfg.iamRoleName }));
    cfg.iamRoleArn = existing.Role.Arn;
    printSuccess(`Role already exists: ${cfg.iamRoleArn}`);
    return;
  } catch (err) {
    if (err.name !== 'NoSuchEntityException') throw err;
  }

  // Trust policy
  const trustPolicy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [{
      Effect: 'Allow',
      Principal: { Service: 'osis-pipelines.amazonaws.com' },
      Action: 'sts:AssumeRole',
    }],
  });

  try {
    const result = await client.send(new CreateRoleCommand({
      RoleName: cfg.iamRoleName,
      AssumeRolePolicyDocument: trustPolicy,
      Tags: stackTags(cfg.pipelineName),
    }));
    cfg.iamRoleArn = result.Role.Arn;
    printSuccess(`Role created: ${cfg.iamRoleArn}`);
  } catch (err) {
    printError('Failed to create IAM role');
    console.error();
    if (/AccessDenied|not authorized/i.test(err.message)) {
      console.error(`  ${chalk.bold('Permission denied.')} Your IAM identity needs ${chalk.bold('iam:CreateRole')}.`);
    } else {
      console.error(`  ${chalk.dim(err.message)}`);
    }
    console.error();
    throw new Error('Failed to create IAM role');
  }

  // Permissions policy — different actions for managed vs serverless
  const statements = cfg.opensearchType === 'serverless'
    ? [
        {
          Effect: 'Allow',
          Action: ['aoss:APIAccessAll', 'aoss:BatchGetCollection', 'aoss:DashboardsAccessAll'],
          Resource: '*',
        },
        {
          Effect: 'Allow',
          Action: ['aps:RemoteWrite'],
          Resource: `arn:aws:aps:${cfg.region}:${cfg.accountId}:workspace/*`,
        },
      ]
    : [
        {
          Effect: 'Allow',
          Action: ['es:DescribeDomain', 'es:ESHttp*'],
          Resource: `arn:aws:es:${cfg.region}:${cfg.accountId}:domain/*`,
        },
        {
          Effect: 'Allow',
          Action: ['aps:RemoteWrite'],
          Resource: `arn:aws:aps:${cfg.region}:${cfg.accountId}:workspace/*`,
        },
      ];

  const permissionsPolicy = JSON.stringify({
    Version: '2012-10-17',
    Statement: statements,
  });

  try {
    await client.send(new PutRolePolicyCommand({
      RoleName: cfg.iamRoleName,
      PolicyName: `${cfg.iamRoleName}-policy`,
      PolicyDocument: permissionsPolicy,
    }));
    printSuccess('Permissions policy attached');
  } catch (err) {
    printError('Failed to attach permissions policy');
    console.error(`  ${chalk.dim(err.message)}`);
    console.error();
    throw new Error('Failed to attach IAM permissions policy');
  }

  // Give IAM a moment to propagate
  await sleep(5000);
}

// ── APS workspace ───────────────────────────────────────────────────────────

export async function createApsWorkspace(cfg) {
  printStep(`Creating APS workspace '${cfg.apsWorkspaceAlias}'...`);

  const client = new AmpClient({ region: cfg.region });

  // Check if workspace already exists
  try {
    const list = await client.send(new ListWorkspacesCommand({ alias: cfg.apsWorkspaceAlias }));
    const existing = list.workspaces?.[0];
    if (existing?.workspaceId) {
      cfg.apsWorkspaceId = existing.workspaceId;
      cfg.prometheusUrl = `https://aps-workspaces.${cfg.region}.amazonaws.com/workspaces/${cfg.apsWorkspaceId}/api/v1/remote_write`;
      printSuccess(`Workspace already exists: ${cfg.apsWorkspaceId}`);
      printInfo(`Remote write URL: ${cfg.prometheusUrl}`);
      return;
    }
  } catch { /* proceed to create */ }

  try {
    const result = await client.send(new CreateWorkspaceCommand({
      alias: cfg.apsWorkspaceAlias,
      tags: { [TAG_KEY]: cfg.pipelineName },
    }));
    cfg.apsWorkspaceId = result.workspaceId;
    cfg.prometheusUrl = `https://aps-workspaces.${cfg.region}.amazonaws.com/workspaces/${cfg.apsWorkspaceId}/api/v1/remote_write`;

    // Wait for workspace to be active
    const spinner = createSpinner('Waiting for APS workspace...');
    spinner.start();
    const maxWait = 60_000;
    const start = Date.now();
    while (Date.now() - start < maxWait) {
      try {
        const check = await client.send(new ListWorkspacesCommand({ alias: cfg.apsWorkspaceAlias }));
        if (check.workspaces?.[0]?.status?.statusCode === 'ACTIVE') break;
      } catch { /* keep waiting */ }
      await sleep(5000);
    }
    spinner.succeed(`Workspace created: ${cfg.apsWorkspaceId}`);
    printInfo(`Remote write URL: ${cfg.prometheusUrl}`);
  } catch (err) {
    printError('Failed to create APS workspace');
    console.error();
    if (/AccessDenied|not authorized/i.test(err.message)) {
      console.error(`  ${chalk.bold('Permission denied.')} Your IAM identity needs ${chalk.bold('aps:CreateWorkspace')}.`);
    } else {
      console.error(`  ${chalk.dim(err.message)}`);
    }
    console.error();
    throw new Error('Failed to create APS workspace');
  }
}

// ── OSI pipeline ────────────────────────────────────────────────────────────

/**
 * Validate an OSI pipeline role ARN before it is handed to CreatePipeline.
 * OSIS requires a non-empty, well-formed IAM role ARN as PipelineRoleArn; an
 * empty or malformed value is only rejected ~11 min into a run (after the domain
 * is built), so we check it up front. Returns an error string, or '' when valid.
 * @param {string} arn
 * @returns {string}
 */
export function pipelineRoleArnError(arn) {
  if (!arn) return 'The OSI pipeline requires an IAM role (PipelineRoleArn) but none was resolved.';
  if (!arn.startsWith('arn:aws:iam:')) return `The OSI pipeline role must be an IAM role ARN (arn:aws:iam:...), got: ${arn}`;
  return '';
}

export async function createOsiPipeline(cfg, pipelineYaml) {
  printStep(`Creating OSI pipeline '${cfg.pipelineName}'...`);

  const client = new OSISClient({ region: cfg.region });

  // Check if pipeline already exists
  let skipCreate = false;
  try {
    const resp = await client.send(new GetPipelineCommand({ PipelineName: cfg.pipelineName }));
    const status = resp.Pipeline?.Status;
    if (status === 'ACTIVE') {
      cfg.ingestEndpoints = resp.Pipeline?.IngestEndpointUrls || [];
      printSuccess(`Pipeline '${cfg.pipelineName}' already exists (ACTIVE)`);
      for (const url of cfg.ingestEndpoints) printInfo(`Ingestion endpoint: https://${url}`);
      return;
    }
    if (status === 'CREATING') {
      printInfo(`Pipeline '${cfg.pipelineName}' is already being created — waiting...`);
      skipCreate = true;
    } else {
      printWarning(`Pipeline '${cfg.pipelineName}' exists with status ${status} — skipping creation`);
      return;
    }
  } catch (err) {
    if (err.name !== 'ResourceNotFoundException') throw err;
  }

  if (!skipCreate) {
    // Last-line guard before the expensive OSIS CreatePipeline call. The pipeline
    // role ARN is populated several steps earlier (createIamRole, or reuse), and a
    // gap anywhere in that chain leaves it empty — OSIS then rejects the request
    // ~11 min into the run (after domain create) with a misleading cross-account
    // pass-role error. validateConfig() catches the common CLI paths, but this
    // defends the REPL/interactive/programmatic callers too so an empty or
    // malformed ARN never reaches AWS. Fail fast, before any pipeline work.
    const roleErr = pipelineRoleArnError(cfg.iamRoleArn);
    if (roleErr) {
      printError('Cannot create OSI pipeline: no valid pipeline role ARN is set.');
      console.error();
      console.error(`  ${roleErr}`);
      console.error(`  Got: ${chalk.dim(cfg.iamRoleArn ? JSON.stringify(cfg.iamRoleArn) : '(empty)')}`);
      console.error(`  Ensure the role was created (quick mode) or pass ${chalk.bold('--iam-role-arn')} to reuse one.`);
      console.error();
      throw new Error('OSI pipeline role ARN is missing or malformed');
    }

    try {
      // When the domain lives in a VPC, attach the pipeline to the same network so it
      // can reach the private domain endpoint. OSIS accepts at most 2 subnets; pick the
      // first two provided (each in a distinct AZ). The ingestion endpoint becomes
      // VPC-private, which is what in-VPC workloads (EKS/ECS) expect.
      const inVpc = Boolean(cfg.vpcId);
      const vpcOptions = inVpc ? {
        VpcOptions: {
          SubnetIds: cfg.subnetIds.slice(0, 2),
          SecurityGroupIds: cfg.securityGroupIds,
        },
      } : {};

      // OSIS validates the pipeline role's assume-role trust synchronously. When
      // the role was just created, IAM may not have propagated yet, so retry on
      // role-not-found / cannot-assume errors instead of failing the whole run.
      await withRetry(
        () => client.send(new CreatePipelineCommand({
          PipelineName: cfg.pipelineName,
          MinUnits: cfg.minOcu,
          MaxUnits: cfg.maxOcu,
          PipelineConfigurationBody: pipelineYaml,
          PipelineRoleArn: cfg.iamRoleArn,
          ...vpcOptions,
          Tags: stackTags(cfg.pipelineName),
        })),
        {
          shouldRetry: (e) => isRoleNotPropagatedError(e) || isOsisInternalError(e) || isTransientHttpError(e),
          onRetry: (e, i) => printInfo(`CreatePipeline failed (attempt ${i + 1}), retrying: ${e.message.slice(0, 120)}`),
        },
      );
      printSuccess(`Pipeline '${cfg.pipelineName}' creation initiated${inVpc ? ` (VPC-attached)` : ''}`);
    } catch (err) {
      printError('Failed to create OSI pipeline');
      console.error();
      if (/AccessDenied|not authorized/i.test(err.message)) {
        console.error(`  ${chalk.bold('Permission denied.')} Your IAM identity needs ${chalk.bold('osis:CreatePipeline')}.`);
        console.error(`  ${chalk.dim(err.message)}`);
      } else {
        console.error(`  ${chalk.dim(err.message)}`);
      }
      console.error();
      throw new Error('Failed to create OSI pipeline');
    }
  }

  // Wait for pipeline to become active
  const spinner = createSpinner('Waiting for pipeline to activate...');
  spinner.start();
  const anim = createAsciiAnimation('pipeline');
  anim.start(spinner);
  // OSIS pipeline activation is AWS-paced and routinely takes ~15-20 min; under
  // regional load or for VPC-attached pipelines it can exceed 20 min. Use the same
  // 30-min ceiling as domain provisioning so a legitimately-slow-but-healthy
  // pipeline isn't abandoned in CREATING (which then can't even be torn down).
  const maxWait = 1800_000; // 30 min
  const start = Date.now();
  anim.setStatus(() => `Waiting for pipeline... (${fmtElapsed(Math.round((Date.now() - start) / 1000))})`);

  while (Date.now() - start < maxWait) {
    try {
      const resp = await client.send(new GetPipelineCommand({ PipelineName: cfg.pipelineName }));
      const status = resp.Pipeline?.Status;

      // Feed real stage progress into the fish animation
      try {
        const cp = await client.send(new GetPipelineChangeProgressCommand({ PipelineName: cfg.pipelineName }));
        const stages = cp.ChangeProgressStatuses?.[0]?.ChangeProgressStages || [];
        const current = stages.find((s) => s.Status === 'IN_PROGRESS') || stages.findLast((s) => s.Status === 'COMPLETED');
        anim.setDomainStatus(current?.Description || current?.Name || 'Initializing...');
      } catch { /* change progress may not be available yet */ }

      if (status === 'ACTIVE') {
        const urls = resp.Pipeline?.IngestEndpointUrls || [];
        cfg.ingestEndpoints = urls;
        anim.stop();
        spinner.succeed(`Pipeline is active (${fmtElapsed(Math.round((Date.now() - start) / 1000))})`);
        for (const url of urls) {
          printInfo(`Ingestion endpoint: https://${url}`);
        }
        return;
      }
      if (status === 'CREATE_FAILED') {
        const reason = resp.Pipeline?.StatusReason?.Description || 'unknown';
        anim.stop();
        spinner.fail(`Pipeline creation failed (${fmtElapsed(Math.round((Date.now() - start) / 1000))})`);
        printInfo(`Reason: ${reason}`);
        throw new Error(`Pipeline creation failed: ${reason}`);
      }
    } catch (err) {
      if (err.message?.startsWith('Pipeline creation failed')) throw err;
      /* keep polling */
    }
    await sleep(10_000);
  }

  anim.stop();
  spinner.fail(`Timed out waiting for pipeline (${fmtElapsed(Math.round((Date.now() - start) / 1000))})`);
  throw new Error(`Pipeline '${cfg.pipelineName}' did not become active within 30 minutes`);
}

// ── OpenSearch UI workspace ──────────────────────────────────────────

/**
 * Set up OpenSearch UI: derive the URL and create an Observability workspace.
 * Skipped when dashboardsAction is 'reuse' (user provided their own URL).
 */
export async function setupDashboards(cfg) {
  if (!cfg.opensearchEndpoint) return;
  if (cfg.dashboardsAction === 'reuse') {
    printStep('OpenSearch UI');
    printSuccess(`Using existing Dashboards: ${cfg.dashboardsUrl}`);
    return;
  }

  printStep('Setting up OpenSearch UI...');

  // Use OpenSearch Application URL
  if (!cfg.appEndpoint && cfg.appId) {
    const client = new OpenSearchClient({ region: cfg.region });
    await fetchAppEndpoint(client, cfg);
  }
  cfg.dashboardsUrl = cfg.appEndpoint || '';
  if (!cfg.dashboardsUrl) {
    printWarning('No OpenSearch Application endpoint available');
    printInfo('Create an OpenSearch Application in the AWS console to get the UI URL');
    return;
  }
  printSuccess(`URL: ${cfg.dashboardsUrl}`);
}

// ── Connected Data Source (AMP → OpenSearch) ────────────────────────────────

/**
 * Create an IAM role for the Connected Data Source to access AMP.
 * Trust policy allows directquery.opensearchservice.amazonaws.com to assume it.
 */
export async function createConnectedDataSourceRole(cfg) {
  const roleName = cfg.connectedDataSourceRoleName;
  printStep(`Creating Connected Data Source Prometheus role '${roleName}'...`);

  const client = new IAMClient({ region: cfg.region });

  // Check if role already exists
  try {
    const existing = await client.send(new GetRoleCommand({ RoleName: roleName }));
    cfg.connectedDataSourceRoleArn = existing.Role.Arn;
    printSuccess(`Connected Data Source role already exists: ${cfg.connectedDataSourceRoleArn}`);
    return;
  } catch (err) {
    if (err.name !== 'NoSuchEntityException') throw err;
  }

  const trustPolicy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [{
      Effect: 'Allow',
      Principal: { Service: 'directquery.opensearchservice.amazonaws.com' },
      Action: 'sts:AssumeRole',
    }],
  });

  try {
    const result = await client.send(new CreateRoleCommand({
      RoleName: roleName,
      AssumeRolePolicyDocument: trustPolicy,
      Tags: stackTags(cfg.pipelineName),
    }));
    cfg.connectedDataSourceRoleArn = result.Role.Arn;
    printSuccess(`Connected Data Source role created: ${cfg.connectedDataSourceRoleArn}`);
  } catch (err) {
    printError('Failed to create Connected Data Source Prometheus role');
    console.error(`  ${chalk.dim(err.message)}`);
    console.error();
    throw new Error('Failed to create Connected Data Source Prometheus role');
  }

  // Attach APS access policy.
  //
  // The data source needs to query metrics AND manage alerting resources
  // (alerting rule groups and alert-manager silences) in the workspace.
  // AMP authorizes these against two different resource ARNs:
  //   - Workspace-scoped actions (queries, remote write, alert-manager
  //     definition + silences) resolve against the workspace ARN.
  //   - Rule-groups-namespace CRUD (Put/Delete/DescribeRuleGroupsNamespace)
  //     resolve against the rulegroupsnamespace ARN, NOT the workspace ARN.
  // Granting aps:* only on the workspace ARN silently denies rule-group
  // create/update/delete, so we list both resources.
  const apsWorkspaceArn = `arn:aws:aps:${cfg.region}:${cfg.accountId}:workspace/${cfg.apsWorkspaceId}`;
  const apsRuleGroupsNamespaceArn = `arn:aws:aps:${cfg.region}:${cfg.accountId}:rulegroupsnamespace/${cfg.apsWorkspaceId}/*`;
  const permissionsPolicy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [{
      Effect: 'Allow',
      Action: 'aps:*',
      Resource: [apsWorkspaceArn, apsRuleGroupsNamespaceArn],
    }],
  });

  try {
    await client.send(new PutRolePolicyCommand({
      RoleName: roleName,
      PolicyName: 'APSAccess',
      PolicyDocument: permissionsPolicy,
    }));
    printSuccess('APS access policy attached to Connected Data Source role');
  } catch (err) {
    printError('Failed to attach APS policy to Connected Data Source role');
    console.error(`  ${chalk.dim(err.message)}`);
    console.error();
    throw new Error('Failed to attach APS policy to Connected Data Source role');
  }

  await sleep(5000);
}

/**
 * Create a Connected Data Source connecting OpenSearch to AMP (Prometheus).
 * Uses the OpenSearch service control plane API.
 */
export async function createConnectedDataSource(cfg) {
  const dataSourceName = cfg.connectedDataSourceName;
  printStep(`Creating Connected Data Source '${dataSourceName}'...`);

  const client = new OpenSearchClient({ region: cfg.region });
  const workspaceArn = `arn:aws:aps:${cfg.region}:${cfg.accountId}:workspace/${cfg.apsWorkspaceId}`;

  try {
    // The direct-query data source assumes connectedDataSourceRoleArn, which may
    // have just been created; retry while IAM propagation catches up.
    const result = await withRetry(
      () => client.send(new AddDirectQueryDataSourceCommand({
        DataSourceName: dataSourceName,
        DataSourceType: {
          Prometheus: {
            RoleArn: cfg.connectedDataSourceRoleArn,
            WorkspaceArn: workspaceArn,
          },
        },
        Description: `Prometheus data source for ${cfg.pipelineName} observability stack`,
      })),
      {
        shouldRetry: isRoleNotPropagatedError,
        onRetry: (e, i) => printInfo(`Connected Data Source role not propagated yet (attempt ${i + 1}) — retrying`),
      },
    );
    cfg.connectedDataSourceArn = result.DataSourceArn;
    printSuccess(`Connected Data Source created: ${cfg.connectedDataSourceArn}`);
    await tagResource(cfg.region, cfg.connectedDataSourceArn, cfg.pipelineName);
  } catch (err) {
    // Treat "already exists" as success
    if (/already exists/i.test(err.message) || err.name === 'ResourceAlreadyExistsException') {
      cfg.connectedDataSourceArn = `arn:aws:opensearch:${cfg.region}:${cfg.accountId}:datasource/${dataSourceName}`;
      printSuccess(`Data source '${dataSourceName}' already exists`);
      return;
    }
    printError('Failed to create Connected Data Source');
    console.error(`  ${chalk.dim(err.message)}`);
    console.error();
    throw new Error('Failed to create Connected Data Source');
  }
}

/**
 * Create an OpenSearch Application (the new OpenSearch UI) and associate
 * the OpenSearch domain/collection and the Connected Data Source with it.
 */
export async function createOpenSearchApplication(cfg) {
  const appName = cfg.appName;
  printStep(`Creating OpenSearch Application '${appName}'...`);

  const client = new OpenSearchClient({ region: cfg.region });

  // Check if app already exists
  try {
    const list = await client.send(new ListApplicationsCommand({}));
    const existing = (list.ApplicationSummaries || []).find((a) => a.name === appName);
    if (existing) {
      cfg.appId = existing.id;
      printSuccess(`Application '${appName}' already exists (id: ${cfg.appId})`);
      await fetchAppEndpoint(client, cfg);
      // Update data sources on existing app
      await associateDataSourcesWithApp(cfg, client);
      return;
    }
  } catch { /* proceed to create */ }

  // Build data sources list
  const dataSources = buildAppDataSources(cfg);

  try {
    const result = await client.send(new CreateApplicationCommand({
      name: appName,
      dataSources,
      appConfigs: [
        {
          key: 'opensearchDashboards.dashboardAdmin.users',
          value: JSON.stringify(['*']),
        },
        {
          key: 'opensearchDashboards.dashboardAdmin.groups',
          value: JSON.stringify([cfg.iamRoleArn]),
        },
      ],
      iamIdentityCenterOptions: {
        enabled: false,
      },
    }));
    cfg.appId = result.id;
    printSuccess(`Application created: ${cfg.appId}`);
    if (result.arn) {
      await tagResource(cfg.region, result.arn, cfg.pipelineName);
    }
    await fetchAppEndpoint(client, cfg);
  } catch (err) {
    if (/already exists/i.test(err.message) || err.name === 'ResourceAlreadyExistsException' || err.name === 'ConflictException') {
      printSuccess(`Application '${appName}' already exists`);
      // Try to find and update it
      try {
        const list = await client.send(new ListApplicationsCommand({}));
        const existing = (list.ApplicationSummaries || []).find((a) => a.name === appName);
        if (existing) {
          cfg.appId = existing.id;
          await fetchAppEndpoint(client, cfg);
          await associateDataSourcesWithApp(cfg, client);
        }
      } catch { /* best effort */ }
      return;
    }
    printWarning(`Could not create OpenSearch Application: ${err.message}`);
    printInfo('You can create one manually in the AWS console');
  }
}

/**
 * Fetch the application endpoint via GetApplicationCommand, waiting for the app
 * to reach ACTIVE with a populated endpoint. CreateApplication returns before the
 * endpoint is provisioned, so a single read races an empty value — which would
 * skip FGAC role mapping and UI setup for VPC domains. Poll until it appears.
 */
async function fetchAppEndpoint(client, cfg) {
  if (!cfg.appId) return;
  const maxWait = 300_000; // 5 min
  const interval = 5_000;
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    try {
      const resp = await client.send(new GetApplicationCommand({ id: cfg.appId }));
      if (resp.endpoint) {
        cfg.appEndpoint = resp.endpoint;
        return; // endpoint logged by setupDashboards
      }
      if (resp.status && !['CREATING', 'UPDATING', 'ACTIVE'].includes(resp.status)) {
        printWarning(`OpenSearch Application status is ${resp.status} — endpoint may not become available`);
        return;
      }
    } catch { /* keep polling */ }
    await sleep(interval);
  }
  printWarning('Timed out waiting for the OpenSearch Application endpoint');
}

/**
 * Build the data sources list for application create/update.
 */
function buildAppDataSources(cfg) {
  const dataSources = [];
  if (cfg.opensearchType === 'serverless') {
    if (cfg.collectionId) {
      dataSources.push({
        dataSourceArn: `arn:aws:aoss:${cfg.region}:${cfg.accountId}:collection/${cfg.collectionId}`,
      });
    }
  } else {
    // Derive the domain name from the endpoint URL if reusing,
    // otherwise use cfg.osDomainName (which may be set by applyQuickDefaults)
    let domainName = cfg.osDomainName;
    if (cfg.opensearchEndpoint && cfg.osAction === 'reuse') {
      const m = cfg.opensearchEndpoint.match(/search-(.+?)-[a-z0-9]+\.[a-z0-9-]+\.es\.amazonaws\.com/);
      if (m) domainName = m[1];
    }
    if (domainName) {
      dataSources.push({
        dataSourceArn: `arn:aws:es:${cfg.region}:${cfg.accountId}:domain/${domainName}`,
      });
    }
  }
  if (cfg.connectedDataSourceArn) {
    dataSources.push({ dataSourceArn: cfg.connectedDataSourceArn });
  }
  return dataSources;
}

/**
 * Associate the OpenSearch domain and Connected Data Source with the application.
 */
async function associateDataSourcesWithApp(cfg, client) {
  if (!cfg.appId) return;

  const dataSources = buildAppDataSources(cfg);
  if (dataSources.length === 0) return;

  try {
    await client.send(new UpdateApplicationCommand({
      id: cfg.appId,
      dataSources,
    }));
    printSuccess('Data sources associated with application');
  } catch (err) {
    printWarning(`Could not associate data sources: ${err.message}`);
  }
}

// ── Resource listing (for interactive reuse selection) ──────────────────────

/**
 * List all OpenSearch managed domain endpoints in the given region.
 * Returns [{ name, endpoint, engineVersion }].
 */
export async function listDomains(region) {
  const results = [];

  try {
    const client = new OpenSearchClient({ region });
    const { DomainNames } = await client.send(new ListDomainNamesCommand({}));
    if (DomainNames?.length) {
      const names = DomainNames.map((d) => d.DomainName);
      for (let j = 0; j < names.length; j += 5) {
        const { DomainStatusList } = await client.send(
          new DescribeDomainsCommand({ DomainNames: names.slice(j, j + 5) }),
        );
        for (const d of DomainStatusList || []) {
          results.push({
            name: d.DomainName,
            endpoint: d.Endpoint ? `https://${d.Endpoint}` : '',
            engineVersion: d.EngineVersion || '',
          });
        }
      }
    }
  } catch { /* listing failed */ }

  return results;
}

/**
 * List AOSS collections in the given region.
 * Returns [{ name, id, endpoint, status }].
 */
export async function listCollections(region) {
  try {
    const client = new OpenSearchServerlessClient({ region });
    const { collectionSummaries } = await client.send(new ListCollectionsCommand({}));
    return (collectionSummaries || []).map((c) => ({
      name: c.name,
      id: c.id,
      endpoint: `https://${c.id}.${region}.aoss.amazonaws.com`,
      status: c.status,
    }));
  } catch { return []; }
}

/**
 * List IAM roles, optionally filtered by a prefix/keyword.
 * Returns [{ name, arn }].
 */
export async function listRoles(region) {
  const client = new IAMClient({ region });
  const roles = [];
  let marker;

  // Paginate (IAM can have many roles)
  do {
    const resp = await client.send(new ListRolesCommand({
      MaxItems: 200,
      Marker: marker,
    }));
    for (const r of resp.Roles || []) {
      roles.push({ name: r.RoleName, arn: r.Arn });
    }
    marker = resp.IsTruncated ? resp.Marker : undefined;
  } while (marker);

  return roles;
}

/**
 * List APS workspaces in the given region.
 * Returns [{ alias, id, url }].
 */
export async function listWorkspaces(region) {
  const client = new AmpClient({ region });
  const resp = await client.send(new ListWorkspacesCommand({}));
  return (resp.workspaces || [])
    .filter((w) => w.status?.statusCode === 'ACTIVE')
    .map((w) => ({
      alias: w.alias || '',
      id: w.workspaceId,
      url: `https://aps-workspaces.${region}.amazonaws.com/workspaces/${w.workspaceId}/api/v1/remote_write`,
    }));
}

/**
 * List OpenSearch Applications in the given region.
 * Returns [{ name, id, endpoint }].
 */
export async function listApplications(region) {
  const client = new OpenSearchClient({ region });
  const resp = await client.send(new ListApplicationsCommand({}));
  return (resp.ApplicationSummaries || []).map((a) => ({
    name: a.name,
    id: a.id,
    endpoint: a.endpoint || '',
  }));
}

// ── VPC / subnet / security group listing (for interactive VPC selection) ────

function nameTag(tags) {
  return (tags || []).find((t) => t.Key === 'Name')?.Value || '';
}

/**
 * List VPCs in the given region.
 * Returns [{ id, cidr, isDefault, name }].
 */
export async function listVpcs(region) {
  const { EC2Client, DescribeVpcsCommand } = await import('@aws-sdk/client-ec2');
  const client = new EC2Client({ region });
  const resp = await client.send(new DescribeVpcsCommand({}));
  return (resp.Vpcs || []).map((v) => ({
    id: v.VpcId,
    cidr: v.CidrBlock || '',
    isDefault: Boolean(v.IsDefault),
    name: nameTag(v.Tags),
  }));
}

/**
 * List subnets for a VPC.
 * Returns [{ id, az, cidr, name, mapPublicIp }].
 */
export async function listSubnets(region, vpcId) {
  const { EC2Client, DescribeSubnetsCommand } = await import('@aws-sdk/client-ec2');
  const client = new EC2Client({ region });
  const resp = await client.send(new DescribeSubnetsCommand({
    Filters: [{ Name: 'vpc-id', Values: [vpcId] }],
  }));
  return (resp.Subnets || []).map((s) => ({
    id: s.SubnetId,
    az: s.AvailabilityZone || '',
    cidr: s.CidrBlock || '',
    name: nameTag(s.Tags),
    mapPublicIp: Boolean(s.MapPublicIpOnLaunch),
  }));
}

/**
 * List security groups for a VPC.
 * Returns [{ id, name, description }].
 */
export async function listSecurityGroups(region, vpcId) {
  const { EC2Client, DescribeSecurityGroupsCommand } = await import('@aws-sdk/client-ec2');
  const client = new EC2Client({ region });
  const resp = await client.send(new DescribeSecurityGroupsCommand({
    Filters: [{ Name: 'vpc-id', Values: [vpcId] }],
  }));
  return (resp.SecurityGroups || []).map((g) => ({
    id: g.GroupId,
    name: g.GroupName || '',
    description: g.Description || '',
  }));
}

/**
 * Validate the VPC topology against live EC2 state so the run fails fast, before
 * any OpenSearch/OSIS resources are created. The syntactic checks in
 * validateConfig() only confirm the IDs are well-formed; this confirms they
 * actually exist, belong together, and satisfy OpenSearch's zone-awareness rules.
 *
 * Catches (each of which otherwise surfaces minutes into domain/pipeline creation):
 *   - VPC does not exist / wrong region.
 *   - A subnet or security group is not a member of the given VPC. OpenSearch's
 *     CreateDomain rejects a subnet/SG that lives in a different VPC.
 *   - Two subnets share an Availability Zone. createOpenSearch() derives the
 *     zone-awareness AZ count from the subnet count (min(subnetIds.length, 3)),
 *     so duplicate AZs make CreateDomain fail with a ValidationException.
 *
 * @param {object} cfg  the resolved config (needs region, vpcId, subnetIds, securityGroupIds)
 * @param {object} [deps]  optional injected EC2 accessors for testing
 * @returns {Promise<string[]>}  error strings (empty = valid)
 */
export async function validateVpcTopology(cfg, deps = {}) {
  // Only relevant when a VPC deployment was requested. Well-formedness is assumed
  // to have been checked by validateConfig() already.
  if (!cfg.vpcId) return [];

  const describeVpcs = deps.describeVpcs || (async (region, ids) => {
    const { EC2Client, DescribeVpcsCommand } = await import('@aws-sdk/client-ec2');
    const client = new EC2Client({ region });
    return (await client.send(new DescribeVpcsCommand({ VpcIds: ids }))).Vpcs || [];
  });
  const describeSubnets = deps.describeSubnets || (async (region, ids) => {
    const { EC2Client, DescribeSubnetsCommand } = await import('@aws-sdk/client-ec2');
    const client = new EC2Client({ region });
    return (await client.send(new DescribeSubnetsCommand({ SubnetIds: ids }))).Subnets || [];
  });
  const describeSecurityGroups = deps.describeSecurityGroups || (async (region, ids) => {
    const { EC2Client, DescribeSecurityGroupsCommand } = await import('@aws-sdk/client-ec2');
    const client = new EC2Client({ region });
    return (await client.send(new DescribeSecurityGroupsCommand({ GroupIds: ids }))).SecurityGroups || [];
  });

  const errors = [];
  const region = cfg.region;
  const subnetIds = cfg.subnetIds || [];
  const securityGroupIds = cfg.securityGroupIds || [];

  // 1. VPC exists. A missing/invalid VPC throws InvalidVpcID.NotFound — translate
  //    that into a clean error rather than an SDK stack trace.
  try {
    const vpcs = await describeVpcs(region, [cfg.vpcId]);
    if (!vpcs.length) {
      errors.push(`VPC ${cfg.vpcId} was not found in ${region}. Check the ID and region.`);
      return errors; // Nothing else can be validated without the VPC.
    }
  } catch (err) {
    if (/InvalidVpcID\.NotFound|does not exist/i.test(err.message || '')) {
      errors.push(`VPC ${cfg.vpcId} was not found in ${region}. Check the ID and region.`);
    } else {
      errors.push(`Could not verify VPC ${cfg.vpcId}: ${err.message}`);
    }
    return errors;
  }

  // 2. Subnets: each must exist and belong to the VPC; collect their AZs.
  if (subnetIds.length) {
    try {
      const subnets = await describeSubnets(region, subnetIds);
      const found = new Map(subnets.map((s) => [s.SubnetId, s]));
      for (const id of subnetIds) {
        const s = found.get(id);
        if (!s) {
          errors.push(`Subnet ${id} was not found in ${region}.`);
        } else if (s.VpcId !== cfg.vpcId) {
          errors.push(`Subnet ${id} belongs to VPC ${s.VpcId}, not ${cfg.vpcId}. All subnets must be in the target VPC.`);
        }
      }
      // Zone-awareness: subnets must be in distinct AZs. createOpenSearch()
      // enables zone awareness with AvailabilityZoneCount = min(subnetIds, 3)
      // and places one node group per AZ, so two subnets in the same AZ make
      // CreateDomain fail. Only meaningful with more than one subnet.
      const inVpc = subnets.filter((s) => s.VpcId === cfg.vpcId);
      if (inVpc.length > 1) {
        const azSeen = new Map();
        for (const s of inVpc) {
          const az = s.AvailabilityZone;
          if (azSeen.has(az)) {
            errors.push(`Subnets ${azSeen.get(az)} and ${s.SubnetId} are both in ${az}. OpenSearch requires each subnet to be in a distinct Availability Zone for a zone-aware domain.`);
          } else {
            azSeen.set(az, s.SubnetId);
          }
        }
      }
    } catch (err) {
      if (/InvalidSubnetID\.NotFound|does not exist/i.test(err.message || '')) {
        errors.push(`One or more subnets were not found in ${region}: ${subnetIds.join(', ')}.`);
      } else {
        errors.push(`Could not verify subnets: ${err.message}`);
      }
    }
  }

  // 3. Security groups: each must exist and belong to the VPC.
  if (securityGroupIds.length) {
    try {
      const groups = await describeSecurityGroups(region, securityGroupIds);
      const found = new Map(groups.map((g) => [g.GroupId, g]));
      for (const id of securityGroupIds) {
        const g = found.get(id);
        if (!g) {
          errors.push(`Security group ${id} was not found in ${region}.`);
        } else if (g.VpcId !== cfg.vpcId) {
          errors.push(`Security group ${id} belongs to VPC ${g.VpcId}, not ${cfg.vpcId}. All security groups must be in the target VPC.`);
        }
      }
    } catch (err) {
      if (/InvalidGroup\.NotFound|does not exist/i.test(err.message || '')) {
        errors.push(`One or more security groups were not found in ${region}: ${securityGroupIds.join(', ')}.`);
      } else {
        errors.push(`Could not verify security groups: ${err.message}`);
      }
    }
  }

  return errors;
}

// ── Security-group rule analysis (best-effort data-path check) ───────────────

/**
 * Does a permission entry cover TCP `port`? IpProtocol '-1' means all protocols
 * and all ports.
 */
function permCoversPort(p, port) {
  const proto = p.IpProtocol;
  return proto === '-1' || (proto === 'tcp' && (p.FromPort ?? 0) <= port && (p.ToPort ?? 65535) >= port);
}

/**
 * Does a set of IpPermissions entries allow TCP `port` from/to an intra-stack
 * source? A source counts as intra-stack when the rule references one of the
 * stack's own security groups (`selfIds`) or a CIDR not narrower than the VPC
 * (0.0.0.0/0, or a VPC-CIDR entry).
 */
export function permissionsAllowPort(permissions, port, { selfIds = [], vpcCidrs = [] } = {}) {
  const selfSet = new Set(selfIds);
  const cidrOk = (cidr) => cidr === '0.0.0.0/0' || vpcCidrs.includes(cidr);
  for (const p of permissions || []) {
    if (!permCoversPort(p, port)) continue;
    if ((p.UserIdGroupPairs || []).some((g) => selfSet.has(g.GroupId))) return true;
    if ((p.IpRanges || []).some((r) => cidrOk(r.CidrIp))) return true;
  }
  return false;
}

/**
 * Does a set of IpPermissions entries allow TCP `port` to the public internet
 * (a 0.0.0.0/0 IpRanges entry)? A self-referencing SG rule or a VPC-scoped CIDR
 * does NOT count; those keep traffic inside the VPC. The demo instance needs
 * this for bootstrap (dnf, GitHub, container registries), which does not route
 * through the VPC-private OSIS endpoint.
 */
export function permissionsAllowInternet(permissions, port) {
  for (const p of permissions || []) {
    if (!permCoversPort(p, port)) continue;
    if ((p.IpRanges || []).some((r) => r.CidrIp === '0.0.0.0/0')) return true;
  }
  return false;
}

/**
 * Return WARNING strings for security-group rules that break the stack's data
 * path. Pure (takes the DescribeSecurityGroups result). Warnings only: a user's
 * network may route the same traffic via other groups, a NAT, or NACLs we can't
 * see. The EC2 demo, OSIS, and domain share `groupIds`, so the union must allow:
 *   - Intra-VPC egress 443 (always): OSIS to domain; with a demo, demo collector
 *     to the VPC-private OSIS ingest. Any of self-ref, VPC-CIDR, or 0.0.0.0/0.
 *   - Internet egress 443 (demo only): the instance bootstraps over the public
 *     internet (dnf, GitHub, image pulls), which does not use the VPC-private
 *     endpoint. Only 0.0.0.0/0 (via a NAT/IGW) satisfies it, not a VPC-CIDR rule.
 *   - Intra-VPC ingress 443 (always): OSIS from the demo, domain from OSIS.
 *
 * @param {object[]} groups  DescribeSecurityGroups result
 * @param {object} opts
 * @param {string[]} opts.groupIds  the stack's SG ids (self-reference set)
 * @param {string[]} [opts.vpcCidrs]  the VPC's CIDR block(s)
 * @param {boolean} [opts.demo=true]  whether an EC2 demo will launch (adds the
 *   internet-egress requirement); pass false for --skip-demo
 */
export function analyzeSecurityGroupRules(groups, { groupIds = [], vpcCidrs = [], demo = true } = {}) {
  const warnings = [];
  const ids = groupIds.length ? groupIds : (groups || []).map((g) => g.GroupId);
  const opts = { selfIds: ids, vpcCidrs };
  const list = groups || [];

  const intraVpcEgress443 = list.some((g) => permissionsAllowPort(g.IpPermissionsEgress, 443, opts));
  const internetEgress443 = list.some((g) => permissionsAllowInternet(g.IpPermissionsEgress, 443));
  const intraVpcIngress443 = list.some((g) => permissionsAllowPort(g.IpPermissions, 443, opts));

  if (!intraVpcEgress443) {
    warnings.push(
      `No outbound (egress) rule allowing TCP 443 within the VPC was found on ${ids.join(', ')}. ` +
      `OSIS cannot reach the OpenSearch domain${demo ? ' and the demo collector cannot reach the OSIS ingest endpoint' : ''}, so no telemetry will appear. ` +
      `Add an egress rule allowing TCP 443 to these security groups themselves (self-reference), the VPC CIDR, or 0.0.0.0/0.`
    );
  }
  if (demo && !internetEgress443) {
    warnings.push(
      `No outbound (egress) rule allowing TCP 443 to the internet (0.0.0.0/0) was found on ${ids.join(', ')}. ` +
      `The EC2 demo bootstraps over the public internet (package install, GitHub clone, container image pulls); that traffic does not use the VPC-private endpoint, so a VPC-scoped egress rule is not enough. ` +
      `Add an egress rule allowing TCP 443 to 0.0.0.0/0 (reachable via a NAT gateway for private subnets, or an internet gateway for public ones).`
    );
  }
  if (!intraVpcIngress443) {
    warnings.push(
      `No inbound (ingress) rule allowing TCP 443 from within the VPC was found on ${ids.join(', ')}. ` +
      `OSIS will reject OTLP${demo ? ' from the demo' : ''} and the domain will reject requests from OSIS. ` +
      `Add an ingress rule allowing TCP 443 from these security groups themselves (self-reference) or from the VPC CIDR.`
    );
  }
  return warnings;
}

/**
 * Best-effort check of the stack's security-group rules against the data path.
 * Returns WARNING strings (never throws, never blocks the run). When the caller
 * lacks ec2:DescribeSecurityGroups, returns a single warning telling the user to
 * verify the rules manually, since we can't inspect them.
 *
 * @param {object} cfg  resolved config (needs region, vpcId, securityGroupIds)
 * @param {object} [deps]  optional injected accessors for testing
 * @returns {Promise<string[]>}
 */
export async function checkSecurityGroupRules(cfg, deps = {}) {
  if (!cfg.vpcId || !(cfg.securityGroupIds || []).length) return [];

  const demo = !cfg.skipDemo;

  const describeSecurityGroups = deps.describeSecurityGroups || (async (region, ids) => {
    const { EC2Client, DescribeSecurityGroupsCommand } = await import('@aws-sdk/client-ec2');
    const client = new EC2Client({ region });
    return (await client.send(new DescribeSecurityGroupsCommand({ GroupIds: ids }))).SecurityGroups || [];
  });
  const describeVpcs = deps.describeVpcs || (async (region, ids) => {
    const { EC2Client, DescribeVpcsCommand } = await import('@aws-sdk/client-ec2');
    const client = new EC2Client({ region });
    return (await client.send(new DescribeVpcsCommand({ VpcIds: ids }))).Vpcs || [];
  });

  const ids = cfg.securityGroupIds;
  let groups;
  try {
    groups = await describeSecurityGroups(cfg.region, ids);
  } catch (err) {
    if (/UnauthorizedOperation|AccessDenied|not authorized/i.test(err.message || err.name || '')) {
      return [
        `Could not verify security-group rules (the current role lacks ec2:DescribeSecurityGroups). ` +
        `Ensure ${ids.join(', ')} allow outbound TCP 443 within the VPC (OSIS to domain${demo ? ', demo collector to OSIS ingest' : ''}), ` +
        `inbound TCP 443 from within the VPC (OSIS from ${demo ? 'demo, ' : ''}domain from OSIS)` +
        `${demo ? ', and outbound TCP 443 to 0.0.0.0/0 for the demo to bootstrap over the internet' : ''}, or telemetry will not appear.`,
      ];
    }
    return [`Could not verify security-group rules: ${err.message}`];
  }

  let vpcCidrs = [];
  try {
    const vpcs = await describeVpcs(cfg.region, [cfg.vpcId]);
    vpcCidrs = (vpcs[0]?.CidrBlockAssociationSet || []).map((a) => a.CidrBlock).filter(Boolean);
    if (!vpcCidrs.length && vpcs[0]?.CidrBlock) vpcCidrs = [vpcs[0].CidrBlock];
  } catch { /* VPC CIDR is a refinement; self-reference checks still work without it */ }

  return analyzeSecurityGroupRules(groups, { groupIds: ids, vpcCidrs, demo });
}

// ── Pipeline listing / describe / update ─────────────────────────────────────

/**
 * List all OSI pipelines in the given region.
 * Returns [{ name, status, minUnits, maxUnits, createdAt, lastUpdatedAt }].
 */
export async function listPipelines(region) {
  const client = new OSISClient({ region });
  const resp = await client.send(new ListPipelinesCommand({ MaxResults: 100 }));
  return (resp.Pipelines || []).map((p) => ({
    name: p.PipelineName,
    status: p.Status,
    minUnits: p.MinUnits,
    maxUnits: p.MaxUnits,
    createdAt: p.CreatedAt,
    lastUpdatedAt: p.LastUpdatedAt,
  }));
}


/**
 * Get the OTLP ingest endpoint URL for an OSI pipeline.
 */
export async function getPipelineEndpoint(region, pipelineName) {
  const client = new OSISClient({ region });
  const resp = await client.send(new GetPipelineCommand({ PipelineName: pipelineName }));
  const urls = resp.Pipeline?.IngestEndpointUrls;
  return urls?.length ? urls[0] : null;
}

// ── Stack discovery (tag-based) ──────────────────────────────────────────────

/**
 * Tag a resource after creation using the Resource Groups Tagging API.
 * Best-effort — failures are silently ignored.
 */
export async function tagResource(region, arn, stackName) {
  try {
    const client = new ResourceGroupsTaggingAPIClient({ region });
    await client.send(new TagResourcesCommand({
      ResourceARNList: [arn],
      Tags: { [TAG_KEY]: stackName },
    }));
  } catch { /* best effort */ }
}

/**
 * List all stacks in a region by querying the Resource Groups Tagging API.
 * Returns [{ name, resources: [{ arn, type }] }] grouped by stack name.
 */
export async function listStacks(region) {
  const client = new ResourceGroupsTaggingAPIClient({ region });
  const stacks = new Map();

  let paginationToken;
  do {
    const resp = await client.send(new GetResourcesCommand({
      TagFilters: [{ Key: TAG_KEY }],
      PaginationToken: paginationToken || undefined,
    }));

    for (const r of resp.ResourceTagMappingList || []) {
      const tag = (r.Tags || []).find((t) => t.Key === TAG_KEY);
      if (!tag) continue;
      const stackName = tag.Value;
      if (!stacks.has(stackName)) {
        stacks.set(stackName, []);
      }
      stacks.get(stackName).push({
        arn: r.ResourceARN,
        type: arnToType(r.ResourceARN),
      });
    }

    paginationToken = resp.PaginationToken;
  } while (paginationToken);

  // Supplement with OpenSearch Applications (may not appear in tagging API)
  await supplementApplications(region, stacks);

  return [...stacks.entries()].map(([name, resources]) => ({ name, resources }));
}

/**
 * Get all resources for a specific stack by its tag value.
 * Returns [{ arn, type }].
 */
export async function getStackResources(region, stackName) {
  const client = new ResourceGroupsTaggingAPIClient({ region });
  const resources = [];

  let paginationToken;
  do {
    const resp = await client.send(new GetResourcesCommand({
      TagFilters: [{ Key: TAG_KEY, Values: [stackName] }],
      PaginationToken: paginationToken || undefined,
    }));

    for (const r of resp.ResourceTagMappingList || []) {
      resources.push({
        arn: r.ResourceARN,
        type: arnToType(r.ResourceARN),
      });
    }

    paginationToken = resp.PaginationToken;
  } while (paginationToken);

  // Supplement with OpenSearch Application if not already present
  const stacks = new Map([[stackName, resources]]);
  await supplementApplications(region, stacks);

  return resources;
}

/**
 * Map an ARN to a human-readable resource type.
 */
function arnToType(arn) {
  if (/^arn:aws:osis:/.test(arn)) return 'OSI Pipeline';
  if (/^arn:aws:aoss:/.test(arn)) return 'AOSS Collection';
  if (/^arn:aws:es:.*:domain\//.test(arn)) return 'OpenSearch Domain';
  if (/^arn:aws:iam:.*:role\//.test(arn)) return 'IAM Role';
  if (/^arn:aws:aps:.*:workspace\//.test(arn)) return 'APS Workspace';
  if (/^arn:aws:opensearch:.*:datasource\//.test(arn)) return 'DQ Data Source';
  if (/^arn:aws:opensearch:.*:application\//.test(arn)) return 'OpenSearch Application';
  return 'Resource';
}

/**
 * Extract the resource name from an ARN.
 */
export function arnToName(arn) {
  // IAM roles: arn:aws:iam::123:role/role-name
  const iamMatch = arn.match(/:role\/(.+)$/);
  if (iamMatch) return iamMatch[1];
  // Most others: .../{name} or ...:<name>
  const lastSlash = arn.lastIndexOf('/');
  if (lastSlash !== -1) return arn.slice(lastSlash + 1);
  const lastColon = arn.lastIndexOf(':');
  if (lastColon !== -1) return arn.slice(lastColon + 1);
  return arn;
}

/**
 * Enrich resource objects with display names where the ARN-derived name is not
 * human-friendly (e.g. APS workspace IDs → aliases, application IDs → names).
 */
export async function enrichResourceNames(region, resources) {
  // APS workspaces: resolve alias
  const apsResources = resources.filter((r) => r.type === 'APS Workspace');
  if (apsResources.length) {
    const client = new AmpClient({ region });
    for (const r of apsResources) {
      try {
        const wsId = arnToName(r.arn);
        const resp = await client.send(new DescribeWorkspaceCommand({ workspaceId: wsId }));
        if (resp.workspace?.alias) r.displayName = resp.workspace.alias;
      } catch { /* keep default */ }
    }
  }
  // OpenSearch Applications: resolve name from ID
  const appResources = resources.filter((r) => r.type === 'OpenSearch Application');
  if (appResources.length) {
    try {
      const client = new OpenSearchClient({ region });
      const list = await client.send(new ListApplicationsCommand({}));
      for (const r of appResources) {
        const appId = arnToName(r.arn);
        const app = (list.ApplicationSummaries || []).find((a) => a.id === appId);
        if (app?.name) r.displayName = app.name;
      }
    } catch { /* keep default */ }
  }
}

/**
 * Find OpenSearch Applications whose name matches a stack name and add them
 * to the resource list if not already present (tagging API may not return them).
 */
async function supplementApplications(region, stacks) {
  if (stacks.size === 0) return;
  try {
    const client = new OpenSearchClient({ region });
    const list = await client.send(new ListApplicationsCommand({}));
    for (const app of list.ApplicationSummaries || []) {
      if (!app.name || !app.arn) continue;
      const resources = stacks.get(app.name);
      if (!resources) continue;
      const alreadyPresent = resources.some((r) => r.type === 'OpenSearch Application');
      if (!alreadyPresent) {
        resources.push({ arn: app.arn, type: 'OpenSearch Application' });
      }
    }
  } catch { /* best effort */ }
}

/**
 * Fetch detailed information for a single resource by ARN.
 * Returns { entries: [[label, value], ...], rawConfig?: string }.
 */
export async function describeResource(region, resource) {
  const { arn, type } = resource;
  const name = arnToName(arn);
  const entries = [['ARN', arn]];
  let rawConfig;

  try {
    if (type === 'OSI Pipeline') {
      const client = new OSISClient({ region });
      const resp = await client.send(new GetPipelineCommand({ PipelineName: name }));
      const p = resp.Pipeline || {};
      entries.push(['Status', p.Status || 'Unknown']);
      if (p.StatusReason?.Message) entries.push(['Status Reason', p.StatusReason.Message]);
      entries.push(['Min Units', String(p.MinUnits ?? '')]);
      entries.push(['Max Units', String(p.MaxUnits ?? '')]);
      if (p.IngestEndpointUrls?.length) {
        for (const url of p.IngestEndpointUrls) entries.push(['Ingest Endpoint', url]);
      }
      if (p.PipelineRoleArn) entries.push(['Role ARN', p.PipelineRoleArn]);
      if (p.CreatedAt) entries.push(['Created', p.CreatedAt.toISOString()]);
      if (p.LastUpdatedAt) entries.push(['Last Updated', p.LastUpdatedAt.toISOString()]);
      if (p.PipelineConfigurationBody) rawConfig = p.PipelineConfigurationBody;
    } else if (type === 'OpenSearch Domain') {
      const client = new OpenSearchClient({ region });
      const resp = await client.send(new DescribeDomainCommand({ DomainName: name }));
      const d = resp.DomainStatus || {};
      if (d.EngineVersion) entries.push(['Engine Version', d.EngineVersion]);
      if (d.Endpoint) entries.push(['Endpoint', `https://${d.Endpoint}`]);
      if (d.ClusterConfig) {
        const cc = d.ClusterConfig;
        if (cc.InstanceType) entries.push(['Instance Type', cc.InstanceType]);
        entries.push(['Instance Count', String(cc.InstanceCount ?? 1)]);
      }
      entries.push(['Processing', String(d.Processing ?? false)]);
      if (d.Created !== undefined) entries.push(['Created', String(d.Created)]);
    } else if (type === 'APS Workspace') {
      const wsId = name;
      const client = new AmpClient({ region });
      const resp = await client.send(new DescribeWorkspaceCommand({ workspaceId: wsId }));
      const w = resp.workspace || {};
      if (w.status?.statusCode) entries.push(['Status', w.status.statusCode]);
      if (w.alias) entries.push(['Alias', w.alias]);
      if (w.prometheusEndpoint) entries.push(['Prometheus Endpoint', w.prometheusEndpoint]);
      if (w.createdAt) entries.push(['Created', w.createdAt.toISOString()]);
    } else if (type === 'IAM Role') {
      const client = new IAMClient({ region });
      const resp = await client.send(new GetRoleCommand({ RoleName: name }));
      const r = resp.Role || {};
      if (r.Description) entries.push(['Description', r.Description]);
      if (r.Path) entries.push(['Path', r.Path]);
      if (r.CreateDate) entries.push(['Created', r.CreateDate.toISOString()]);
      if (r.MaxSessionDuration) entries.push(['Max Session Duration', `${r.MaxSessionDuration}s`]);
    } else if (type === 'DQ Data Source') {
      const client = new OpenSearchClient({ region });
      const resp = await client.send(new GetDirectQueryDataSourceCommand({ DataSourceName: name }));
      if (resp.DataSourceType) {
        const typeKey = Object.keys(resp.DataSourceType)[0];
        if (typeKey) entries.push(['Data Source Type', typeKey]);
      }
      if (resp.Description) entries.push(['Description', resp.Description]);
      if (resp.OpenSearchArns?.length) {
        for (const a of resp.OpenSearchArns) entries.push(['OpenSearch ARN', a]);
      }
    } else if (type === 'AOSS Collection') {
      const client = new OpenSearchServerlessClient({ region });
      const resp = await client.send(new BatchGetCollectionCommand({ ids: [name] }));
      const c = resp.collectionDetails?.[0];
      if (c) {
        if (c.status) entries.push(['Status', c.status]);
        if (c.collectionEndpoint) entries.push(['Endpoint', c.collectionEndpoint]);
        if (c.type) entries.push(['Type', c.type]);
        if (c.createdDate) entries.push(['Created', new Date(c.createdDate).toISOString()]);
      }
    } else if (type === 'OpenSearch Application') {
      const client = new OpenSearchClient({ region });
      const appId = name;
      const resp = await client.send(new GetApplicationCommand({ id: appId }));
      if (resp.status) entries.push(['Status', resp.status]);
      if (resp.endpoint) entries.push(['Endpoint', resp.endpoint]);
      if (resp.dataSources?.length) {
        for (const ds of resp.dataSources) {
          if (ds.dataSourceArn) entries.push(['Data Source', ds.dataSourceArn]);
        }
      }
      if (resp.createdAt) entries.push(['Created', resp.createdAt.toISOString()]);
      if (resp.lastUpdatedAt) entries.push(['Last Updated', resp.lastUpdatedAt.toISOString()]);
    }
  } catch (err) {
    entries.push(['Error', err.message]);
  }

  return { entries, rawConfig };
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retry an async operation on transient failures with exponential backoff.
 * `shouldRetry(err)` decides whether an error is worth retrying (default: any).
 * Returns the operation's result, or rethrows the last error once `attempts`
 * is exhausted. `onRetry(err, attempt)` runs between tries for progress output.
 */
async function withRetry(fn, { attempts = 6, delayMs = 5000, backoff = 1.6, maxDelayMs = 30_000, shouldRetry = () => true, onRetry } = {}) {
  let lastErr;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn(i);
    } catch (err) {
      lastErr = err;
      if (i === attempts - 1 || !shouldRetry(err)) throw err;
      if (onRetry) onRetry(err, i);
      await sleep(Math.min(maxDelayMs, Math.round(delayMs * backoff ** i)));
    }
  }
  throw lastErr;
}

/**
 * True when an error is a freshly-created IAM role that hasn't propagated yet.
 * OSIS/OpenSearch validate assume-role synchronously and reject with these
 * shapes until the role and its trust policy are globally consistent.
 */
function isRoleNotPropagatedError(err) {
  const msg = err?.message || '';
  const name = err?.name || '';
  return (
    /cannot be assumed|not authorized to perform: sts:AssumeRole|unable to assume|does not have permission to assume|role .*(does not exist|not found)|Invalid .*RoleArn|no such entity/i.test(msg) ||
    name === 'ValidationException' && /role/i.test(msg)
  );
}

/**
 * True when an HTTP/network error against a just-provisioned OpenSearch domain
 * or the managed UI proxy is transient (cluster still warming up, VPC endpoint
 * connection not yet live). These clear on their own within a minute or two.
 */
function isTransientHttpError(err) {
  const msg = err?.message || String(err || '');
  return /ECONNREFUSED|ECONNRESET|ETIMEDOUT|EAI_AGAIN|socket hang up|network|fetch failed|terminated|502|503|504|timeout/i.test(msg);
}

// OSIS CreatePipeline intermittently returns an internal exception that the API
// itself asks the caller to retry ("Please try again..."). This fails a deploy
// after the domain is already built, so treat it as retryable.
function isOsisInternalError(err) {
  const msg = err?.message || '';
  const name = err?.name || '';
  return (
    name === 'InternalException' ||
    /internal (exception|failure|error)|please try again|internalservererror/i.test(msg)
  );
}

// Exported for unit tests.
export { withRetry as _withRetry, isRoleNotPropagatedError as _isRoleNotPropagatedError, isTransientHttpError as _isTransientHttpError, isOsisInternalError as _isOsisInternalError };

function fmtElapsed(totalSec) {
  if (totalSec < 60) return `${totalSec}s`;
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m ${s}s`;
}

/** Sleep for `totalMs`, updating `spinner.text` every second via `textFn(elapsedSec)`. */
async function sleepWithTicker(totalMs, spinner, startTime, textFn) {
  const end = Date.now() + totalMs;
  while (Date.now() < end) {
    spinner.text = textFn(Math.round((Date.now() - startTime) / 1000));
    await sleep(Math.min(1000, end - Date.now()));
  }
}
