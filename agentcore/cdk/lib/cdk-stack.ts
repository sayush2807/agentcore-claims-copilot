import { AgentCoreApplication, type AgentCoreApplicationProps } from '@aws/agentcore-cdk';
import { Stack, type StackProps, aws_bedrockagentcore as agentcore } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as fs from 'fs';
import * as path from 'path';

export interface AgentCoreStackProps extends StackProps {
  /** Props for the AgentCore application, produced by transformAgentCoreJson from agentcore/agentcore.json. */
  application: AgentCoreApplicationProps;
}

const GATEWAY_NAME = 'LegacySystems';
const POLICY_ENGINE_NAME = 'ClaimsGuardrails';

/** Locate the repository's policies/ folder from wherever this file is compiled to. */
function findPoliciesDir(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i++) {
    const candidate = path.join(dir, 'policies');
    if (fs.existsSync(path.join(candidate, 'README.md'))) return candidate;
    dir = path.dirname(dir);
  }
  throw new Error('Could not find the policies/ folder above ' + __dirname);
}

/**
 * The stack the AgentCore CLI deploys. Everything declared in agentcore/agentcore.json is
 * created by the AgentCoreApplication construct. Resources added here are wired to it
 * through the application's accessors.
 */
export class AgentCoreStack extends Stack {
  public readonly application: AgentCoreApplication;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);
    this.application = new AgentCoreApplication(this, 'Application', props.application);

    // Cedar policies live as reviewable files in policies/. They are created here rather
    // than in agentcore.json because each statement must name the Gateway's ARN, which is
    // only known at deploy time and should not be committed to a public repository.
    const gateway = this.application.gateway(GATEWAY_NAME);
    const engine = this.application.policyEngine(POLICY_ENGINE_NAME);
    const policiesDir = findPoliciesDir();

    for (const file of fs.readdirSync(policiesDir).filter(f => f.endsWith('.cedar')).sort()) {
      const name = path.basename(file, '.cedar');
      const statement = fs
        .readFileSync(path.join(policiesDir, file), 'utf8')
        .split('\n')
        .filter(line => !line.trim().startsWith('//'))
        .join('\n')
        .trim()
        .replace(/\{\{GATEWAY_ARN\}\}/g, gateway.gatewayArn);

      const policy = new agentcore.CfnPolicy(this, `Policy_${name}`, {
        name,
        policyEngineId: engine.policyEngineId,
        definition: { policy: { statement } },
        validationMode: 'FAIL_ON_ANY_FINDINGS',
        enforcementMode: 'ACTIVE',
      });
      // Validation checks the statement against the Gateway's tools, so they must exist first.
      policy.node.addDependency(gateway);
    }
  }
}
