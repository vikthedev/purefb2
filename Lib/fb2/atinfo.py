#!/usr/bin/python

__all__ = ("ATInfo", "genres_en", "genres_ru", "genre_name")

from datetime import datetime
from typing import Self, Optional
import re
import requests


def normalize_text(data: str = '', strip_dots: bool = False, check_single_letters: bool = False) -> str:
    data = re.sub(r'(?<![\.\?\!])\.{2,5}(?!\.)', '…', data).replace('Ё', 'Е').replace('ё', 'е').strip().strip('_ ')
    if strip_dots:
        if not check_single_letters or (check_single_letters and not re.match(r'^(\w\.\s*)+$', data)):
            data = data.strip('…._ ')
    return data


def empty_if_none(data: str | bool | int | float) -> str | bool | int | float:
    if isinstance(data, str):
        return '' if data is None or data.strip() == '' else data
    elif isinstance(data, bool):
        return False if data is None else data
    elif isinstance(data, int):
        return 0 if data is None else data
    elif isinstance(data, float):
        return .0 if data is None else data


class ATInfo:
    def __init__(self, available: bool = True):
        self.__url: Optional[str] = None
        self.__data: Optional[dict] = None
        self.__available: bool = available
        self.__api_url: str = 'https://api.author.today/v1/work/{0}/meta-info'
        self.__author_url: str = 'https://author.today/u/{0}/works'
        self.__date_format: str = '%Y-%m-%d %H:%M'

    @property
    def url(self) -> Optional[str]:
        return self.__url

    @url.setter
    def url(self, url: str) -> None:
        if match := re.search(r"^(?:https?://)author.today/work/(\d+)/?$", url.strip()):
            self.__connect(int(match.group(1)))

    @property
    def id(self) -> int:
        return empty_if_none(self.__data['id']) if self.is_valid() else 0

    @property
    def title(self) -> str:
        return empty_if_none(self.__data['title'])

    @property
    def cover(self) -> str:
        return empty_if_none(self.__data['cover'])

    @property
    def time_modified(self) -> str:
        return self.__convert_date(self.__data['lastModificationTime']) if self.is_valid() else ''

    @property
    def time_updated(self) -> str:
        return self.__convert_date(self.__data['lastUpdateTime']) if self.is_valid() else ''

    @property
    def time_finished(self) -> str:
        return self.__convert_date(self.__data['finishTime']) if self.is_valid() else ''

    @property
    def finished(self) -> bool:
        return empty_if_none(self.__data['isFinished']) if self.is_valid() else False

    @property
    def price(self) -> float:
        return empty_if_none(self.__data['price']) if self.is_valid() else .0

    @property
    def authors(self) -> list[list]:
        authors = []
        if self.is_valid():
            if (author := self.__author(self.__data['authorFIO'], self.__data['authorUserName'])) is not None:
                authors.append(author)
            if (author := self.__author(self.__data['coAuthorFIO'], self.__data['coAuthorUserName'])) is not None:
                authors.append(author)
            if (author := self.__author(self.__data['secondCoAuthorFIO'],
                                        self.__data['secondCoAuthorUserName'])) is not None:
                authors.append(author)
        return authors

    @property
    def genres(self) -> list:
        genre = []
        if self.is_valid():
            if self.__data['genreId'] is not None:
                genre.append(self.__data['genreId'])
            if self.__data['firstSubGenreId'] is not None:
                genre.append(self.__data['firstSubGenreId'])
            if self.__data['secondSubGenreId'] is not None:
                genre.append(self.__data['secondSubGenreId'])
        return genre

    @property
    def genres_ru(self) -> list:
        genres = []
        if self.is_valid():
            if (gentre := genre_name(self.__data['genreId'], 'ru')) is not None:
                genres.append(gentre)
            if (gentre := genre_name(self.__data['firstSubGenreId'], 'ru')) is not None:
                genres.append(gentre)
            if (gentre := genre_name(self.__data['secondSubGenreId'], 'ru')) is not None:
                genres.append(gentre)
        return genres

    @property
    def genres_en(self) -> list:
        genres = []
        if self.is_valid():
            if (gentre := genre_name(self.__data['genreId'], 'en')) is not None:
                genres.append(gentre)
            if (gentre := genre_name(self.__data['firstSubGenreId'], 'en')) is not None:
                genres.append(gentre)
            if (gentre := genre_name(self.__data['secondSubGenreId'], 'en')) is not None:
                genres.append(gentre)
        return genres

    @property
    def adult_only(self) -> bool:
        return empty_if_none(self.__data['adultOnly']) if self.is_valid() else False

    @property
    def likes_count(self) -> int:
        return empty_if_none(self.__data['likeCount']) if self.is_valid() else 0

    @property
    def rewards_count(self) -> int:
        return empty_if_none(self.__data['rewardCount']) if self.is_valid() else 0

    @property
    def comments_count(self) -> int:
        return empty_if_none(self.__data['commentCount']) if self.is_valid() else 0

    def series(self) -> list:
        series = []
        if self.is_valid() and self.__data['seriesId'] is not None:
            series.append(int(self.__data['seriesId']))
            series.append(int(self.__data['seriesOrder']))
            series.append(str(self.__data['seriesTitle']))
        return series

    def available(self, available: bool = True) -> Self:
        self.__available = available
        return self

    def get(self, url: str) -> Self:
        self.url = empty_if_none(url)
        return self

    def is_valid(self) -> bool:
        return self.__data is not None

    def __connect(self, id: int) -> None:
        if self.__available:
            try:
                with requests.get(self.__api_url.format(id),
                                  headers={'Authorization': 'Bearer guest'}) as response:
                    if 'id' in (resp := response.json()):
                        self.__data = resp
            except EnvironmentError as err:
                print(f'AT Connection Error: {err}')
                pass

    def __convert_date(self, data: str) -> str:
        return datetime.fromisoformat(data).astimezone(
            datetime.utcnow().astimezone().tzinfo
        ).strftime(self.__date_format) if data is not None else ''

    def __author(self, name: str, username: str) -> Optional[list]:
        """
        :param name: Combined Author's full name
        :param username: Author's username
        :return: list[first-name, middle-name, last-name, home-page] | None
        """
        author = []
        if name is not None:
            # name = name.replace('Ё', 'Е').replace('ё', 'е').strip()
            name = re.sub(r'\s+', ' ', name).strip()
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
                        author = [name[0], ' '.join(name[1:namelen - 1]), name[-1]]
                if username is not None:
                    author.append(self.__author_url.format(username.lower().strip()))
        return author if len(author) > 0 else None


