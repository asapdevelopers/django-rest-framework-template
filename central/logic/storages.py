import boto3
from django.conf import settings
from botocore.exceptions import ClientError, BotoCoreError
from logic.exceptions import OperationError, ExceptionCodes, NotFound
from django.core.files.storage import Storage
from django.core.files.base import File #Django's File proxy
import time
import shutil
import mimetypes
from urllib import quote
from tempfile import TemporaryFile
from uuid import uuid4
from os.path import splitext, basename
from functools import partial
from django.utils.deconstruct import deconstructible
from django.core.files.utils import FileProxyMixin
import logging
from io import BufferedIOBase, BufferedReader, BufferedRandom, BytesIO

s3logger = logging.getLogger('storages.s3')


S3_KEY = settings.AWS_KEY
S3_SECRET = settings.AWS_SECRET
UPLOAD_BUCKET = settings.S3_UPLOAD_BUCKET

S3_PREFIX = settings.S3_UPLOAD_PREFIX

#Use different prefixes for dev so we have no conflicts
if settings.DEBUG:
    S3_PREFIX = S3_PREFIX + "_dev"
    

#region ---------- File names generation functions --------

#Need to create some factory classes so they can be used in models upload_to as callables.

# Example
@deconstructible
class UserProfilePictureFolder(object):
    def __init__(self):
        pass

    def __call__(self, instance, name):
        if not instance.pk:
            raise ValueError("User instance needs to be saved before saving a picture.")

        return "{0}/ppics/{2}{3}".format(S3_PREFIX, instance.pk, splitext(name)[1])


#--------------------------------------------------
#endregion


#region ---------- S3 file handling ---------------


def safeS3Path(path):
    '''
        converts a path into a safe aws s3 path doing url encoding. This is required when not using boto3 to
        generate urls.
    '''

    #Make sure we use bytes strings otherwise quote won't know how to translate them
    encoded = path.encode('utf-8') if isinstance(path, unicode) else path
    
    #replace all names between '/' with the escaped one and then join them back
    return "/".join(quote(v) for v in encoded.split('/'))


def handleException(e, reraiseMsg):
    s3logger.critical(reraiseMsg, extra={'extra':unicode(e)})    
    raise OperationError(reraiseMsg, ExceptionCodes.s3Error)


class S3StreamWrapper(BufferedIOBase):
    '''
    boto3 S3 stream wrapper that makes it usable with buffered io classes.
    This stream can not be written to and is not seekable.
    '''
    def __init__(self, body):
        self.body = body
        self.read = body.read
    
    def readable(self): return True     
       
    def close(self):                
        self.body.close()
        super(S3StreamWrapper, self).close()


class TempFileWrapper(BufferedIOBase):
    '''
    Buffered temp file wrapper so we can use io classes
    '''

    def __init__(self, raw):
        self.raw = raw
        self.read = raw.read
        self.write = raw.write      
        self._seek = raw.seek
        self.tell = raw.tell  
        
    def readable(self): return True 
    def writable(self): return True
    def seekable(self): return True
    
    def seek(self, offset, whence=0):        
        self._seek(offset, whence)
        return self.tell()
   
    def close(self):                
        self.raw.close()
        super(TempFileWrapper, self).close()


# Inherit from BufferedReader so it handles all buffering automatically from the wrapper.
class S3RawFile(BufferedReader):
    '''
    S3 Raw file with buffered reading. File is not seekable but is streamed directly from S3
    Will provide properties from s3:
        name, size, contentType, lastModified, meta
    ''' 

    def __init__(self, storage, name, stream, contentType, size, lastModified, meta):
        super(S3RawFile, self).__init__(S3StreamWrapper(stream), 64*1024)   # Larger buffer since S3 is really fast
        self.storage = storage

        self.key = name        
        self.size = size
        self.contentType = contentType
        self.lastModified = lastModified
        self.meta = meta

    # For some reason can override the name property
    @property
    def name(self):
        return self.key

    def toTemp(self):
        '''
        returns a S3TempFile version of this RawFile instance, reading the whole stream and closing
        the connection.
        '''

        res = S3TempFile(self.storage, self.name, self, self.contentType, self.size, self.lastModified, self.meta)
        self.close()
        return res


