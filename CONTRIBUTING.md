# Contributing to Observability Stack

Thank you for your interest in contributing to Observability Stack! This document provides guidelines for both human developers and AI coding assistants to contribute effectively to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Testing Requirements](#testing-requirements)
- [Code Style Guidelines](#code-style-guidelines)
- [Pull Request Process](#pull-request-process)
- [AI Agent Contributions](#ai-agent-contributions)
- [Documentation Guidelines](#documentation-guidelines)
- [Community](#community)

## Code of Conduct

This project follows the OpenSearch Project Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git
- Python 3.8+ (for testing and examples)
- kubectl and Helm 3.8+ (for Kubernetes contributions)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
```bash
git clone https://github.com/YOUR_USERNAME/observability-stack.git
cd observability-stack
```

3. Add the upstream repository:
```bash
git remote add upstream https://github.com/opensearch-project/observability-stack.git
```

4. Create a branch for your changes:
```bash
git checkout -b feature/your-feature-name
```

## Development Workflow

### 1. Make Your Changes

- Edit configuration files, documentation, or examples
- Follow the repository's naming conventions (kebab-case)
- Add inline comments to explain configuration settings
- Keep changes focused and atomic

### 2. Test Locally

#### Docker Compose Testing

```bash
# Start the stack
cd docker-compose
docker compose up -d

# Verify all services are running
docker-compose ps

# Check logs for errors
docker-compose logs

# Send test data
python ../examples/python/sample_agent.py

# Verify data in OpenSearch
curl http://localhost:9200/_cat/indices?v

# Stop the stack
docker-compose down
```

#### Helm Chart Testing

```bash
# Validate chart syntax
helm lint helm/observability-stack

# Render templates to check for errors
helm template observability-stack helm/observability-stack

# Deploy to a test cluster (kind, minikube, etc.)
helm install observability-stack-test helm/observability-stack

# Verify deployment
kubectl get pods
kubectl logs <pod-name>

# Clean up
helm uninstall observability-stack-test
```

### 3. Run Validation Tests

```bash
# Run configuration validation tests
pytest tests/

# Run YAML linters
yamllint docker-compose/
yamllint helm/

# Run markdown linters
markdownlint *.md docs/*.md
```

### 4. Update Documentation

- Update README.md if you've changed functionality or configuration
- Update AGENTS.md if you've changed repository structure
- Add or update examples if you've added new features
- Include inline comments in configuration files

### 5. Commit Your Changes

Use clear, descriptive commit messages following this format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `config`: Configuration changes
- `test`: Test additions or modifications
- `refactor`: Code refactoring
- `chore`: Maintenance tasks

**Examples**:
```bash
git commit -m "feat(otel-collector): add support for additional OTLP endpoints"
git commit -m "docs(readme): update quick start instructions"
git commit -m "config(prometheus): increase retention to 30 days"
git commit -m "fix(docker-compose): correct service dependency order"
```

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear title describing the change
- Detailed description of what changed and why
- Reference to any related issues
- Screenshots or logs if applicable

## Testing Requirements

### Configuration Validation

All configuration changes must pass validation tests:

```bash
pytest tests/test_docker_compose_config.py
pytest tests/test_otel_collector_config.py
pytest tests/test_data_prepper_config.py
pytest tests/test_helm_charts.py
```

### Integration Testing

For significant changes, run integration tests:

```bash
# Docker Compose integration test
./scripts/integration-test-docker.sh

# Helm integration test (requires Kubernetes cluster)
./scripts/integration-test-helm.sh
```

### Example Code Testing

If you add or modify examples:

```bash
# Test Python examples
cd examples/python
python -m pytest

# Test JavaScript examples
cd examples/javascript
npm test
```

## Code Style Guidelines

### YAML Configuration Files

- **Indentation**: Use 2 spaces (no tabs)
- **Comments**: Include inline comments explaining key settings
- **Ordering**: Group related settings together
- **Quotes**: Use quotes for strings containing special characters
- **Line Length**: Keep lines under 100 characters when possible

**Example**:
```yaml
# OpenTelemetry Collector configuration
receivers:
  # OTLP receiver accepts telemetry data via OpenTelemetry Protocol
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317  # Standard OTLP gRPC port
      http:
        endpoint: 0.0.0.0:4318  # Standard OTLP HTTP port
```

### Docker Compose Files

- Use specific image versions (not `latest`)
- Declare service dependencies explicitly
- Use named volumes for persistence
- Include health checks where applicable
- Document exposed ports

**Example**:
```yaml
opensearch:
  image: opensearchproject/opensearch:2.11.0
  container_name: opensearch
  environment:
    - discovery.type=single-node
    - OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m
  ports:
    - "9200:9200"
  volumes:
    - opensearch-data:/usr/share/opensearch/data
  networks:
    - observability-stack-network
```

### Helm Charts

- Follow Helm best practices
- Use `values.yaml` for all configurable parameters
- Include helpful comments in templates
- Provide sensible defaults
- Document all values in comments

### Python Code

- Follow PEP 8 style guide
- Use type hints where appropriate
- Include docstrings for functions and classes
- Keep functions focused and small

### JavaScript/TypeScript Code

- Follow Airbnb JavaScript Style Guide
- Use ES6+ features
- Include JSDoc comments
- Use TypeScript for type safety when possible

### Documentation

- Use Markdown for all documentation
- Include code examples with syntax highlighting
- Provide both quick start and detailed explanations
- Keep language clear and concise
- Use proper heading hierarchy

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass locally
- [ ] Documentation is updated
- [ ] Commit messages are clear and descriptive
- [ ] Changes are focused and atomic
- [ ] No merge conflicts with main branch

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Configuration change
- [ ] Documentation update
- [ ] Test addition/modification

## Related Issues
Fixes #123
Related to #456

## Testing
Describe how you tested these changes:
- [ ] Local docker-compose deployment
- [ ] Helm chart deployment
- [ ] Configuration validation tests
- [ ] Integration tests

## Screenshots/Logs
If applicable, add screenshots or log outputs.

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing tests pass locally
```

### Review Process

1. Maintainers will review your PR within 3-5 business days
2. Address any feedback or requested changes
3. Once approved, a maintainer will merge your PR
4. Your contribution will be included in the next release

### After Merge

- Delete your feature branch
- Pull the latest changes from upstream:
```bash
git checkout main
git pull upstream main
```

## AI Agent Contributions

AI coding assistants are welcome to contribute! When contributing as an AI agent:

### Best Practices

1. **Read AGENTS.md First**: Understand repository structure and conventions
2. **Follow Patterns**: Use existing code as templates for new contributions
3. **Include Context**: Provide clear commit messages and PR descriptions
4. **Test Thoroughly**: Run all validation tests before submitting
5. **Document Changes**: Update relevant documentation files
6. **Ask Questions**: If uncertain, ask for clarification in the PR

### Common AI Contribution Areas

- Adding new language examples
- Improving documentation clarity
- Adding inline comments to configurations
- Creating new dashboard templates
- Writing validation tests
- Fixing typos and formatting issues

### AI-Specific Guidelines

- Always validate generated YAML syntax
- Test generated code examples before submitting
- Ensure generated documentation is accurate
- Follow existing patterns rather than inventing new ones
- Include references to source documentation when applicable

## Documentation Guidelines

### README.md

- Keep quick start section concise
- Include architecture diagrams
- Provide troubleshooting guidance
- Maintain production readiness warnings
- Update when adding new features

### AGENTS.md

- Explain repository structure clearly
- Document naming conventions
- Provide common task examples
- Include configuration patterns
- Keep AI-assistant focused

### llms.txt

`docs/public/llms.txt` is a first-class doc artifact, on the same footing as README.md and AGENTS.md. It lists every page in the docs site with a one-line description, served at the site root for AI assistants and other automated readers.

Update it whenever you change something it reflects: adding, removing, or renaming a docs page, or changing a page's `title` or `description` frontmatter.

- Do not hand-edit `docs/public/llms.txt`. It is generated; regenerate it instead using the config in `docs/starlight-docs/llms-txt/`.
- After regenerating, check that every link is a fully qualified `https://observability.opensearch.org/...` URL, not a relative `/docs/...` path, and that the title and tagline lines at the top are unchanged.

### Code Comments

- Explain *why*, not just *what*
- Document security implications
- Note performance considerations
- Reference relevant specifications
- Keep comments up to date
- Avoid narrative prose and internal team voice (e.g., "we deliberately...") — comments are for future maintainers, not decision history

### Examples

- Include complete, runnable code
- Add README.md in example directories
- Show both basic and advanced usage
- Follow language-specific conventions
- Test examples before committing

### Writing Tenets (for agents)

Applies to all user-facing documentation: READMEs, public docs under `docs/`, migration guides, and PR descriptions.

**Framing**

- No us-vs-them. Write "Point your agents at observability-stack," not "at us." In open-source projects, the reader is part of the same community.
- Don't leak internal conversation into docs. Design-doc voice ("this is the canonical case where...", "we deliberately omitted...") belongs in PR discussion or design documents, not user-facing artifacts.
- Factual, not promotional. Avoid marketing phrases like "does ONE thing," "zero drift risk," or "honest limits."
- Acknowledge nuance via asides (`:::note` in Starlight docs) or italic notes, not prose digressions.

**Maintenance hygiene**

- Don't pin version strings. Link to `main` of upstream repos (e.g., `opentelemetry-collector-contrib/tree/main/receiver/...`), not to a specific tag. Version pins go stale.
- Don't duplicate source code in docs. Config YAML, pipeline definitions, and translation tables drift from the real source. Link to the source file instead.
- Don't maintain per-vendor translation tables beyond 3–5 canonical well-known fields. Defer to upstream receiver READMEs and vendor documentation. Positioning this repo as a schema authority creates permanent maintenance burden.
- Repo READMEs should link to public docs, not duplicate them. One source of truth per content type.

**Accuracy**

- Verify specific claims before writing them. Dates, version numbers, protocol behavior, UI terminology — check primary sources.
- If a claim cannot be verified from primary sources, phrase it more vaguely. "Modern versions support X" beats "as of v1.42, X is supported" when the version claim is unverified.
- Check existing conventions. Before using a UI name or terminology, grep the rest of the docs to see what other pages call it.
- Run the documentation build (`npm run build` in `docs/starlight-docs`) before committing doc changes. Verify internal links are valid.

**Public-doc page structure**

Pages for users migrating TO observability-stack should cover, in order:

1. Action-oriented lead (one sentence — what the reader can do)
2. Decision table when multiple paths exist ("Do I need this?" / "Which path applies?")
3. Configuration — concrete environment variables, example config, code snippet per path
4. Verify step — one-command check that it's working
5. What lands in OpenSearch — concrete example of end state (field names, index patterns)
6. Caveats — real observed gotchas surfaced from validation, not theoretical ones
7. Not covered — honest scope boundaries
8. References — upstream sources, vendor docs

**Repo READMEs** are for contributors, not migrators. Keep them short (20–40 lines for leaf READMEs; 100 max for overview). Link out to public docs for user-facing content. Include repo-local context only: config file paths, upstream receiver links, local dev workflow commands.

**Caveats from real validation are more trustworthy than theoretical ones.** When end-to-end testing reveals a gotcha (e.g., an attribute gets overwritten, a field doesn't translate), document it in the caveats section. Lead with what the user will see, not why it happens.

**Scope discipline**

- Prune aggressively when in doubt. Deletion is cheaper than maintenance.
- Don't commit working files — audit tables, compatibility matrices, session notes, TODO lists, WIP drafts. If it's not useful to a future reader with no context, it's not a docs artifact.

## Community

### Getting Help

- **GitHub Issues**: Report bugs or request features
- **GitHub Discussions**: Ask questions and share ideas
- **Slack**: Join the OpenSearch community Slack (if available)

### Reporting Bugs

When reporting bugs, include:

1. Description of the issue
2. Steps to reproduce
3. Expected behavior
4. Actual behavior
5. Environment details (OS, Docker version, etc.)
6. Relevant logs or error messages

### Requesting Features

When requesting features, include:

1. Clear description of the feature
2. Use case and motivation
3. Proposed implementation (if any)
4. Alternatives considered

### Security Issues

**Do not report security vulnerabilities in public issues.**

Email security@opensearch.org with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Recognition

Contributors will be recognized in:
- Release notes
- CONTRIBUTORS.md file
- GitHub contributor graph

Thank you for contributing to Observability Stack! Your efforts help make agent observability accessible to everyone.

## Questions?

If you have questions about contributing, please:
1. Check existing documentation
2. Search GitHub Issues and Discussions
3. Ask in GitHub Discussions
4. Reach out to maintainers

---

**Remember**: Quality over quantity. Well-tested, documented contributions are more valuable than numerous quick fixes.
