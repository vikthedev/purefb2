#!/usr/bin/python
import os
import re
import getopt
import shutil

from Lib.fb2.purefb2 import PureFb2
from Lib.inout import System, unixtime


class Elib2Ebook:
    def __init__(self, argv: list):
        self.__executive = 'Elib2Ebook'
        self.__destination = ''
        self.__temp = ''
        self.__arguments = []
        self.__allowed_format = ['fb2', 'fb2.zip']
        self.__format = []
        self.__without_image = False
        self.__save_temp = False
        self.__prepare_arguments(argv)
        # print([self.__executive] + self.__arguments)

    def get(self) -> None:
        result = System.exec(' '.join([self.__executive] + self.__arguments))

        if result['return_code'] == 0:
            re_success = re.compile('^Книга ".+[\\\\/]+(.+)\\.fb2" успешно сохранена$')
            re_chapters = re.compile('^Загружаю главу "(.+)"$')
            chapters = []

            for res_line in result['output']:
                if matches := re_chapters.match(res_line):
                    print('"%s" обработана' % matches.group(1))
                    chapters.append(matches.group(1))

                elif matches := re_success.match(res_line):
                    print('Книга "%s" сохранена' % matches.group(1))
                    temporary_name = f'{matches.group(1)}-{unixtime()}'
                    os.rename(os.path.join(self.__temp, f'{matches.group(1)}.fb2'),
                              os.path.join(self.__temp, f'{temporary_name}.fb2'))
                    # if os.path.isfile(os.path.join(self.__temp, f'{matches.group(1)}_cover.jpg')):
                    #     os.rename(os.path.join(self.__temp, f'{matches.group(1)}_cover.jpg'),
                    #               os.path.join(self.__temp, f'{temporary_name}.jpg'))

            fb2 = PureFb2().open('tmp/1687172810289/raw_book')
            print(fb2.get_author())
            print(fb2.get_title())
            # content = file_get_contents(os.path.join(self.__temp, 'raw_book'))
            # soup = BeautifulSoup(content, "xml")
            # save book

            # remove tmp dir
            if not self.__save_temp:
                shutil.rmtree(self.__temp)

    # Declaring private method
    def __prepare_arguments(self, argv: list) -> None:
        # Remove 1st argument from the
        # list of command line arguments (file name)
        argument_list = argv[1:]

        # Actual arguments
        argument_dict = {}

        # Options
        options = 'r:u:s:f:'

        # Long options
        long_options = ['root=', 'url=', 'save=', 'format=', 'no-image', 'save-temp', 'temp=']

        try:

            arguments, values = getopt.getopt(argument_list, options, long_options)

            # checking each argument
            for currentArgument, currentValue in arguments:
                if currentArgument in ('-r', '--root'):
                    self.__executive = os.path.join(currentValue.rstrip('"\\/'), self.__executive)
                if currentArgument in ('-u', '--url'):
                    argument_dict['u'] = '-u %s' % currentValue
                elif currentArgument in ('-s', '--save'):
                    self.__destination = os.path.join(currentValue.rstrip('"\\/'))
                elif currentArgument in ('-f', '--format'):
                    for f in currentValue.split(','):
                        if f in self.__allowed_format:
                            self.__format.append(f)
                elif currentArgument in '--no-image':
                    self.__without_image = True
                    argument_dict['ni'] = '--no-image'
                elif currentArgument in '--save-temp':
                    self.__save_temp = True
                elif currentArgument in '--temp':
                    self.__temp = os.path.join(currentValue.rstrip('"\\/'))

            if not argument_dict.get('u'):
                raise ValueError('Book Url is not specified')
            elif not self.__format:
                self.__format.append('fb2')
                # raise ValueError('Book Format(s) is not specified. Allowed "fb2, fb2.zip"')

            self.__executive = '"%s"' % self.__executive

            # save only FB2
            argument_dict['f'] = '-f fb2'
            # temp folder path
            self.__temp = os.path.join((self.__temp if self.__temp != ''
                                        else os.path.join(os.getcwd(), 'tmp')
                                        ), unixtime())
            argument_dict['tmp'] = '--temp "%s"' % self.__temp
            # save book to temp folder
            argument_dict['s'] = '-s "%s"' % self.__temp
            # save inline images
            #argument_dict['st'] = '--save-temp'
            # save cover image in file
            #argument_dict['c'] = '-c'

            # exec_string = 'Elib2Ebook.exe'
            # for argument in argument_dict:
            #     exec_string += ' ' + argument_dict[argument]
            # print(shlex.split(exec_string))

            self.__arguments = list(argument_dict.values())
        except getopt.error as err:
            print(str(err))
