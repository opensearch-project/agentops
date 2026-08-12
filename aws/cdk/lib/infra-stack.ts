import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { OpenSearchConstruct } from './opensearch';
import { OpenSearchServerlessConstruct } from './opensearch-serverless';
import { PrometheusConstruct } from './prometheus';

export interface InfraStackProps extends cdk.StackProps {
  opensearchType?: 'managed' | 'serverless';
  osInstanceType?: string;
  osInstanceCount?: number;
  osVolumeSize?: number;
  osEngineMode?: 'GENERAL' | 'OPTIMIZED';
}

export class InfraStack extends cdk.Stack {
  public readonly opensearchType: string;
  public readonly domainEndpoint: string;
  public readonly domainArn: string;
  public readonly masterPasswordSecretArn: string;
  public readonly pipelineRoleArn: string;
  public readonly ampWorkspaceArn: string;
  public readonly ampWorkspaceId: string;
  public readonly dqsDataSourceArn: string;
  public readonly dqsRoleArn: string;

  constructor(scope: Construct, id: string, props: InfraStackProps) {
    super(scope, id, props);

    cdk.Tags.of(this).add('observability-stack', this.stackName);

    this.opensearchType = props.opensearchType ?? 'managed';

    if (this.opensearchType === 'serverless') {
      const collectionName = `obs-${this.stackName}`.toLowerCase().replace(/[^a-z0-9-]/g, '-').slice(0, 32);
      const serverless = new OpenSearchServerlessConstruct(this, 'OpenSearchServerless', {
        collectionName,
      });

      this.domainEndpoint = serverless.collectionEndpoint;
      this.domainArn = serverless.collectionArn;
      this.masterPasswordSecretArn = '';
      this.pipelineRoleArn = serverless.pipelineRole.roleArn;
    } else {
      const opensearch = new OpenSearchConstruct(this, 'OpenSearch', {
        instanceType: props.osInstanceType ?? 'or2.large.search',
        instanceCount: props.osInstanceCount ?? 1,
        volumeSize: props.osVolumeSize ?? 100,
        engineMode: props.osEngineMode ?? 'OPTIMIZED',
      });

      this.domainEndpoint = opensearch.domain.domainEndpoint;
      this.domainArn = opensearch.domain.domainArn;
      this.masterPasswordSecretArn = opensearch.masterPasswordSecret.secretArn;
      this.pipelineRoleArn = opensearch.pipelineRole.roleArn;
    }

    const prometheus = new PrometheusConstruct(this, 'Prometheus', {
      domainArn: this.domainArn,
    });

    this.ampWorkspaceArn = prometheus.workspace.attrArn;
    this.ampWorkspaceId = prometheus.workspace.attrWorkspaceId;
    this.dqsDataSourceArn = prometheus.dataSourceArn;
    this.dqsRoleArn = prometheus.dqsRole.roleArn;

    // Exports
    const exp = (name: string, value: string) =>
      new cdk.CfnOutput(this, name, { value, exportName: `${this.stackName}-${name}` });

    exp('OpenSearchType', this.opensearchType);
    exp('DomainEndpoint', this.domainEndpoint);
    exp('DomainArn', this.domainArn);
    if (this.masterPasswordSecretArn) {
      exp('MasterPasswordSecretArn', this.masterPasswordSecretArn);
    }
    exp('PipelineRoleArn', this.pipelineRoleArn);
    exp('AmpWorkspaceArn', this.ampWorkspaceArn);
    exp('AmpWorkspaceId', this.ampWorkspaceId);
    exp('DqsDataSourceArn', this.dqsDataSourceArn);
    exp('DqsRoleArn', this.dqsRoleArn);
  }
}
