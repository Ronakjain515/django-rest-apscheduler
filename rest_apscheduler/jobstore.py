import logging
import pickle
from typing import Union, List

from apscheduler import triggers
from apscheduler import events
from apscheduler.events import JobExecutionEvent
from apscheduler.job import Job as AppSchedulerJob
from apscheduler.jobstores.base import BaseJobStore, JobLookupError, ConflictingIdError
from apscheduler.jobstores.memory import MemoryJobStore

from django import db
from django.db import transaction, IntegrityError
from django.utils import timezone

from .models import DjangoJob, DjangoJobExecution
from .util import (
    get_apscheduler_datetime,
    get_django_internal_datetime,
)

logger = logging.getLogger(__name__)


class DjangoResultStoreMixin:
    """Mixin class that adds the ability for a JobStore to store job execution results in the Django database"""

    lock = None

    def start(self, scheduler, alias):
        super().start(scheduler, alias)
        self.register_event_listeners()

    @classmethod
    def handle_execution_event(cls, event: JobExecutionEvent) -> Union[int, None]:
        """
        Store "successful" job execution status in the database.

        :param event: JobExecutionEvent instance
        :return: DjangoJobExecution ID or None if the job execution could not be logged.
        """
        if event.code != events.EVENT_JOB_EXECUTED:
            raise NotImplementedError(
                f"Don't know how to handle JobExecutionEvent '{event.code}'. Expected "
                f"'{events.EVENT_JOB_EXECUTED}'."
            )
        try:
            job_execution = DjangoJobExecution.objects.get(job=event.job_id)
            job_execution.status = DjangoJobExecution.SUCCESS
            job_execution.finished = timezone.now()
            job_execution.save()
            return job_execution.id
        except DjangoJobExecution.DoesNotExist:
            logger.warning(
                f"Job '{event.job_id}' no longer exists! Skipping logging of job execution..."
            )
        except IntegrityError:
            logger.warning(
                f"Job '{event.job_id}' no longer exists! Skipping logging of job execution..."
            )
        return None

    @classmethod
    def handle_error_event(cls, event: JobExecutionEvent) -> Union[int, None]:
        """
        Store "failed" job execution status in the database.

        :param event: JobExecutionEvent instance
        :return: DjangoJobExecution ID or None if the job execution could not be logged.
        """
        try:
            if event.code == events.EVENT_JOB_ERROR:

                if event.exception:
                    exception = str(event.exception)
                    traceback = str(event.traceback)
                else:
                    exception = f"Job '{event.job_id}' raised an error!"
                    traceback = None

                try:
                    job_execution = DjangoJobExecution.objects.get(job=event.job_id)
                    job_execution.status = DjangoJobExecution.ERROR
                    job_execution.exception = exception
                    job_execution.traceback = traceback
                    job_execution.save()
                    return job_execution.id
                except DjangoJobExecution.DoesNotExist:
                    logger.warning(
                        f"Job '{event.job_id}' no longer exists! Skipping logging of job execution..."
                    )

            elif event.code == events.EVENT_JOB_MISSED:
                exception = f"Run time of job '{event.job_id}' was missed!"
                try:
                    job_execution = DjangoJobExecution.objects.get(job=event.job_id)
                    job_execution.status = DjangoJobExecution.MISSED
                    job_execution.exception = exception
                    job_execution.save()
                    return job_execution.id
                except DjangoJobExecution.DoesNotExist:
                    logger.warning(
                        f"Job '{event.job_id}' no longer exists! Skipping logging of job execution..."
                    )

            else:
                raise NotImplementedError(
                    f"Don't know how to handle JobExecutionEvent '{event.code}'. Expected "
                    f"one of '{[events.EVENT_JOB_ERROR, events.EVENT_JOB_MAX_INSTANCES, events.EVENT_JOB_MISSED]}'."
                )
        except IntegrityError:
            logger.warning(
                f"Job '{event.job_id}' no longer exists! Skipping logging of job execution..."
            )
        return None

    @classmethod
    def handle_added_job_event(cls, event: JobExecutionEvent) -> Union[int, None]:
        """
        Store "Added New Job" job execution status in the database.

        :param event: JobExecutionEvent instance
        :return: DjangoJobExecution ID or None if the job execution could not be logged.
        """
        job = DjangoJob.objects.get(id=event.job_id)
        try:
            execution = DjangoJobExecution.objects.get(job=event.job_id)
            execution.status = DjangoJobExecution.START
            execution.run_time = timezone.now()
            execution.type = job.trigger
            execution.save()
        except DjangoJobExecution.DoesNotExist:
            execution = DjangoJobExecution.objects.create(
                job=event.job_id,
                status=DjangoJobExecution.START,
                type=job.trigger,
                run_time=timezone.now()
            )
        return execution

    @classmethod
    def handle_modify_event(cls, event: JobExecutionEvent) -> Union[int, None]:
        """
        Store "Modify Job" job execution status in the database.

        :param event: JobExecutionEvent instance
        :return: DjangoJobExecution ID or None if the job execution could not be logged.
        """
        try:
            job_execution = DjangoJobExecution.objects.get(job=event.job_id)
            job = DjangoJob.objects.get(id=event.job_id)
            job_execution.run_time = job.next_run_time
            job_execution.save()
            return job_execution.id
        except DjangoJobExecution.DoesNotExist:
            logger.warning(
                f"Job '{event.job_id}' no longer exists! Skipping logging of job execution..."
            )
        return None

    def register_event_listeners(self):
        """
        Register various event listeners.

        See: https://github.com/agronholm/apscheduler/blob/master/docs/modules/events.rst for details on which event
        class is used for each event code.

        """
        self._scheduler.add_listener(
            self.handle_added_job_event, events.EVENT_JOB_ADDED
        )

        self._scheduler.add_listener(
            self.handle_execution_event, events.EVENT_JOB_EXECUTED
        )

        self._scheduler.add_listener(
            self.handle_error_event, events.EVENT_JOB_ERROR | events.EVENT_JOB_MISSED,
        )

        self._scheduler.add_listener(
            self.handle_modify_event, events.EVENT_JOB_MODIFIED,
        )


