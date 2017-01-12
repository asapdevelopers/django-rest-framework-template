from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone


class CentralErrorLog(models.Model):
    '''
        Will hold all generic errors created with the logging framework.
        This is pretty much unhandled or unexpected exceptions.
    '''
    level = models.CharField(max_length=50)
    logName = models.CharField(max_length=255,blank=True, null=True)
    fileName = models.CharField(max_length=1024,blank=True, null=True)
    lineNumber = models.IntegerField(blank=True, null=True)
    
    userId = models.IntegerField(blank=True, null=True)
    date = models.DateTimeField()
    

    message = models.CharField(max_length=10240,blank=True, null=True)
    extra = models.CharField(max_length=10240,blank=True, null=True)
    
    def __unicode__(self):
        return unicode(self.pk)

    class Meta:
        verbose_name = "Central Error Log"
        verbose_name_plural = "Central Error Logs"

