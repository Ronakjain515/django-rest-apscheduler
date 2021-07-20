from django.db import models
from django.utils.translation import ugettext_lazy as _

import logging

from . import util

logger = logging.getLogger(__name__)

TRIGGER_TYPE = (
    ("DATE", "Date"),
    ("CRON", "Cron"),
    ("INTERVAL", "Interval")
)


class DjangoJob(models.Model):
    id = models.CharField(
        max_length=255, primary_key=True, help_text=_("Unique id for this job.")
    )

    next_run_time = models.DateTimeField(
        db_index=True,
        blank=True,
        null=True,
        help_text=_(
            "Date and time at which this job is scheduled to be executed next."
        ),
    )

    job_state = models.BinaryField()
    trigger = models.CharField(max_length=30, choices=TRIGGER_TYPE)

    def __str__(self):
        status = (
            f"next run at: {util.get_local_dt_format(self.next_run_time)}"
            if self.next_run_time
            else "paused"
        )
        return f"{self.id} ({status})"

    class Meta:
        ordering = ("next_run_time",)


class DjangoJobExecution(models.Model):
    START = "Job Added"
    SENT = "Started execution"
    SUCCESS = "Executed"
    MISSED = "Missed!"
    MAX_INSTANCES = "Max instances!"
    ERROR = "Error!"

    STATUS_CHOICES = [(x, x) for x in [START, SENT, ERROR, SUCCESS,]]

    id = models.BigAutoField(
        primary_key=True, help_text=_("Unique ID for this job execution.")
    )

    job = models.CharField(
        max_length=100,
        help_text=_("The job that this execution relates to."),
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        help_text=_("The current status of this job execution."),
    )

    run_time = models.DateTimeField(
        db_index=True, help_text=_("Date and time at which this job was added."),
    )

    type = models.CharField(
        max_length=50,
        choices=TRIGGER_TYPE,
        help_text=_("defines the trigger type of this job.")
    )

    finished = models.DateTimeField(
        null=True,
        help_text=_("Timestamp at which this job was finished."),
    )

    exception = models.CharField(
        max_length=1000,
        null=True,
        help_text=_(
            "Details of exception that occurred during job execution (if any)."
        ),
    )

    traceback = models.TextField(
        null=True,
        help_text=_(
            "Traceback of exception that occurred during job execution (if any)."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_(
            "stores created job time."
        )
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_(
            "stores last update time."
        )
    )
