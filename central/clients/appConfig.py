'''
    Django app information and initialization
'''

from django.apps import AppConfig
import sys

 
class Config(AppConfig): 
    name = 'clients'
    verbose_name = 'Clients'
         
    def ready(self):        

        if not hasattr(self, 'isStarted'):
            self.isStarted = False           

                
        #Do not run if already started or management command
        if not self.isStarted and len(sys.argv) > 0 and not sys.argv[0].endswith('manage.py'):
            #Code that needs to be ran before app start can be run here.
            pass
            
        self.isStarted = True