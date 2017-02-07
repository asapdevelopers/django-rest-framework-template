import boto3
from django.conf import settings
from botocore.exceptions import ClientError, BotoCoreError
from core.exceptions import OperationError, ExceptionCodes, NotFound
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


def safe_S3_path(path):
    '''
        converts a path into a safe aws s3 path doing url encoding. This is required when not using boto3 to
        generate urls.
    '''

    #Make sure we use bytes strings otherwise quote won't know how to translate them
    encoded = path.encode('utf-8') if isinstance(path, unicode) else path
    
    #replace all names between '/' with the escaped one and then join them back
    return "/".join(quote(v) for v in encoded.split('/'))


def handle_exception(e, reraise_msg):
    s3logger.critical(reraise_msg, extra={'extra':unicode(e)})    
    raise OperationError(reraise_msg, ExceptionCodes.s3Error)


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
        name, size, content_type, last_modified, meta
    ''' 

    def __init__(self, storage, name, stream, content_type, size, last_modified, meta):
        super(S3RawFile, self).__init__(S3StreamWrapper(stream), 64*1024)   # Larger buffer since S3 is really fast
        self.storage = storage

        self.key = name        
        self.size = size
        self.content_type = content_type
        self.last_modified = last_modified
        self.meta = meta

    # For some reason can override the name property
    @property
    def name(self):
        return self.key

    def to_temp(self):
        '''
        returns a S3TempFile version of this RawFile instance, reading the whole stream and closing
        the connection.
        '''

        res = S3TempFile(self.storage, self.name, self, self.content_type, self.size, self.last_modified, self.meta)
        self.close()
        return res


class S3TempFile(BufferedRandom):
    '''
    S3 file downloaded to a temporary local file, making it seekable
    Will provide properties from s3:
        name, size, content_type, last_modified, meta
    ''' 

    def __init__(self, storage, name, stream, content_type, size, last_modified, meta):
        self.storage = storage

        # Do memory/tempfile spooling here since we now the file size beforehand
        # so we don't have the overhead of a spooled file with auto roll

        if size > storage.max_memory_file_size:
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
        self.content_type = content_type
        self.last_modified = last_modified
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
    s3_key = None
    s3_secret = None
    s3_bucket = None

    #----- Defaults ------
    #This class is intended to be overriden to create various storage backends
    #to be used with django rather than manually creating a backend.

    storage_class = 'STANDARD' #|'REDUCED_REDUNDANCY'|'STANDARD_IA'
    acl = 'private' #|'public-read'|'public-read-write'|'authenticated-read'|'aws-exec-read'|
    cache_control = 'max-age=31536000, public'   #1 year    
    default_content_type = "application/octet-stream"

    url_expiration = 60*60*24              #1 day in seconds. Can be either None or False for no expiration links.
    max_memory_file_size = 1024*1024*10      #10mb max in memory size for downloaded files, will fallback to temp file


    #---------------------

    #The storage class can not have sensitive data on its constructor because it goes into migrations otherwise.
    def __init__(self):

        if not self.s3_key or not self.s3_secret or not self.s3_bucket:
            raise ValueError("Missing S3 credentials")


        #Store locally for faster lookups
        self.s3_bucket = self.s3_bucket

        self.s3_client = boto3.client('s3', aws_access_key_id=self.s3_key, aws_secret_access_key=self.s3_secret)        

        #Save function locally to improve performance
        self._generate_signed_url = partial(self.s3_client.generate_presigned_url, 'get_object')

        self._put_object = partial(
                                    self.s3_client.put_object, 
                                    ACL = self.acl,
                                    Bucket = self.s3_bucket,
                                    CacheControl = self.cache_control,
                                    StorageClass = self.storage_class
    
                            )
        self._get_object = partial(self.s3_client.get_object, Bucket = self.s3_bucket)
        self._delete_object = partial(self.s3_client.delete_object, Bucket = self.s3_bucket)
        self._head_object = partial(self.s3_client.head_object, Bucket = self.s3_bucket)        
        self._public_url = u"https://{0}.s3.amazonaws.com/".format(self.s3_bucket) + "{0}"

        if self.url_expiration:
            self._get_url = partial(self.get_private_url, expires=self.url_expiration)

        else:
            self._get_url = self.get_public_url

    def upload_file(self, name, data, meta = None ):
        '''
            Uploads a file to S3 given its complete name and this storage bucket.
            data can be either a file like object or a byte string
            meta should be a k,v dict
        '''
        try:            
            self._put_object(
                    Body = data,
                    ContentType = mimetypes.guess_type(name,strict=False)[0] or self.default_content_type,                
                    Key = name,
                    Metadata = meta or {},
                )
        except Exception as e:
            handle_exception(e, "Failed to upload file.")
            

    def download_file(self, name, stream = True):
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
            result = self._get_object(Key=name)
        
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

            handle_exception(e, "Failed to download file.")
        except Exception as e:
            handle_exception(e, "Failed to download file.")


    def get_public_url(self, name):
        '''
            No checks are done if file doesn't exist.
        '''
        #return self.generate_signed_url(Params = {"Bucket":self.s3_bucket, "Key":name}, ExpiresIn=31536000) #1 year
        return self._public_url.format(safe_S3_path(name))

    def get_private_url(self, name, expires):
        '''
            Signed url for private files with expires in seconds.
        '''
        return self._generate_signed_url(Params = {"Bucket":self.s3_bucket, "Key":name}, ExpiresIn=expires)
    


    def delete_file(self, name):
        '''
            Deletes a file. The s3 service doesn't seem to raise errors if file not found.
        '''
        try:
            self._delete_object(Key=name)
        except Exception as e:
            handle_exception(e, "Failed to delete file.")

    def head_file(self, name):
        '''
            Performs a HEAD request to determine if a file exists and get its metadata.
            
            Returns {
                
                content_type
                size
                last_modified : datetime
                meta : object meta        

            }

            Raises NotFound if file not found due to 404 code.
        '''
        try:
            d = self._head_object(Key=name)
            return {
                'content_type':d['ContentType'],
                'size':d["ContentLength"],
                'last_modified':d['LastModified'],
                'meta':d['Metadata']
    
            }
        except ClientError as e:            
            if 'ResponseMetadata' in e.response:
                status = e.response['ResponseMetadata'].get('HTTPStatusCode',None)
                if status == 404:
                    raise NotFound("File not found.")

            handle_exception(e, "Failed to head file.")
        except Exception as e:
            handle_exception(e, "Failed to head file.")

    #---------------------------------------------------------------------------------------------

    #Override django's Storage methods so this base implementation can be used.
    #As a django storage system

    def open(self, name, mode='rb'):        
        
        # S3 doesn't care about the mode will always be 'rb'
        # But allow sending a 'stream' mode to use a different download type        
        return self.download_file(name)

    def save(self, name, content, max_length=None):

        if content is None:
            raise ValueError("No file given.")
    
        if name is None:
            name = content.name

        if name is None:
            raise ValueError("File to save needs a name.")
        
        self.upload_file(name,content)

        return name

    #all names are valid for S3 although there are some recomendations
    def get_valid_name(self, name):
        return name

    #Right now any name is available and we allow override.
    #Should we perform a head and generate a random name if it already exists?
    def get_available_name(self, name, max_length=None):
        return name

    def delete(self, name):
        self.delete_file(name)

    def path(self, name):
        return self.s3_bucket + ": " + name

    def exists(self, name):
        try:
            self.head_file(name)
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
        return self.head_file(name)['size']
        
    
    def url(self, name):
        return self._get_url(name)


    def head(self,name):
        '''
            Custom for this storage, allows retrieval of S3 metadata through HEAD request.
            returns{
                content_type,
                size,
                last_modified,
                meta
            }
        '''    
        return self.head_file(name)

    def generate_filename(self, filename):
        '''
        Very important override, otherwise default Storage breaks folder separators
        since we can't use them on S3
        '''
        return self.get_valid_name(filename)

    def accessed_time(self, name):
        raise NotImplementedError('Not implemented, open file and check last_modified field instead.')

    def created_time(self, name):
        raise NotImplementedError('Not implemented, open file and check last_modified field instead.')

    def modified_time(self, name):
        raise NotImplementedError('Not implemented, open file and check last_modified field instead.')

# Example
class UserPicturesStorage(BaseS3Storage):
    '''
        Storage for user profile pictures, override some defaults.
    '''
    
    s3_key = S3_KEY
    s3_secret = S3_SECRET
    s3_bucket = UPLOAD_BUCKET

    max_memory_file_size = 1024*1024*2      #2mb

    



#endregion
# ------------------------------------------------------------------------------

#Instantiate some storages we need

user_picture_storage = UserPicturesStorage()
