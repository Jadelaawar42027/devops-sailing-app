# Infrastructure as code

`main.bicep` declares every Azure resource of the group (see the table in
[docs/azure-setup.md](../docs/azure-setup.md)). The CD pipeline applies it on every merge to `main`
with the new image tags, so the deployed state always matches the repository.

Check locally (no Azure access needed): `az bicep build --file infra/main.bicep`.
