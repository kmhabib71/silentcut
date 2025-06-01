# GitHub Actions Quick Commands Reference

## 🚀 Initial Setup Commands

```bash
# Initialize repository and push workflows
git add .github/
git commit -m "Add GitHub Actions workflows for automated builds"
git push origin main

# Create and push first release tag
git tag v1.0.0
git push origin v1.0.0
```

## 🏷️ Version Management

```bash
# Create semantic version tags
git tag v1.0.0        # Major release
git tag v1.1.0        # Minor release
git tag v1.0.1        # Patch release

# Pre-release versions
git tag v1.0.0-beta   # Beta release
git tag v1.0.0-rc1    # Release candidate

# Push tags to trigger workflows
git push origin v1.0.0
git push origin --tags  # Push all tags
```

## 📝 Quick Workflow Triggers

### Manual Triggers (via GitHub UI)

1. Go to repository → Actions tab
2. Select workflow → "Run workflow"
3. Choose branch/parameters → "Run workflow"

### Command Line Triggers

```bash
# Trigger simple build (push to main)
git push origin main

# Trigger release build (create tag)
git tag v1.0.0 && git push origin v1.0.0

# Trigger secure release (semantic version tag)
git tag v1.0.0 && git push origin v1.0.0
```

## 🔍 Monitoring Commands

```bash
# Check workflow status
gh run list  # GitHub CLI

# View specific workflow
gh run view <run-id>

# Download artifacts
gh run download <run-id>
```

## 🛠️ Troubleshooting Commands

```bash
# Check workflow files syntax
yamllint .github/workflows/*.yml

# Validate GitHub Actions locally (using act)
act -l  # List workflows
act     # Run workflows locally

# Force re-run failed workflow
gh run rerun <run-id>
```

## 📊 Release Management

```bash
# Create GitHub release manually
gh release create v1.0.0 dist/*.zip --title "Silent Cut Complete v1.0.0" --notes "Release notes here"

# List releases
gh release list

# Delete release (if needed)
gh release delete v1.0.0
```

## 🔧 Quick Workflow Modifications

### Edit workflow file locally

```bash
# Edit main workflow
code .github/workflows/build-and-release.yml

# Test changes
git add .github/workflows/
git commit -m "Update workflow configuration"
git push
```

### Common YAML edits

```yaml
# Change Python version
env:
  PYTHON_VERSION: '3.10'

# Add new OS support
strategy:
  matrix:
    os: [windows-latest, ubuntu-latest, macos-latest]

# Modify app name
env:
  APP_NAME: YourNewAppName
```

## 📦 Artifact Management

```bash
# Download latest build artifacts
gh run download --name "SilentCutComplete_*"

# List available artifacts
gh api repos/:owner/:repo/actions/artifacts

# Clean up old artifacts (via GitHub UI)
# Go to Actions → Artifacts → Delete old ones
```

## 🔐 Security Settings

### Repository Settings Commands

```bash
# Enable Actions (if disabled)
gh api repos/:owner/:repo --method PATCH --field has_actions=true

# Set workflow permissions (use GitHub UI)
# Settings → Actions → General → Workflow permissions
```

### Secrets Management

```bash
# Add repository secrets
gh secret set SECRET_NAME

# List secrets
gh secret list

# Remove secret
gh secret remove SECRET_NAME
```

## 🚨 Emergency Commands

```bash
# Stop all running workflows
gh api repos/:owner/:repo/actions/runs --method GET | jq '.workflow_runs[] | select(.status=="in_progress") | .id' | xargs -I {} gh api repos/:owner/:repo/actions/runs/{}/cancel --method POST

# Disable workflow
gh api repos/:owner/:repo/actions/workflows/:workflow_id/disable --method PUT

# Re-enable workflow
gh api repos/:owner/:repo/actions/workflows/:workflow_id/enable --method PUT
```

## 📋 Pre-flight Checklist

Before releasing:

- [ ] `requirements.txt` is updated
- [ ] All tests pass locally
- [ ] Version number is incremented
- [ ] Release notes are prepared
- [ ] Tag follows semantic versioning

```bash
# Complete release process
git add .
git commit -m "Prepare release v1.0.0"
git push origin main
git tag v1.0.0
git push origin v1.0.0
# Monitor GitHub Actions for build completion
```

## 🎯 One-Line Release

```bash
# Complete release in one command
VERSION="1.0.0" && git tag v$VERSION && git push origin v$VERSION && echo "Release v$VERSION triggered!"
```

---

## 📞 Quick Help

- **GitHub CLI**: `gh --help`
- **Actions syntax**: [GitHub Docs](https://docs.github.com/en/actions)
- **Workflow status**: Repository → Actions tab
- **Logs**: Click on failed workflow run for details
