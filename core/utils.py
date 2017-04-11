from builtins import object
import struct
import os
import time
import sys
import shutil
from PIL import Image
from tempfile import SpooledTemporaryFile
from zipfile import BadZipfile, ZipInfo, ZipFile, PyZipFile, LargeZipFile, ZIP64_LIMIT, zlib, crc32, ZIP_DEFLATED
from pdfrw.pdfwriter import PdfWriter, IndirectPdfDict, PdfName, \
    PdfOutputError, PdfDict, PdfString, user_fmt


class ImageThumbnail(object):
    size = (128, 128)
    max_memory_size = 1024 * 1024 * 2  # 2mb
    # Max file size to be processed, since the image data needs to be loaded completely in memory.
    max_file_size = 1024 * 1024 * 15
    format = "PNG"  # Leave None to use original format
    quality = Image.ANTIALIAS

    @classmethod
    def check_file(self, data):
        """
        Checks file constraints in order to be used as thumbnail and by the PIL library.
        """

        size = None

        if hasattr(data, 'size'):
            size = data.size
        else:

            can_seek = hasattr(data, 'tell') and hasattr(data, 'seek')

            if not can_seek:
                raise ValueError("File object must be seekable.")

            data.seek(0, os.SEEK_END)
            size = data.tell()
            data.seek(0)

        if size > self.max_file_size:
            raise ValueError("File is too big.")

    @classmethod
    def create(cls, data):
        """
        Given a file-like object, creates an image thumbnail from it, with a fixed format.
        Returns the results a temporary file that might or might not be sent to disk and the caller is
        responsable of closing it. Also returns the thumbnail picture extension (without the "." )

            data object must be already seeked to position 0
            data must be seekable or have a size property

        Will raise ValueError if file is not a valid image.
        
        """

        cls.check_file(data)

        try:
            img = Image.open(data)
        except Exception:
            raise ValueError("Invalid image file.")

        res = SpooledTemporaryFile(max_size=cls.max_memory_size, mode='w+b', prefix='thmbtemp')

        img_format = (cls.format or img.format)

        img.thumbnail(cls.size, cls.quality)
        img.save(res, format=img_format)
        res.seek(0)

        return res, img_format


class ZipFile2(ZipFile):
    """
    Wrapper class around zip file to allow writing from a stream without reading everything into memory
    """

    def write_stream(self, arcname, stream, compress_type=None):
        """
        Wriets to the zip file from a stream in an efficient way
        stream must be seekable (or contain a size property) and only files (not dirs) can be used
        """

        if not self.fp:
            raise RuntimeError("Attempt to write to ZIP archive that was already closed")

        date_time = time.localtime(time.time())[:6]

        zinfo = ZipInfo(arcname, date_time)
        zinfo.external_attr = 0o600 << 16  # ?rw-------

        if compress_type is None:
            zinfo.compress_type = self.compression
        else:
            zinfo.compress_type = compress_type

        if hasattr(stream, 'size'):
            zinfo.file_size = stream.size
        else:
            stream.seek(0, os.SEEK_END)
            zinfo.file_size = stream.tell()  # Uncompressed size
            stream.seek(0)

        zinfo.flag_bits = 0x00
        zinfo.header_offset = self.fp.tell()  # Start of header bytes

        self._writecheck(zinfo)
        self._didModify = True

        fp = stream

        # Must overwrite CRC and sizes with correct data later
        zinfo.CRC = CRC = 0
        zinfo.compress_size = compress_size = 0

        # Compressed size can be larger than uncompressed size
        zip64 = self._allowZip64 and zinfo.file_size * 1.05 > ZIP64_LIMIT
        self.fp.write(zinfo.FileHeader(zip64))
        if zinfo.compress_type == ZIP_DEFLATED:
            cmpr = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
                                    zlib.DEFLATED, -15)
        else:
            cmpr = None

        file_size = 0

        while 1:
            buf = fp.read(1024 * 64)
            if not buf:
                break
            file_size = file_size + len(buf)
            CRC = crc32(buf, CRC) & 0xffffffff
            if cmpr:
                buf = cmpr.compress(buf)
                compress_size = compress_size + len(buf)
            self.fp.write(buf)

        if cmpr:
            buf = cmpr.flush()
            compress_size = compress_size + len(buf)
            self.fp.write(buf)
            zinfo.compress_size = compress_size
        else:
            zinfo.compress_size = file_size
        zinfo.CRC = CRC
        zinfo.file_size = file_size
        if not zip64 and self._allowZip64:
            if file_size > ZIP64_LIMIT:
                raise RuntimeError('File size has increased during compressing')
            if compress_size > ZIP64_LIMIT:
                raise RuntimeError('Compressed size larger than uncompressed size')
        # Seek backwards and write file header (which will now include
        # correct CRC and file sizes)

        position = self.fp.tell()  # Preserve current position in file

        self.fp.seek(zinfo.header_offset, 0)
        self.fp.write(zinfo.FileHeader(zip64))
        self.fp.seek(position, 0)
        self.filelist.append(zinfo)
        self.NameToInfo[zinfo.filename] = zinfo


# Extend pdfrw to be able to add bookmarks and metadata

class NewPdfWriter(PdfWriter):
    _outline = None
    _info = None

    def add_bookmark(self, title, page_num, parent=None):
        """
        Adds a new bookmark entry.
        page_num must be a valid page number in the writer
        and parent can be a bookmark object returned by
        a previous add_bookmark call
        """

        try:
            page = self.pagearray[page_num]
        except IndexError:
            # TODO: Improve error handling ?            
            raise PdfOutputError("Invalid page number: %s" % (pageNum))

        parent = parent or self._outline
        if parent is None:
            parent = self._outline = IndirectPdfDict()

        bookmark = IndirectPdfDict(
            Parent=parent,
            Title=PdfString.encode(title),
            A=PdfDict(
                D=[page, PdfName.Fit],
                S=PdfName.GoTo
            )
        )

        if parent.Count:
            parent.Count += 1
            prev = parent.Last
            bookmark.Prev = prev
            prev.Next = bookmark
            parent.Last = bookmark
        else:
            parent.Count = 1
            parent.First = bookmark
            parent.Last = bookmark

        return bookmark

    def set_info(self, info):
        """
        Sets pdf metadata, info must be a dict where each key is the metadata key
        standard/known keys are:
            Title
            Author
            Creator
            Producer
        """
        # Need to encode values
        self._info = {k: PdfString.encode(v) for k, v in list(info.items())}

    def write(self, fname, trailer=None, user_fmt=user_fmt, disable_gc=True):

        # Only add info and outlines if a custom trailer is not given
        if not trailer:
            if self._info:
                self.trailer.Info = IndirectPdfDict(**self._info)

            self.trailer.Root.Outlines = self._outline

        super(NewPdfWriter, self).write(fname, trailer, user_fmt, disable_gc)
