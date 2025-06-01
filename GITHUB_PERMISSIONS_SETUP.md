# GitHub Repository Permissions Setup

## 🔧 Fix for 403 Release Creation Error

The 403 error when creating GitHub releases is a permissions issue. Follow these steps to fix it:

### 1. Repository Settings

Go to your repository settings:

- Navigate to `Settings` → `Actions` → `General`
- Under "Workflow permissions", select:
  - ✅ **"Read and write permissions"**
  - ✅ **"Allow GitHub Actions to create and approve pull requests"**

### 2. Verify Token Permissions

The workflows now include explicit permissions:

```yaml
permissions:
  contents: write
  packages: write
  actions: read
  security-events: write
```

### 3. Alternative: Personal Access Token (PAT)

If the issue persists, create a Personal Access Token:

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with these scopes:

   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
   - ✅ `write:packages` (Write packages to GitHub Package Registry)

3. Add the token as a repository secret:

   - Go to repository Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PAT`
   - Value: Your generated token

4. Update the workflow to use PAT instead:
   ```yaml
   token: ${{ secrets.PAT }}
   ```

### 4. Workflow Changes Made

The following improvements have been applied:

1. **Added explicit permissions** at workflow and job level
2. **Updated action versions** to latest (v2)
3. **Added debug logging** to troubleshoot token issues
4. **Changed token parameter** from `env` to `with.token`

### 5. Test the Fix

1. Create a new tag:

   ```bash
   git tag v1.0.3
   git push origin v1.0.3
   ```

2. Check the workflow runs in the Actions tab
3. The release should now create successfully

### 6. Verification

After the fix, you should see:

- ✅ Release created without 403 errors
- ✅ Files properly uploaded to release
- ✅ Release notes generated correctly

## 🚨 If Issues Persist

If you still get 403 errors:

1. Check repository ownership permissions
2. Verify you have admin access to the repository
3. Try using a PAT with broader permissions
4. Contact GitHub Support if the repository has special restrictions

---

This setup ensures reliable, automated releases with proper permissions handling.
