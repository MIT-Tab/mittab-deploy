resource "digitalocean_droplet" "mittab-${var.tournament_name}" {
  image = "docker"
  name = "mittab-${var.tournament_name}"
  region = "nyc3"
  size = "512mb"
  private_networking = true
  ssh_keys = [
    "${var.ssh_fingerprint}"
  ]

  connection {
      user = "root"
      type = "ssh"
      private_key = "${file(var.pvt_key)}"
      agent = true
      timeout = "2m"
  }

  provisioner "remote-exec" {
    inline = [
      "apt-get update",
      "apt-get -y install python-pip",
      "pip install docker-compose",
      "mkdir /var/www/",
      "mkdir /var/www/tab",
      "git clone ${var.clone_path} /var/www/tab",
      "cd /var/www/tab",
      "docker-compose up -d --build",
      "docker-compose run --rm web python manage.py migrate",
      "docker-compose run --rm web python manage.py initialize_tourney --tab-password ${var.tournament_password} tournament .",
      "docker-compose run --rm web python manage.py collectstatic --noinput"
    ]
  }
}
