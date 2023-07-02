#!/usr/bin/python

replacements_def = {
    'promo': True
}


def get_promo(**args):
    src_url = args["src_url"] if "src_url" in args else '#'
    book_title = args["book_title"] if "book_title" in args else ''
    return f'<section>\n<title>\n<p>Nota bene</p>\n</title>\n' \
           f'<p>С вами был <a l:href="https://searchfloor.ru/">Цокольный этаж</a> (через VPN), на котором ' \
           f'есть книги. Ищущий да обрящет!</p>\n' \
           f'<subtitle>Понравилась книга?</subtitle>\n' \
           f'<p>Наградите автора лайком и донатом:</p>\n' \
           f'<p><a l:href="{src_url}">{book_title}</a></p>\n</section>\n'
