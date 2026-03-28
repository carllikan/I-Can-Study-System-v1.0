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
/*
##################### Reflection Evaluation API ###################
module "cr_reflection_evaluation_api" {
  source                          = "./google_cloud_run"
  deploy_cloud_run                = var.deployment_reflection_evaluation_api
  service_name                    = var.cr_reflection_evaluation_api
  region                          = var.region
  image_path                      = var.reflection_evaluation_api_image_path
  project_id                      = var.project_id
  max_instance                    = var.reflection_evaluation_api_max_instance
  sql_connection_name             = var.reflection_evaluation_api_sql_connection_name
  timeout_seconds                 = var.reflection_evaluation_api_timeout_seconds 
  allocated_cpu                   = var.reflection_evaluation_api_allocated_cpu
  allocated_memory                = var.reflection_evaluation_api_allocated_memory
  ingress                         = var.default_ingress 
}*/


###################################################################
##################### Reflection Evaluation Pipeline ##############
module "cr_reflection_evaluation_pipeline" {
  source                          = "./google_cloud_run"
  deploy_cloud_run                = var.deployment_reflection_evaluation_pipeline
  service_name                    = var.cr_reflection_evaluation_pipeline
  region                          = var.region
  image_path                      = var.reflection_evaluation_pipeline_image_path
  project_id                      = var.project_id
  max_instance                    = var.reflection_evaluation_pipeline_max_instance
  sql_connection_name             = var.reflection_evaluation_pipeline_sql_connection_name
  timeout_seconds                 = var.reflection_evaluation_pipeline_timeout_seconds 
  allocated_cpu                   = var.reflection_evaluation_pipeline_allocated_cpu
  allocated_memory                = var.reflection_evaluation_pipeline_allocated_memory
  ingress                         = var.default_ingress
  #depends_on                      = [ module.ics_ai_jobs_cloud_sql]
}

output "reflection_evaluation_pipeline_url" {
  value = module.cr_reflection_evaluation_pipeline.cloud_run_url
}
