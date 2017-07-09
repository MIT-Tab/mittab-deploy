[ ![Codeship Status for BenMusch/mittab-deploy](https://app.codeship.com/projects/a04919f0-41c5-0135-d736-06284f5b6d31/status?branch=master)](https://app.codeship.com/projects/230129)

This is an application to handle automatic deployments of the
[mit-tab](https://github.com/jolynch/mit-tab/) application

# What this application does

- Deploys an instance of mit-tab to a Digital Oceal droplet (using Digital
  Ocean's remote Docker hosts)
- Creates a DNS record at {tournament}.nu-tab.com that maps to that droplet's IP
  address using the Digital Ocean DNS services


# TODO:
- Integrate payment system to cover infrastructure costs
- Send an email with instructions for setting up the tournament
- Error handling
- Manage the deletion of droplets of old tournaments once they are completed
- Improved user interface to poll for progress on the tournament creation
- Automate staging deploys with PRs to mit-tab
- Get SSH set up on created tournaments so I can troubleshoot


# Installation and Running

This application requires you to have docker and docker-compose installed. You
can also do your own thing with virtualenv and stuff I guess. Just make sure it
works with Postgres and whatever I end up using for background tasks

To run:

```
docker-compose build
./bin/start
```

## Environment Variables

Most env vars are defined in `.env`. My API keys are not in there for
obvious reasons, so code that hits APIs will not function until I figure out how
to mock it

# Deployment

On each commit to master, the server pulls the code. However, the docker
containers need to be manually restarted (TODO?)
