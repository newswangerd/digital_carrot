import os
import argparse
import json

from getpass import getpass

from digital_carrot import assets
from digital_carrot.config import Config

from digital_carrot.annoying_scheduler import (
    AnnoyingScheduler,
    IN_PIPE,
    OUT_PIPE,
    hash
)
import dis

def send_cmd(cmd):
    with open(IN_PIPE, "w") as pipe:
        pipe.write(cmd)

    with open(OUT_PIPE, "r") as pipe:
        return pipe.read()


def absify_the_config(cfg):
    for condition in cfg["conditions"]:
        cfg["conditions"][condition]["script"] = os.path.abspath(cfg["conditions"][condition]["script"])
    return cfg

def unblock(args):
    print(send_cmd("unblock"))


def update_config(args):
    with open(args.config[0], "r+") as f:
        cfg = json.loads(f.read())
        cfg = absify_the_config(cfg)
        f.seek(0)
        f.write(json.dumps(cfg, indent=4))
        f.truncate()

    print(send_cmd("update:" + os.path.abspath(args.config[0])))


def pause(args):
    print(send_cmd("pause:" + args.days + ":" + args.condition))

def init(args):
    files = {
        "instructions.md": assets.INSTRUCTIONS,
        "config.json": assets.JSON_CONFIG_TEMPLATE,
        "sample_script.py": assets.SAMPLE_SCRIPT
    }

    for name, template in files.items():
        if os.path.exists(name):
            continue
        with open(name, "w") as f:
            f.write(template)

def purge(args):
    print(send_cmd("purge"))

def start(args):
    if args.config:
        cfg = Config.parse_file(args.config)

        if cfg.disable_method == "password":

            while True:
                pw = getpass("Enter a password: ")
                if pw != getpass("Confirm password: "):
                    print("Passwords must match")
                else:
                    break

            sched_cfg = absify_the_config(cfg.dict(exclude_none=True))
            sched_cfg["hashed_password"] = hash(pw)
        else:
            print("ya gotta use a password for now")
            exit()

    else:
        sched_cfg = None

    AnnoyingScheduler(initial_config=sched_cfg).propagate()


def disable(args):
    print(send_cmd("disable_challenge"))
    response = getpass("Enter response: ")
    print(send_cmd("disable:" + response))


def get_parser():
    parser = argparse.ArgumentParser(description='Digital Carrot')
    subparsers = parser.add_subparsers()

    parse_unblock(subparsers)
    parse_update_config(subparsers)
    parse_pause(subparsers)
    parse_init(subparsers)
    parse_start(subparsers)
    parse_disable(subparsers)
    parse_purge_failing(subparsers)

    return parser

def parse_purge_failing(subparsers):
    parser = subparsers.add_parser('purge', help='Remove any conditions that are broken or have never returned a success.')
    parser.set_defaults(func=purge)

def parse_start(subparsers):
    parser = subparsers.add_parser('start', help='Start digital-carrot.')
    parser.add_argument('config', nargs="?", help='Path to the config file that you wish to use to launch.')
    parser.set_defaults(func=start)

def parse_init(subparsers):
    parser = subparsers.add_parser('init', help='Initialize a new digital carrot project.')
    parser.set_defaults(func=init)

def parse_disable(subparsers):
    parser = subparsers.add_parser('disable', help='Completely disable the digital carrot daemon.')
    parser.set_defaults(func=disable)

def parse_unblock(subparsers):
    parser = subparsers.add_parser('unblock', help='Request to unblock your laptop.')
    parser.set_defaults(func=unblock)

def parse_update_config(subparsers):
    parser = subparsers.add_parser(
        'update',
        help='Add a new website or condition from your config file. NOTE, you can only use this add additional constraints.'
    )
    parser.add_argument('config', nargs=1, help='Path to the config file that you wish to use to launch.')
    parser.set_defaults(func=update_config)


def parse_pause(subparsers):
    parser = subparsers.add_parser(
        'pause',
        help=(
            'Request a longer pause. This will require you to meet an additional '
            'condition of your choosing on top of your daily goals.'
        )
    )
    parser.add_argument('condition', help='Condition to pause.')
    parser.add_argument('days',  help='Number of days to pause.')
    parser.set_defaults(func=pause)

def main():
    parser = get_parser()
    args = parser.parse_args()

    if "func" not in args:
        parser.print_help()
        exit()

    try:
        if args.func != init:
            if os.getuid() != 0:
                print("You must run this program as root.")
                exit()
        args.func(args)
    except KeyboardInterrupt:
        print()
        exit(1)
