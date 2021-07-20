import logging
from django.conf import settings
from rest_apscheduler.jobstore import DjangoJobStore
from apscheduler.schedulers.background import BackgroundScheduler


logger = logging.getLogger(__name__)

Scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
Scheduler.add_jobstore(DjangoJobStore(), "default")


def start_scheduler():
	try:
		logger.info("Starting scheduler...")
		Scheduler.start()
	except KeyboardInterrupt:
		logger.info("Stopping scheduler...")
		Scheduler.shutdown()
		logger.info("Scheduler shut down successfully!")


start_scheduler()
