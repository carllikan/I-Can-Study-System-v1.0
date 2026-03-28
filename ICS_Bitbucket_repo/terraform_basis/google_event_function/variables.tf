variable "function_name"                   { type = string }
# variable "function_runtime"                { type = string }
variable "function_bucket"                 {  type = string }
# variable "function_entry_point"            { type = string }
variable "function_source_files"           { type = list(string) }
variable "project_id"                      { type = string }
variable "region"                          { type = string }
# variable "function_event_trigger_type"     { type = string }
# variable "function_event_trigger_resource" { type = string }
variable "available_memory_mb"             { type = string }
variable "available_cpu"                   { type = string }
variable "trigger_bucket_name"             { type = string }

