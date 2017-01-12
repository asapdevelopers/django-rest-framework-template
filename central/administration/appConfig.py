'''
    Django app information and initialization
'''

from django.apps import AppConfig
 

 
class Config(AppConfig): 
    name = 'administration'
    verbose_name = 'Central Administration'
         
    def ready(self):        

        if not hasattr(self, 'isStarted'):
            self.isStarted = False           
        
        if not self.isStarted:
            #Code that needs to be ran before app start can be run here.
            pass
            
        self.isStarted = True