from deployer import create_app
from deployer.extensions import celery

app = create_app()
app.app_context().push()
