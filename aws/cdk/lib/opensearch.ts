import * as cdk from 'aws-cdk-lib';
import * as opensearch from 'aws-cdk-lib/aws-opensearchservice';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

// Optimized instance families. OR1/OR2/OM2 use gp3/io1 EBS; OI2 uses local NVMe.
const OPTIMIZED_FAMILIES = ['or1', 'or2', 'om2', 'oi2'];
const NVME_FAMILIES = ['oi2'];

function instanceFamily(instanceType: string): string {
  return (instanceType || '').split('.')[0].toLowerCase();
}

export interface OpenSearchConstructProps {
  instanceType: string;
  instanceCount: number;
  volumeSize: number;
  // 'GENERAL' (default) or 'OPTIMIZED' (OR1/OR2/OM2/OI2 instances).
  engineMode?: 'GENERAL' | 'OPTIMIZED';
}

export class OpenSearchConstruct extends Construct {
  public readonly domain: opensearch.Domain;
  public readonly pipelineRole: iam.Role;
  public readonly masterPasswordSecret: secretsmanager.Secret;

  constructor(scope: Construct, id: string, props: OpenSearchConstructProps) {
    super(scope, id);

    const stack = cdk.Stack.of(this);

    this.masterPasswordSecret = new secretsmanager.Secret(this, 'MasterPassword', {
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: 'admin' }),
        generateStringKey: 'password',
        excludePunctuation: false,
        passwordLength: 24,
      },
    });

    const family = instanceFamily(props.instanceType);
    const nvmeOnly = NVME_FAMILIES.includes(family);
    const optimized = props.engineMode === 'OPTIMIZED' || OPTIMIZED_FAMILIES.includes(family);

    this.domain = new opensearch.Domain(this, 'Domain', {
      version: opensearch.EngineVersion.openSearch('3.5'),
      capacity: {
        dataNodeInstanceType: props.instanceType,
        dataNodes: props.instanceCount,
      },
      // OI2 uses local NVMe; EBS conflicts with it. The L2 defaults ebs.enabled
      // to true, so disable it explicitly rather than omitting the prop.
      ebs: nvmeOnly
        ? { enabled: false }
        : {
            volumeSize: props.volumeSize,
            volumeType: cdk.aws_ec2.EbsDeviceVolumeType.GP3,
          },
      nodeToNodeEncryption: true,
      encryptionAtRest: { enabled: true },
      enforceHttps: true,
      fineGrainedAccessControl: {
        masterUserName: 'admin',
        masterUserPassword: this.masterPasswordSecret.secretValueFromJson('password'),
      },
      accessPolicies: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          principals: [new iam.AnyPrincipal()],
          actions: ['es:*'],
          resources: [`arn:aws:es:${stack.region}:${stack.account}:domain/*/*`],
        }),
      ],
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // EngineMode/UseCase have no L2 props yet; set them on the underlying CfnDomain.
    if (optimized) {
      const cfnDomain = this.domain.node.defaultChild as opensearch.CfnDomain;
      cfnDomain.addPropertyOverride('EngineMode', 'OPTIMIZED');
      cfnDomain.addPropertyOverride('UseCase', 'OBSERVABILITY');
    }

    // IAM role for OSIS pipeline
    this.pipelineRole = new iam.Role(this, 'PipelineRole', {
      assumedBy: new iam.ServicePrincipal('osis-pipelines.amazonaws.com'),
    });
    this.domain.grantReadWrite(this.pipelineRole);
    this.pipelineRole.addToPolicy(new iam.PolicyStatement({
      actions: ['es:DescribeDomain'],
      resources: [this.domain.domainArn],
    }));
    this.pipelineRole.addToPolicy(new iam.PolicyStatement({
      actions: ['aps:RemoteWrite'],
      resources: ['*'], // Will be scoped when AMP workspace is known
    }));
  }
}