class S3TempFile(BufferedRandom):
    '''
    S3 file downloaded to a temporary local file, making it seekable
    Will provide properties from s3:
        name, size, contentType, lastModified, meta
    ''' 

    def __init__(self, storage, name, stream, contentType, size, lastModified, meta):
        self.storage = storage

        # Do memory/tempfile spooling here since we now the file size beforehand
        # so we don't have the overhead of a spooled file with auto roll

        if size > storage.maxMemoryFileSize:
            data = TemporaryFile(mode='w+b', prefix='s3temp')
            shutil.copyfileobj(stream, data, 64 * 1024) # Use a bigger buffer size
            data.seek(0)
            super(S3TempFile, self).__init__(TempFileWrapper(data))
        else:            
            data = BytesIO()
            shutil.copyfileobj(stream, data, 64 * 1024) # Use a bigger buffer size
            data.seek(0)
            super(S3TempFile, self).__init__(data)

        self.key = name        
        self.size = size
        self.contentType = contentType
        self.lastModified = lastModified
        self.meta = meta

    # For some reason can override the name property
    @property
    def name(self):
        return self.key   





@deconstructible
class BaseS3Storage(Storage):
    '''
        Base class for S3 Storage.
        Will handle all low level S3 api calls
    '''

    #----- Credentials ----
    s3Key = None
    s3Secret = None
    s3Bucket = None

    #----- Defaults ------
    #This class is intended to be overriden to create various storage backends
    #to be used with django rather than manually creating a backend.

    storageClass = 'STANDARD' #|'REDUCED_REDUNDANCY'|'STANDARD_IA'
    acl = 'private' #|'public-read'|'public-read-write'|'authenticated-read'|'aws-exec-read'|
    cacheControl = 'max-age=31536000, public'   #1 year    
    defaultContentType = "application/octet-stream"

    urlExpiration = 60*60*24              #1 day in seconds. Can be either None or False for no expiration links.
    maxMemoryFileSize = 1024*1024*10      #10mb max in memory size for downloaded files, will fallback to temp file


    #---------------------

    #The storage class can not have sensitive data on its constructor because it goes into migrations otherwise.
    def __init__(self):

        if not self.s3Key or not self.s3Secret or not self.s3Bucket:
            raise ValueError("Missing S3 credentials")


        #Store locally for faster lookups
        self.s3Bucket = self.s3Bucket

        self.s3Client = boto3.client('s3', aws_access_key_id=self.s3Key, aws_secret_access_key=self.s3Secret)        

        #Save function locally to improve performance
        self._generateSignedUrl = partial(self.s3Client.generate_presigned_url, 'get_object')

        self._putObject = partial(
                                    self.s3Client.put_object, 
                                    ACL = self.acl,
                                    Bucket = self.s3Bucket,
                                    CacheControl = self.cacheControl,
                                    StorageClass = self.storageClass
    
                            )
        self._getObject = partial(self.s3Client.get_object, Bucket = self.s3Bucket)
        self._deleteObject = partial(self.s3Client.delete_object, Bucket = self.s3Bucket)
        self._headObject = partial(self.s3Client.head_object, Bucket = self.s3Bucket)        
        self._publicUrl = u"https://{0}.s3.amazonaws.com/".format(self.s3Bucket) + "{0}"

        if self.urlExpiration:
            self._getUrl = partial(self.getPrivateUrl, expires=self.urlExpiration)

        else:
            self._getUrl = self.getPublicUrl

    def uploadFile(self, name, data, meta = None ):
        '''
            Uploads a file to S3 given its complete name and this storage bucket.
            data can be either a file like object or a byte string
            meta should be a k,v dict
        '''
        try:            
            self._putObject(
                    Body = data,
                    ContentType = mimetypes.guess_type(name,strict=False)[0] or self.defaultContentType,                
                    Key = name,
                    Metadata = meta or {},
                )
        except Exception as e:
            handleException(e, "Failed to upload file.")
            

    def downloadFile(self, name, stream = True):
        '''
            Downloads a file from s3 returning a S3RawFile or S3TempFile instance
                depending on the stream flag.
            stream: 
                if True, will download the whole file into a temporary location making it seekable and closing the connection                    
                if False, file is streamed directly from S3 but is not seekable and connection remains open                

            The caller is responsable to correctly close the returned data object

            Raises NotFound if file not found due to 404 code.
        '''

        try:
            result = self._getObject(Key=name)
        
            if stream:                
                res = S3RawFile(self, name, result['Body'], result["ContentType"], result["ContentLength"], result["LastModified"], result["Metadata"])
            else:
                res = S3TempFile(self, name, result['Body'], result["ContentType"], result["ContentLength"], result["LastModified"], result["Metadata"])
                result["Body"].close()
                
            return res

        except ClientError as e:            
            if 'ResponseMetadata' in e.response:
                status = e.response['ResponseMetadata'].get('HTTPStatusCode',None)
                if status == 404:
                    s3logger.warn("File not found at S3 when attempting download.",extra={'extra':name})
                    raise NotFound("File not found.")

            handleException(e, "Failed to download file.")
        except Exception as e:
            handleException(e, "Failed to download file.")


    def getPublicUrl(self, name):
        '''
            No checks are done if file doesn't exist.
        '''
        #return self.generateSignedUrl(Params = {"Bucket":self.s3Bucket, "Key":name}, ExpiresIn=31536000) #1 year
        return self._publicUrl.format(safeS3Path(name))

    def getPrivateUrl(self, name, expires):
        '''
            Signed url for private files with expires in seconds.
        '''
        return self._generateSignedUrl(Params = {"Bucket":self.s3Bucket, "Key":name}, ExpiresIn=expires)
    


    def deleteFile(self, name):
        '''
            Deletes a file. The s3 service doesn't seem to raise errors if file not found.
        '''
        try:
            self._deleteObject(Key=name)
        except Exception as e:
            handleException(e, "Failed to delete file.")

    def headFile(self, name):
        '''
            Performs a HEAD request to determine if a file exists and get its metadata.
            
            Returns {
                
                contentType
                size
                lastModified : datetime
                meta : object meta        

            }

            Raises NotFound if file not found due to 404 code.
        '''
        try:
            d = self._headObject(Key=name)
            return {
                'contentType':d['ContentType'],
                'size':d["ContentLength"],
                'lastModified':d['LastModified'],
                'meta':d['Metadata']
    
            }
        except ClientError as e:            
            if 'ResponseMetadata' in e.response:
                status = e.response['ResponseMetadata'].get('HTTPStatusCode',None)
                if status == 404:
                    raise NotFound("File not found.")

            handleException(e, "Failed to head file.")
        except Exception as e:
            handleException(e, "Failed to head file.")

    #---------------------------------------------------------------------------------------------

    #Override django's Storage methods so this base implementation can be used.
    #As a django storage system

    def open(self, name, mode='rb'):        
        
        # S3 doesn't care about the mode will always be 'rb'
        # But allow sending a 'stream' mode to use a different download type        
        return self.downloadFile(name)

    def save(self, name, content, max_length=None):

        if content is None:
            raise ValueError("No file given.")
    
        if name is None:
            name = content.name

        if name is None:
            raise ValueError("File to save needs a name.")
        
        self.uploadFile(name,content)

        return name

    #all names are valid for S3 although there are some recomendations
    def get_valid_name(self, name):
        return name

    #Right now any name is available and we allow override.
    #Should we perform a head and generate a random name if it already exists?
    def get_available_name(self, name, max_length=None):
        return name

    def delete(self, name):
        self.deleteFile(name)

    def path(self, name):
        return self.s3Bucket + ": " + name

    def exists(self, name):
        try:
            self.headFile(name)
            return True
        except NotFound:
            return False

    def listdir(self, path):
        """
        Lists the contents of the specified path, returning a 2-tuple of lists;
        the first item being directories, the second item being files.
        """
        #TODO: Implement this with S3 get_objects
        raise NotImplementedError('subclasses of Storage must provide a listdir() method')

    def size(self, name):
        s3logger.warn('Storage size method called instead of file.')
        return self.headFile(name)['size']
        
    
    def url(self, name):
        return self._getUrl(name)


    def head(self,name):
        '''
            Custom for this storage, allows retrieval of S3 metadata through HEAD request.
            returns{
                contentType,
                size,
                lastModified,
                meta
            }
        '''    
        return self.headFile(name)

    def generate_filename(self, filename):
        '''
        Very important override, otherwise default Storage breaks folder separators
        since we can't use them on S3
        '''
        return self.get_valid_name(filename)

    def accessed_time(self, name):
        raise NotImplementedError('Not implemented, open file and check lastModified field instead.')

    def created_time(self, name):
        raise NotImplementedError('Not implemented, open file and check lastModified field instead.')

    def modified_time(self, name):
        raise NotImplementedError('Not implemented, open file and check lastModified field instead.')

# Example
class UserPicturesStorage(BaseS3Storage):
    '''
        Storage for user profile pictures, override some defaults.
    '''
    
    s3Key = S3_KEY
    s3Secret = S3_SECRET
    s3Bucket = UPLOAD_BUCKET

    maxMemoryFileSize = 1024*1024*2      #2mb

    



#endregion
# ------------------------------------------------------------------------------

#Instantiate some storages we need

userPicturesStorage = UserPicturesStorage()
