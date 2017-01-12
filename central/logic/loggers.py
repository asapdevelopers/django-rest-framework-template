import logging
import sys
import locale
from django.utils import timezone
from logic.threadPool import ThreadPool

#Use a thread pool to offload db logs 
#so we can bypass any existing transaction. Otherwise logs would get rolled back.
#We will have 1 pool per server process so it should be enough
POOL_SIZE = 1
pool = ThreadPool(workers=POOL_SIZE)

if sys.stdout.isatty():
    default_encoding = sys.stdout.encoding
else:
    default_encoding = locale.getpreferredencoding()


#Helper to wrap the model.save method inside a try catch as it could fail as well.
def wrapper(f):
    try:
        f()
    except Exception as e:        
        print (u"Error Saving log: " + unicode(e)).encode(default_encoding,"replace")


class ConsoleLogger(logging.Handler):
    '''
        Just logs to console
    '''
   
    def __init__(self):    
        logging.Handler.__init__(self)
        
    def emit(self, record):       
        print self.format(record).encode(default_encoding,"replace")


class CentralErrorLogger(logging.Handler): 
    '''
        Logs to the central error log db table.
    '''   

    logModel = None

    @classmethod
    def getLogModel(cls):
        '''
            Need to lazy load model.
        '''

        if not cls.logModel:
            from logsApp.models import CentralErrorLog
            cls.logModel = CentralErrorLog
        return cls.logModel

   
    def __init__(self):    
        logging.Handler.__init__(self)
        
    def emit(self, record):       
        try:
            cls = self.getLogModel()

            extra = getattr(record,'extra', None)
            userId = getattr(record,'userId', None)

            # If no extra data, try to get data from request if the logger has it
            if not extra:
                request = getattr(record, 'request', None)
    
                if request:
                    
                    try:
                        data = getattr(request, 'data', '')
                        xff = request.META.get('HTTP_X_FORWARDED_FOR')
                        remoteAddr = request.META.get('REMOTE_ADDR')
                        extra = u"[{}] {}\n{}\n{} - {}".format(request.method, request.path, data, xff, remoteAddr)
                    except Exception as e:
                        extra = "Failed to get extra request data: " + unicode(e)
                    
            t = cls(
                level = record.levelname,
                logName = record.name,
                fileName = record.filename,
                lineNumber = record.lineno,                
                userId = userId,
                date=timezone.now(), 
                message=self.format(record)[:2048],
                extra = extra[:2048] if extra else None
            )
            
            pool.apply_async(wrapper, args=(t.save,))
            
        except Exception as er:
            print (u"Error Logging central: " + unicode(er)).encode(default_encoding,"replace")


