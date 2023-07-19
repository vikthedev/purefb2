#!/usr/bin/python

__all__ = "PureFb2"

import os
import base64
import io
import re
import sys
import xml.dom.minidom as xmldom

from datetime import datetime
from typing import Self, Optional

from PIL import Image
from bs4 import BeautifulSoup, Tag, NavigableString

from Lib.fb2.atinfo import ATInfo
from Lib.fb2.zipper import InMemoryZipper, Zipper
from Lib.transliterator import to_latin
from Lib.typus import ru_typus

WHSP = '\u0020'  # SPACE
NBSP = '\u00A0'  # NO-BREAK SPACE
NNBSP = '\u202F'  # NARROW NO-BREAK SPACE
THNSP = '\u2009'  # THIN SPACE
ANYSP = r'[{}{}{}{}]'.format(WHSP, NBSP, NNBSP, THNSP)

HMINUS = '-'  # HYPHEN-MINUS
MINUS = '−'  # MINUS
FDASH = '‒'  # FIGURE DASH
NDASH = '–'  # EN DASH
MDASH = '—'  # EM DASH
# TMDASH = '⸺'  # TWO-EM DASH
ANYDASH = r'[{}{}{}{}{}]'.format(HMINUS, MINUS, FDASH, NDASH, MDASH)
# MDASH_PAIR = NNBSP + MDASH + THNSP
MDASH_PAIR = NBSP + MDASH + WHSP

ANYSUB = r'(?:[\*_~\{}\{}\{}\{}\{}] ?)'.format(HMINUS, MINUS, FDASH, NDASH, MDASH)


def max_filename_length(path):
    """
    Query filesystem for maximum filename length (e.g. AUFS has 242).
    """
    try:
        return os.pathconf(path, 'PC_NAME_MAX')
    except Exception:
        return 255  # Should be safe on most backends


def clear_tags(parent: Tag | NavigableString, name: str) -> None:
    """

    :param soup:
    :param parent:
    :param name:
    :return:
    """
    for tag in parent.find_all(name):
        tag.decompose()


def append_tags(soup: BeautifulSoup, parent: Tag | NavigableString, name: str, values: list) -> None:
    """
    Appends multiple tags inside parent tag to the end

    :param soup: BeautifulSoup object
    :param parent: Parent node
    :param name: Tag name
    :param values: Multiple Tag values
    :return:
    """
    for value in values:
        append_tag(soup, parent, name, value)


def append_tag(soup: BeautifulSoup, parent: Tag | NavigableString, name: str, value: str | list) -> None:
    """
    Appends tag inside parent tag to the end

    :param soup: BeautifulSoup object
    :param parent: Parent node
    :param name: Tag name
    :param value: Tag value
    :return:
    """
    tag = soup.new_tag(name)
    if isinstance(value, str):
        tag.string = value
    elif isinstance(value, list) and len(value) == 3:
        tag[value[0]] = value[1]
        tag.string = value[2]
    parent.append(tag)


def get_namespaces(soap: BeautifulSoup, as_string: bool = False) -> dict | str:
    """
    :param soap: BeautifulSoup object
    :return: list of namespaces
    """
    namespaces = {}
    namespaces_str = ''
    for ns in soap.find("FictionBook").attrs.items():
        #namespaces.append(f'{ns[0]}="{ns[1]}"')
        _ns = ns[0].split(':')
        namespaces[ns[1]] = _ns[1] if len(_ns) == 2 else ''
        namespaces_str += f' {ns[0]}="{ns[1]}"'
    # namespaces = list([f'xmlns{ns[1]}="{ns[0]}"' for ns in namespaces])
    return namespaces_str if as_string else namespaces


def normalize_text(data: str = '', strip_dots: bool = False, check_single_letters: bool = False) -> str:
    data = re.sub(r'(?<![\.\?\!])\.{2,5}(?!\.)', '…', data).replace('Ё', 'Е').replace('ё', 'е').strip().strip('_ ')
    if strip_dots:
        if not check_single_letters or (check_single_letters and not re.match(r'^(\w\.\s*)+$', data)):
            data = data.rstrip('…._ ')
    return data


def file_safe(data: str = '') -> str:
    data = re.sub(r'["\\?!@#$%^&*_+|/:;\[\]{}<>]', '', data)
    data = re.sub(r'[{}{}{}{}{}]'.format('-', '−', '‒', '–', '—'), '-', data)
    data = re.sub(r'\s+', ' ', data)
    return data.strip('. _')


