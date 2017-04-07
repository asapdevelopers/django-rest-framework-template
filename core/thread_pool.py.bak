from multiprocessing.pool import ThreadPool as TP
from django.db import connection
from django.conf import settings

'''
    Helper module to help with thread pools to offload async work
    and wrap any required connection handling.
    Will also allow to globally scale the amount of threads so users can
    start with a low value and it can changed globally after.
'''

# Use this to globally handle pool sizes.
POOL_SIZE_FACTOR = settings.THREAD_POOL_SIZE_FACTOR


# connection.close_if_unusable_or_obsolete()


def _apply_wrapper(fun, args):
    # Wrap function with connection checking before and after each call.
    try:
        connection.close_if_unusable_or_obsolete()

        return fun(*args)

    finally:
        connection.close_if_unusable_or_obsolete()


class ThreadPool(object):
    def __init__(self, workers):
        self.pool = TP(processes=workers * POOL_SIZE_FACTOR)

    def apply_async(self, fun, args=()):
        '''
            Applies fun with the given args (tuple) and returns an object
            that can be used to get the results back
            through get(timeout=0)
        '''

        return self.pool.apply_async(_apply_wrapper, (fun, args))
