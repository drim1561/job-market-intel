# Infra (Terraform → Snowflake)

Provisions the warehouse, database, schemas, working role, and a credit-cap resource
monitor. Run once; re-run after edits.

## Prerequisites
- A Snowflake account (the free 30-day trial works; the default user is ACCOUNTADMIN).
- Terraform >= 1.6.

## Setup
1. Set auth as environment variables (do not hardcode):
   ```powershell
   $env:SNOWFLAKE_ACCOUNT  = "<account_identifier>"   # e.g. ABCDEFG-XY12345
   $env:SNOWFLAKE_USER     = "<your_user>"
   $env:SNOWFLAKE_PASSWORD = "<your_password>"
   ```
   If `terraform plan` complains about the account format, your provider build wants
   `SNOWFLAKE_ORGANIZATION_NAME` + `SNOWFLAKE_ACCOUNT_NAME` instead of `SNOWFLAKE_ACCOUNT`
   (find both under Snowsight → Admin → Accounts).
2. `copy terraform.tfvars.example terraform.tfvars` and set `grant_to_user` to your user.
3. Provider account identity (v1 provider): set `SNOWFLAKE_ORGANIZATION_NAME` and
   `SNOWFLAKE_ACCOUNT_NAME` (the two halves of `ORG-ACCOUNT`). The provider ignores
   `SNOWFLAKE_ACCOUNT`.
4. **First-run bootstrap:** clear the "use this object" env vars so the provider doesn't
   try to attach to the warehouse/db it's about to create:
   ```powershell
   Remove-Item Env:\SNOWFLAKE_WAREHOUSE, Env:\SNOWFLAKE_DATABASE, Env:\SNOWFLAKE_SCHEMA -ErrorAction SilentlyContinue
   ```
   (Only needed before the objects exist; harmless after.)
5. Run:
   ```powershell
   terraform init
   terraform plan
   terraform apply
   ```

## Teardown (to stop all credit use)
```powershell
terraform destroy
```
`apply` again to recreate. The resource monitor (`monthly_credit_quota`, default 5)
caps spend even while running.
