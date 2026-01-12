from celery import Celery
from app import app  # Ensure app.py does not import tasks.py

def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=app.config["CELERY_BROKER_URL"],
        backend=app.config["CELERY_RESULT_BACKEND"]
    )
    # Load configuration from Flask app using the namespace "CELERY"
    celery.config_from_object(app.config, namespace="CELERY")

    # Wrap tasks so they run within the Flask application context.
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# Force registration of tasks.
import tasks
