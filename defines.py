#!/usr/bin/python

__all__ = ('at_enabled', 'document', 'author_replaces', 'get_authors_dict', 'out_format', 'name_format')

import os
import sqlite3
import re

# path_databases = '/home/groundfloor/databases/'
path_databases = 'c:\\dev\\projects\\python\\BatchElib2Ebook\\db\\'
author_rename_db = os.path.join(path_databases, 'author_rename.db')


def get_authors_dict():
    try:
        with sqlite3.connect(author_rename_db) as db:
            cursor = db.cursor()
            authors_dict = cursor.execute(f'select * from author_rename').fetchall()
            return dict({item[0]: item[1] for item in authors_dict})
    except EnvironmentError as err:
        print(f'Authors Dict Error: {err}')
        return {}


# allow to switch off the Author.Today checker
at_enabled = True
# allowed tags in out format:
# 'zip' - fb2.zip
# 'fb2' - fb2
# ['fb2', 'zip'] - fb2 & fb2.zip
out_format = 'fb2'
# allowed tags in file name
# {author} - author name (first last)
# {author_lf} - author name (last first)
# {title} - book title
# {seq_name} - sequence name
# {seq_num} - sequence number
# {current_time} - current time in %Y-%m-%d %H:%M
# {current_date} - current time in %Y-%m-%d
# {book_time} - original book modified time in %Y-%m-%d %H:%M (Author.today's based)
name_format = '{seq_num} {title}'

document = {
    'author_name': 'Цокольный этаж',
    'author_home': 'https://searchfloor.ru/',
    # allowed tags in promo
    # {author_name} - author_name from this dict
    # {author_home} - author_home from this dict
    # {src_url} - url to the book from document-info>src-url
    # {url_xmlns} - xmlns for hrefs in document
    # {book_title} - title of the book from title-info>book-title
    'promo_section': f'<title>'
                     '<p>Nota bene</p>'
                     '</title>'
                     '<p>С вами был <a {url_xmlns}href="{author_home}">{author_name}</a> (через VPN), на котором '
                     'есть книги. Ищущий да обрящет!</p>'
                     '<subtitle>Понравилась книга?</subtitle>'
                     '<p>Наградите автора лайком и донатом:</p>'
                     '<p><a {url_xmlns}href="{src_url}">{book_title}</a></p>'
}

author_replaces = [
    {
        'name': 'Дмитрий Янтарный',
        'patterns': [
            (r'(?<!<title>)\s+<p>\s*(?:часть|глава|том|книга|раздел|арка)\s*(?:\d+\.?)+\s*</p>(?!(?:\s+</title>))', '',
             re.IGNORECASE)
        ]
    },
    {
        'name': 'Артем Каменистый',
        'patterns': [
            (
                r'(<section>\s*<title>\s*<p>\s*(глава\s+\d+)\s+(.+?)</p>\s*</title>\s*)(?:(?:<p>[^<]*</p>|<p/>|<empty-line/>)\s*){,4}<p>\s*\2\s*</p>\s*<p>\s*\3\s*</p>',
                r'\g<1>', re.IGNORECASE),
            (
                r'(<section>\s*<title>\s*<p>\s*(глава\s+\d+)\s+(.+?)</p>\s*</title>)([\s\S]+?)<p>\s*\2\s*</p>\s*<p>\s*\3\s*</p>',
                r'\g<1>\g<4>', re.IGNORECASE),
        ]
    },
    {
        'name': 'Павел Корнев',
        'patterns': [
            (r'(<section>\s*<title>\s*<p>.+?</p>\s*</title>\s*)(?:(?:<p>.*?</p>|<p/>|<empty-line/>)\s*){1,4}(<p>глава)',
             r'\g<1>\g<2>', re.IGNORECASE),
            (r'(<title>\s*<p>.*?(глава\s+\d+).*?</p>\s*</title>\s*)<p>\2</p>', r'\g<1>', re.IGNORECASE)
        ]
    }
]
