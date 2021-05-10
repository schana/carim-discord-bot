import asyncio
import datetime
import json
import logging

import requests

from carim_discord_bot import managed_service, config

API = 'https://data.cftools.cloud'
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


class CloudService(managed_service.ManagedService):
    def __init__(self):
        super().__init__()
        self.application_id = config.get().cf_cloud_application_id
        self.secret = config.get().cf_cloud_secret
        self.logged_in = False
        self.logged_in_time = None
        self.token = None
        self.request_lock = asyncio.Lock()
        self.leaderboard_cache = LeaderboardCache()

    async def handle_message(self, message: managed_service.Message):
        if isinstance(message, Leaderboard):
            result = await self.query_leaderboard(message.server_name, message.stat)
            message.result.set_result(result)
        elif isinstance(message, Stats):
            result = await self.query_stats(message.server_name, message.steam64)
            message.result.set_result(result)

    async def service(self):
        while True:
            if self.logged_in:
                if datetime.datetime.now() - self.logged_in_time > datetime.timedelta(hours=23):
                    await self.login()
            else:
                await self.login()
            await asyncio.sleep(10)

    async def login(self):
        self.logged_in = False

        payload = dict(application_id=self.application_id, secret=self.secret)
        async with self.request_lock:
            request = requests.post(f'{API}/v1/auth/register', headers=self.get_headers(), json=payload)

            log.debug(f'login request')
            log.debug(f'request headers: {request.request.headers}')
            log.debug(f'request body:    {request.request.body}')
            log.debug(f'response status: {request.status_code}')
            log.debug(f'response:        {request.content}')

            if request.status_code != 200:
                log.warning(f'failed to log in {request.json()}')
                return

            log.info('logged in')

            self.logged_in = True
            self.logged_in_time = datetime.datetime.now()
            self.token = request.json().get('token')

    async def query_leaderboard(self, server_name, stat):
        cached = self.leaderboard_cache.get(server_name, stat)
        if cached is not None:
            log.debug('using cached value')
            return cached
        else:
            server_api_id = config.get_server(server_name).cf_cloud_server_api_id
            request = await self.locking_request('GET', f'{API}/v1/server/{server_api_id}/leaderboard',
                                                 payload=dict(stat=stat, limit=20, order=1))
            result = request.json()
            if not result.get('status', False):
                return 'Query failed'
            self.leaderboard_cache.set(server_name, stat, result)
            return result

    async def query_stats(self, server_name, steam64):
        server_api_id = config.get_server(server_name).cf_cloud_server_api_id
        request = await self.locking_request('GET', f'{API}/v1/server/{server_api_id}/lookup',
                                             payload=dict(identifier=steam64))
        result = request.json()
        if not result.get('status', False):
            return 'Not found'
        cftools_id = result.get('cftools_id')

        request = await self.locking_request('GET', f'{API}/v1/server/{server_api_id}/player',
                                             payload=dict(cftools_id=cftools_id))

        result = request.json()
        log.debug(f'result: {result}')
        user = result.get('user', dict())
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

    async def locking_request(self, method, url, payload=None):
        async with self.request_lock:
            if not self.logged_in:
                log.warning(f'not logged in')
                return
            if method == 'GET':
                request = requests.request(method, url, headers=self.get_headers(), params=payload)
            elif method == 'POST':
                request = requests.request(method, url, headers=self.get_headers(), json=payload)
        log.info(f'{method} {url}')
        log.debug(f'request headers: {request.request.headers}')
        log.debug(f'request body:    {request.request.body}')
        log.info(f'response status: {request.status_code}')
        log.info(f'response:        {request.content}')
        return request

    def get_headers(self):
        headers = {}
        if self.logged_in:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers


service = None


def get_service_manager():
    global service
    if service is None:
        service = CloudService()
    return service
