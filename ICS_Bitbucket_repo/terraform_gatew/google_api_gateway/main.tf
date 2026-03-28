resource "google_api_gateway_api" "api_gateway" {
  count = var.deploy_api_gateway ? 1 : 0
  provider = google-beta
  api_id = var.api_id
}

resource "google_api_gateway_api_config" "api_gateway" {
  count = var.deploy_api_gateway ? 1 : 0
  provider = google-beta
  # api = google_api_gateway_api.api_gateway.api_id
  api = google_api_gateway_api.api_gateway[0].api_id
  api_config_id = var.api_config_id#"runconf-moretimeout-2ckjkt1v3k2cd"

  openapi_documents {
    document {
      path = "spec.yaml"
      contents = filebase64(var.api_gateway_source)
    }
  }
  lifecycle {
    create_before_destroy = true
  }
}

resource "google_api_gateway_gateway" "api_gateway" {
  count      = var.deploy_api_gateway ? 1 : 0
  provider   = google-beta
  api_config = google_api_gateway_api_config.api_gateway[0].id
  gateway_id = var.api_gateway_id
}

output "gateway_id" {
  value = google_api_gateway_gateway.api_gateway[0].gateway_id
}
