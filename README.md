# Digital Carrot

This project aims to help you achieve your goals by hanging a digital carrot in front of you for motivation!

This program will block you from accessing a set of user configurable websites on your computer until you have
met a certain set of goals for the day. These goals can be anything you want, as long as it is enforceable by
a computer script.

## Requirements

Currently only MacOS is supported. Linux support is planned. Windows will probably never be supported.

## Installation

Clone this repository, cd to it and run `pip install -e .`

## How it Works

The first step is to create a new project using `digital-carrot init`. This will lay down a directory with
the following files:

- `config.json`
- `sample_script.py`

The `config.json` file looks like this:

```json
{
    "blocked_websites": [
        "example.com"
    ],
    "conditions": {
        "example_condition": {
            "script": "sample_script.py",
            "args": ["arg1", "arg2"],
            "require_on": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        }
    },
    "disable_method": "password",
    "pause_condition": {
        "script": "sample_script.py",
        "args": [],
        "max_pause_days": 3
    }
}
```

You'll use this file to set up the restrictions you want to place on yourself!

### Setting your Conditions
This is where you provide your unlock scripts. Lets say you want to walk 10,000 steps per
day. You can create a script like the one bellow that checks an API for the smart watch of your choice:

```python
#!/usr/bin/python3
import requests
import sys

steps = requests.get("https://my_api.example.com").json()["steps"]
required_steps = int(sys.argv[1])

if steps >= required_steps:
    print("You got all your steps!")
    exit(0)
else:
    exit(2)
exit(0)
```

Save this file to `check_steps.py` and then add the following to your conditions:

```json
{
    "conditions": {
        "complete_steps": {
            "script": "check_steps.py",
            "args": ["10000"],
            "require_on": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        }
    }
}
```

With this configuration, the system will unblock once `check_steps.py` returns a success.

### Starting the Blocker

To start the blocker run `sudo digital-carrot start config.json`. This will load the blocker with the configurations
you just created. You will be prompted for a password. *MAKE SURE YOU DON'T FORGET IT!* The only way to stop
the system will be to provide this password.

Once you have accomplished your goals for the day simply run `sudo digital-carrot unblock`. The system will check
if you met your goals. If you have, it will stay unblocked until 2am on the next day.

*WARNING*

Once you start digital carrot, you cannot edit anything about your configuration unless you disable it completely.

This program is intentionally very tamper resistant! If you lose your password, it will be very hard for you to
stop the system from running.

### Addition Additional Restrictions

New websites and conditions can be added by adding them to your `config.json` and then running
`digital-carrot update config.json`. NOTE: You can only add restrictions this way. Once your
config is set up, there's no going back!

### What if one of my scripts breaks?

There is a reason we use exit code 2 to indicate failure, instead of exit code 1. If one of your scripts
ever runs into an unexpected error, you can run `digital carrot purge` and it will remove any conditions
that are broken or have never returned a success from your configuration.

## config.json

The config file takes the following settings:

- `blocked_websites`: a list of websites that you want to block.
- `conditions`: the conditions that need to be met to unblock access to your websites.
- `disable_method`: your escape hatch for disabling the blocker complete. Right now
  only `password` is supported, but more will be coming.
- `pause_condition`: This is optional. If you want to be able to take a longer break,
  you can provide another script here. This will let you use the `digital-carrot pause <days>`
  command to take a break. You can only activate this if you have already hit your
  daily goals.
