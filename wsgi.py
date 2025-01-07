from deployer import create_app
from flask_migrate import cli as migrate_cli

app = create_app()
app.cli.add_command(migrate_cli.db)
