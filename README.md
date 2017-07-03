This is an application to handle automatic deployments of the
[mit-tab](https://github.com/jolynch/mit-tab/) application

# Installation and Running

This application requires you to have docker and docker-compose installed

To run:

```
docker-compose build
./bin/start
```

# What this application does (or... will do once I finish it)

- Deploys an instance of mit-tab to a Digital Oceal droplet (using Digital
  Ocean's remote Docker hosts)
- Creates a DNS record at {tournament}.nu-tab.com that maps to that droplet's IP
  address using the DNSimple API
- Manages the deletion of droplets of old tournaments once they are completed
