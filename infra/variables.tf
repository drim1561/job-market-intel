variable "warehouse_name" {
  type    = string
  default = "JOB_MARKET_WH"
}

variable "database_name" {
  type    = string
  default = "JOB_MARKET"
}

variable "role_name" {
  type    = string
  default = "JOB_MARKET_ROLE"
}

variable "resource_monitor_name" {
  type    = string
  default = "JOB_MARKET_MONITOR"
}

variable "monthly_credit_quota" {
  description = "Hard monthly credit cap. Warehouse is suspended when exceeded."
  type        = number
  default     = 5
}

variable "grant_to_user" {
  description = "Snowflake user that should receive JOB_MARKET_ROLE (your login user)."
  type        = string
}
