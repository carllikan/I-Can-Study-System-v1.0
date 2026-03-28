resource "google_sql_database_instance" "instance" {
  name          = var.database_instance_name
  region        = var.region
  root_password = var.password #random_password.my_db_password.result
  database_version = "MYSQL_8_0"
  settings {
    tier = "db-custom-4-16384"
    disk_size = 100
    ip_configuration {
      ipv4_enabled = true
    }
    backup_configuration {
      enabled = true
      backup_retention_settings {
        retention_unit = "COUNT"
        retained_backups = 7
      }
    }
  }
  deletion_protection  = false
}

resource "google_sql_database" "database" {
  name     = var.database_name
  instance = google_sql_database_instance.instance.name
}

resource "google_sql_user" "user" {
  instance = google_sql_database_instance.instance.name
  name     = "root"
  password = var.password
}