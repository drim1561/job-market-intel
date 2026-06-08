terraform {
  required_version = ">= 1.6"
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake" # formerly Snowflake-Labs/snowflake
      version = "~> 1.0"
    }
  }
}

# Auth comes from environment variables (do NOT hardcode credentials):
#   SNOWFLAKE_ACCOUNT   (account locator/identifier; some provider builds prefer
#                        SNOWFLAKE_ORGANIZATION_NAME + SNOWFLAKE_ACCOUNT_NAME)
#   SNOWFLAKE_USER
#   SNOWFLAKE_PASSWORD
# Creating warehouses, account roles, and resource monitors requires ACCOUNTADMIN,
# which the default trial user has.
provider "snowflake" {
  role = "ACCOUNTADMIN"
}
