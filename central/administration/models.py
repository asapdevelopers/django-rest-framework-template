from django.db import models
from django.contrib.auth.models import  BaseUserManager, AbstractBaseUser


#custom django user manager and class
#Define any field you want.
class AdministratorManager(BaseUserManager):

    def _createUser(self, email, password=None, isAdmin = False, **extraArgs):
        if not email:
            msg = 'Administrators must have an email address.'
            raise ValueError(msg)
            
        if not password:
            msg = 'Administrators must have a password.'
            raise ValueError(msg)
               

        user = self.model(email=AdministratorManager.normalize_email(email), is_admin = isAdmin, **extraArgs)

        #Set password with this method which handles hashing
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extraArgs):
        self._createUser(email, password, False, **extraArgs)

    def create_superuser(self, email, password=None, **extraArgs):
        self._createUser(email, password, True, **extraArgs)
        

#In order for User to work with django password recovery, it needs to have 'email' and 'is_active' fields exactly as that.
class Administrator(AbstractBaseUser):    
    email = models.CharField(max_length=250, unique=True)
    
    USERNAME_FIELD = 'email'
    
    firstName = models.CharField(max_length=250,default="", blank=True)
    lastName = models.CharField(max_length=250,default="", blank=True)

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)   #Superuser
    
    objects = AdministratorManager()

    class Meta:
        verbose_name = "Administrator"
        verbose_name_plural = "Administrators"
        
    
    def get_full_name(self):
        return self.firstName + " " + self.lastName
    
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

