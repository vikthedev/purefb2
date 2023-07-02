#!/usr/bin/python
import base64
import io
import re
import sys

from PIL import Image
from bs4 import BeautifulSoup

from Lib.fb2.patterns import get_promo
from Lib.inout import file_get_contents
from Lib.prettieflier import prettierfier
from Lib.typus import ru_typus


class PureFb2:
    __source: str
    __destination: str
    __soup: BeautifulSoup | None

    def __init__(self, source: str = '', destination: str = ''):
        self.__source = source
        self.__destination = destination
        self.__soup = None

    @property
    def author(self) -> str:
        return self.__get_author()

    @property
    def author_safe(self) -> str:
        return self.__get_author(True)

    @property
    def title(self) -> str:
        return self.__get_title()

    @property
    def url(self) -> str:
        return self.__get_url()

    @property
    def title_safe(self) -> str:
        return self.__get_title(True)

    @property
    def sequence(self) -> dict | None:
        return self.__get_sequence()

    @property
    def sequence_safe(self) -> dict | None:
        return self.__get_sequence(True)

    @property
    def chapters(self) -> list:
        return self.__get_chapters()

    def open(self, source: str = ''):
        if source != '':
            self.__source = source
        if self.__source != '' and (content := file_get_contents(self.__source)):
            content = self.optimize_global(content)
            self.__soup = BeautifulSoup(content, "xml")
        return self

    def file_safe(self, data: str = '', remove_suffix: bool = False) -> str:
        data = re.sub(r'[|:<>"/\\?*—]', r' ', data)
        data = re.sub(r'\s+', r' ', data)
        if remove_suffix is True:
            data = data.removesuffix('.')
        return data

    def optimize_global(self, content: str = '', **args) -> str:
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
        MDASH_PAIR = NNBSP + MDASH + THNSP

        starts_at = content.find('<body')
        ends_at = content.rfind('</body>') + len('</body>')

        header = content[:starts_at]
        footer = content[ends_at:]

        # we will replace occurrences in body section only
        content = content[starts_at:ends_at]

        header = header.replace("PureFB2 ,", "").replace(", PureFB2", "").replace("PureFB2", "</program-used>"). \
            replace("</program-used>", ", PureFB2</program-used>")

        replaces = []

        # TWO ANY STANDALONE DASH to EM DASH
        replaces.append(['(?<!{})'.format(ANYDASH) +
                         ANYDASH + '{2}' +
                         r'(?!{})'.format(ANYDASH), MDASH])

        # add space after any dashes at dialogue & convert it into the md dash
        replaces.append([ANYSP + ANYDASH + ANYSP, MDASH_PAIR])
        replaces.append([r'<p>' + ANYDASH + ANYSP, '<p>' + MDASH + THNSP])
        replaces.append(['>' + ANYDASH + r'([<A-ZА-ЯҐІЇЄ\.,\'«"])', '>' + MDASH + THNSP + r'\g<1>'])
        replaces.append([ANYSP + ANYDASH + r'([<A-ZА-ЯҐІЇЄ\.,\'«"])', MDASH + THNSP + r'\g<1>'])

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
        replaces.append([r'<p>(\s*)<((?:p|title|annotation|section)|(?:/section|/title))>', r'\g<1><\g<2>>'])
        replaces.append([r'<((?:/p|/title|/annotation)|(?:section|title))>(\s*)</p>', r'<\g<1>>\g<2>'])
        replaces.append([r'<p>(\s*)</p>', r'\g<1>'])

        # optimize & transform subtitle
        # <empty-line/><p|subtitle>***</p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><strong|emphasis>* * * *</strong|emphasis></p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><strong><emphasis>* *</emphasis></strong></p|subtitle><empty-line/>
        # <empty-line/><p|subtitle><emphasis><strong>******</strong></emphasis></p|subtitle><empty-line/>
        replaces.append([
            r'(?:(?:<empty-line */>)\s*)*<(p|subtitle)> ?(?:(?:<(strong|emphasis)> ?(?:\* ?)+? ?</\2>)|(?:<strong> ?<emphasis> ?(?:\* ?)+? ?</emphasis> ?</strong>)|(?: ?<emphasis> ?<strong> ?(?:\* ?)+? ?</strong> ?</emphasis>)|(?:\* ?)+?) ?</\1>(?:\s*(?:<empty-line */>))*',
            '<subtitle>* * *</subtitle>'])

        for r in replaces:
            content = re.sub(f'{r[0]}', f'{r[1]}', content, 0, r[2] if len(r) > 2 else re.NOFLAG)

        # sys.exit()
        return header + content + footer

    def __optimize(self, args):
        if args.get('image', False) is not False:
            self.__optimize_images()
        if args.get('paragraph', False) is not False:
            self.__optimize_paragraphs()
        return self

    def save(self, destination: str = '', **args) -> object:
        if self.__soup is not None:
            if destination != '':
                self.__destination = destination
                # False True 'Force'
                if args.get('image', False) is not False:
                    self.__optimize_images()
                xml = str(self.__soup.prettify()) if args.get('typography', False) is not False else str(self.__soup)
                if xml is not None:
                    if args.get('paragraph', False) is not False:
                        xml = self.__optimize_paragraphs(xml)
                    if args.get('promo', False) is not False:
                        # add the end promo
                        xml = re.sub(r'(?<=</section>)\s*(?=</body>)',
                                     r'\n{}\n'.format(get_promo(src_url=self.url, book_title=self.title)), xml)
                    with open(self.__destination, 'w+', encoding='utf-8') as f:
                        if args.get('typography', False) is not False:
                            f.write(prettierfier.prettify_fb2(xml))
                        else:
                            f.write(xml)
        return self

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
    def __get_author(self, safe: bool = False) -> str:
        author = ''
        if self.__soup is not None:
            if author := self.__soup.find('title-info').findChild('author'):
                f_name = author.find('first-name').text.strip(' ') if author.find('first-name') else ''
                l_name = author.find('last-name').text.strip(' ') if author.find('last-name') else ''
                author = f"{l_name} {f_name}".strip(' ')
        return author if author == '' or safe is False else self.file_safe(author)

    def __get_title(self, safe: bool = False) -> str:
        title = ''
        if self.__soup is not None:
            if title := self.__soup.find('title-info').findChild('book-title'):
                title = title.text
        return title if title == '' or safe is False else self.file_safe(title, True)

    def __get_url(self) -> str:
        url = ''
        if self.__soup is not None:
            if (url := self.__soup.find('document-info').findChild('src-url')) is not None:
                url = url.text
        return url

    def __get_sequence(self, safe: bool = False) -> dict | None:
        sequence = None
        if self.__soup is not None:
            if seq := self.__soup.find('sequence'):
                sequence = {'name': seq.get('name') if safe is False else self.file_safe(seq.get('name'), True),
                            'number': seq.get('number') if safe is False else '{:0>2}'.format(int(seq.get('number')))}
        return sequence

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

    def __optimize_paragraphs(self, xml: str = "") -> str:
        if xml != '':
            # xml = re.sub(r'<p>([\s\S]+?)</p>', self.convert_to_lower, xml)
            xml = re.sub(r'<p>([\s\S]+?)</p>', lambda x: ru_typus(x.group()), xml)
            # см. http://old-rozental.ru/punctuatio.php?sid=176
            xml = re.sub(',— ', ', — ', xml)
        return xml

    def __optimize_images(self) -> None:
        if self.__soup is not None:
            for binary in self.__soup.find_all('binary'):
                if binary.get('content-type') in ['image/jpg', 'image/jpeg', 'image/png']:
                    binary['content-type'] = 'image/jpg'
                    # binary['id'] = re.sub(r'(.+?)\\.(jpeg|jpg|png)', r'\g<1>.jpg', binary.get('id'))
                    binary.string = self.__optimize_image(binary.text, binary.get('content-type'))
                    print(binary.get('id'))

    def __optimize_image(self, raw, mime: str):
        if raw:
            if mime in ['image/jpg', 'image/png']:
                with Image.open(io.BytesIO(base64.b64decode(raw))) as image:
                    image.thumbnail((640, 480))
                    stream = io.BytesIO()

                    if mime == 'image/png':
                        data = image.getdata()
                        new_data = []
                        for item in data:
                            if item[3] == 0:
                                if item[0] == 0 and item[1] == 0 and item[2] == 0:
                                    new_data.append((255, 255, 255, 1))
                                else:
                                    new_data.append((item[0], item[1], item[2], 1))
                            else:
                                new_data.append(item)
                        image.putdata(new_data)
                    image = image.convert('RGB')

                    image.save(stream, format="JPEG", subsampling=2, quality=60)
                    raw = base64.b64encode(stream.getvalue()).decode()
        return raw
