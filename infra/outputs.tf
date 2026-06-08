output "warehouse" {
  value = snowflake_warehouse.wh.name
}

output "database" {
  value = snowflake_database.db.name
}

output "raw_schema" {
  value = snowflake_schema.raw.name
}

output "analytics_schema" {
  value = snowflake_schema.analytics.name
}

output "role" {
  value = snowflake_account_role.role.name
}

output "resource_monitor" {
  value = snowflake_resource_monitor.monitor.name
}
