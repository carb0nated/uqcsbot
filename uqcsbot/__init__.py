import os
import sys
import importlib
import logging
import argparse
from base64 import b64decode
import json
import requests
from uqcsbot.base import UQCSBot, bot, Command

SLACK_VERIFICATION_TOKEN = os.environ.get("SLACK_VERIFICATION_TOKEN", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# UQCSTesting bot tokens. Everything is base64 encoded to somewhat circumvent
# token tracking by GitHub etal.
#
# Order: uqcsbot-alpha, uqcsbot-beta, uqcsbot-gamma, uqcsbot-delta
BOT_TOKENS = {'U9LA6BX8X': b64decode('eG94Yi0zMjYzNDY0MDUzMDMteGpIbFhlamVNUG1McVhRSnNnZFoyZVhT').decode('utf-8'),
              'U9K81NL7N': b64decode('eG94Yi0zMjUyNzM3NjgyNjAtNFd0SGhRUWhLb3BSVUlJNFJuc0VRRXJL').decode('utf-8'),
              'U9JJZ1ZJ4': b64decode('eG94Yi0zMjQ2NDUwNjc2MTYtaHNpR3B3S0ZhSnY3bzJrOW43UU9uRXFp').decode('utf-8'),
              'U9K5W508K': b64decode('eG94Yi0zMjUyMDAxNzAyOTEtTlJvdVVLcWdyVEpVSE9SMjBoUzhBcnhW').decode('utf-8')}
# Channel group which contains all the bots. Easy way to get all their ids.
SECRET_BOT_MEETING_ROOM = 'G9JJXHF7S'
# Mitch's UQCSTesting Slack API Token. No touchie >:(
API_TOKEN = b64decode('eG94cC0yNjA3ODI2NzQ2MTAtMjYwMzQ1MTQ0NTI5LTMyNTEyMzU5ODExNS01YjdmYjlhYzAyZWYzNDAyNTYyMTJmY2Q2YjQ1NmEyYg==').decode('utf-8')

logger = logging.getLogger("uqcsbot")

def get_bot_info(user_id):
    '''
    Returns info about the bot

    See https://api.slack.com/methods/users.info for the contents of info
    '''
    api_url = 'https://slack.com/api/users.info'
    response = requests.get(api_url, params={'token': API_TOKEN, 'user': user_id})

    if response.status_code != requests.codes['ok']:
        logger.error(f'Received status code {response.status.code}')
        sys.exit(1)

    json_contents = json.loads(response.content)
    if not json_contents['ok']:
        logger.error(json_contents['error'])
        sys.exit(1)

    return json_contents

def is_bot_active(info):
    '''
    Returns true if the provided bot info describes an active bot (i.e. not deleted)
    '''
    return info['ok'] and info['user']['is_bot'] and not info['user']['deleted']


def is_bot_avaliable(info, user_id):
    '''
    Returns true if the given user_id is an active bot that is avaliable (i.e. is
    not currently 'active' which would mean it is in use by another user).
    '''

    api_url = 'https://slack.com/api/users.getPresence'
    response = requests.get(api_url, params={'token': API_TOKEN, 'user': user_id})
    if response.status_code != requests.codes['ok']:
        return False

    json_contents = json.loads(response.content)
    return json_contents['ok'] and json_contents['presence'] == 'away'


def get_free_test_bot():
    '''
    Pings a channel on the UQCSTesting Slack that contains all the available
    bots, and Mitch. We can poll this channel to find  bots which are 'away'
    (that is, not currently being used by anyone else)

    Returns some bot info, and token in a dictionary: {'info': ..., 'token': ...}

    See https://api.slack.com/methods/users.info for the contents of info
    '''
    api_url = 'https://slack.com/api/conversations.members'
    response = requests.get(api_url, params={'token': API_TOKEN, 'channel': SECRET_BOT_MEETING_ROOM})
    if response.status_code != requests.codes['ok']:
        logger.error(f'Received status code {response.status.code}')
        sys.exit(1)

    json_contents = json.loads(response.content)
    if not json_contents['ok']:
        logger.error(json_contents['error'])
        sys.exit(1)

    for user_id in json_contents['members']:
        info = get_bot_info(user_id)
        if is_bot_active(info) and is_bot_avaliable(info, user_id):
            return {'info': info, 'token': BOT_TOKENS.get(user_id, None)}
    return None

def get_test_bot_name(info):
    '''
    Get's a bot's name from provided info
    '''
    return info['user']['name']


def main():
    # Import scripts
    dir_path = os.path.dirname(__file__)
    scripts_dir = os.path.join(dir_path, 'scripts')
    for sub_file in os.listdir(scripts_dir):
        if not sub_file.endswith('.py') or sub_file == '__init__.py':
            continue
        module = f'uqcsbot.scripts.{sub_file[:-3]}'
        importlib.import_module(module)

    # Setup the CLI argument parser
    parser = argparse.ArgumentParser(description='Run UQCSBot')
    parser.add_argument('--local',
                        dest='local',
                        action='store_true',
                        help='Runs the bot in local (CLI) mode')
    parser.add_argument('--dev',
                        dest='dev',
                        action='store_true',
                        help='Runs the bot in development mode (auto assigns a '
                             'bot on the uqcstesting Slack team)')
    parser.add_argument('--log_level',
                        dest='log_level',
                        default='INFO',
                        help='Specifies the output logging level to be used '
                             '(i.e. DEBUG, INFO, WARNING, ERROR, CRITICAL)')

    # Retrieve the CLI args
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)

    # Run the bot
    if args.local:
        bot.run_cli()
    else:
        # If in development mode, attempt to allocate an available bot token,
        # else stick with the default. If no bot could be allocated, exit.
        test_bot = get_free_test_bot() if args.dev else SLACK_BOT_TOKEN
        if test_bot is None:
            logger.error('Something went wrong during bot allocation. '
                  'Please ensure there are bots available and try again later. '
                  'Exiting.')
            sys.exit(1)
        logger.info("Bot name: " + get_test_bot_name(test_bot['info']))
        bot.run(test_bot['token'], SLACK_VERIFICATION_TOKEN)

if __name__ == "__main__":
    main()
