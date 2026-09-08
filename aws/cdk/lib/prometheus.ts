import * as cdk from 'aws-cdk-lib';
import * as aps from 'aws-cdk-lib/aws-aps';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as path from 'path';
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';
import { Runtime } from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export interface PrometheusConstructProps {
  domainArn: string;
}

export class PrometheusConstruct extends Construct {
  public readonly workspace: aps.CfnWorkspace;
  public readonly dqsRole: iam.Role;
  public readonly dataSourceArn: string;

  constructor(scope: Construct, id: string, props: PrometheusConstructProps) {
    super(scope, id);

    const stack = cdk.Stack.of(this);

    this.workspace = new aps.CfnWorkspace(this, 'Workspace', {
      alias: `observability-stack-${stack.stackName}`,
    });

    this.dqsRole = new iam.Role(this, 'DqsRole', {
      assumedBy: new iam.ServicePrincipal('directquery.opensearchservice.amazonaws.com'),
    });
    // The data source queries metrics AND manages alerting resources (alerting
    // rule groups and alert-manager silences) in the workspace. AMP authorizes
    // rule-groups-namespace CRUD (Put/Delete/DescribeRuleGroupsNamespace) against
    // the rulegroupsnamespace ARN, NOT the workspace ARN, so granting aps:* only
    // on the workspace ARN silently denies rule-group create/update/delete.
    // Alert-manager definitions and silences resolve against the workspace ARN.
    this.dqsRole.addToPolicy(new iam.PolicyStatement({
      actions: ['aps:*'],
      resources: [
        this.workspace.attrArn,
        `arn:${stack.partition}:aps:${stack.region}:${stack.account}:rulegroupsnamespace/${this.workspace.attrWorkspaceId}/*`,
      ],
    }));

    const dqsDataSourceName = `prometheus_${stack.stackName}`.toLowerCase().replace(/[^a-z0-9_]/g, '_');

    const dqsFn = new NodejsFunction(this, 'DqsFn', {
      runtime: Runtime.NODEJS_22_X,
      handler: 'handler',
      entry: path.join(__dirname, '..', 'custom-resources', 'dqs-datasource', 'index.ts'),
      timeout: cdk.Duration.minutes(5),
      bundling: { externalModules: ['@aws-sdk/*'] },
    });
    dqsFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'es:AddDirectQueryDataSource', 'es:DeleteDirectQueryDataSource', 'es:GetDirectQueryDataSource',
        'opensearch:AddDirectQueryDataSource', 'opensearch:DeleteDirectQueryDataSource', 'opensearch:GetDirectQueryDataSource',
      ],
      resources: ['*'],
    }));
    dqsFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['iam:PassRole'],
      resources: [this.dqsRole.roleArn],
    }));

    const dqsProvider = new cr.Provider(this, 'DqsProvider', {
      onEventHandler: dqsFn,
    });

    const dataSource = new cdk.CustomResource(this, 'DqsDataSource', {
      serviceToken: dqsProvider.serviceToken,
      properties: {
        DataSourceName: dqsDataSourceName,
        DataSourceType: {
          Prometheus: {
            RoleArn: this.dqsRole.roleArn,
            WorkspaceArn: this.workspace.attrArn,
          },
        },
        Description: 'Prometheus data source for observability stack',
      },
    });

    this.dataSourceArn = dataSource.getAttString('DataSourceArn');
  }
}
