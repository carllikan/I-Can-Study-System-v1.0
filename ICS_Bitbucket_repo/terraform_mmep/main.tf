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


###################################################################
##################### Mind_Map_Evaluation_API #####################
/*module "cr_mind_map_evaluation_api" {
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
}*/
###################################################################
##################### Mind_Map_Evaluation_Pipeline ################
module "cr_mind_map_evaluation_pipeline" {
  source                          = "./google_cloud_run"
  deploy_cloud_run                = var.deployment_mind_map_evaluation_pipeline
  service_name                    = var.cr_mind_map_evaluation_pipeline
  region                          = var.region
  image_path                      = var.mind_map_evaluation_pipeline_image_path
  project_id                      = var.project_id
  max_instance                    = var.mind_map_evaluation_pipeline_max_instance
  sql_connection_name             = var.mind_map_evaluation_pipeline_sql_connection_name
  timeout_seconds                 = var.mind_map_evaluation_pipeline_timeout_seconds 
  allocated_cpu                   = var.mind_map_evaluation_pipeline_allocated_cpu
  allocated_memory                = var.mind_map_evaluation_pipeline_allocated_memory 
  ingress                         = var.default_ingress
 }
 output "mind_map_evaluation_pipeline_url" {
   value = module.cr_mind_map_evaluation_pipeline.cloud_run_url
 }
