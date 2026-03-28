resource "google_secret_manager_secret" "secret_data" {
  secret_id = var.secret_name
  replication {
    auto {
    }
  }
}
resource "google_secret_manager_secret_version" "secret_data" {
  secret      = google_secret_manager_secret.secret_data.id
  secret_data = var.secret_data
}
