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

##################### Deploy Firestore #####################
module "google_firestore" {
  source           = "./google_firestore"
  project_id       = var.project_id
  region           = var.region
  deploy_firestore = var.deploy_firestore
}


##################### Deploy Storage Buckets #####################
module "function_bucket" { 
    source   = "./google_storage"
    bucket_name     = "${lower(var.project_id)}-functions" 
    region = var.region
}

module "text_ocr_bucket" {
    source   = "./google_storage"
    bucket_name     = "${lower(var.project_id)}-mindmaps-ocr-data" 
    region = var.region
}

module "mindmaps_bucket" { 
    source   = "./google_storage"
    bucket_name     = "${lower(var.project_id)}-mindmaps" 
    region = var.region
}

module "search_documents_bucket" { 
    source   = "./google_storage"
    bucket_name     = "${lower(var.project_id)}-search-documents" 
    region = var.region
}

module "video_transcription_bucket" { 
    source   = "./google_storage"
    bucket_name     = "${lower(var.project_id)}-video-transcription" 
    region = var.region
}

module "search_videos_bucket" { 
    source   = "./google_storage"
    bucket_name     = "${lower(var.project_id)}-search-videos" 
    region = var.region
}

# store the yolo model in the folder 'models'
module "yolo_checkpoints_bucket" { 
    source   = "./google_storage"
    bucket_name     = "${lower(var.project_id)}-yolo-checkpoints" 
    region = var.region
}

##################### Deploy Cloud Functions #####################

module "cf_document_process" {
  source                          = "./google_event_function"
  function_bucket                 = module.function_bucket.return_bucket_name#"${lower(var.project_id)}-functions"
  function_name                   = var.name_cf_ics_document_process
  function_source_files           = var.source_files_ics_document_process
  depends_on                      = [ module.function_bucket,
                                      module.search_documents_bucket]
  project_id                      = var.project_id
  region                          = var.region
  trigger_bucket_name             = module.search_documents_bucket.return_bucket_name 
  available_cpu                   = var.ics_document_process_available_cpu
  available_memory_mb             = var.ics_document_process_available_memory_mb
}

module "cf_transcript_process" {
  source                          = "./google_event_function"
  function_bucket                 = module.function_bucket.return_bucket_name#"${lower(var.project_id)}-functions"
  function_name                   = var.name_cf_ics_transcript_process
  function_source_files           = var.source_files_ics_transcript_process
  depends_on                      = [ module.function_bucket,
                                      module.video_transcription_bucket]
  project_id                      = var.project_id
  region                          = var.region
  trigger_bucket_name             = module.video_transcription_bucket.return_bucket_name 
  available_cpu                   = var.ics_transcript_process_available_cpu
  available_memory_mb             = var.ics_transcript_process_available_memory_mb 
}

module "cf_video_process" {
  source                          = "./google_event_function"
  function_bucket                 = module.function_bucket.return_bucket_name#"${lower(var.project_id)}-functions"
  function_name                   = var.name_cf_ics_video_process
  function_source_files           = var.source_files_ics_video_process
  depends_on                      = [ module.function_bucket,
                                      module.search_videos_bucket]
  project_id                      = var.project_id
  region                          = var.region
  trigger_bucket_name             = module.search_videos_bucket.return_bucket_name
  available_cpu                   = var.ics_video_process_available_cpu
  available_memory_mb             = var.ics_video_process_available_memory_mb
}

module "function_initial_table_creation" {
  source                        = "./google_http_function"
  function_bucket               = module.function_bucket.return_bucket_name#"${lower(var.project_id)}-functions"
  function_name                 = var.name_initial_table_creation
  function_source_files         = var.source_files_initial_table_creation
  depends_on                    = [module.function_bucket, module.ics_ai_jobs_cloud_sql]
  project_id                    = var.project_id
}

module "function_initial_firestore_config" {
  source                        = "./google_http_function"
  function_bucket               = module.function_bucket.return_bucket_name#"${lower(var.project_id)}-functions"
  function_name                 = var.name_initial_firestore_config
  function_source_files         = var.source_files_initial_firestore_config
  depends_on                    = [module.function_bucket]
  project_id                    = var.project_id
}

##################### Deploy Cloud Task queues #####################
module "cloud_tasks_queue_mindmap" {
  source                        = "./google_cloud_task"
  task_queue_name               = var.cloud_tasks_queue_mindmap_name
  location                      = var.region
}

module "cloud_tasks_queue_reflection" {
  source                        = "./google_cloud_task"
  task_queue_name               = var.cloud_tasks_queue_reflection_name
  location                      = var.region
}

##################### Create Artifact Registry Repo #################
module "cloud_run_artifacts" {
  source                          = "./google_artifact_registry_repo"
  repository_id                   = var.cloud_run_repo
  region                          = var.region
}

##################### Deploy Cloud SQL #####################
module "ics_ai_jobs_cloud_sql" {
  source                          = "./google_cloud_sql"
  database_instance_name          = var.database_instance_name
  region                          = var.region
  password                        = var.cloud_sql_password
  database_name                   = var.database_name
}

##################### Deploy Secret Manager #####################
module "secret_pinecone_api_key" {
  source      = "./google_secret"
  secret_name = var.pinecone_api_key_name
  secret_data = var.pinecone_api_key
}

module "secret_openai_api_key" {
  source      = "./google_secret"
  secret_name = var.openai_api_key_name
  secret_data = var.openai_api_key
}

module "secret_cloud_sql_key" {
  source      = "./google_secret"
  secret_name = var.cloud_sql_key_name
  secret_data = var.cloud_sql_password
}

module "secret_api_key" {
  source      = "./google_secret"
  secret_name = var.api_key_name
  secret_data = var.api_key_password
}

module "secret_hf_access_token" {
  source      = "./google_secret"
  secret_name = var.hf_access_token_name
  secret_data = var.hf_access_token
}

module "secret_aws_access_key_id" {
  source      = "./google_secret"
  secret_name = var.aws_access_key_name
  secret_data = var.aws_access_key_id
}

module "secret_aws_secret_access_key" {
  source      = "./google_secret"
  secret_name = var.aws_secret_access_key_name
  secret_data = var.aws_secret_access_key
}
##################### Add roles to default SA #####################
resource "google_project_iam_member" "storage_objectviewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
}
resource "google_project_iam_member" "cloudfunctions_invoker" {
  project = var.project_id
  role    = "roles/cloudfunctions.invoker"
  member  = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
}
resource "google_project_iam_member" "secretmanager_secretaccessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
}
resource "google_project_iam_member" "secretmanager_secretversionmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretVersionManager"
  member  = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
}
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
}
resource "google_project_iam_member" "storage_objectadmin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
}
# Add the Firestore client role to the gcf default SA
resource "google_project_iam_member" "datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
}
# Add the Pub/Sub Publisher role to the gcs default SA
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${var.project_number}@gs-project-accounts.iam.gserviceaccount.com"
}