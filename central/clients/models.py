from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from uuid import uuid4
from django.core.exceptions import NON_FIELD_ERRORS
from django.db import transaction
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import JSONField


class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_args):
        raise Exception("Can not create users with this method.")

    def create_superuser(self, email, password=None, **extra_args):
        raise Exception("Can not create superusers of this kind.")
        

class User(AbstractBaseUser): 

    id = models.AutoField(primary_key=True)
    email = models.CharField(max_length=250, unique=True)    
    USERNAME_FIELD = 'email'   
    
    first_name = models.CharField(max_length=250,default="", blank=True)
    last_name = models.CharField(max_length=250,default="", blank=True)    
         
    # Used for authentication
    last_password_change = models.DateTimeField(null=True, blank=True, default=timezone.now)

    is_active = models.BooleanField(default=True)       # Field required by django
    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        
    
    def get_full_name(self):
        return self.first_name + " " + self.last_name
    
    def get_short_name(self):
        return self.email

    def __unicode__(self):
        return u"User: {} - {}".format(self.pk, self.email)

