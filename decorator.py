# !/usr/bin/python

import re

from Lib.fb2.purefb2 import PureFb2

__all__ = 'decorate'


def decorate(fb2: PureFb2, donation: bool = False) -> str:
    tag_status = []
    book_title = fb2.title
    authors_str = f'Автор: ' + ', '.join(fb2.authors_plain)
    authors_tag = []
    for author_plain in fb2.authors_last_name_plain:
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

    if fb2.donated:
        tag_status.append('дон')

    tag_status = ' #'.join(tag_status)

    text += f'\n#{tag_status}'

    return text
