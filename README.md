This is an application to handle automatic deployments of the
[mit-tab](https://github.com/jolynch/mit-tab/) application

# What this application does

- Deploys an instance of mit-tab to a Digital Oceal droplet (using Digital
  Ocean's remote Docker hosts)
- Creates a DNS record at {tournament}.nu-tab.com that maps to that droplet's IP
  address using the Digital Ocean DNS services
- Useful scripts to backup tournaments
- Admin interface to delete tournaments


# TODO:
- Automate staging deploys with PRs to mit-tab
- Add more functionality (stripe refunds, task logs, etc.) to the admin interface


# Installation and Running

You will need the AWS, DigitalOcean and Stripe credentials to test this. Please set up
your own account if you plan on developing on this. Feel free to contact me directly
with any questions.

The easiest way to run is with `pipenv`

```
pip install pipenv
pipenv install
PYTHONPATH=$(pwd) FLASK_APP=deployer pipenv run flask run
```

## Environment Variables

These are in `.env`, which is `.gitignore`'d. Run `cp .env.example .env` to get started.

# Deployment

On each master commit, the dockerhub image `benmusch/mit-tab:latest` is built and
pushed. To deploy, pull this image, pull the code, and run `dc up -d`.
