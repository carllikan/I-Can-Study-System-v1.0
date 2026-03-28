resource "google_cloud_run_service" "api_service" {
  count    = var.deploy_cloud_run ? 1 : 0
  name     = var.service_name
  location = var.region
  template {
  
    metadata {
      annotations = {
        # "autoscaling.knative.dev/minScale" = var.instances.min
        "autoscaling.knative.dev/maxScale" = var.max_instance
        "run.googleapis.com/cloudsql-instances" = var.sql_connection_name
      }
    }

    
    spec {
      container_concurrency = 80
      timeout_seconds = var.timeout_seconds
      containers {
        image = var.image_path
        

      resources {
          limits = {
            cpu    = var.allocated_cpu
            memory = var.allocated_memory
            }
          }
        }
      }
      
    }


  traffic {
    percent         = 100
    latest_revision = true
  }

  metadata {
    annotations = {
      "run.googleapis.com/ingress" = var.ingress
    }
  }
}
data "google_iam_policy" "noauth" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allAuthenticatedUsers",
    ]
  }
}
resource "google_cloud_run_service_iam_policy" "noauth" {
  count       = var.deploy_cloud_run ? 1 : 0
  location    = var.region
  project     = var.project_id
  service     = google_cloud_run_service.api_service[0].name
  policy_data = data.google_iam_policy.noauth.policy_data
}

output "cloud_run_url" {
  value = var.deploy_cloud_run ? google_cloud_run_service.api_service[0].status[0].url : null
}