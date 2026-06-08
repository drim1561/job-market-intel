# Resource monitor: the hard credit cap. Suspends the warehouse if the monthly quota
# is exceeded, so a runaway job or public traffic can never blow the budget.
resource "snowflake_resource_monitor" "monitor" {
  name            = var.resource_monitor_name
  credit_quota    = var.monthly_credit_quota
  frequency       = "MONTHLY"
  start_timestamp = "IMMEDIATELY"

  notify_triggers           = [50, 80]  # email at 50% and 80% of quota
  suspend_trigger           = 90        # suspend (let running queries finish) at 90%
  suspend_immediate_trigger = 100       # kill running queries at 100%
}

# XS warehouse, aggressive auto-suspend, starts suspended. Cheapest viable compute;
# only wakes for the dlt load + dbt build, then sleeps after 60s idle.
resource "snowflake_warehouse" "wh" {
  name                = var.warehouse_name
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
  resource_monitor    = snowflake_resource_monitor.monitor.name
}

resource "snowflake_database" "db" {
  name = var.database_name
}

# RAW = dlt landing (VARIANT payloads); ANALYTICS = dbt-built models.
resource "snowflake_schema" "raw" {
  database = snowflake_database.db.name
  name     = "RAW"
}

resource "snowflake_schema" "analytics" {
  database = snowflake_database.db.name
  name     = "ANALYTICS"
}

# Working role for dlt + dbt (least privilege: this DB + this warehouse only).
resource "snowflake_account_role" "role" {
  name = var.role_name
}

resource "snowflake_grant_privileges_to_account_role" "wh_usage" {
  account_role_name = snowflake_account_role.role.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.wh.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "db_usage" {
  account_role_name = snowflake_account_role.role.name
  privileges        = ["USAGE", "CREATE SCHEMA"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.db.name
  }
}

# Full control on the two schemas + their current and future objects, so dlt can
# create RAW tables and dbt can build/replace models freely.
resource "snowflake_grant_privileges_to_account_role" "schema_all" {
  for_each          = toset([snowflake_schema.raw.name, snowflake_schema.analytics.name])
  account_role_name = snowflake_account_role.role.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW", "CREATE STAGE", "CREATE FILE FORMAT"]
  on_schema {
    schema_name = "\"${snowflake_database.db.name}\".\"${each.value}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "future_tables" {
  for_each          = toset([snowflake_schema.raw.name, snowflake_schema.analytics.name])
  account_role_name = snowflake_account_role.role.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.db.name}\".\"${each.value}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "future_views" {
  for_each          = toset([snowflake_schema.raw.name, snowflake_schema.analytics.name])
  account_role_name = snowflake_account_role.role.name
  privileges        = ["SELECT", "REFERENCES"]
  on_schema_object {
    future {
      object_type_plural = "VIEWS"
      in_schema          = "\"${snowflake_database.db.name}\".\"${each.value}\""
    }
  }
}

# Let your login user assume the working role.
resource "snowflake_grant_account_role" "to_user" {
  role_name = snowflake_account_role.role.name
  user_name = var.grant_to_user
}
