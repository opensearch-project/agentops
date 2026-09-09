#!/usr/bin/env node
/**
 * Launch only the EC2 demo workload against an existing OSI pipeline.
 * Usage: node bin/launch-demo.mjs --profile <p> --pipeline-name <name> --region <r>
 */
import { Command } from 'commander';
import { addProfileOption, configureAwsProfile } from '../src/aws-profile.mjs';
import { OSISClient, GetPipelineCommand } from '@aws-sdk/client-osis';
import { STSClient, GetCallerIdentityCommand } from '@aws-sdk/client-sts';
import { launchDemoInstance } from '../src/ec2-demo.mjs';
import { printError, printInfo, printSuccess } from '../src/ui.mjs';

const program = new Command()
  .requiredOption('--pipeline-name <name>', 'Existing OSI pipeline name')
  .requiredOption('--region <region>', 'AWS region');
addProfileOption(program);
program.parse(process.argv);
const opts = program.opts();
configureAwsProfile(opts.profile);

try {
  const sts = new STSClient({ region: opts.region });
  const { Account } = await sts.send(new GetCallerIdentityCommand({}));
  printInfo(`Account: ${Account}`);

  const osis = new OSISClient({ region: opts.region });
  const { Pipeline } = await osis.send(new GetPipelineCommand({ PipelineName: opts.pipelineName }));
  const urls = Pipeline?.IngestEndpointUrls || [];
  if (!urls.length) {
    printError(`Pipeline ${opts.pipelineName} has no ingest endpoints`);
    process.exit(1);
  }
  printInfo(`Ingest endpoint: https://${urls[0]}`);

  const cfg = {
    pipelineName: opts.pipelineName,
    region: opts.region,
    accountId: Account,
    ingestEndpoints: urls,
  };

  const instanceId = await launchDemoInstance(cfg);
  printSuccess(`Done. Instance ${instanceId}`);
  printInfo(`Connect: aws ssm start-session --target ${instanceId} --region ${opts.region}`);
} catch (e) {
  printError(e.message);
  process.exit(1);
}
