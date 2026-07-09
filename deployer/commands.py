import click
from flask.cli import with_appcontext

from deployer.clients import digital_ocean
from deployer.models import App
from deployer.tasks import deploy_tournament


@click.command("list-tournaments")
@click.option("--limit", default=20, show_default=True, type=int)
@with_appcontext
def list_tournaments(limit):
    apps = App.query.order_by(App.created_at.desc()).limit(limit).all()

    if not apps:
        click.echo("No tournaments found.")
        return

    click.echo("id\tcreated_at\tname\tactive\tconfirmed\tstatus\tdeletion_date\temail")
    for app in apps:
        click.echo(
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                app.id,
                app.created_at,
                app.name,
                app.active,
                app.confirmed,
                app.status,
                app.deletion_date,
                app.email,
            )
        )


@click.command("redeploy-tournament")
@click.argument("app_id", type=int)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="TAB_PASSWORD to set on the redeployed tournament.",
)
@with_appcontext
def redeploy_tournament(app_id, password):
    app = App.query.get(app_id)
    if app is None:
        raise click.ClickException(f"No tournament found with id {app_id}")

    deploy_tournament.delay(app.id, password)
    click.echo(f"Queued redeploy for {app.name} (id={app.id}).")


@click.command("delete-digitalocean-resource")
@click.argument("name")
@click.option(
    "--type",
    "resource_type",
    type=click.Choice(["database", "app"]),
    default="database",
    show_default=True,
    help="DigitalOcean resource type to delete by name.",
)
@with_appcontext
def delete_digitalocean_resource(name, resource_type):
    if resource_type == "database":
        try:
            digital_ocean.delete_database(name)
        except ValueError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Deleted DigitalOcean database {name}.")
        return

    try:
        digital_ocean.get_app(name)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    digital_ocean.delete_app(name)
    click.echo(f"Deleted DigitalOcean app {name}.")


def register_commands(app):
    app.cli.add_command(list_tournaments)
    app.cli.add_command(redeploy_tournament)
    app.cli.add_command(delete_digitalocean_resource)
