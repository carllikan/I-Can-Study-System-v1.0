resource "google_firestore_database" "database" {
  count                             = var.deploy_firestore ? 1 : 0
  project                           = var.project_id
  name                              = "(default)"
  location_id                       = var.region
  type                              = "FIRESTORE_NATIVE"
  concurrency_mode                  = "OPTIMISTIC"
  app_engine_integration_mode       = "DISABLED"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"
  delete_protection_state           = "DELETE_PROTECTION_ENABLED"
  deletion_policy                   = "DELETE"
}

resource "google_firestore_backup_schedule" "daily-backup" {
  count     = var.deploy_firestore ? 1 : 0
  project   = var.project_id
  database  = google_firestore_database.database[0].name

  retention = "604800s" // 7 days (maximum possible value for daily backups)
  daily_recurrence {}
}