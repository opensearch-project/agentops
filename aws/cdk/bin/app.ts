#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { InfraStack } from '../lib/infra-stack';
import { ObservabilityStack } from '../lib/observability-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

const opensearchType = (app.node.tryGetContext('opensearchType') as 'managed' | 'serverless') || 'managed';
// Defaults to the optimized engine (OR2). Pass -c engineMode=general -c osInstanceType=r6g.large.search for a standard domain.
const engineMode = ((app.node.tryGetContext('engineMode') as string) || 'optimized').toUpperCase() === 'GENERAL'
  ? 'GENERAL'
  : 'OPTIMIZED';
const osInstanceType = (app.node.tryGetContext('osInstanceType') as string)
  || (engineMode === 'OPTIMIZED' ? 'or2.large.search' : 'r6g.large.search');

// Slow-changing infra: OpenSearch domain/collection, AMP workspace, DQS data source
const infra = new InfraStack(app, 'ObsInfra', {
  env,
  opensearchType,
  ...(opensearchType !== 'serverless' && {
    osInstanceType,
    osInstanceCount: 1,
    osVolumeSize: 100,
    osEngineMode: engineMode,
  }),
});

// Fast-iteration stack: FGAC, OSIS pipeline, OpenSearch App, UI init
new ObservabilityStack(app, 'ObservabilityStack', {
  env,
  infra,
  minOcu: 1,
  maxOcu: 4,
  enableDemo: true,
});
