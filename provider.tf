variable "do_token" {}
variable "pub_key" {}
variable "pvt_key" {}
variable "ssh_fingerprint" {}
variable "tournament_name" {}
variable "tournament_password" {}
variable "clone_path" {}

provider "digitalocean" {
  token = "${var.do_token}"
}
