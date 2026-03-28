resource "google_storage_bucket" "bucket" {
  name     = var.bucket_name
  location = var.region
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
        type            = "SetStorageClass"
        storage_class   = "STANDARD"
    }
    condition {
        num_newer_versions = 7
    }
  }
}

output "return_bucket_name" {
value = google_storage_bucket.bucket.name
}