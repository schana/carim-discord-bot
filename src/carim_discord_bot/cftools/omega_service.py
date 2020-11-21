import asyncio
import datetime
import hashlib
import json
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


class Stats(managed_service.Message):
    def __init__(self, server_name, steam64):
        super().__init__(server_name)
        self.steam64 = steam64


class QueuePriorityList(managed_service.Message):
    def __init__(self, server_name):
        super().__init__(server_name)


class QueuePriorityCreate(managed_service.Message):
    def __init__(self, server_name, cftools_id, comment, expires_at):
        super().__init__(server_name)
        self.cftools_id = cftools_id
        self.comment = comment
        self.expires_at = expires_at


class QueuePriorityRevoke(managed_service.Message):
    def __init__(self, server_name, cftools_id):
        super().__init__(server_name)
        self.cftools_id = cftools_id


class CacheItem:
    def __init__(self, value):
        self.value = value
        self.time = datetime.datetime.now()

    def is_valid(self):
        return datetime.datetime.now() - self.time < datetime.timedelta(minutes=5)


class LeaderboardCache:
    def __init__(self):
        self.state = dict()

    def get(self, server_name, stat):
        item: CacheItem = self.state.get((server_name, stat), None)
        if item and item.is_valid():
            return item.value
        return None

    def set(self, server_name, stat, value):
        self.state[(server_name, stat)] = CacheItem(value)


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
        self.leaderboard_cache = LeaderboardCache()

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Leaderboard):
            result = await self.query_leaderboard(message.server_name, message.stat)
            message.result.set_result(result)
        elif isinstance(message, Stats):
            result = await self.query_stats(message.server_name, message.steam64)
            message.result.set_result(result)
        elif isinstance(message, QueuePriorityList):
            result = await self.query_queue_priority(message.server_name)
            message.result.set_result(result)
        elif isinstance(message, QueuePriorityCreate):
            result = await self.create_queue_priority(message.server_name,
                                                      message.cftools_id,
                                                      message.comment,
                                                      message.expires_at)
            message.result.set_result(result)
        elif isinstance(message, QueuePriorityRevoke):
            result = await self.revoke_queue_priority(message.server_name, message.cftools_id)
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

    def get_service_token(self, server_name):
        try:
            return self.service_tokens[config.get_server(server_name).cftools_service_id]
        except IndexError:
            return None

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
        cached = self.leaderboard_cache.get(server_name, stat)
        if cached is not None:
            log.debug('using cached value')
            return cached
        else:
            service_token = self.get_service_token(server_name)
            request = await self.locking_request('GET', f'{API}/v2/omega/{service_token.token}/leaderboard',
                                                 payload=dict(stat=stat, limit=20))
            result = request.json()
            self.leaderboard_cache.set(server_name, stat, result)
            return result

    async def query_stats(self, server_name, steam64):
        request = await self.locking_request('GET', f'{API}/v1/user/lookup',
                                             payload=dict(identity=steam64, identity_type='steam64'))
        result = request.json()
        if not result.get('status', False):
            return 'Invalid steam64'
        cftools_id = result.get('cftools_id')

        service_token = self.get_service_token(server_name)
        request = await self.locking_request('GET', f'{API}/v1/user/{service_token.token}/service',
                                             payload=dict(platform='omega', cftools_id=cftools_id))

        result = request.json()
        user = result.get('user', dict()).get(config.get_server(server_name).cftools_service_id, dict())
        stats = user.get('stats', dict())

        response = dict(
            playtime=str(datetime.timedelta(seconds=user.get('playtime', 0))),
            sessions=user.get('sessions', 0),
            average_engagement_distance=f'{stats.get("average_engagement_distance", 0):0.2f}m',
            kills=stats.get('kills', 0),
            deaths=stats.get('deaths', 0),
            longest_kill_distance=f'{stats.get("longest_kill_distance", 0)}m',
            longest_kill_weapon=stats.get('longest_kill_weapon', '')
        )

        return json.dumps(response, indent=1, ensure_ascii=False)

    async def query_queue_priority(self, server_name):
        service_token = self.get_service_token(server_name)
        request = await self.locking_request('GET', f'{API}/v1/queuepriority/{service_token.token}/list')
        return request.json()

    async def create_queue_priority(self, server_name, cftools_id, comment, expires_at):
        service_token = self.get_service_token(server_name)
        request = await self.locking_request('POST', f'{API}/v1/queuepriority/{service_token.token}/create',
                                             payload=dict(cftools_id=cftools_id,
                                                          comment=comment,
                                                          expires_at=expires_at))
        return request.json()

    async def revoke_queue_priority(self, server_name, cftools_id):
        service_token = self.get_service_token(server_name)
        request = await self.locking_request('POST', f'{API}/v1/queuepriority/{service_token.token}/revoke',
                                             payload=dict(cftools_id=cftools_id))
        return request.json()

    async def locking_request(self, method, url, payload=None):
        async with self.request_lock:
            if not self.logged_in:
                log.warning(f'not logged in')
                return
            if method == 'GET':
                request = requests.request(method, url, headers=self.get_headers(), params=payload)
            elif method == 'POST':
                request = requests.request(method, url, headers=self.get_headers(), json=payload)
        log.debug(f'{method} {url}')
        log.debug(f'request headers: {request.request.headers}')
        log.debug(f'request body:    {request.request.body}')
        log.debug(f'response:        {request.content}')
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