def prettify_fb2(data: str = '', indent: int = 1):
    """Prettify FB2 XML with intelligent inline tags.

    :param data: XML text to prettify.
    :param indent: Set size of XML tag indents.
    :return: Prettified XML.
    """
    doc = xmldom.parseString(data)

    data = doc.toprettyxml(indent=' ' * indent)
    # data = doc.toprettyxml(indent=' ' * indent, encoding='utf-8').decode()

    # fix quotes in attributes
    # https://stackoverflow.com/questions/61590447/disable-escaping-when-pretty-printing-an-xml-with-python-elementtree-and-minidom
    data = re.sub(
        r'({0})="(.+?)"'.format('|'.join(['name', 'value', 'prefix', 'localName', 'ownerDocument', 'ownerElement'])),
        lambda m: '{}="{}"'.format(m.group(1), m.group(2).replace('&quot;', '&#34;')),
        data)

    replaces: list = []

    # inline all tags
    replaces.append([r'>\n\s*([^<>\s].*?)\n\s*</', r'>\g<1></', re.DOTALL])
    # whitespaces
    replaces.append([r'^[\s\n]*$', '', re.MULTILINE])
    # empty tags
    replaces.append([r'(<[^/]*?>)(\n|\s)*(</)', r'\g<1>\g<3>', re.MULTILINE])
    # blankline
    replaces.append([r'(>)\n$', r'\g<1>', re.MULTILINE])

    # Inlining common inline elements
    # inline start
    replaces.append([r'[\n\s]*(<(strong|emphasis|strikethrough|sup|sub|code)>)[\n\s]*', r' \g<1>', re.DOTALL])
    # inline a start
    replaces.append([r'[\n\s]*(<a .+?>)[\n\s]*', r' \g<1>', re.DOTALL])
    # Removes whitespace between end of inline tags and beginning of new tag
    # inline end
    replaces.append([r'[\n\s]*(</(strong|a|emphasis|strikethrough|sup|sub|code)>)[\n\s]*(?=<)', r'\g<1>', re.DOTALL])
    # Adds a space between the ending inline tags and following words
    # inline WHSP
    replaces.append(
        [rf'[\n\s]*(</(strong|a|emphasis|strikethrough|sup|sub|code)>)([a-zA-Zа-яґіїєА-ЯҐІЇЄ0-9])',
         rf'\g<1>{WHSP}\g<3>',
         re.DOTALL])
    # Adds a no breakable space between the ending inline tags and following dash
    # inline NBSP
    replaces.append(
        [rf'[\n\s]*(</(strong|a|emphasis|strikethrough|sup|sub|code)>)({ANYDASH})', rf'\g<1>{NBSP}\g<3>', re.DOTALL])
    # Removes spaces between nested inline tags
    # nested spaces start
    replaces.append([r'(<[^/]*?>) (?=<)', r'\g<1>'])

    # Removes spaces between nested end tags--which don't have attributes
    # so can be differentiated by string only content
    # nested spaces end
    replaces.append([r'(</\w*?>) (?=</)', r'\g<1>'])

    # quot
    replaces.append([r'(&quot;)', '"'])
    # encoding
    replaces.append([r'(<\?xml.+?)\?>', r'\g<1>encoding="utf-8"?>'])

    return process_replaces(data, replaces)


def process_replaces(data: str = '', replaces: Optional[list] = None):
    if replaces is None:
        replaces = []
    if data:
        for r in replaces:
            replace = r[1] if len(r) > 1 else ''
            flags = r[2] if len(r) > 2 else re.NOFLAG
            if len(r) > 3 and r[3] == 'UNTIL_FOUND':
                while re.search(f'{r[0]}', data, flags):
                    data = re.sub(f'{r[0]}', replace, data, 0, flags)
            else:
                data = re.sub(f'{r[0]}', replace, data, 0, flags)
    return data


def empty_if_none(data: str) -> str:
    return '' if data is None or data.strip() == '' else data


