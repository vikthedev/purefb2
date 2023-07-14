#!/usr/bin/python
from zipfile import ZipFile, ZIP_DEFLATED
from os.path import basename
from io import BytesIO as StringIO

class Zipper:

    def __init__(self, source: str, destination: str):
        self.__source = source
        self.__destination = destination

    def save(self):
        with ZipFile(self.__destination + '.zip',
                     mode='w',
                     compression=ZIP_DEFLATED,
                     compresslevel=7) as zf:
            zf.write(self.__source, basename(self.__destination))
        return basename(self.__destination) + '.zip'


class InMemoryZipper(object):
    # original idea from http://stackoverflow.com/a/19722365/1307905
    def __init__(self, file_name=None, compression=None, debug=0):
        if compression is None:
            compression = ZIP_DEFLATED

        # Create the in-memory file-like object
        if hasattr(file_name, '_from_parts'):
            self._file_name = str(file_name)
        else:
            self._file_name = file_name
        self.in_memory_data = StringIO()
        # Create the in-memory zipfile
        self.in_memory_zip = ZipFile(
            self.in_memory_data, "w", compression, False)
        self.in_memory_zip.debug = debug

    def append(self, filename_in_zip, file_contents):
        '''Appends a file with name filename_in_zip and contents of
        file_contents to the in-memory zip.'''
        self.in_memory_zip.writestr(filename_in_zip, file_contents)
        return self  # so you can daisy-chain

    def write_to_file(self, filename):
        '''Writes the in-memory zip to a file.'''
        # Mark the files as having been created on Windows so that
        # Unix permissions are not inferred as 0000
        for zfile in self.in_memory_zip.filelist:
            zfile.create_system = 0
        self.in_memory_zip.close()
        with open(filename, 'wb') as f:
            f.write(self.data)

    @property
    def data(self):
        return self.in_memory_data.getvalue()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._file_name is None:
            return
        self.write_to_file(self._file_name)