def genre_name(genre: int, lang: str = 'ru') -> Optional[str]:
    dictionary = genres_en if lang == 'en' else genres_ru
    return None if genre is None else dictionary[genre if genre in dictionary else None]


genres_en: dict = {
    None: 'other',
    1: 'prose_contemporary',
    2: 'fantasy',
    3: 'sf_etc',
    4: 'detective',
    5: 'det_action',
    6: 'love',
    7: 'erotica',
    8: 'adventure',
    9: 'fanfiction',
    10: 'sf_mystic',
    11: 'thriller',
    12: 'humor',
    13: 'poetry',
    16: 'prose',
    17: 'prose_history',
    18: 'sf_horror',
    19: 'other',
    20: 'sf_litrpg',
    21: 'popadancy',
    28: 'sf_history',
    29: 'sf_social',
    30: 'sf_action',
    31: 'sf_heroic',
    32: 'sf_postapocalyptic',
    33: 'sf_space',
    34: 'sf_cyberpunk',
    35: 'sf_stimpank',
    36: 'sf',
    37: 'sf_humor',
    38: 'fantasy_action',
    39: 'urban_fantasy',
    40: 'love_sf',
    41: 'sf_fantasy',
    42: 'sf_humor',
    43: 'sf_epic',
    44: 'dark_fantasy',
    45: 'love_short',
    46: 'love_history',
    47: 'popadantsy_vo_vremeni',
    48: 'popadantsy_v_magicheskie_miry',
    49: 'det_political',
    50: 'det_history',
    51: 'det_espionage',
    52: 'sf_detective',
    53: 'love_erotica',
    54: 'sf-erotika',
    55: 'fantasy-erotika',
    56: 'love_erotica',
    57: 'love_erotica',
    60: 'modern_tale',
    62: 'other',
    63: 'sf_social',
    64: 'sf_heroic',
    66: 'popadancy',
    67: 'love_contemporary',
    68: 'love_erotica',
    69: 'sf_realrpg',
    70: 'adv_history',
    71: 'boyar_anime',
    72: 'back_to_ussr'
}

genres_ru: dict = {
    None: 'Иное',
    1: 'Современная проза',
    2: 'Фэнтези',
    3: 'Фантастика',
    4: 'Детектив',
    5: 'Боевик',
    6: 'Любовные романы',
    7: 'Эротика',
    8: 'Приключения',
    9: 'Фанфик',
    10: 'Мистика',
    11: 'Триллер',
    12: 'Юмор',
    13: 'Поэзия',
    16: 'Подростковая проза',
    17: 'Историческая проза',
    18: 'Ужасы',
    19: 'Разное',
    20: 'ЛитРПГ',
    21: 'Попаданцы',
    28: 'Альтернативная история',
    29: 'Антиутопия',
    30: 'Боевая фантастика',
    31: 'Героическая фантастика',
    32: 'Постапокалипсис',
    33: 'Космическая фантастика',
    34: 'Киберпанк',
    35: 'Стимпанк',
    36: 'Научная фантастика',
    37: 'Юмористическая фантастика',
    38: 'Боевое фэнтези',
    39: 'Городское фэнтези',
    40: 'Любовное фэнтези',
    41: 'Историческое фэнтези',
    42: 'Юмористическое фэнтези',
    43: 'Эпическое фэнтези',
    44: 'Темное фэнтези',
    45: 'Короткий любовный роман',
    46: 'Исторические любовные романы',
    47: 'Попаданцы во времени',
    48: 'Попаданцы в магические миры',
    49: 'Политический роман',
    50: 'Исторический детектив',
    51: 'Шпионский детектив',
    52: 'Фантастический детектив',
    53: 'Романтическая эротика',
    54: 'Эротическая фантастика',
    55: 'Эротическое фэнтези',
    56: 'Эротический фанфик',
    57: 'Слэш',
    60: 'Сказка',
    62: 'Развитие личности',
    63: 'Социальная фантастика',
    64: 'Героическое фэнтези',
    66: 'Попаданцы в космос',
    67: 'Современный любовный роман',
    68: 'Фемслэш',
    69: 'РеалРПГ',
    70: 'Исторические приключения',
    71: 'Бояръ-Аниме',
    72: 'Назад в СССР'
}
