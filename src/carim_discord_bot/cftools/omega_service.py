import asyncio
import datetime
import hashlib
import logging

import requests

from carim_discord_bot import managed_service, config

API = 'https://cfapi.de'
log = logging.getLogger(__name__)


class ServiceToken:
    def __init__(self, raw):
        self.service_id = raw.get('service_id')
        self.token = raw.get('token')
        self.token_id = raw.get('token_id')
        self.token_type = raw.get('token_type')


class Leaderboard(managed_service.Message):
    def __init__(self, server_name, stat):
        super().__init__(server_name)
        self.stat = stat


class OmegaService(managed_service.ManagedService):
    def __init__(self):
        super().__init__()
        self.user_agent = config.get().cftools_application_id
        self.client_id = config.get().cftools_client_id
        secret = config.get().cftools_secret
        self.hashed_secret = hashlib.sha256(secret.encode('utf-8')).hexdigest()
        self.logged_in = False
        self.logged_in_time = None
        self.access_token = None
        self.refresh_token = None
        self.service_tokens = dict()
        self.request_lock = asyncio.Lock()

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Leaderboard):
            result = await self.query_leaderboard(message.server_name, message.stat)
            message.result.set_result(result)

    async def service(self):
        while True:
            if self.logged_in:
                if datetime.datetime.now() - self.logged_in_time > datetime.timedelta(hours=23):
                    await self.renew_login()
            else:
                await self.login()
                if self.logged_in:
                    await self.get_service_tokens()
            await asyncio.sleep(10)

    async def login(self):
        self.logged_in = False

        payload = dict(secret=self.hashed_secret)
        async with self.request_lock:
            request = requests.post(f'{API}/auth/login', headers=self.get_headers(), json=payload)

            if request.status_code != 200:
                log.warning(f'failed to log in {request.json()}')
                return

            log.info('logged in')

            self.logged_in = True
            self.logged_in_time = datetime.datetime.now()
            self.access_token = request.json().get('access_token')
            self.refresh_token = request.json().get('refresh_token')

    async def get_service_tokens(self):
        request = await self.locking_request('GET', f'{API}/v1/servicetokens')
        tokens = request.json().get('tokens', list())
        if len(tokens) < 1:
            log.warning('Not authorized for any services')
        for token in tokens:
            new_service_token = ServiceToken(token)
            self.service_tokens[new_service_token.service_id] = new_service_token

    async def renew_login(self):
        async with self.request_lock:
            headers = self.get_headers()
            headers['Authorization'] = f'Bearer {self.refresh_token}'
            request = requests.post(f'{API}/auth/refresh', headers=headers)
            if request.status_code != 200:
                log.warning(f'failed to renew tokens {request.json()}')
                self.logged_in = False
                return

            log.info('renewed tokens')
            self.logged_in_time = datetime.datetime.now()
            self.access_token = request.json().get('access_token')
            self.refresh_token = request.json().get('refresh_token')

    async def query_leaderboard(self, server_name, stat):
        service_token = self.service_tokens[config.get_server(server_name).cftools_service_id]
        request = await self.locking_request('GET', f'{API}/v2/omega/{service_token.token}/leaderboard',
                                             payload=dict(stat=stat))
        return request.json()

    async def locking_request(self, method, url, payload=None):
        async with self.request_lock:
            if not self.logged_in:
                log.warning(f'not logged in')
                return
            request = requests.request(method, url, headers=self.get_headers(), params=payload)
        return request

    def get_headers(self):
        headers = {
            'User-Agent': self.user_agent,
            'Client-ID': self.client_id
        }
        if self.logged_in:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers


service = None


def get_service_manager():
    global service
    if service is None:
        service = OmegaService()
    return service
