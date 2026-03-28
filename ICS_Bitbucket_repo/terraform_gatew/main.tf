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


###################################################################
##################### Deploy API Gateway #####################

module "evaluation_gateway" {
  source                          = "./google_api_gateway"
  deploy_api_gateway              = var.deploy_api_gateway
  api_id                          = var.evaluation_api_id
  api_config_id                   = var.evaluation_api_config_id
  api_gateway_source              = var.evaluation_yml
  api_gateway_id                  = var.evaluation_api_gateway_id
}

####################################################################
################## Deploy load balancer #########################
# Reserved IP address for the load balancer
# resource "google_compute_global_address" "lb_ip" {
#   name       = "ics-ai-gs-ip-d"
#   address    = "34.36.32.236"
# }

# Backend Service
resource "google_compute_backend_service" "default" {
  name                  = "api-gateway-backend-service"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL"
  connection_draining_timeout_sec = 0

  backend {
    group = google_compute_region_network_endpoint_group.default.id
  }
}

# Serverless Network Endpoint Group
resource "google_compute_region_network_endpoint_group" "default" {
  provider              = google-beta
  name                  = "gateway-sneg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  depends_on            = [module.evaluation_gateway]
  serverless_deployment {
    platform = "apigateway.googleapis.com"
    resource = module.evaluation_gateway.gateway_id
  }
}

# URL Map
resource "google_compute_url_map" "default" {
  name            = "api-gateway-url-map"
  default_service = google_compute_backend_service.default.self_link
}

# Target HTTPS Proxy
resource "google_compute_target_https_proxy" "default" {
  name             = "eval-fw"
  url_map          = google_compute_url_map.default.self_link
  ssl_certificates = var.ssl_certificates
}

# Global Forwarding Rule
resource "google_compute_global_forwarding_rule" "default" {
  name                  = "eval-fw"
  ip_address            = var.lb_ip_address
  port_range            = "443"
  target                = google_compute_target_https_proxy.default.self_link
  load_balancing_scheme = "EXTERNAL"
}

####################################################################
################## Deploy cloud armor policy ######################
resource "google_compute_security_policy" "policy" {
  name        = "rate-limit-policy"
  description = "throttle rule with enforce_on_key_configs"
  type        = "CLOUD_ARMOR"
  depends_on  = [resource.google_compute_url_map.default]
  
  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "default rule"
  }

  rule {
    action   = "throttle"
    priority = "2147483646"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "rate limit rule"

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(403)"
      enforce_on_key = "IP"

      rate_limit_threshold {
        count        = 500
        interval_sec = 60
      }
    }
  }

  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable         = true
      rule_visibility = "STANDARD"
    }
  }
}