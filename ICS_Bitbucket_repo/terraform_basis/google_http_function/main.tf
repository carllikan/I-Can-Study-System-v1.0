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
  content_disposition = "attachment"
  content_encoding = "gzip"
  content_type = "application/zip"
}

resource "google_cloudfunctions_function" "function" {
  name                  = var.function_name
  runtime               = "python311"
  entry_point           = "main"
  source_archive_bucket = var.function_bucket
  trigger_http          = true
  available_memory_mb   = 512
  timeout               = 300
#  ingress_settings      = "ALLOW_ALL"
  source_archive_object = google_storage_bucket_object.archive_object.name
  environment_variables = {
      project_id = var.project_id
  }
}

