resource "google_artifact_registry_repository" "ar_repository" {
  location      = var.region
  repository_id = var.repository_id
  description   = "Cloud Run image respository"
  format        = "DOCKER"

#   cleanup_policy_dry_run = false
#   cleanup_policies {
#     id     = "keep-7-latest-images"
#     most_recent_versions {
#       keep_count = 7
#     }
#   }
}