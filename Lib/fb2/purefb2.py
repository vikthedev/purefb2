#!/usr/bin/python

__all__ = "PureFb2"

import os
from datetime import datetime
from typing import Self, Optional

import base64
import io
import re

import xml.dom.minidom as xmldom

from PIL import Image
from bs4 import BeautifulSoup, Tag, NavigableString

from Lib.fb2.atinfo import ATInfo
from Lib.fb2.zipper import InMemoryZipper
from Lib.transliterator import to_latin
from Lib.typus import ru_typus


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


def get_namespaces(soap: BeautifulSoup) -> list:
    """
    :param soap: BeautifulSoup object
    :return: list of namespaces
    """
    namespaces = []
    for ns in soap.find("FictionBook").attrs.items():
        namespaces.append(f'{ns[0]}="{ns[1]}"')
    return namespaces


def normalize_text(data: str = '', safe: bool = False) -> str:
    if safe:
        data = data.replace('Ё', 'Е').replace('ё', 'е').strip().removesuffix('.')
        data = re.sub(r'(?<![\.\?\!])\.{2,5}(?!\.)', '…', data)
    data = re.sub(r'\s+', ' ', data).strip()
    return data


def prettify_fb2(data: str = '', indent: int = 1):
    """Prettify FB2 XML with intelligent inline tags.

    :param data: XML text to prettify.
    :param indent: Set size of XML tag indents.
    :return: Prettified XML.
    """
    doc = xmldom.parseString(data)

    data = doc.toprettyxml(indent=' ' * indent)

    # ugly_xml = doc.toprettyxml(indent=' ' * indent, encoding='utf-8').decode()

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
    replaces.append([r'[\n\s]*(<(strong|emphasis)>)[\n\s]*', r' \g<1>', re.DOTALL])
    # inline a start
    replaces.append([r'[\n\s]*(<a .+?>)[\n\s]*', r' \g<1>', re.DOTALL])
    # Removes whitespace between end of inline tags and beginning of new tag
    # inline end
    replaces.append([r'[\n\s]*(</(strong|a|emphasis)>)[\n\s]*(?=<)', r'\g<1>', re.DOTALL])
    # Adds a space between the ending inline tags and following words
    # inline space
    replaces.append([r'[\n\s]*(</(strong|a|emphasis)>)([a-zA-Zа-яґіїєА-ЯҐІЇЄ0-9])', r'\g<1> \g<3>', re.DOTALL])
    # Removes spaces between nested inline tags
    # nested spaces start
    replaces.append([r'(<[^/]*?>) (?=<)', r'\g<1>', 0])

    # Removes spaces between nested end tags--which don't have attributes
    # so can be differentiated by string only content
    # nested spaces end
    replaces.append([r'(</\w*?>) (?=</)', r'\g<1>', 0])
    # quot
    replaces.append([r'(&quot;)', r'"', 0])
    # encoding
    replaces.append([r'(<\?xml.+?)\?>', r'\g<1>encoding="utf-8"?>', 0])

    return process_replaces(data, replaces)


def process_replaces(data: str = '', replaces=None):
    if replaces is None:
        replaces = []
    if data:
        for r in replaces:
            data = re.sub(f'{r[0]}', f'{r[1]}', data, 0, r[2] if len(r) > 2 else re.NOFLAG)
    return data


def file_safe(data: str = '', remove_suffix: bool = False) -> str:
    data = re.sub(r'["\\?!@#$%^&*_+|/:;\[\]{}<>—]', '', data)
    data = re.sub(r'\s+', ' ', data)
    if remove_suffix is True:
        data = data.removesuffix('.')
    return data.strip()


