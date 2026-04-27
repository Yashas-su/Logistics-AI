variable "project_id" { description = "GCP project ID" }
variable "region"     { default = "us-central1" }

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_container_cluster" "logisticai" {
  name             = "logisticai-prod"
  location         = var.region
  enable_autopilot = true
  release_channel  { channel = "REGULAR" }
}

resource "google_pubsub_topic" "gps" {
  name = "shipment-gps-events"
}
resource "google_pubsub_topic" "weather" {
  name = "weather-alerts"
}
resource "google_pubsub_topic" "reroutes" {
  name = "reroute-decisions"
}

resource "google_bigquery_dataset" "logistics" {
  dataset_id  = "logistics_prod"
  location    = "US"
}

resource "google_redis_instance" "cache" {
  name           = "logisticai-cache"
  tier           = "STANDARD_HA"
  memory_size_gb = 16
  region         = var.region
  redis_version  = "REDIS_7_0"
}

output "gke_cluster"    { value = google_container_cluster.logisticai.name }
output "redis_host"     { value = google_redis_instance.cache.host }
output "redis_port"     { value = google_redis_instance.cache.port }
