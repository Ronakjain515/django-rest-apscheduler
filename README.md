# django-rest-apscheduler
This package built over APScheduler and will help you to schedule task for far future. This package stores all the task in the Database like: MySQL, PostgreSQL, SQLite, and etc.
<br />
This package manages all records of tasks in the Database table. Also stores error occurred and their Traceback.
<br />
You can create Three types of jobs:
1. DateTrigger.
2. CronTrigger.
3. IntervalTrigger.

Installation
------------

```python
pip install rest-apscheduler
```

Quick start
-----------

- Add ``rest_apscheduler`` to your ``INSTALLED_APPS`` setting like this:
```python
INSTALLED_APPS = (
    # ...
    "rest_apscheduler",
)
```

- Run `python manage.py migrate` to create the django_apscheduler models.

- Now, just import ``Scheduler`` into your ``views.py`` and using this.
```python
from rest_apscheduler.scheduler import Scheduler
```

- Here's an example to use Schedule to add new Job Task. I am using ``DateTrigger`` to schedule task.
```python
    # Date Trigger
    Scheduler.add_job(
    	schedule_task,
    	trigger=DateTrigger(run_date=schedule_date),
    	replace_existing=True
    )
```
