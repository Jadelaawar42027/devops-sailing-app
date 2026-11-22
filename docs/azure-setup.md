# Azure and GitHub setup (one time)

Everything in Azure is declared in [`infra/main.bicep`](../infra/main.bicep) and applied by the CD
pipeline on every merge to `main`. The steps below are the only manual ones. Replace `<N>` with the
group number, `<owner>/<repo>` with the GitHub repository. Nothing here creates a resource group.

## 1. Identity for GitHub Actions (OIDC, no secret)

The pipeline logs in to Azure with OpenID Connect. Brief §4 says it uses the group's own identity sent
by the professor; we expect a user-assigned managed identity `sdd-3a-g<N>-github` (or a service
principal) with **Contributor on `rg-sdd-3a-g<N>` only**. No client secret or credentials JSON is
ever stored: GitHub gets a short-lived token for each run.

```bash
az login
az account show --query "{subscriptionId:id, tenantId:tenantId}" -o table

# Managed identity: read its client id
az identity show -g rg-sdd-3a-g<N> -n sdd-3a-g<N>-github --query "{clientId:clientId, principalId:principalId}" -o table

# Trust GitHub Actions runs on main of our repo (one federated credential)
az identity federated-credential create \
  --name github-main \
  --identity-name sdd-3a-g<N>-github \
  --resource-group rg-sdd-3a-g<N> \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:<owner>/<repo>:ref:refs/heads/main \
  --audiences api://AzureADTokenExchange
```

If the professor sent an **app registration / service principal** instead of a managed identity,
the federated credential goes on the app (needs owner rights on the app; ask the professor if denied):

```bash
az ad app federated-credential create --id <application-client-id> --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<owner>/<repo>:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

Only if the identity has no role yet (needs Owner or User Access Administrator, so probably the
professor runs it):

```bash
az role assignment create --assignee <principalId> --role Contributor \
  --scope /subscriptions/<subscriptionId>/resourceGroups/rg-sdd-3a-g<N>
```

## 2. GitHub variables and secrets

Repository → Settings → Secrets and variables → Actions. With the GitHub CLI:

```bash
gh variable set GROUP_PREFIX          --body "sdd-3a-g<N>"
gh variable set AZURE_RESOURCE_GROUP  --body "rg-sdd-3a-g<N>"
gh variable set AZURE_CLIENT_ID       --body "<clientId from step 1>"
gh variable set AZURE_TENANT_ID       --body "<tenantId>"
gh variable set AZURE_SUBSCRIPTION_ID --body "<subscriptionId>"

# SQL admin password: generated locally, typed into the prompt, never written to a file.
openssl rand -base64 24   # copy the output, add e.g. "Aa1!" for the complexity rules
gh secret set SQL_ADMIN_PASSWORD      # paste when prompted
```

Container images: either make the two GHCR packages **public** after the first push
(GitHub → your profile/org → Packages → `api` and `forecast` → Package settings → Change visibility),
or create a classic token with only `read:packages` and store it as a secret:

```bash
gh secret set GHCR_PULL_TOKEN         # optional; only for private packages
```

## 3. Branch protection (brief §2)

```bash
gh api -X PUT repos/<owner>/<repo>/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": [
    "api - lint, format, tests", "forecast - lint, format, tests",
    "ui - format check and syntax", "api - image build", "forecast - image build"] },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 1 },
  "restrictions": null
}
JSON
```

## 4. Optional: preview before the first deploy (read-only)

```bash
az deployment group what-if -g rg-sdd-3a-g<N> -f infra/main.bicep \
  -p prefix=sdd-3a-g<N> \
     apiImage=mcr.microsoft.com/k8se/quickstart:latest \
     forecastImage=mcr.microsoft.com/k8se/quickstart:latest \
     sqlAdminPassword='<the same password>'
```

## 5. First deploy

Merge to `main` (or run the CD workflow by hand: Actions → CD → Run workflow). The run creates all
resources the first time (about 10 minutes, mostly SQL), then only updates them. The run summary
prints the three URLs; copy them into the README.

## What gets created

| Resource | Name |
| --- | --- |
| Log Analytics workspace (+ saved dashboard/SLO queries) | `sdd-3a-g<N>-logs` |
| Container Apps environment (Consumption) | `sdd-3a-g<N>-env` |
| Container App, API (min 0, max 1 replica) | `sdd-3a-g<N>-api` |
| Container App, forecast (min 0, max 1 replica) | `sdd-3a-g<N>-forecast` |
| Azure SQL logical server | `sdd-3a-g<N>-sql` |
| Serverless database, API (auto-pause 60 min) | `sdd-3a-g<N>-api-db` |
| Serverless database, forecast (auto-pause 60 min) | `sdd-3a-g<N>-forecast-db` |
| Static Web App (Free) | `sdd-3a-g<N>-ui` |

CI never touches the Azure databases; tests use SQLite and local runs use SQL Server in compose.
