terraform {
  backend "gcs" {
    key = "terraform.tfState"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
#   zone    = var.zone
}

provider "google-beta" {
  project     = var.project_id
  region      = var.region
}

data "google_project" "project" {
}

##################### Deploy Cloud Run Services #####################
##################### Global Search API #####################
module "cr_global_search_api" {
  source                          = "./google_cloud_run"
  service_name                    = var.cr_global_search_api
  deploy_cloud_run                = var.deployment_global_search_api
  region                          = var.region
  image_path                      = var.global_search_api_image_path
  project_id                      = var.project_id
  max_instance                    = var.global_search_api_max_instance
  min_instance                    = var.global_search_api_min_instance
  sql_connection_name             = var.global_search_api_sql_connection_name
  timeout_seconds                 = var.global_search_api_timeout_seconds 
  allocated_cpu                   = var.global_search_api_allocated_cpu
  allocated_memory                = var.global_search_api_allocated_memory
  ingress                         = var.global_search_api_ingress
}
output "global_search_api_url" {
  value = module.cr_global_search_api.cloud_run_url
}

###################################################################
##################### Final Feedback ##############
module "cr_final_feedback" {
  source                          = "./google_cloud_run"
  deploy_cloud_run                = var.deployment_final_feedback
  service_name                    = var.cr_final_feedback
  region                          = var.region
  image_path                      = var.final_feedback_image_path
  project_id                      = var.project_id
  max_instance                    = var.final_feedback_max_instance
  min_instance                    = var.final_feedback_min_instance
  sql_connection_name             = var.final_feedback_sql_connection_name
  timeout_seconds                 = var.final_feedback_timeout_seconds 
  allocated_cpu                   = var.final_feedback_allocated_cpu
  allocated_memory                = var.final_feedback_allocated_memory
  ingress                         = var.default_ingress 
  #depends_on                      = [ module.ics_ai_jobs_cloud_sql]

}

output "final_feedback_url" {
  value = module.cr_final_feedback.cloud_run_url
}
