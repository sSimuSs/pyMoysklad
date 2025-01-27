import functools
import json
import logging
from urllib.parse import urljoin

import requests
from pyrate_limiter import Limiter, RequestRate, Duration
from requests.auth import HTTPBasicAuth
from requests_ratelimiter import LimiterSession

from pymoysklad.json.exceptions import AuthError, ApiError, ERRORS

ENDPOINT = "https://api.moysklad.ru/api/remap/1.2/"


class TokenAuth(requests.auth.AuthBase):
    def __init__(self, token: str):
        self.token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r


class Requester:
    @staticmethod
    def _check_for_errors(func):
        @functools.wraps(func)
        def wrap(self, *args, **kwargs):
            answer = func(self, *args, **kwargs)
            error = None
            if isinstance(answer, list):
                if any(map(lambda x: "errors" in x, answer)):
                    error = answer[0]['errors'][0]
            else:
                if 'errors' in answer:
                    error = answer['errors'][0]
            if error:
                if error['code'] in ERRORS:
                    raise ERRORS[error['code']](error['error'])
                else:
                    exception = ApiError(error['error'], code=error['code'])
                    raise exception
            return answer

        return wrap

    @_check_for_errors
    def get(self, url: str, params: dict = None, raw=False):
        self.session.auth = self._auth
        answer = self.session.get(urljoin(ENDPOINT, url),
                                  params=params,
                                  headers={
                                      'Content-type': 'application/json',
                                      'Accept-Encoding': 'gzip'
                                  })
        if raw:
            return answer
        return answer.json()

    @_check_for_errors
    def post(self, url: str, data: dict | list):
        self.session.auth = self._auth
        return self.session.post(urljoin(ENDPOINT, url),
                                 data=json.dumps(data),
                                 headers={
                                     'Content-type': 'application/json',
                                     'Accept-Encoding': 'gzip'
                                 }).json()

    @_check_for_errors
    def put(self, url: str, data: dict):
        self.session.auth = self._auth
        return self.session.put(urljoin(ENDPOINT, url),
                                data=json.dumps(data),
                                headers={
                                    "Content-type": "application/json",
                                    'Accept-Encoding': 'gzip'
                                }).json()

    @_check_for_errors
    def delete(self, url: str):
        self.session.auth = self._auth
        return self.session.delete(urljoin(ENDPOINT, url))

    def __init__(self, auth: str | tuple[str, str]):
        self._auth: HTTPBasicAuth | TokenAuth
        if isinstance(auth, tuple):
            self._auth = HTTPBasicAuth(*auth)
        else:
            self._auth = TokenAuth(auth)
        self.session = LimiterSession(auth=self._auth,
                                      limiter=Limiter(RequestRate(45, Duration.SECOND * 3)))
