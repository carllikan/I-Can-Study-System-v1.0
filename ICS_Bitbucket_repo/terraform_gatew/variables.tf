######## Variables that need to be set from Bitbucket repository variables
variable "region"         { type = string }
# variable "zone"           { type = string }
variable "project_id"     { type = string }
variable "project_number" { type = string }
variable "deploy_api_gateway" { 
    type = bool
    default = false
    }

###################### Variables for API Gateways ######################
############ API Gateway for Document Search ############
variable "global_search_api_id" {
    type = string
    default = "ics-global-search-api"
}

variable "global_search_api_config_id" {
    type = string
    default = "ics-global-search-config"
}

variable "global_search_yml" {
    type =string
    default = "../api_gateway_source/ics_global_search_api_gateway/openapi.yml"
}

variable "global_search_api_gateway_id" {
    type = string
    default = "ics-global-search-gatew"
}

############ API Gateway for Mind Map Evaluation ############
variable "mind_map_evaluation_api_id" {
    type = string
    default = "ics-mind-map-evaluation-api"
}

variable "mind_map_evaluation_api_config_id" {
    type = string
    default = "ics-mind-map-evaluation-config"
}

variable "mind_map_evaluation_yml" {
    type =string
    default = "../api_gateway_source/ics_mind_map_evaluation_api_gateway/openapi.yml"
}

variable "mind_map_evaluation_api_gateway_id" {
    type = string
    default = "ics-mind-map-evaluation-gatew"
}

############ API Gateway for Reflection Evaluation ############
variable "reflection_evaluation_api_id" {
    type = string
    default = "ics-reflection-evaluation-api"
}

variable "reflection_evaluation_api_config_id" {
    type = string
    default = "ics-reflection-evaluation-config"
}

variable "reflection_evaluation_yml" {
    type =string
    default = "../api_gateway_source/ics_reflection_evaluation_api_gateway/openapi.yml"
}

variable "reflection_evaluation_api_gateway_id" {
    type = string
    default = "ics-reflection-evaluation-gatew"
}

############ API Gateway for Evaluation API (combined MM & RF)############
variable "evaluation_api_id" {
    type = string
    default = "ics-evaluation-api"
}

variable "evaluation_api_config_id" {
    type = string
    default = "ics-evaluation-config"
}

variable "evaluation_yml" {
    type =string
    default = "../api_gateway_source/ics_evaluation_api_gateway/openapi.yml"
}

variable "evaluation_api_gateway_id" {
    type = string
    default = "ics-evaluation-gatew"
}

############# Variables for load balancer ###############################
variable "lb_ip_address"       {type = string}
variable "ssl_certificates"    {type = list(string)}