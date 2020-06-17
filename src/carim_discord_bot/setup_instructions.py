import json
import os

from pkg_resources import resource_filename


def print_setup_instructions(setup_part=None):
    header = 'Setup instructions for the Carim Discord Bot'
    print_header(header)
    print('For additional help, visit the Carim Discord at https://discord.gg/kdPnVu4')
    print()
    if setup_part not in ('configuration', 'service'):
        print_setup_instructions_bot()
    if setup_part not in ('bot', 'service'):
        print_setup_instructions_config()
    if setup_part not in ('configuration', 'bot'):
        print_setup_instructions_service()


def print_setup_instructions_bot():
    permissions = ('Manage Channels', 'View Channels', 'Send Messages', 'Embed Links')
    required_permissions = ', '.join(f'"{p}"' for p in permissions[:-1])
    required_permissions += f', and "{permissions[-1]}"'
    print_header('Create bot account')
    print('Follow the guide at https://discordpy.readthedocs.io/en/v1.3.3/discord.html')
    print('Save the token for later')
    print()
    print('In step 6 under "Creating a Bot Account", make sure "Public Bot" is unticked')
    print()
    print('Under "Inviting Your Bot", step 6 has you setup the permissions for the bot')
    print(f'Currently, the bot needs {required_permissions}')
    print()


def print_setup_instructions_config():
    print_header('Update configuration')
    config_template_path = resource_filename(__name__, 'data/config.json')
    config_descriptions_path = resource_filename(__name__, 'data/config_descriptions.json')
    print('The template configuration file is located at:')
    print(config_template_path)
    print()
    if os.name == 'nt':
        print('For new installs, copy this template to a permanent location')
    elif os.name == 'posix':
        print('For new installs, copy this template to /etc/carim/config.json')
        print('You might need to create the carim directory first')
        print('STEPS')
        steps = (
            'sudo mkdir -p /etc/carim',
            f'sudo cp {config_template_path} /etc/carim/config.json',
            'sudo chmod 755 /etc/carim',
            'sudo chmod 640 /etc/carim/config.json'
        )
        for step in steps:
            print(' ', step)
    print('Edit the copy with your values following the descriptions below:')
    with open(config_descriptions_path) as f:
        descriptions = json.load(f)
    for entry_type in ('global', 'servers', 'scheduled_commands', 'custom_commands'):
        print(entry_type.upper())
        if entry_type == 'optional':
            print("  Note: if you don't want any of these features, remove the entry from the config.json")
        for entry, description in descriptions.get(entry_type, dict()).items():
            print(' ', f'"{entry}"', ':', description)
    print()
    print('To get Discord Channel IDs, you need to enable developer mode in the app:')
    print('  Settings -> Appearance -> Advanced -> Developer Mode')
    print('Then, you will be able to right click on a Channel and select "Copy ID"')
    print()


def print_setup_instructions_service():
    print_header('Run the bot as a service')
    if os.name == 'nt':
        print('Setting up a service in Windows using sc')
        print()
        print('STEPS')
        steps = (
            'Ensure your bot runs with your configuration by calling "carim-bot" from command prompt',
            '  Use Ctrl+C to quit the running process, or use --kill from the admin channel in discord',
            'Create the service with the following command',
            '  sc create CarimBot start= delayed-auto binpath= "carim-bot -c <path to config file>"',
            '  Example:',
            '  sc create CarimBot start= delayed-auto binpath ="carim-bot -c D:\\config.json"'
        )
        for step in steps:
            print(' ', step)
        print()
    elif os.name == 'posix':
        print('Setting up a systemd service in Linux')
        print()
        service_template_path = resource_filename(__name__, 'data/carim.service')
        print(f'Service file: {service_template_path}')
        print('STEPS')
        steps = (
            'Ensure your bot runs with your configuration by calling "carim-bot" from the terminal',
            '  Use Ctrl+C to quit the running process, or use --kill from the admin channel in discord',
            'Copy the service file to /etc/systemd/system/carim.service',
            'Enable and start the service with the following commands:',
            '  sudo systemctl enable carim.service',
            '  sudo systemctl start carim.service'
        )
        for step in steps:
            print(' ', step)
        print()
    else:
        print('no instructions available for your platform')
    print()


def print_header(header):
    box = '+' + '-' * (len(header) + 2) + '+'
    print(box)
    print('| ' + header + ' |')
    print(box)
