######## Variables that need to be set from Bitbucket repository variables
variable "region"         { type = string }
# variable "zone"           { type = string }
variable "project_id"     { type = string }
variable "project_number" { type = string }


variable "deployment_global_search_api" {
    type =bool
    default = true
    }

variable "deployment_final_feedback" {
    type=bool
    default = true
    }



###################### Variables for Cloud Run Services ######################

############ cloud run global search api  ############ 
variable "cr_global_search_api" {
    type = string
    default = "ics-global-search-api"
}

variable "global_search_api_max_instance" {
    type = string
    default = "50"
}

variable "global_search_api_min_instance" {
    type = string
    default = "1"
}

variable "global_search_api_sql_connection_name" {
    type = string
    default = ""
}
variable "global_search_api_timeout_seconds" {
    type = number
    default = 300
}
variable "global_search_api_allocated_cpu" {
    type = string
    default = "1"
}
variable "global_search_api_allocated_memory" {
    type = string
    default = "1Gi"
}


variable "global_search_api_image_path" { 
    type = string
    default = ""
}

variable "global_search_api_ingress" { 
    type = string
    #default = "internal-and-cloud-load-balancing"
    default = "all"
}

### for all the default cloud run ingress control ###

variable "default_ingress" { 
    type = string
    default = "all"
}


############ cloud run final feedback  ############ 
variable "cr_final_feedback" {
    type = string
    default = "ics-final-feedback"
}

variable "final_feedback_max_instance" {
    type = string
    default = "50"
}

variable "final_feedback_min_instance" {
    type = string
    default = "0"
}

variable "final_feedback_sql_connection_name" {
    type = string
    default =""
}
variable "final_feedback_timeout_seconds" {
    type = number
    default = 300
}
variable "final_feedback_allocated_cpu" {
    type = string
    default = "1"
}
variable "final_feedback_allocated_memory" {
    type = string
    default = "1Gi"
}

variable "final_feedback_image_path" { 
    type = string
    default = ""
    }


