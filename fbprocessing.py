import os
import re
import defines
from Lib.fb2.purefb2 import PureFb2

path_databases = '/home/groundfloor/databases/'
books_db = os.path.join(path_databases, 'books.db')

path_books = '/home/groundfloor/books/'

logins_of_donation_books = [

]


class Fb2:
    def __init__(self, file_name_raw, login):
        self.file_name_raw = file_name_raw
        self.login = login

    def processing(self):
        if (fb2 := PureFb2().
                at_ready(defines.at_enabled).
                set_author_replaces(defines.author_replaces)
                .set_authors_dict(defines.authors_dict)
                .set_document_info(defines.document)
                .set_out_format(defines.out_format)
                .set_name_format(defines.name_format))\
                .open(self.file_name_raw):

            tag_status = []

            if self.login in logins_of_donation_books:
                fb2.add_custom_tag('donated', 'true')

            fb2.save(path_books,
                     typography=True, image=True, prettify=True, promo=True)

            book_title = fb2.title
            authors_str = f'Автор: ' + ', '.join(fb2.authors_plain)
            authors_tag = []
            for author_plain in fb2.authors_plain:
                authors_tag.append(re.sub(r'\W+', '', author_plain.lower()))
            tag_status.extend(authors_tag)

            text = f'{book_title}\n{authors_str}\n'

            if fb2.sequence['name']:
                text += f'Серия: {fb2.sequence["name"]} № {fb2.sequence["number"]}\n'
                tag_sequence = re.sub(r'\W+', '', fb2.sequence["name"].lower())
                tag_status.append(tag_sequence)
            if fb2.finished:
                tag_status.append('книгазавершена')
            else:
                text += f'\nПо: {fb2.last_chapter_title} (от {fb2.time_modified})\n'

            if self.login in logins_of_donation_books:
                tag_status.append('дон')

            tag_status = '#' + ' #'.join(tag_status)

            text += f'\n{tag_status}'

            return fb2.get_file_name() + '.fb2' + ('.zip' if defines.out_format == 'zip' else ''), text, fb2.finished

        """
            NEED TO RECHECK IT CAREFULLY !
        
            (r'(?<=</section>\n)(?=</body>)', 'promo'),
            (r'[-–](?=\s)', '—'),
            (r'((?<=<p>)\s+)|(\s+(?=</p>))', ''),
            (r'\.\.\.', '…'),
            (r'<title>\s*\n*<p>(.*)</p>\s*\n*</title>\n*<p>\s*(\1|(<strong>\1</strong>))\s*</p>', r'<title>\n<p>\1</p>\n</title>'),
            (r'<p>(<\w+>)*\s*\*\s*\*\s*\*s*(</\w+>)*</p>', '<subtitle>* * *</subtitle>'),
            (r'<empty-line/>|(<p>\s*</p>)|<p/>', ''),
            (r'\n+', '\n'),
            (r'\.(?=</p>\s*\n*</title>)', ''),
        """
