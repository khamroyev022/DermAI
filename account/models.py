from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    email = models.EmailField(blank=True)
    def __str__(self):
        return self.username
    class Meta:
        db_table = 'user'
        verbose_name = 'user'
        verbose_name_plural = 'users'