class PureFb2:
    __source: bytes | str
    __destination: str
    __finished: bool | None
    __soup: BeautifulSoup | None

    def __init__(self, source: str = '', destination: str = ''):
        self._debug = False
        self._time_modified = None
        self._time_created = None
        self._custom_tags: list = []
        self._authors_dict: dict = {}
        self._author_replaces: list = []
        self._document_info: list = []
        self._out_format: list = ['fb2']
        self._out_name_format: str = '{author_lf} - {title}'
        self._atinfo: Optional[ATInfo] = None
        self._at_ready: bool = True
        self.__source = source
        self.__destination = destination
        self.__finished = None
        self.__soup = None

    @property
    def out_format(self) -> list:
        return self._out_format

    @out_format.setter
    def out_format(self, out_format: list | str) -> None:
        self._out_format = []
        if isinstance(out_format, str):
            out_format = [out_format]
        if 'fb2' in out_format:
            self._out_format.append('fb2')
        if 'zip' in out_format:
            self._out_format.append('zip')

    @property
    def name_format(self) -> str:
        return self._out_name_format

    @name_format.setter
    def name_format(self, _out_name_format: str) -> None:
        self._out_name_format = _out_name_format

    @property
    def author(self) -> str:
        return self.__get_author()

    @property
    def author_last_first(self) -> str:
        return self.__get_author(True)

    @property
    def authors(self) -> list:
        return self.__get_authors()

    @property
    def authors_plain(self) -> list:
        return self.__get_authors_plain('{first_name} {last_name}')

    @property
    def authors_last_name_plain(self) -> list:
        return self.__get_authors_plain('{last_name}')

    @property
    def genres(self) -> list:
        return self.__get_genres()

    @property
    def title(self) -> str:
        return self.__get_title()

    @title.setter
    def title(self, title: str) -> None:
        if self.is_opened():
            self.__soup.select_one('book-title').string.replace_with(title)

    @property
    def last_chapter_title(self) -> str:
        return self.__get_last_chapter_title()

    @property
    def url(self) -> str:
        return self.__get_url()

    @property
    def time_created(self) -> str:
        return empty_if_none(self._time_created)

    @property
    def time_modified(self) -> str:
        return empty_if_none(self._time_modified)

    @property
    def sequence(self) -> Optional[dict]:
        return self.__get_sequence()

    @sequence.setter
    def sequence(self, sequence: dict) -> None:
        if self.is_opened() and self.__soup.select_one('sequence'):
            self.__soup.sequence['name'] = sequence['name']
            self.__soup.sequence['number'] = sequence['number']

    @property
    def chapters(self) -> list:
        return self.__get_chapters()

    @property
    def finished(self) -> bool:
        return self.__check_finished_state()

    @property
    def donated(self) -> bool:
        return self.__check_donated_state()

    @property
    def authors_dict(self) -> dict:
        return self._authors_dict

    @authors_dict.setter
    def authors_dict(self, authors_dict: dict) -> None:
        self._authors_dict = authors_dict

    @property
    def atinfo(self) -> ATInfo:
        return self._atinfo

    @atinfo.setter
    def atinfo(self, url: str) -> None:
        if self.is_opened():
            self._atinfo = ATInfo().available(self._at_ready).get(url)

    def at_ready(self, ready: bool = True) -> Self:
        self._at_ready = ready
        return self

    def has_author(self, name: str) -> bool:
        result: bool = False
        name = re.sub(r'\s+', ' ', name.strip())
        authors: list = self.authors
        for first_name, middle_name, last_name, home_page in authors:
            author_name = f'{first_name} {middle_name} {last_name}'.replace('  ', ' ').strip()
            if name.lower() == author_name.lower():
                result = True
                break
        return result

    def get_file_name(self) -> str:

        file_name = file_safe(self.name_format.format(
            author=self.author,
            author_lf=self.author_last_first,
            title=self.title,
            seq_name=self.sequence['name'],
            seq_num=self.sequence['number'],
            current_time=self._time_created,
            current_date=datetime.now().strftime('%Y-%m-%d'),
            book_time=self._time_modified
        ))

        if len(file_name.encode("utf-8")) > (max_filename_length(file_name) - 8):  # 8 = '.fb2.zip'
            file_name = file_name.encode("utf-8")[0:(max_filename_length(file_name) - 8)].decode('utf-8')

        return file_name

    def open_zip(self, source: str | bytes) -> Self:
        source = Zipper(io.BytesIO(source) if isinstance(source, bytes) else source).open().encode('utf-8')
        return self.open(source)

    def open(self, source: str | bytes | bytearray) -> Self:
        if isinstance(source, bytearray):
            source = bytes(source)
        if isinstance(source, str) and source.endswith('.zip'):
            source = Zipper(source).open().encode('utf-8')
        if isinstance(source, bytes) and "<?xml" not in str(source[:10]):
            source = Zipper(io.BytesIO(source)).open().encode('utf-8')

        if source:
            self.__source = source
        if self.__source:

            try:
                if isinstance(source, bytes) and '' != (file := source.decode('utf-8')):
                    if self._debug:
                        print('Got from bytes')
                    self.__soup = BeautifulSoup(file, "xml")
                    self.atinfo = self.url
                else:
                    if self._debug:
                        print('Got from file')
                    with open(self.__source, 'r+', encoding='utf-8') as file:
                        self.__soup = BeautifulSoup(file, "xml")
                        self.atinfo = self.url
            except EnvironmentError as err:
                print(f'Book opening Error: {err}')
                pass
            # sys.exit()
        return self if self.is_opened else False

    def is_opened(self) -> bool:
        return self.__soup is not None

    def save(self, destination: Optional[str] = '', **args) -> Self:
        if self.__soup is not None:

            self._time_created = datetime.now().strftime('%Y-%m-%d %H:%M')
            self._time_modified = self.atinfo.time_updated if self.atinfo.is_valid() else self._time_created

            if destination != '':
                self.__destination = destination
                self.__process_title_info()
                self.__process_document_info()
                self.__process_custom()
                self.__process_body(args.get('typography', True))
                self.__process_promo(args.get('promo', True))
                self.__optimize_images(args.get('image', True))

                file_name = self.get_file_name()

                # full_name = os.path.basename(self.__destination)

                if args.get('prettify', True):
                    xml = prettify_fb2(str(self.__soup.prettify()))
                else:
                    xml = str(self.__soup)

                if self.__destination is None:
                    if 'zip' in self.out_format:
                        if self._debug:
                            print(os.path.join(self.__destination, file_name + '.fb2.zip'))
                        with InMemoryZipper(None) as imz:
                            imz.append(to_latin(file_name, 'lower', True) + '.fb2', xml)
                        self.__source = imz.data
                    else:
                        self.__source = bytes(xml, 'utf-8')
                else:
                    try:
                        if 'zip' in self.out_format:
                            if self._debug:
                                print(os.path.join(self.__destination, file_name + '.fb2.zip'))
                            with InMemoryZipper(os.path.join(self.__destination, file_name + '.fb2.zip')) as imz:
                                imz.append(to_latin(file_name, 'lower', True) + '.fb2', xml)
                    except EnvironmentError as err:
                        print(f'Saving book to ZIP Error: {err}')
                        pass

                    try:
                        if 'fb2' in self.out_format:
                            if self._debug:
                                print(os.path.join(self.__destination, file_name + '.fb2'))
                            with open(os.path.join(self.__destination, file_name + '.fb2'), 'w+',
                                      encoding='utf-8') as file:
                                file.write(xml)
                    except EnvironmentError as err:
                        print(f'Saving book to FB2 Error: {err}')
                        pass
        return self

    def get_source(self) -> str | bytes:
        return self.__source

    def __process_body(self, typography: bool = True) -> None:
        # it was the BAD idea to process each paragraph separately
        # VERY, VERY SLOW! :(
        # Let's proceed whole body!
        for body in self.__soup.find_all('body'):
            new_body = str(body)

            replaces = []

            # author specific replaces
            if self.atinfo.is_valid() and self._author_replaces:
                for ar in self._author_replaces:
                    if self.has_author(ar.get('name')):
                        if self._debug:
                            print('APPLIED: ' + ar.get('name'))
                        for arp in ar.get('patterns'):
                            replaces.append(arp)

            replaces = self.__optimize_global(replaces)

            new_body = process_replaces(new_body, replaces)

            if typography:
                new_body = re.sub(r'<p>([\s\S]+?)</p>', lambda x: ru_typus(x.group()), new_body)
                # Special case with leading punctuation
                # см. http://old-rozental.ru/punctuatio.php?sid=176
                # new_body = re.sub(r'([,\.!\?;]) — ', r'\g<1> — ', new_body)
            soup = BeautifulSoup(f'<xml {get_namespaces(self.__soup, True)}>{new_body}</xml>', 'xml')
            new_body = soup.select_one('xml')
            body.replace_with(new_body)
            new_body.unwrap()

    def set_authors_dict(self, authors_dict: dict) -> Self:
        self.authors_dict = authors_dict
        return self if self.is_opened else False

    def set_document_info(self, document_info: dict) -> Self:
        self._document_info = document_info
        return self if self.is_opened else False

    def set_out_format(self, out_format: list | str) -> Self:
        self.out_format = out_format
        return self if self.is_opened else False

    def set_name_format(self, out_name_format: str) -> Self:
        self.name_format = out_name_format
        return self if self.is_opened else False

    def add_custom_tag(self, name: str, value: str, override: bool = False) -> Self:
        exists = False
        for custom in self._custom_tags:
            if custom[1] == name:
                if override:
                    custom[2] = value
                exists = True
                break
        if not exists:
            self._custom_tags.append(['info-type', name, value])
        if self._debug:
            print(f'{name}: {value}')
            print(self._custom_tags)
        return self

    def set_author_replaces(self, author_replaces: list) -> Self:
        self._author_replaces = author_replaces
        return self if self.is_opened else False

    def set_debug(self, debug: bool = False) -> Self:
        self._debug = debug
        return self if self.is_opened else False

    def __process_title_info(self) -> None:
        if self.__soup is not None:
            if (parent := self.__soup.find('title-info')) is None:
                parent = self.__soup.new_tag('title-info')
                self.__soup.find('description').insert(1, parent)
            self.__process_title()
            self.__process_sequence()
            self.__process_genres()
            self.__process_authors()
            self.__process_date(parent)

    def __process_title(self):
        self.title = self.__get_title(True)

    def __process_sequence(self):
        self.sequence = self.__get_sequence(True)

    def __process_genres(self) -> None:
        genres: list = self.genres if not (
                self.atinfo.is_valid() and (at_genres := self.atinfo.genres_en)) else at_genres
        if len(genres):
            parent = self.__soup.find('title-info')
            clear_tags(parent, 'genre')
            append_tags(self.__soup, parent, 'genre', genres)

    def __get_genres(self) -> list:
        genres: list = []
        if self.__soup is not None:
            for genre in self.__soup.find('title-info').find_all('genre'):
                genres.append(genre.text)
        return genres

    def __process_authors(self) -> None:
        authors: list = self.authors if not (self.atinfo.is_valid() and (at_atrs := self.atinfo.authors)) else at_atrs
        if len(authors):
            clear_tags(self.__soup.find('title-info'), 'author')
            root = self.__soup.find('title-info').find('book-title')
            # we will add each author at the top of position so let's reverce the list first
            authors.reverse()
            for first_name, middle_name, last_name, home_page in authors:
                author_name = f'{first_name} {middle_name} {last_name}'.replace('  ', ' ').strip()
                if (author_name := self.authors_dict.get(author_name, None)) is not None:
                    first_name, middle_name, last_name, home_page = self.__split_dict_author(author_name, home_page)
                tag = self.__soup.new_tag('author')
                # root.append(tag)
                root.insert_after(tag)

                if first_name != '':
                    append_tag(self.__soup, tag, 'first-name', first_name)
                if middle_name != '':
                    append_tag(self.__soup, tag, 'middle-name', middle_name)
                if last_name != '':
                    append_tag(self.__soup, tag, 'last-name', last_name)
                if home_page != '':
                    append_tag(self.__soup, tag, 'home-page', home_page)
        return

    def __get_author(self, last_first: bool = False, safe: bool = True) -> str:
        author = self.__get_authors(True, safe)
        if len(author):
            first_name, middle_name, last_name, home_page = author[0]
            author = (f"{last_name} {first_name}" if last_first else f"{first_name} {last_name}").strip()
        else:
            author = ''
        return author

    def __get_authors(self, only_one: bool = False, safe: bool = True) -> list:
        authors: list = []
        if self.__soup is not None:
            for author in self.__soup.find('title-info').find_all('author'):
                first_name = author.select_one('first-name')
                middle_name = author.select_one('middle-name')
                last_name = author.select_one('last-name')
                home_page = author.select_one('home-page')
                authors.append([
                    normalize_text(first_name.text, safe, True) if first_name is not None else '',
                    normalize_text(middle_name.text, safe, True) if middle_name is not None else '',
                    normalize_text(last_name.text, safe, True) if last_name is not None else '',
                    home_page.text if home_page is not None else ''
                ])
                if only_one:
                    break
        return authors

    def __get_authors_plain(self, author: str = '{first_name} {last_name}') -> list:
        authors: list = self.authors
        authors_plain: list = []
        for first_name, middle_name, last_name, home_page in authors:
            if last_name == '' and author.find('{last_name}') != -1 and author.find('{first_name}') == -1:
                last_name = first_name
            authors_plain.append(author.format(
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name
            ).replace('  ', ' ').strip())
        return authors_plain

    def __split_dict_author(self, name: str, homepage: str) -> Optional[list]:
        """
        :param name: Combined Author's full name
        :param homepage: Author's homepage
        :return: list[first-name, middle-name, last-name, home-page] | None
        """
        author = []
        if name is not None:
            # name = name.replace('Ё', 'Е').replace('ё', 'е').strip().removesuffix('.')
            # name = re.sub(r'\s+', ' ', name)
            name = re.sub(r'\s+', ' ', name).strip()
            if name != '':
                name = name.split(' ')
                match namelen := len(name):
                    # case 3:
                    #    author = [name[0], name[1], name[2]]
                    case 2:
                        author = [name[0], '', name[1]]
                    case 1:
                        author = [name[0], '', '']
                    case _:
                        # author = [name[0], ' '.join(name[1:namelen - 1]), name[-1]]
                        author = [' '.join(name[0:namelen - 1]), '', name[-1]]
            author.append(homepage)
        return author

    def __process_date(self, parent: Tag) -> None:
        if self.atinfo.is_valid():
            clear_tags(parent, 'date')
            date_tag = self.__soup.new_tag('date')
            # date_value = self.atinfo.time_modified if self.atinfo.is_valid() else datetime.now().strftime('%Y-%m-%d %H:%M')
            date_value = self.atinfo.time_updated
            date_tag['value'] = date_value
            date_tag.string = date_value
            parent.append(date_tag)

    def __process_document_info(self) -> None:
        if self.__soup is not None:
            if (parent := self.__soup.find('document-info')) is None:
                parent = self.__soup.new_tag('document-info')
                self.__soup.find('description').insert(2, parent)
            else:
                clear_tags(parent, 'author')
                author_tag = self.__soup.new_tag('author')
                parent.insert(1, author_tag)
                append_tag(self.__soup, author_tag, 'first-name',
                           self._document_info['author_name'] if 'author_name' in self._document_info and
                                                                 self._document_info['author_name'] != ''
                           else 'PureFb2')
                if 'author_home' in self._document_info and self._document_info['author_home'] != '':
                    append_tag(self.__soup, author_tag, 'home-page', self._document_info['author_home'])

                clear_tags(parent, 'date')
                date_tag = self.__soup.new_tag('date')
                date_value = datetime.now().strftime('%Y-%m-%d %H:%M')
                date_tag['value'] = date_value
                date_tag.string = date_value
                parent.insert(2, date_tag)

                programs = []
                if (programs_used := parent.select_one('program-used')) is not None:
                    # re.split('\s*,\s*', programs_used.string)
                    for program_used in programs_used.string.split(','):
                        if '' != (program_used := program_used.strip()) and program_used != 'PureFB2':
                            programs.append(program_used)
                programs.append('PureFB2')
                clear_tags(parent, 'program-used')
                append_tag(self.__soup, parent, 'program-used', ', '.join(programs))

    def __process_promo(self, add_custom_promo: bool = False) -> None:
        if self.__soup is not None:
            promo = self.__soup.find('p', text="Nota bene")
            if promo is not None \
                    and promo.find_parent().name == 'title' \
                    and promo.find_parent().find_parent().name == 'section':
                promo.find_parent().find_parent().decompose()
            if add_custom_promo and 'promo_section' in self._document_info:
                # promo = eval(f"f'{self._document_info['promo_section']}'")
                url_xmlns = f'{get_namespaces(self.__soup)["http://www.w3.org/1999/xlink"]}:' \
                    if 'http://www.w3.org/1999/xlink' in get_namespaces(self.__soup) else ''
                promo = self._document_info['promo_section'].format(
                    author_name=self._document_info['author_name'] if 'author_name' in self._document_info and
                                                                      self._document_info['author_name'].strip() != ''
                    else 'PureFb2',
                    author_home=self._document_info['author_home'] if 'author_home' in self._document_info and
                                                                      self._document_info['author_home'].strip() != ''
                    else '#',
                    src_url=self.url,
                    url_xmlns=url_xmlns,
                    book_title=self.title
                )
                soup = BeautifulSoup(f'<promo {get_namespaces(self.__soup, True)}><section>{promo}</section></promo>', 'xml')
                promo = soup.select_one('promo')
                self.__soup.select_one('body').append(promo)
                promo.unwrap()

    def __process_custom(self) -> None:
        if self.finished:
            self.add_custom_tag('status', ('fulltext' if self.atinfo.is_valid() else '3'))
        for info in self.__soup.find('description').find_all('custom-info'):
            attrs = dict({atr[0]: atr[1] for atr in info.attrs.items()})
            if 'info-type' in attrs and attrs['info-type'] == 'donated' and info.text.lower() in ('true', '1', 'false', '0'):
                self.add_custom_tag('donated', info.text, True)
        parent = self.__soup.find('description')
        clear_tags(parent, 'custom-info')
        custom: list = self._custom_tags
        if len(custom):
            clear_tags(parent, 'custom-info')
            append_tags(self.__soup, parent, 'custom-info', custom)

    def __optimize_global(self, replaces: list = []) -> list:
        """
        (r'<title>\s*\n*<p>(.*)</p>\s*\n*</title>\n*<p>\s*(\1|(<strong>\1</strong>))\s*</p>',
            r'<title>\n<p>\1</p>\n</title>'),
        (r'<p>(<\w+>)*\s*\*\s*\*\s*\*s*(</\w+>)*</p>', '<subtitle>* * *</subtitle>'),
        (r'\n+', '\n'),
        (r'\.(?=</p>\s*\n*</title>)', ''),
        """
        # starts_at = content.find('<body')
        # ends_at = content.rfind('</body>') + len('</body>')
        # header = content[:starts_at]
        # footer = content[ends_at:]
        # we will replace occurrences in body section only
        # content = content[starts_at:ends_at]

        # !!! EXPERIMENTAL !!!
        # remove some ugly cases after title like:
        # <title>
        # <p>Глава 1.1</p>
        # </title>
        # <p>Часть 1.</p>
        # <p>Глава 1.1</p>
        # replaces.append(
        #    [r'(?<!<title>)\s+<p>\s*(?:часть|глава|том|книга|раздел|арка)\s*(?:\d+\.?)+\s*</p>(?!(?:\s+</title>))',
        #     '', re.IGNORECASE])

        # TWO ANY STANDALONE DASH to EM DASH
        replaces.append([f'(?<!{ANYDASH}){ANYDASH}{{2}}(?!{ANYDASH})', MDASH])

        # add space after any dashes at dialogue & convert it into the md dash
        replaces.append([f'{ANYSP}{ANYDASH}{ANYSP}', MDASH_PAIR])
        replaces.append([f'<p>{ANYDASH}{ANYSP}', f'<p>{MDASH}{NBSP}'])
        replaces.append([rf'>{ANYDASH}([<A-ZА-ЯҐІЇЄ\.,\'«"])', rf'>{MDASH}{NBSP}\g<1>'])
        replaces.append([rf'({ANYSP}{ANYDASH}[<A-ZА-ЯҐІЇЄ\.,\'«"])', rf'{MDASH}{NBSP}\g<1>'])

        # clean up bold, italic, underline, strike HTML tags
        replaces.append([r'<([b|i|u|s])>([\s\S]*?)</\1>', r'\g<2>', re.IGNORECASE])
        replaces.append([r'<([b|i|u|s])\s*/>', '', re.IGNORECASE])

        # optimize empty tags:
        # <strong|emphasis|strikethrough|sup|sub|code}> </strong|emphasis|strikethrough|sup|sub|code>
        # <emphasis> <strong> </strong> </emphasis>
        # <strong> <emphasis> </emphasis> </strong>
        # <strong|emphasis|strikethrough|sup|sub|code />
        # replaces.append([
        #    r'(?:'
        #    r'<(strong|emphasis|strikethrough|sup|sub|code)>?\s*<(strong|emphasis|strikethrough|sup|sub|code)>\s*<(strong|emphasis|strikethrough|sup|sub|code)>\s*</\3>\s*</\2>\s*</\1>|'
        #    r'<(strong|emphasis|strikethrough|sup|sub|code)>?\s*<(strong|emphasis|strikethrough|sup|sub|code)>\s*</\2>\s*</\1>|'
        #    r'<(strong|emphasis|strikethrough|sup|sub|code)>\s*</\1>|'
        #    r'<(?:strong|emphasis|strikethrough|sup|sub|code)\s*/>'
        #    r')',
        #    ' '])
        replaces.append([r'<(?:strong|emphasis|strikethrough|sup|sub|code)\s*/>', ' ', re.IGNORECASE])
        # instead one very big expression we will repeat one the same unlill found :)
        replaces.append([r'<(strong|emphasis|strikethrough|sup|sub|code)>\s*</\1>', ' ', re.IGNORECASE, 'UNTIL_FOUND'])

        # place quotes inside tags
        replaces.append([r'(["\'])(\s*)<(strong|emphasis|strikethrough|sup|sub|code)>(.*)</\3>([\s\.!\?,:]*)\1',
                         r'\g<2><\g<3>>\g<1>\g<4>\g<1></\g<3>>\g<5>', re.IGNORECASE, 'UNTIL_FOUND'])
        replaces.append([r'«(\s*)<(strong|emphasis|strikethrough|sup|sub|code)>(.*)</\2>([\s\.!\?,:]*)»',
                         r'\g<1><\g<2>>«\g<3>»</\g<2>>\g<4>', re.IGNORECASE, 'UNTIL_FOUND'])

        # convert multyspaces into the one
        replaces.append([f'{ANYSP}{{2, }}', ' '])

        # 2-5 dots into triple one (more dots may be placed with author's reason)
        replaces.append([r'(?<![\.\?\!])\.{2,5}(?!\.)', '…'])

        # При «встрече» многоточия с запятой последняя поглощается многоточием, которое указывает
        # не только на пропуск слов, но и на пропуск знака препинания
        replaces.append([r'(?:,…|…,)', '…'])
        replaces.append([r'(?<!\?)\?{3,5}(?!\?)', '???'])
        replaces.append([r'(?<!\?)\?\?(?!\?)', '⁇'])
        replaces.append([r'(?<!\!)\!{3,5}(?!\!)', '!!!'])
        replaces.append([r'(?<!\!)!!(?<!\!)', '‼'])
        replaces.append([r'(?<![\?\!])\!\?(?![\?\!])', '⁉'])
        replaces.append([r'(?<![\?\!])\?\!(?![\?\!])', '⁈'])

        # После вопросительного/восклицательного знака ставятся не три точки (обычный вид многоточия),
        # а две (третья точка стоит под одним из названных знаков)
        replaces.append([r'\?…', '?..'])
        replaces.append([r'!…', '!..'])

        # Если у вас вопросительно-восклицательное предложение, т. е. вы используете и вопросительный
        # и восклицательный знак одновременно, то добавляется только одна точка.
        replaces.append([r'!\?…', '!?.'])
        replaces.append([r'\?!…', '?!.'])
        replaces.append([r'\?\?…', '??.'])
        replaces.append([r'\!\!…', '!!.'])
        replaces.append([r'⁈!', '?!!'])
        replaces.append([r'⁉\?', '!??'])

        # strip paragraphs (clear first & last spaces)
        replaces.append([r'<p>\s+', '<p>'])
        replaces.append([rf'\s*</p>{ANYSP}*', '</p>'])

        # optimize & transform empty paragraphs
        # <p></p>, <p/>
        replaces.append([r'(?:<p>\s*?</p>|<p */>)', '<empty-line/>'])

        # split multiple empty paragraphs into one
        replaces.append([r'(?:<empty-line/>\s*){2,}', '<empty-line/>\n'])

        # clear empty first & last paragraphs
        # <title|section><empty-line/>
        # <empty-line/></title|section>
        replaces.append([r'(?:(?:<empty-line/>\s*)?(</?(?:title|section)>)(?:\s*<empty-line/>)?)', r'\g<1>'])

        # extract images from paragraph
        # <p><image id="..." l:href="#..." /></p>
        # <p>text <image id="..." l:href="#..." /> text</p>
        # <empty-line/><image id="..." l:href="#..." /><empty-line/>
        replaces.append([r'(?:<empty-line/>\s*)?(<p>(?:^</p>)*?)?(<image[^>]+>)((?:^<p>)*?</p>)?(?:\s*<empty-line/>)?',
                         r'\g<1></p>\g<2><p>\g<3>'])
        # clean up tails from previous replace
        replaces.append(
            [
                r'<p>(\s*)<((?:p|title|epigraph|annotation|section|subtitle|poem|cite|text-author)|(?:/section|/title|/epigraph))>',
                r'\g<1><\g<2>>'])
        replaces.append([
            r'<((?:/p|/title|/epigraph|/annotation|/subtitle|/poem|/cite|/text-author)|(?:section|title|epigraph))>(\s*)</p>',
            r'<\g<1>>\g<2>'])
        replaces.append([r'<p>(\s*)</p>', r'\g<1>'])

        # very strange fact - single image in section broke whole document
        # let's add the empty line
        replaces.append([r'(<section>\s*<image[^>]+?>)(\s*</section>)', r'\g<1>\n<empty-line/>\g<2>'])

        # optimize & transform subtitle
        # <empty-line/><p|subtitle>***</p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><strong|emphasis|strikethrough|sup|sub|code>* * * *</strong|emphasis|strikethrough|sup|sub|code></p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><strong><emphasis>* *</emphasis></strong></p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><emphasis><strong>******</strong></emphasis></p|subtitle><empty-line/>

        replaces.append([
            rf'(?:(?:<empty-line */>)\s*)*<(p|subtitle)> ?(?:(?:<(strong|emphasis|strikethrough|sup|sub|code)> ?{ANYSUB}' +
            rf'+? ?</\2>)|(?:<strong> ?<emphasis> ?{ANYSUB}' +
            rf'+? ?</emphasis> ?</strong>)|(?: ?<emphasis> ?<strong> ?{ANYSUB}' +
            rf'+? ?</strong> ?</emphasis>)|{ANYSUB}' +
            r'+?) ?</\1>(?:\s*(?:<empty-line */>))*',
            '<subtitle>* * *</subtitle>'])

        return replaces

    def chapter_exists(self, title: str) -> bool:
        if self.__soup is not None:
            for section in self.__soup.find('body').findChildren('section'):
                if section.findChild('title').find('p', string=f"{title}") is not None:
                    return True
        return False

    def chapter_exists_alt(self, title: str) -> bool:
        if self.__soup is not None:
            title = self.__soup.find('p', string=f"{title}")
        return title is not None \
            and title.find_parent().name == 'title' \
            and title.find_parent().find_parent().name == 'section' \
            and title.find_parent().find_parent().find_parent().name == 'body'

    # private methods

    def __get_title(self, safe: bool = True) -> str:
        title = ''
        if self.__soup is not None:
            if (title := self.__soup.find('title-info').findChild('book-title')) is not None:
                title = title.text
            else:
                title = ''
        return title if title == '' or safe is False else normalize_text(str(title), True)

    def __get_url(self) -> str:
        url = ''
        if self.__soup is not None:
            if (url := self.__soup.find('document-info').findChild('src-url')) is not None:
                url = url.text
            else:
                url = ''
        return url

    def __get_sequence(self, safe: bool = True) -> dict:
        sequence = {'name': '', 'number': ''}
        if self.__soup is not None:
            if seq := self.__soup.select_one('sequence'):
                sequence = {'name': str(seq.get('name')), 'number': int(seq.get('number', '0'))}
                if safe:
                    sequence['name'] = normalize_text(sequence['name'], True)
                    sequence['number'] = '{:0>2}'.format(sequence['number'])
        return sequence

    def __get_last_chapter_title(self) -> str:
        section = ''
        if self.__soup is not None:
            if (sections := self.__soup.find('body').findChildren('section')) is not None:
                index = -1 if sections[-1].findChild('title').find('p') is not None and \
                              sections[-1].findChild('title').find('p').text.strip() != 'Nota bene' else -2
                if (section := sections[index].findChild('title').find('p')) is not None:
                    section = section.text.strip()
                    section = str(section).removesuffix('.')
        return section

    def __check_finished_state(self) -> bool:
        if self.__finished is None:
            for info in self.__soup.find('description').find_all('custom-info'):
                attrs = dict({atr[0]: atr[1] for atr in info.attrs.items()})
                if 'info-type' in attrs and attrs['info-type'] == 'status' and info.text.lower() in \
                        ('fulltext', 'full', 'finished', '3'):
                    self.__finished = True
            if not self.__finished:
                if 'author.today' in self.url:
                    self.__finished = self.atinfo.finished
                else:
                    epilogues = ['Эпилог', 'ЭПИЛОГ', 'эпилог', 'Послесловие', 'Примечания', 'ПРИМЕЧАНИЯ']
                    self.__finished = True if any(epilogue in self.last_chapter_title for epilogue in epilogues) else False
        return self.__finished

    def __check_donated_state(self) -> bool:
        for info in self.__soup.find('description').find_all('custom-info'):
            attrs = dict({atr[0]: atr[1] for atr in info.attrs.items()})
            if 'info-type' in attrs and attrs['info-type'] == 'donated' and info.text.lower() in ('true', '1'):
                return True
        return False

    def __get_chapters(self, root_section: list = None) -> list | None:
        chapters = []
        if root_section is None:
            root_section = self.__soup.find('body')
        if self.__soup is not None:
            for section in self.__soup.find('body').findChildren('section'):
                if root_section == section.find_parent():
                    chapters.append(section.findChild('title').find('p').text
                                    if section.find('section') is None
                                    else [section.findChild('title').find('p').text, self.__get_chapters(section)]
                                    )
        return chapters if len(chapters) else None

    def __optimize_images(self, process: bool = True) -> None:
        if self.__soup is not None:
            for binary in self.__soup.find_all('binary'):
                if process:
                    if binary.get('content-type') in ['image/jpg', 'image/jpeg', 'image/png']:
                        # binary['id'] = re.sub(r'(.+?)\\.(jpeg|jpg|png)', r'\g<1>.jpg', binary.get('id'))
                        binary.string = self.__optimize_image(binary.text, binary.get('content-type'), binary.get('id'))
                        binary['content-type'] = 'image/jpg'
                else:
                    # just normalizing the same image to the single base64 line
                    binary.string = base64.b64encode(
                        base64.b64decode(binary.text)
                    ).decode()

    def __optimize_image(self, raw, mime: str, id: str = ''):
        if raw:
            if mime in ['image/jpeg', 'image/jpg', 'image/png']:
                with Image.open(io.BytesIO(base64.b64decode(raw))) as image:
                    if self._debug:
                        print(f'{id} {image.mode} {mime}')
                    if mime == 'image/png':
                        image = image.convert('RGBA')
                        data = image.getdata()
                        new_data = []
                        for item in data:
                            if item[3] == 0:
                                new_data.append((239, 238, 238, 255))
                            else:
                                new_data.append(item)
                        image.putdata(new_data)
                        # image = image.convert('RGB')
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    image.thumbnail((640, 480))
                    stream = io.BytesIO()
                    image.save(stream, format="JPEG", subsampling=2, quality=70)
                    # image.save(stream, format="JPEG", subsampling=2, quality='medium')
                    raw = base64.b64encode(stream.getvalue()).decode()
        return raw
