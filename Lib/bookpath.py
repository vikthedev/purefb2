#!/usr/bin/python
import re


class BookPath:
    def __init__(self, url):
        self._params = {
            'img': False,
            'zip': False,
        }
        self.__allowed_params = list(self._params.keys())
        self.__url_re = re.compile('(https?://)([^/]+)@(.+)')
        self.url = url

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, url: str):
        self.__prepare(url)

    @property
    def params(self):
        return self._params

    @params.setter
    def params(self, params: dict):
        self._params = params
        self.__allowed_params = list(params.keys())

    @property
    def login(self):
        return self.params['login']

    @login.setter
    def login(self, login: str):
        self.params['login'] = login

    @property
    def password(self):
        return self.params['pass']

    @password.setter
    def password(self, password: str):
        self.params['pass'] = password

    @property
    def with_img(self):
        return self.params['img']

    @with_img.setter
    def with_img(self, with_img: bool):
        self.params['img'] = with_img

    @property
    def zipped(self):
        return self.params['zip']

    @zipped.setter
    def zipped(self, zipped: bool):
        self.params['zip'] = zipped

    # Declaring private method
    def __prepare(self, url: str):
        _params = []
        matches = self.__url_re.match(url)
        if matches:
            self._url = matches[1] + matches[3]
            for x in matches[2].split(':'):
                if x in self.__allowed_params:
                    self._params[x] = True
                else:
                    _params.append(x)
            self.params['login'] = _params[0] if len(_params) == 2 else None
            self.params['pass'] = _params[1] if len(_params) == 2 else None
        else:
            self._url = url
            self.params['login'] = None
            self.params['pass'] = None
