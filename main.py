#!/usr/bin/python
from Lib.fb2.purefb2 import PureFb2


links_i = [
    r'',
    r'',
    r'',
    r''
]


for l in links_i:
    if l != '':
        fb2 = PureFb2().open(l)
        book_name = '{} - {}'.format(fb2.author_safe, fb2.title_safe)
        print(book_name)
        fb2.save(r'c:\Downloads\{}.fb2'.format(book_name),
                 paragraph=True, image=True, typography=True, promo=False)
