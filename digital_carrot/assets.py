import sys

JSON_CONFIG_TEMPLATE="""{
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
}"""

SAMPLE_SCRIPT=f"""#!{sys.executable}

# Note ^ the shebang is very important. Scripts need to be able to run by themselves.
# eg "$ ./sample_script.py" not "$ python3 ./sample_script.py"

# Anything printed to stdout will get shown to your in the client when you unblock.
print("Success! You completed your goal.")

# Exit codes are important. If they script exits with:
# 0 -> This indicates that you've accomplished this goal
# 1 -> There was an unexpected error. The system is failsafe. If this code is
#      received, digital_carrot will shut itself down.
# 2 -> This goal has not been met.
#
# If any of your scripts return an exit code of 2, the system won't unblock.
exit(0)
"""

INSTRUCTIONS = """
"""
