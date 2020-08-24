import argparse
import json
import os
import dataclasses
from getpass import getpass
from os import environ, path, makedirs
from typing import Optional, List

from winix import WinixAccount, WinixDevice, WinixDeviceStub
from winix.auth import WinixAuthResponse, login, refresh

DEFAULT_CONFIG_PATH = '~/.config/winix/config.json'


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        return dataclasses.asdict(o) if dataclasses.is_dataclass(o) else super().default(o)


class Configuration:
    exists: bool

    cognito: Optional[WinixAuthResponse]
    devices: List[WinixDeviceStub]

    def __init__(self, config_path: str):
        self.config_path = path.expanduser(config_path)
        self._load_from_disk()

    @property
    def device(self) -> WinixDeviceStub:
        return self.devices[0]

    def _load_from_disk(self):
        if path.exists(self.config_path):
            with open(self.config_path) as f:
                js = json.load(f)
                self.exists = True
                self.cognito = WinixAuthResponse(**js['cognito']) if js.get('cognito') is not None else None
                self.devices = [WinixDeviceStub(**d) for d in js.get('devices', [])]
        else:
            self.exists = False
            self.cognito = None
            self.devices = []

    def save(self):
        makedirs(path.dirname(self.config_path), mode=0o755, exist_ok=True)
        with open(os.open(self.config_path, os.O_CREAT | os.O_WRONLY, 0o755), 'w') as f:
            json.dump({
                'cognito': self.cognito,
                'devices': self.devices,
            }, f, cls=JSONEncoder)


class Cmd:
    def __init__(self, args: argparse.Namespace, config: Configuration):
        self.args = args
        self.config = config


class LoginCmd(Cmd):
    parser_args = {
        'name': 'login',
        'help': 'Authenticate Winix account',
    }

    @classmethod
    def add_parser(cls, parser):
        parser.add_argument('--username', help='Username (email)', required=False)
        parser.add_argument('--password', help='Password', required=False)
        parser.add_argument('--refresh', dest='refresh', action='store_true',
                            help='Refresh the Winix Cognito token instead of logging in')

    def execute(self):
        if getattr(self.args, 'refresh'):
            return self._refresh()
        else:
            return self._login()

    def _login(self):
        username = getattr(self.args, 'username') or input('Username (email): ')
        password = getattr(self.args, 'password') or getpass('Password: ')

        self.config.cognito = login(username, password)
        account = WinixAccount(self.config.cognito.access_token)
        account.register_user(username)
        account.check_access_token()
        self.config.devices = account.get_device_info_list()
        self.config.save()
        print('Ok')

    def _refresh(self):
        self.config.cognito = refresh(
            user_id=self.config.cognito.user_id,
            refresh_token=self.config.cognito.refresh_token,
        )
        WinixAccount(self.config.cognito.access_token).check_access_token()
        self.config.save()
        print('Ok')


class DevicesCmd(Cmd):
    parser_args = {
        'name': 'devices',
        'help': 'List registered Winix devices',
    }

    @classmethod
    def add_parser(cls, parser):
        pass

    def execute(self):
        print(f'{len(self.config.devices)} devices:')

        for i, device in enumerate(self.config.devices):
            fields = (
                ('Device ID', device.id),
                ('Mac', device.mac),
                ('Alias', device.alias),
                ('Location', device.location_code)
            )

            label = " (default)" if i == 0 else ""
            print(f'Device#{i}{label} '.ljust(50, '-'))

            for f, v in fields:
                print(f'{f:>15} : {v}')

            print('')

        print('Missing a device? You might need to run refresh.')


class FanCmd(Cmd):
    parser_args = {
        'name': 'fan',
        'help': 'Fan speed controls',
    }

    @classmethod
    def add_parser(cls, parser):
        parser.add_argument('level', help='Fan level', choices=['low', 'medium', 'high', 'turbo'])

    def execute(self):
        level = self.args.level
        # TODO(Hunter): Support getting the fan state instead of only being able to set it
        device = WinixDevice(self.config.device.id)
        getattr(device, level)()
        print('ok')


class PowerCmd(Cmd):
    parser_args = {
        'name': 'power',
        'help': 'Power controls',
    }

    @classmethod
    def add_parser(cls, parser):
        parser.add_argument('state', help='Power state', choices=['on', 'off'])


class RefreshCmd(Cmd):
    parser_args = {
        'name': 'refresh',
        'help': 'Refresh account device metadata',
    }

    @classmethod
    def add_parser(cls, parser):
        pass

    def execute(self):
        account = WinixAccount(self.config.cognito.access_token)
        self.config.devices = account.get_device_info_list()
        self.config.save()
        print('Ok')


def main():
    parser = argparse.ArgumentParser(description='Winix C545 Air Purifier Control')
    subparsers = parser.add_subparsers(dest='cmd')

    commands = {
        cls.parser_args['name']: cls
        for cls in (FanCmd, PowerCmd, LoginCmd, RefreshCmd, DevicesCmd,)
    }

    for cls in commands.values():
        sub = subparsers.add_parser(**cls.parser_args)
        cls.add_parser(sub)

    args = parser.parse_args()
    cmd = args.cmd

    if cmd is None:
        parser.print_help()
        return

    cls = commands[cmd]
    cls(args, config=Configuration('~/.config/winix/config.json')).execute()