######## Variables that need to be set from Bitbucket repository variables
variable "region"         { type = string }
# variable "zone"           { type = string }
variable "project_id"     { type = string }
variable "project_number" { type = string }

variable "deployment_reflection_evaluation_api" {
    type =bool
    default = true
    }
variable "deployment_reflection_evaluation_pipeline" {
    type =bool
    default = true
    }



###################### Variables for Cloud Run Services ######################
### for all the default cloud run ingress control ###

variable "default_ingress" { 
    type = string
    default = "all"
}

############ cloud run reflection evaluation api  ############ 
variable "cr_reflection_evaluation_api" {
    type = string
    default = "ics-reflection-evaluation-api"
}

variable "reflection_evaluation_api_max_instance" {
    type = string
    default = "50"
}

variable "reflection_evaluation_api_sql_connection_name" {
    type = string
    default = ""
}
variable "reflection_evaluation_api_timeout_seconds" {
    type = number
    default = 300
}
variable "reflection_evaluation_api_allocated_cpu" {
    type = string
    default = "1"
}
variable "reflection_evaluation_api_allocated_memory" {
    type = string
    default = "1Gi"
}

variable "reflection_evaluation_api_image_path" { 
    type = string
    default = ""
    }

############ cloud run reflection evaluation pipeline  ############ 
variable "cr_reflection_evaluation_pipeline" {
    type = string
    default = "ics-reflection-evaluation-pipeline"
}

variable "reflection_evaluation_pipeline_max_instance" {
    type = string
    default = "50"
}

variable "reflection_evaluation_pipeline_sql_connection_name" {
    type = string
    default = ""
}
variable "reflection_evaluation_pipeline_timeout_seconds" {
    type = number
    default = 300
}
variable "reflection_evaluation_pipeline_allocated_cpu" {
    type = string
    default = "1"
}
variable "reflection_evaluation_pipeline_allocated_memory" {
    type = string
    default = "1Gi"
}

variable "reflection_evaluation_pipeline_image_path" {
     type = string
     default =""
     }
