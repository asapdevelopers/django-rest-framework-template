from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser


# custom django user manager and class
# Define any field you want.
class AdministratorManager(BaseUserManager):
    def _create_user(self, email, password=None, is_admin=False, **extra_args):
        if not email:
            msg = 'Administrators must have an email address.'
            raise ValueError(msg)

        if not password:
            msg = 'Administrators must have a password.'
            raise ValueError(msg)

        user = self.model(email=AdministratorManager.normalize_email(email), is_admin=is_admin, **extra_args)

        # Set password with this method which handles hashing
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_args):
        self._create_user(email, password, False, **extra_args)

    def create_superuser(self, email, password=None, **extra_args):
        self._create_user(email, password, True, **extra_args)


# In order for User to work with django password recovery, it needs to have 'email' and 'is_active'
# fields exactly as that.
class Administrator(AbstractBaseUser):
    email = models.CharField(max_length=250, unique=True)

    USERNAME_FIELD = 'email'

    first_name = models.CharField(max_length=250, default="", blank=True)
    last_name = models.CharField(max_length=250, default="", blank=True)

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)  # Superuser

    objects = AdministratorManager()

    class Meta:
        verbose_name = "Administrator"
        verbose_name_plural = "Administrators"

    def get_full_name(self):
        return self.first_name + " " + self.last_name

    def get_short_name(self):
        return self.email

    def __unicode__(self):
        return u"Admin: {} - {}".format(self.pk, self.email)

    @property
    def is_superuser(self):
        return self.is_admin

    @property
    def is_staff(self):
        return self.is_admin

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin
