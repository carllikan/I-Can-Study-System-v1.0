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

###################################################################
##################### Mind_Map_Evaluation_API #####################
module "cr_mind_map_evaluation_api" {
  source                          = "./google_cloud_run"
  deploy_cloud_run                = var.deployment_mind_map_evaluation_api
  service_name                    = var.cr_mind_map_evaluation_api
  region                          = var.region
  image_path                      = var.mind_map_evaluation_api_image_path
  project_id                      = var.project_id
  max_instance                    = var.mind_map_evaluation_api_max_instance
  sql_connection_name             = var.mind_map_evaluation_api_sql_connection_name
  timeout_seconds                 = var.mind_map_evaluation_api_timeout_seconds 
  allocated_cpu                   = var.mind_map_evaluation_api_allocated_cpu
  allocated_memory                = var.mind_map_evaluation_api_allocated_memory
  ingress                         = var.default_ingress 
}

###################################################################
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
}


###################################################################
##################### Evaluation API ##############################
module "cr_evaluation_api" {
  source                          = "./google_cloud_run"
  deploy_cloud_run                = var.deployment_evaluation_api
  service_name                    = var.cr_evaluation_api
  region                          = var.region
  image_path                      = var.evaluation_api_image_path
  project_id                      = var.project_id
  max_instance                    = var.evaluation_api_max_instance
  sql_connection_name             = var.evaluation_api_sql_connection_name
  timeout_seconds                 = var.evaluation_api_timeout_seconds 
  allocated_cpu                   = var.evaluation_api_allocated_cpu
  allocated_memory                = var.evaluation_api_allocated_memory
  ingress                         = var.default_ingress 
  #depends_on                      = [ module.ics_ai_jobs_cloud_sql]
}

output "evaluation_api_url" {
  value = module.cr_evaluation_api.cloud_run_url
}