class DjangoJobStore(DjangoResultStoreMixin, BaseJobStore):
    """
    Stores jobs in a Django database. Based on APScheduler's `MongoDBJobStore`.

    See: https://github.com/agronholm/apscheduler/blob/master/apscheduler/jobstores/mongodb.py

    :param int pickle_protocol: pickle protocol level to use (for serialization), defaults to the
           highest available
    """

    def __init__(self, pickle_protocol: int = pickle.HIGHEST_PROTOCOL):
        super().__init__()
        self.pickle_protocol = pickle_protocol

    def lookup_job(self, job_id: str) -> Union[None, AppSchedulerJob]:
        try:
            job_state = DjangoJob.objects.get(id=job_id).job_state
            return self._reconstitute_job(job_state) if job_state else None

        except DjangoJob.DoesNotExist:
            return None

    def get_due_jobs(self, now) -> List[AppSchedulerJob]:
        dt = get_django_internal_datetime(now)
        return self._get_jobs(next_run_time__lte=dt)

    def get_next_run_time(self):
        try:
            job = DjangoJob.objects.filter(next_run_time__isnull=False).earliest(
                "next_run_time"
            )
            return get_apscheduler_datetime(job.next_run_time, self._scheduler)
        except DjangoJob.DoesNotExist:
            # No active jobs - OK
            return None

    def get_all_jobs(self):
        jobs = self._get_jobs()
        self._fix_paused_jobs_sorting(jobs)

        return jobs

    def add_job(self, job: AppSchedulerJob):
        with transaction.atomic():
            try:
                trigger_type = ""
                if type(job.trigger) == triggers.date.DateTrigger:
                    trigger_type = "DATE"
                elif type(job.trigger) == triggers.interval.IntervalTrigger:
                    trigger_type = "INTERVAL"
                elif type(job.trigger) == triggers.cron.CronTrigger:
                    trigger_type = "CRON"
                return DjangoJob.objects.create(
                    id=job.id,
                    next_run_time=get_django_internal_datetime(job.next_run_time),
                    trigger=trigger_type,
                    job_state=pickle.dumps(job.__getstate__(), self.pickle_protocol),
                )
            except IntegrityError:
                raise ConflictingIdError(job.id)

    def update_job(self, job: AppSchedulerJob):
        # Acquire lock for update
        with transaction.atomic():
            try:
                db_job = DjangoJob.objects.get(id=job.id)

                db_job.next_run_time = get_django_internal_datetime(job.next_run_time)
                db_job.job_state = pickle.dumps(
                    job.__getstate__(), self.pickle_protocol
                )

                db_job.save()

            except DjangoJob.DoesNotExist:
                raise JobLookupError(job.id)

    def remove_job(self, job_id: str):
        try:
            DjangoJob.objects.get(id=job_id).delete()
        except DjangoJob.DoesNotExist:
            raise JobLookupError(job_id)

    def remove_all_jobs(self):
        # Implicit: will also delete all DjangoJobExecutions due to on_delete=models.CASCADE
        DjangoJob.objects.all().delete()

    def shutdown(self):
        db.connection.close()

    def _reconstitute_job(self, job_state):
        job_state = pickle.loads(job_state)
        job = AppSchedulerJob.__new__(AppSchedulerJob)
        job.__setstate__(job_state)
        job._scheduler = self._scheduler
        job._jobstore_alias = self._alias

        return job

    def _get_jobs(self, **filters):
        jobs = []
        failed_job_ids = set()

        job_states = DjangoJob.objects.filter(**filters).values_list("id", "job_state")
        for job_id, job_state in job_states:
            try:
                jobs.append(self._reconstitute_job(job_state))
            except Exception:
                self._logger.exception(
                    f"Unable to restore job '{job_id}'. Removing it..."
                )
                failed_job_ids.add(job_id)

        # Remove all the jobs we failed to restore
        if failed_job_ids:
            logger.warning(f"Removing failed jobs: {failed_job_ids}")
            DjangoJob.objects.filter(id__in=failed_job_ids).delete()

        return jobs

    def __repr__(self):
        return f"<{self.__class__.__name__}(pickle_protocol={self.pickle_protocol})>"


class DjangoMemoryJobStore(DjangoResultStoreMixin, MemoryJobStore):
    """
    Adds the DjangoResultStoreMixin to the standard MemoryJobStore so that job executions can be
    logged to the Django database.
    """

    pass
