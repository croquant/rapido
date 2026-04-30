from datetime import datetime

from django.db import models
from django.db.models.fields import DateTimeField


class TimestampedModel(models.Model):
    created_at: DateTimeField[datetime] = models.DateTimeField(
        auto_now_add=True
    )
    updated_at: DateTimeField[datetime] = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