class PureFb2:
    __source: str
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
        authors: list = self.authors
        authors_plain: list = []
        for first_name, middle_name, last_name, home_page in authors:
            authors_plain.append(f'{first_name} {last_name}'.replace('  ', ' ').strip())
        return authors_plain

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
        return self._time_created if self._time_created is not None else ''

    @property
    def time_modified(self) -> str:
        return self._time_modified if self._time_modified is not None else ''

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
        return file_safe(self.name_format.format(
            author=self.author,
            author_lf=self.author_last_first,
            title=self.title,
            seq_name=self.sequence['name'],
            seq_num=self.sequence['number'],
            current_time=self._time_created,
            current_date=datetime.now().strftime('%Y-%m-%d'),
            book_time=self._time_modified
        ))

    def open(self, source: str = '') -> Self:
        if source != '':
            self.__source = source
        if self.__source != '':
            try:
                with open(self.__source, 'r+', encoding='utf-8') as file:
                    self.__soup = BeautifulSoup(file, "xml")
                    # try to add additional author.today information
                    self.atinfo = self.url
            except EnvironmentError:
                pass
        return self if self.is_opened else False

    def is_opened(self) -> bool:
        return self.__soup is not None

    def save(self, destination: str = '', **args) -> object:
        if self.__soup is not None:

            self._time_created = datetime.now().strftime('%Y-%m-%d %H:%M')
            self._time_modified = self.atinfo.time_updated if self.atinfo.is_valid() else self._time_created

            if destination != '':
                self.__destination = destination
                self.__process_title_info()
                self.__process_document_info()
                self.__process_custom()
                self.__process_body(args.get('typography', False) is not False)
                self.__process_promo(args.get('promo', False) is not False)
                self.__optimize_images(args.get('image', False) is not False)

                file_name = self.get_file_name()
                # full_name = os.path.basename(self.__destination)

                if args.get('prettify', False) is not False:
                    xml = prettify_fb2(str(self.__soup.prettify()))
                else:
                    xml = str(self.__soup)

                try:
                    if 'zip' in self.out_format:
                        if self._debug:
                            print(os.path.join(self.__destination, file_name + '.fb2.zip'))
                        with InMemoryZipper(os.path.join(self.__destination, file_name + '.fb2.zip')) as imz:
                            imz.append(to_latin(file_name, 'lower', True) + '.fb2', xml)
                except EnvironmentError:
                   pass

                try:
                    if 'fb2' in self.out_format:
                        if self._debug:
                            print(os.path.join(self.__destination, file_name + '.fb2'))
                        with open(os.path.join(self.__destination, file_name + '.fb2'), 'w+', encoding='utf-8') as file:
                            file.write(xml)
                except EnvironmentError:
                    pass
        return self

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

            soup = BeautifulSoup('<xml ' + ' '.join(get_namespaces(self.__soup)) + '>' + new_body + '</xml>', 'xml')
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

    def add_custom_tag(self, name: str, value: str) -> Self:
        self._custom_tags.append(['info-type', name, value])
        return self

    def set_author_replaces(self, author_replaces: list) -> Self:
        self._author_replaces = author_replaces
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
                if author_name != (author_name := self.authors_dict.get(author_name, author_name)):
                    first_name, middle_name, last_name, home_page = self.__split_author(author_name, home_page)
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
                    normalize_text(first_name.text, safe) if first_name is not None else '',
                    normalize_text(middle_name.text, safe) if middle_name is not None else '',
                    normalize_text(last_name.text, safe) if last_name is not None else '',
                    home_page.text if home_page is not None else ''
                ])
                if only_one:
                    break
        return authors

    def __split_author(self, name: str, homepage: str) -> Optional[list]:
        """
        :param name: Combined Author's full name
        :param homepage: Author's homepage
        :return: list[first-name, middle-name, last-name, home-page] | None
        """
        author = []
        if name is not None:
            name = name.replace('Ё', 'Е').replace('ё', 'е').strip().removesuffix('.')
            name = re.sub(r'\s+', ' ', name)
            if name != '':
                name = name.split(' ')
                match namelen := len(name):
                    case 3:
                        author = [name[0], name[1], name[2]]
                    case 2:
                        author = [name[0], '', name[1]]
                    case 1:
                        author = [name[0], '', '']
                    case _:
                        author = [name[0], ' '.join(list[1:namelen - 2]), name[-1]]
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
            # delete old promo if any
            # promo = self.__soup.find('title').find('p', text=re.compile(r"Nota bene"))
            promo = self.__soup.find('p', text="Nota bene")
            if promo is not None \
                    and promo.find_parent().name == 'title' \
                    and promo.find_parent().find_parent().name == 'section':
                promo.find_parent().find_parent().decompose()
            if add_custom_promo and 'promo_section' in self._document_info:
                # author_name = self._document_info['author_name'] if 'author_name' in self._document_info and self._document_info['author_name'].strip() != '' else 'PureFb2'
                # author_home = self._document_info['author_home'] if 'author_home' in self._document_info and self._document_info['author_home'].strip() != '' else '#'
                # src_url = self.url
                # book_title = self.title
                # promo = eval(f"f'{self._document_info['promo_section']}'")

                promo = self._document_info['promo_section'].format(
                    author_name=self._document_info['author_name'] if 'author_name' in self._document_info and
                                                                      self._document_info['author_name'].strip() != ''
                    else 'PureFb2',
                    author_home=self._document_info['author_home'] if 'author_home' in self._document_info and
                                                                      self._document_info['author_home'].strip() != ''
                    else '#',
                    src_url=self.url,
                    book_title=self.title
                )
                soup = BeautifulSoup('<section>' + f"{promo}" + '</section>', 'xml')
                body = soup.select_one('section')
                self.__soup.select_one('body').append(body)
                # body.unwrap()

    def __process_custom(self) -> None:
        if self.finished:
            self.add_custom_tag('status', ('fulltext' if self.atinfo.is_valid() else '3'))
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
        replaces.append(['(?<!{})'.format(ANYDASH) +
                         ANYDASH + '{2}' +
                         r'(?!{})'.format(ANYDASH), MDASH])

        # add space after any dashes at dialogue & convert it into the md dash
        replaces.append([ANYSP + ANYDASH + ANYSP, MDASH_PAIR])
        replaces.append([r'<p>' + ANYDASH + ANYSP, '<p>' + MDASH + NBSP])
        replaces.append(['>' + ANYDASH + r'([<A-ZА-ЯҐІЇЄ\.,\'«"])', '>' + MDASH + NBSP + r'\g<1>'])
        replaces.append([ANYSP + ANYDASH + r'([<A-ZА-ЯҐІЇЄ\.,\'«"])', MDASH + NBSP + r'\g<1>'])

        # optimize empty tags:
        # <strong|emphasis> </strong|emphasis>
        # <emphasis> <strong> </strong> </emphasis>
        # <strong> <emphasis> </emphasis> </strong>
        # <strong|emphasis />
        replaces.append([
            r'(?:<(strong|emphasis)>\s*</\1>|<emphasis>\s*<strong>\s*</strong>\s*</emphasis>|<strong>\s*<emphasis>\s*</emphasis>\s*</strong>|<(?:strong|emphasis)\s*/>)',
            ' '])

        # convert multyspaces into the one
        replaces.append([ANYSP + '{2, }', ' '])

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
        replaces.append([r'\s*</p>' + ANYSP + '*', '</p>'])

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
            [r'<p>(\s*)<((?:p|title|annotation|section|subtitle|poem|cite|text-author)|(?:/section|/title))>',
             r'\g<1><\g<2>>'])
        replaces.append([r'<((?:/p|/title|/annotation|/subtitle|/poem|/cite|/text-author)|(?:section|title))>(\s*)</p>',
                         r'<\g<1>>\g<2>'])
        replaces.append([r'<p>(\s*)</p>', r'\g<1>'])

        # optimize & transform subtitle
        # <empty-line/><p|subtitle>***</p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><strong|emphasis>* * * *</strong|emphasis></p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><strong><emphasis>* *</emphasis></strong></p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><emphasis><strong>******</strong></emphasis></p|subtitle><empty-line/>
        ANYSUB = r'(?:[\*_~\{}\{}\{}\{}\{}] ?)'.format(HMINUS, MINUS, FDASH, NDASH, MDASH)
        replaces.append([
            r'(?:(?:<empty-line */>)\s*)*<(p|subtitle)> ?(?:(?:<(strong|emphasis)> ?' + ANYSUB +
            r'+? ?</\2>)|(?:<strong> ?<emphasis> ?' + ANYSUB +
            r'+? ?</emphasis> ?</strong>)|(?: ?<emphasis> ?<strong> ?' + ANYSUB +
            r'+? ?</strong> ?</emphasis>)|' + ANYSUB +
            r'+?) ?</\1>(?:\s*(?:<empty-line */>))*',
            '<subtitle>* * *</subtitle>'])
        # content = header + content + footer
        # sys.exit()
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
            if title := self.__soup.find('title-info').findChild('book-title'):
                title = title.text
        return title if title == '' or safe is False else normalize_text(str(title))

    def __get_url(self) -> str:
        url = ''
        if self.__soup is not None:
            if (url := self.__soup.find('document-info').findChild('src-url')) is not None:
                url = url.text
        return url

    def __get_sequence(self, safe: bool = True) -> dict:
        sequence = {'name': '', 'number': ''}
        if self.__soup is not None:
            if seq := self.__soup.select_one('sequence'):
                sequence = {'name': str(seq.get('name')), 'number': int(seq.get('number', '0'))}
                if safe:
                    sequence['name'] = normalize_text(sequence['name'])
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
            if 'author.today' in self.url:
                self.__finished = self.atinfo.finished
            else:
                epilogues = ['Эпилог', 'ЭПИЛОГ', 'эпилог', 'Послесловие', 'Примечания', 'ПРИМЕЧАНИЯ']
                self.__finished = True if any(epilogue in self.last_chapter_title for epilogue in epilogues) else False
        return self.__finished

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
                        binary.string = self.__optimize_image(binary.text, binary.get('content-type'))
                        binary['content-type'] = 'image/jpg'
                        if self._debug:
                            print(binary.get('id'))
                else:
                    # just normalizing the same image to the single base64 line
                    binary.string = base64.b64encode(
                        base64.b64decode(binary.text)
                    ).decode()

    def __optimize_image(self, raw, mime: str):
        if raw:
            if mime in ['image/jpeg', 'image/jpg', 'image/png']:
                with Image.open(io.BytesIO(base64.b64decode(raw))) as image:
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
                        image = image.convert('RGB')

                    image.thumbnail((640, 480))
                    stream = io.BytesIO()
                    image.save(stream, format="JPEG", subsampling=2, quality=70)
                    # image.save(stream, format="JPEG", subsampling=2, quality='medium')
                    raw = base64.b64encode(stream.getvalue()).decode()
        return raw
