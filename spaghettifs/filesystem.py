import os
from errno import ENOENT
from stat import S_IFDIR, S_IFREG
from time import time
import logging

from fuse import FUSE, Operations
from storage import GitStorage

log = logging.getLogger('spaghettifs.filesystem')
log.setLevel(logging.DEBUG)

class SpaghettiFS(Operations):
    def __init__(self, repo):
        self.repo = repo

    def get_obj(self, path):
        #assert(path.startswith('/'))
        obj = self.repo.get_root()
        for frag in path[1:].split('/'):
            if frag == '':
                continue
            try:
                obj = obj[frag]
            except KeyError:
                log.error('Path %s not found', repr(path))
                return None

        return obj

    def getattr(self, path, fh=None):
        obj = self.get_obj(path)
        if obj is None:
            raise OSError(ENOENT, '')

        if obj.is_dir:
            st = dict(st_mode=(S_IFDIR | 0755), st_nlink=2)
        else:
            st = dict(st_mode=(S_IFREG | 0444), st_size=obj.size)

        st['st_ctime'] = st['st_mtime'] = st['st_atime'] = time()
        return st

    def create(self, path, mode):
        parent_path, file_name = os.path.split(path)
        parent = self.get_obj(parent_path)
        parent.create_file(file_name)
        return 0

    def mkdir(self, path, mode):
        parent_path, dir_name = os.path.split(path)
        parent = self.get_obj(parent_path)
        parent.create_directory(dir_name)

    def read(self, path, size, offset, fh):
        obj = self.get_obj(path)
        if obj is None or obj.is_dir:
            return ''
        else:
            return obj.data

    def readdir(self, path, fh):
        obj = self.get_obj(path)
        return ['.', '..'] + list(obj.keys())

    def rmdir(self, path):
        obj = self.get_obj(path)
        if obj is None or not obj.is_dir:
            return

        obj.unlink()

    def truncate(self, path, length, fh=None):
        obj = self.get_obj(path)
        if obj is None or obj.is_dir:
            return

        obj.truncate(length)

    def unlink(self, path):
        obj = self.get_obj(path)
        if obj is None or obj.is_dir:
            return

        obj.unlink()

    def write(self, path, data, offset, fh):
        obj = self.get_obj(path)
        if obj is None or obj.is_dir:
            return 0

        obj.write_data(data, offset)

        return len(data)

#    access = None
    flush = None
    getxattr = None
    listxattr = None
    open = None
    opendir = None
    release = None
    releasedir = None
    statfs = None

    def __call__(self, op, path, *args):
        log.debug('FUSE api call: %r %r %r',
                  op, path, tuple(LogWrap(arg) for arg in args))
        ret = '[Unknown Error]'
        try:
            ret = super(SpaghettiFS, self).__call__(op, path, *args)
            return ret
        except OSError, e:
            ret = str(e)
            raise
        finally:
            log.debug('FUSE api return: %r %r', op, LogWrap(ret))

class LogWrap(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        if isinstance(self.value, basestring) and len(self.value) > 20:
            r = repr(self.value[:12])
            return '%s[...(len=%d)]%s' % (r[:11], len(self.value), r[-1])
        else:
            return repr(self.value)

    def __str__(self):
        return repr(self)

def mount(repo_path, mount_path, default_logging=logging.ERROR):
    if default_logging is not None:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setLevel(default_logging)
        logging.getLogger('spaghettifs').addHandler(stderr_handler)

    fs = SpaghettiFS(GitStorage(repo_path))
    return FUSE(fs, mount_path, foreground=True)
