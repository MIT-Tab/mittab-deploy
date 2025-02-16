import time
import logging
from datetime import datetime

from celery.schedules import crontab
from tenacity import retry, stop_after_attempt, wait_fixed

from deployer.extensions import db, celery
from deployer.clients import email, digital_ocean
from deployer.models import App

logger = logging.getLogger(__name__)


class ServerNotReadyError(Exception):
    pass


class SetupFailedError(Exception):
    pass


class BackupFailedError(Exception):
    pass


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        crontab(hour=10, minute=30),
        delete_apps().s()
    )

@celery.task()
def deploy_tournament(app_id, password):
    app = App.query.get(app_id)

    deploy_app(app, password)
    email.send_confirmation(app, password)
    email.send_notification(app.name)


@retry(stop=stop_after_attempt(5), wait=wait_fixed(300))
def deploy_app(app, password):
    try:
        app.active = True
        app.set_status('Creating database')
        db = digital_ocean.create_database(app.name)

        time.sleep(5 * 60)

        app.set_status('Creating server')
        digital_ocean.create_app(app.name, password, db, app.repo_slug, app.branch)

        app.set_status('Deployed')
    except Exception as e:
        logger.error(f"Error deploying {app.name}: {e}", exc_info=True)
        app.set_status('An error occurred. Retrying up to 5 times')
        app.deactivate()
        raise e


def delete_apps():
    apps = App.query.filter_by(active=True)
    current_date = datetime.now().date()
    logger.info("Checking {} apps for deletion".format(len(apps)))

    for app in apps:
        if app.deletion_date < current_date and app.warning_email_sent:
            try:
                app.deactivate()
                app.set_status('Deleted')
                logger.info("Successfully deleted {}".format(app.name))
            except Exception as e:
                logger.error("Error deleting {}".format(app.name), exc_info=True)
                app.set_status('Error while deleting')
        elif (app.deletion_date - current_date).days <= 3 and \
                not app.warning_email_sent:
            logger.info("Sending warning email to {}".format(app.name))
            email.send_warning(app)
            app.warning_email_sent = True
            db.session.add(app)
            db.session.commit()
