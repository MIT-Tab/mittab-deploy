This is an application to handle automatic deployments of the
[mit-tab](https://github.com/mit-tab/mit-tab/) application

This app is a very light wrapper ontop of the [DigitalOcean App Platform API](https://www.digitalocean.com/products/app-platform),
as the deployments themselves are no longer very complex. In particular,
the deployer:
 - Creates a database instance for the app
 - Creates an App Platform instance connected to that database and the [nu-tab.com](https://nu-tab.com) domain
 - Charges users for the deployment using Stripe
 - Deletes tournaments automatically

# Development

## Pre-requisites: External accounts

### Digital Ocean

The deployer manages deployments to Digital Ocean. (The entire deployer app is
essentially just an API call to Digital Ocean's App Platform API). You will need
to create a DigitalOcean account with an API key. If you wish to test the subdomain
set-up, you must also have the DNS of that domain managed by DigitalOcean ([instructions](https://docs.digitalocean.com/products/networking/dns/how-to/add-domains/)).

### Stripe

Test mode stripe credentials are necessary to test the deployment flow.

## Installation

To run this app, you will need:
 - MySQL (8.0+)
 - Redis

Install these according to your local environment (e.g. `brew install mysql redis`).

Then, install the python dependencies:

```
pip install uv
uv insall
```

## Environment Variables

Copy `.env.example` to `.env` and fill in the necessary values.

## Running

With MySQL and Redis running:

```bash
# Run migrations if necessary
uv run --env-file .env flask db upgrade

# Start the web server
uv run --env-file .env flask run
```

In another tab, start the celery worker to process deployments:

```bash
uv run --env-file .env ./bin/start_celery
```
