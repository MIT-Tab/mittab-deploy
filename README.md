This is an application to handle automatic deployments of the
[mit-tab](https://github.com/jolynch/mit-tab/) application

# What this application does (or... will do once I finish it)

- Deploys an instance of mit-tab to a Digital Oceal droplet (using Digital
  Ocean's remote Docker hosts)
- Creates a DNS record at {tournament}.nu-tab.com that maps to that droplet's IP
  address using the DNSimple API
- Manages the deletion of droplets of old tournaments once they are completed


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

Most env vars are defined in `.env.sample`. My API keys are not in there for
obvious reasons. Copy that file to `.env` to get it to load the variables in the
application
