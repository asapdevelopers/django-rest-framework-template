from django.conf import settings
import imaplib
from django.utils import timezone
from email import message_from_string
from email.header import decode_header
from email.utils import getaddresses
from os.path import splitext
import datetime
import re
import time
from dateutil import parser
from logic.exceptions import ExceptionCodes, OperationError
from django.core.mail import EmailMultiAlternatives
from urllib import quote, quote_plus
from django.core.mail import get_connection
from logic.threadPool import ThreadPool
import logging
import traceback



emailSendingLogger = logging.getLogger('email.sending')

EMAIL_REPLACE_REGEX = re.compile(ur'\r|\n')
POOL = ThreadPool(workers=1)

DEFAULT_FROM_EMAIL = settings.DEFAULT_FROM_EMAIL



def _decodeString(value, charset = None):
    '''
        Given a value string and a charset, decodes it returning an unicode string.
        Uses utf-8 if no charset provided.
        If value is already an unicode string, returns the same value.        
    '''

    return value.decode(charset or "UTF-8", 'ignore') if isinstance(value, str) else value


def _decodeHeader(msg, key, defaultVal):
    '''
        Given a msg and key, tries to decode its header.
        Returns an unicode string converted based on the header charset, or utf-8 if no charset.
    '''
    
    if msg and key in msg:
        decoded = decode_header(msg[key])[0]
        return _decodeString(decoded[0], decoded[1])        
    else:
        return defaultVal


class Attachment(object):
    
    def __init__(self, name, extension, mimeType, data):
        '''
            Data must be a file like object
        '''

        if data is None:
            raise ValueError("Attachment with no data")

        self.name = name
        self.extension = extension
        self.mimeType = mimeType
        self.data = data


def _sendEmail(email, silent=True):
    '''
        Helper to call the email send object and fail silently if required.
    '''
            
    
    try:        
        email.send()        
    except Exception as e:
        emailSendingLogger.error("Failed to send email: " + unicode(e), extra={'extra': traceback.format_exc()})

        if not silent:
            raise OperationError("Failed to send email.", ExceptionCodes.emailSendingError)


def sendEmail(subject, to = None, cc = None, bcc = None,
              plainText = None, htmlText = None, attachments = None, 
              fromEmail = None, fromAccount = None, fromPassword = None, headers = None, async=True):

    '''
        Sends an email. Server and backend used is the one defined on settings: EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS
        and using the django email helpers.
            
        subject: Subject, will be escaped and new lines replaced

        to, cc, bcc: list of string emails

        plainText: email body in plain text, required.

        htmlText: email body in html, optional

        attachments: list of Attachment objects, extension wont be used. Attachment name will be escaped

        fromEmail, fromAccount, fromPassword: If not present, will be used defaults from settings, this is:
            DEFAULT_FROM_EMAIL, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD

        additional headers can be set, which are SMTP headers.

        async will control if the email is sent on a thread pool (recommended) or synchronous blocking the current thread.

        Will raise a friendly OperationError on any error when sending.

    '''

    if plainText is None:
        raise ValueError("No email text provided.")
    

    email = EmailMultiAlternatives(
        re.sub(EMAIL_REPLACE_REGEX,'', subject),
        plainText,
        from_email = fromEmail or DEFAULT_FROM_EMAIL,
        to = to,
        cc = cc,
        bcc = bcc,
        headers = headers
    )

    #if we have html body
    if htmlText is not None:
        email.attach_alternative(htmlText, "text/html")

    #If we have a different from account/password, use a different connection.
    if fromAccount and fromPassword:        
        email.connection = get_connection(username=fromAccount, password=fromPassword)
        

    if attachments:
        for a in attachments:            
            email.attach(quote_plus(a.name.encode("UTF-8","ignore")), a.data.read(), a.mimeType)  

    if async:
        POOL.apply_async(_sendEmail, (email, True))
    else:
        _sendEmail(email, False)
        
