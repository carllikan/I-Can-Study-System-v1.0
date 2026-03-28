data "google_project" "project" {
}

resource "google_cloud_tasks_queue" "task_queue" {
  name     = var.task_queue_name
  location = var.location

  retry_config {
    max_attempts       = 100
    max_retry_duration = "600s"
    max_backoff        = "600s"
    min_backoff        = "10s"
    max_doublings      = 10
  }
}