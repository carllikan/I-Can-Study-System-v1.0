locals {
  source_files = var.function_source_files
}

data "template_file" "t_file" {
  count = length(local.source_files)
  template = file(element(local.source_files, count.index))
}

resource "local_file" "to_temp_dir" {
  count = length(local.source_files)
  filename = "./temp/${var.function_name}/${basename(element(local.source_files, count.index))}"
  content = element(data.template_file.t_file.*.rendered, count.index)
}

data "archive_file" "function_archive" {
  type = "zip"
  source_dir = "./temp/${var.function_name}"
  output_path = "./function_archives/${var.function_name}.zip"
  depends_on = [
    local_file.to_temp_dir,
  ]
}

resource "google_storage_bucket_object" "archive_object" {
  name = "${data.archive_file.function_archive.output_md5}.zip"
  bucket = var.function_bucket
  source = data.archive_file.function_archive.output_path
  depends_on = [
    data.archive_file.function_archive
  ]
  # content_disposition = "attachment"
  # content_encoding = "gzip"
  # content_type = "application/zip"
}

resource "google_cloudfunctions2_function" "function" {
  name                  = var.function_name
  location              = var.region
  build_config {
    runtime             = "python311"#var.function_runtime
    entry_point         = "main"#var.function_entry_point
    source  {
      storage_source {
        bucket = var.function_bucket
        object = google_storage_bucket_object.archive_object.name
      }
    
    }
  }

 service_config {
   min_instance_count = 0
   max_instance_count = 100
   timeout_seconds    = 540
   available_memory   = var.available_memory_mb
   available_cpu      = var.available_cpu
   all_traffic_on_latest_revision = true
 }
  

  event_trigger {
    trigger_region = var.region
    event_type = "google.cloud.storage.object.v1.finalized"# var.function_event_trigger_type
    event_filters {
      attribute = "bucket"
      value = var.trigger_bucket_name
    }
  }
  depends_on = [
    google_storage_bucket_object.archive_object
  ]

}

# resource "google_cloudfunctions_function_iam_member" "addaxis_invoker" {
#   project = google_cloudfunctions_function.function.project
#   region = google_cloudfunctions_function.function.region
#   cloud_function = google_cloudfunctions_function.function.name

#   role = "roles/cloudfunctions.invoker"
#   member = "domain:addaxis.ai"
# }

# resource "google_cloudfunctions_function_iam_member" "service_account_invoker" {
#   project = google_cloudfunctions_function.function.project
#   region = google_cloudfunctions_function.function.region
#   cloud_function = google_cloudfunctions_function.function.name

#   role = "roles/cloudfunctions.invoker"
#   member = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
# }
