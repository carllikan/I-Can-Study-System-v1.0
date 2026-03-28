variable "api_gateway_source"              { type = string }
variable "api_id"                          { type = string }
variable "api_config_id"                   { type = string }
variable "api_gateway_id"                  { type = string }

variable "deploy_api_gateway" {
    type = bool
    default = false
}
