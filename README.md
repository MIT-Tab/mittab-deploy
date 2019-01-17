[ ![Codeship Status for BenMusch/mittab-deploy](https://app.codeship.com/projects/a04919f0-41c5-0135-d736-06284f5b6d31/status?branch=master)](https://app.codeship.com/projects/230129)

This is an application to handle automatic deployments of the
[mit-tab](https://github.com/jolynch/mit-tab/) application

# What this application does

- Deploys an instance of mit-tab to a Digital Oceal droplet (using Digital
  Ocean's remote Docker hosts)
- Creates a DNS record at {tournament}.nu-tab.com that maps to that droplet's IP
  address using the Digital Ocean DNS services
- Useful scripts to backup tournaments


# TODO:
- Integrate payment system to cover infrastructure costs (if APDA board can't cover costs)
- Automate tournament deletion
- Automate staging deploys with PRs to mit-tab


# Installation and Running

This application requires you to have docker and docker-compose installed. You
can also run it via virtualenv locally. You will need the AWS credentials to
test this. Email me.

It is not recommended to use docker for local development, because docker also
handles things like the SSL certs, so stuff just gets kinda annoying to work
with. Instead, use virtualenv. I find it convenient to add this to the
postactivate script:

```
export $(grep -v '^#' .env | xargs -0)
export $(grep -v '^#' .env.secret | xargs -0)
```

And this to the postdeactivate script:

```
unset $(grep -v '^#' .env | sed -E 's/(.*)=.*/\1/' | xargs -d '\n')
unset $(grep -v '^#' .env.secret | sed -E 's/(.*)=.*/\1/' | xargs -d '\n')
```

## Environment Variables

Most env vars are defined in `.env`. My API keys are not in there for
obvious reasons, so code that hits APIs will not function until I figure out how
to mock it

# Deployment

On each commit to master, the server pulls the code. However, the docker
containers need to be manually restarted (TODO?)
