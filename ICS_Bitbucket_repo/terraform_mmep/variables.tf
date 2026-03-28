######## Variables that need to be set from Bitbucket repository variables
variable "region"         { type = string }
# variable "zone"           { type = string }
variable "project_id"     { type = string }
variable "project_number" { type = string }

variable "deployment_mind_map_evaluation_pipeline" {
    type =bool
    default = true
    }


### for all the default cloud run ingress control ###

variable "default_ingress" { 
    type = string
    default = "all"
}

############ cloud run mind map evaluation api ############ 
/*
variable "cr_mind_map_evaluation_api" {
    type = string
    default = "ics-mind-map-evaluation-api"
}


variable "mind_map_evaluation_api_max_instance" {
    type = string
    default = "50"
}

variable "mind_map_evaluation_api_sql_connection_name" {
    type = string
    default = ""
}
variable "mind_map_evaluation_api_timeout_seconds" {
    type = number
    default = 300
}
variable "mind_map_evaluation_api_allocated_cpu" {
    type = string
    default = "1"
}
variable "mind_map_evaluation_api_allocated_memory" {
    type = string
    default = "1Gi"
}

variable "mind_map_evaluation_api_image_path" { 
    type = string
    default = ""
    }

*/
############ cloud run mind map pipeline  ############ 
variable "cr_mind_map_evaluation_pipeline" {
    type = string
    default = "ics-mind-map-evaluation-pipeline"
}

variable "mind_map_evaluation_pipeline_max_instance" {
    type = string
    default = "6"
}

variable "mind_map_evaluation_pipeline_sql_connection_name" {
    type = string
    default = ""
}
variable "mind_map_evaluation_pipeline_timeout_seconds" {
    type = number
    default = 300
}
variable "mind_map_evaluation_pipeline_allocated_cpu" {
    type = string
    default = "4"
}
variable "mind_map_evaluation_pipeline_allocated_memory" {
    type = string
    default = "16Gi"
}

variable "mind_map_evaluation_pipeline_image_path" {
     type = string
     default = ""
     }

