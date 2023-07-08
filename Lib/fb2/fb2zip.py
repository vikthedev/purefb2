#!/usr/bin/python
from zipfile import ZipFile, ZIP_DEFLATED
from os.path import basename


class Fb2Zip:

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
