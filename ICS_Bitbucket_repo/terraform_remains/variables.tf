######## Variables that need to be set from Bitbucket repository variables
variable "region"         { type = string }
# variable "zone"           { type = string }
variable "project_id"     { type = string }
variable "project_number" { type = string }


variable "deployment_mind_map_evaluation_api" {
    type =bool
    default = true
    }

variable "deployment_reflection_evaluation_api" {
    type =bool
    default = true
    }

variable "deployment_evaluation_api" {
    type =bool
    default = true
    }


###################### Variables for Cloud Run Services ######################

### for all the default cloud run ingress control ###

variable "default_ingress" { 
    type = string
    default = "all"
}

############ cloud run mind map evaluation api ############ 
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
    default = "2"
}
variable "mind_map_evaluation_api_allocated_memory" {
    type = string
    default = "8Gi"
}

variable "mind_map_evaluation_api_image_path" { 
    type = string
    default = ""
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

############ cloud run evaluation api  ############ 
variable "cr_evaluation_api" {
    type = string
    default = "ics-evaluation-api"
}

variable "evaluation_api_max_instance" {
    type = string
    default = "50"
}

variable "evaluation_api_sql_connection_name" {
    type = string
    default =""
}
variable "evaluation_api_timeout_seconds" {
    type = number
    default = 300
}
variable "evaluation_api_allocated_cpu" {
    type = string
    default = "2"
}
variable "evaluation_api_allocated_memory" {
    type = string
    default = "8Gi"
}

variable "evaluation_api_image_path" { 
    type = string
    default =""
    }


