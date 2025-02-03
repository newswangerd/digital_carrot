import time
import signal
import uuid
import subprocess
import sys
import os
import json
import re
import hashlib
import datetime
import logging
import fcntl

# This file must be able to run on its own without any additional python dependencies.
# When the system starts up, this file copies itself to a different directory, creates
# a .plist file to keep itself alive in MacOS and then stores a copy of itself in memory.
# If it detects that it is being killed, it will save a copy of itself to disk, create
# a new .plist entry and start itself back up again. This makes it VERY DIFFICULT to kill.
#
# This system contains the following safguards:
#   - The scripts that are used to unblock your blocked websites are stored in memory. This
#     means that you can't just cheat by modifying the stop conditions.
#   - As mentioned above, this file will also store itself in memory. This means that you
#     cannot disable it by simply modifying the file on disk and restarting it.
#   - The config file is also stored in memory and dumped to disk periodically and when the
#     program is killed. This prevents you from cheating by changing the configurations.


LOAD_PLIST_CMD = "sudo launchctl load /Library/LaunchDaemons/com.example.{name}.plist"
WORKING_DIR = "/tmp/annoying_scheduler/"

IN_PIPE = os.path.join(WORKING_DIR, "comms_in.pipe")
OUT_PIPE = os.path.join(WORKING_DIR, "comms_out.pipe")
CONFIG_FILE = os.path.join(WORKING_DIR, "config.json")
HOSTS_FILE = "/etc/hosts"
KILLSWITCH = os.path.join(WORKING_DIR, "killswitch")
LOCK_FILE = os.path.join(WORKING_DIR, "process.lock")

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- A unique label for the daemon -->
    <key>Label</key>
    <string>com.example.{name}</string>

    <!-- Path to the Python script -->
    <key>ProgramArguments</key>
    <array>
        <string>{file}</string>
        <string>{name}</string>

    </array>

    <!-- Run the daemon at load time -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Keep the daemon alive if it crashes or exits -->
    <key>KeepAlive</key>
    <true/>

    <!-- Redirect stdout and stderr to log files -->
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>true</string>
    </dict>
</dict>
</plist>
"""

WEEKDAYS = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}

logger = logging.getLogger(__file__.split("/")[-1])
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)s: %(asctime)s - %(levelname)s - %(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)
stderr_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(stdout_handler)
logger.addHandler(stderr_handler)


def is_file_locked(filepath):
    try:
        with open(filepath, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            return False
    except (BlockingIOError, PermissionError):
        return True
    except FileNotFoundError:
        return False


def file_hash(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha.update(data)
    return sha.hexdigest()


def hash(string):
    m = hashlib.sha256()
    m.update(string.encode("utf-8"))
    return m.hexdigest()


def from_now(days=1, hour=2):
    future = datetime.datetime.today() + datetime.timedelta(days=days)
    future = future.replace(hour=hour, minute=0, second=0, microsecond=0)
    return future.isoformat()

class AnnoyingScheduler():
    kill_now = False
    scripts = {}

    def __init__(self, my_plist=None, initial_config=None):
        self.name = my_plist
        logger.info("Starting")

        # If an initial config is provided, save it to memory, otherwise use
        # the file that was saved to disk.
        if initial_config:
            self.config = initial_config
        else:
            with open(CONFIG_FILE, "r") as f:
                self.config = json.loads(f.read())

        self.config["hosts_sha"] = None

        # This is where this script reads itself into memory.
        with open(__file__, "r") as f:
            self.self = f.read()

        # Add the shebang, so that this can be run on it's own.
        if not self.self.startswith("#!"):

            # TODO: Should probably find a way to get the system python.
            self.self = f"#!{sys.executable}\n\n{self.self}"

        self.load_condition_scripts(raise_missing=True)

        if pause_con := self.config.get("pause_condition"):
            with open(pause_con["script"], "r") as f:
                self.scripts["__pause_condition__"] = f.read()

    def load_condition_scripts(self, raise_missing=False):
        # Read the condition scripts into memory so that they can't be tampered with.
        conditions_to_ignore = []
        for name, args in self.config["conditions"].items():
            if name not in self.scripts:
                try:
                    script_path = args.get("internal_script", args["script"])
                    if not os.path.exists(script_path):
                        script_path = args["script"]
                    with open(script_path, "r") as f:
                        self.scripts[name] = f.read()
                except FileNotFoundError:
                    if raise_missing:
                        raise
                    conditions_to_ignore.append(name)
        for name in conditions_to_ignore:
            del self.config["conditions"][name]

    # This method dumps all of the stuff that is held in memory to disk, to prevent
    # tampering.
    def dump_to_disk(self, new_name=None):
        # Scripts are renamed, made executable and stored in a safe location.
        for name, script in self.scripts.items():
            script_path = os.path.join(WORKING_DIR, name)
            with open(script_path, "w") as f:
                f.write(script)
                subprocess.call(f"sudo chmod u+x {script_path}".split(" "))
                if name == "__pause_condition__":
                    self.config["pause_condition"]["internal_script"] = script_path
                else:
                    self.config["conditions"][name]["internal_script"] = script_path


        with open(CONFIG_FILE, "w") as f:
            f.write(json.dumps(self.config, indent=4))

        name = self.name
        if new_name is not None:
            name = new_name

        assert name is not None

        # Write this script back to disk.
        with open(self.get_python_file(name), "w") as f:
            f.write(self.self)

        subprocess.call(f"sudo chmod u+x {self.get_python_file(name)}".split(" "))

        # Write the MacOS .plist config back to disk.
        with open(self.get_plist_file(name), "w") as f:
            new_plist = PLIST.format(
                log_path=os.path.join(WORKING_DIR, "out.log"),
                file=self.get_python_file(name),
                name=name,
            )
            f.write(new_plist)

    # This function clears the blocked websites out of /etc/hosts
    def clear_hosts(self):
        with open(HOSTS_FILE, "r") as hosts:
            data = hosts.read()

        with open(HOSTS_FILE, "w") as hosts:
            hosts.write(re.sub(r"#fitblock\n[\s\S]*#/fitblock", "", data, flags=re.S))

    # Set the blocked websites in /etc/hosts to point to localhost.
    def set_hosts(self):
        blocked = ["#fitblock\n"]
        for site in self.config["blocked_websites"]:
            blocked.append(f"127.0.0.1 {site}")
            blocked.append(f"127.0.0.1 www.{site}")
            blocked.append(f"127.0.0.1 *.{site}")
        blocked.append("\n#/fitblock")

        with open(HOSTS_FILE, "a") as hosts:
            hosts.write("\n".join(blocked))

        self.config["hosts_sha"] = file_hash(HOSTS_FILE)

    def allow_exit(self):
        return os.path.exists(KILLSWITCH)

    # This gets run when the system detects that it has been killed. If we're allowing
    # the program to stop, it will clean itself up. Otherwise, it copies itself to a
    # new location and starts over.
    def exit_gracefully(self, signum, frame):
        self.kill_now = True

        if not self.allow_exit():
            self.propagate()

        logger.info("killed " + str(self.name))

        self.delete_self()

    # Generate the MacOS .plist file from the template saved here.
    def get_plist_file(self, name=None):
        if name is None:
            name = self.name
        return f"/Library/LaunchDaemons/com.example.{name}.plist"

    def get_python_file(self, name=None):
        if name is None:
            name = self.name
        assert name is not None
        return os.path.join(WORKING_DIR, f"{name}.py")

    # This function copies the program to a new location and starts running it again
    def propagate(self):
        logger.info("Copying self to secure location...")
        new_name = str(uuid.uuid4())
        self.dump_to_disk(new_name=new_name)
        subprocess.call(LOAD_PLIST_CMD.format(name=new_name).split(" "))

    # Send a message on the output pipe for the digital-carrot client to read.
    def pipe_out(self, msg):
        try:
            out_pipe = os.open(OUT_PIPE, os.O_WRONLY | os.O_NONBLOCK)
            os.write(out_pipe, msg.encode("utf-8"))
            os.close(out_pipe)
        except OSError:
            logger.error("Could not send to client: " + msg)

    # Clean up any files that this process copied so that it won't automatically run.
    def delete_self(self):
        os.remove(self.get_plist_file())
        os.remove(self.get_python_file())

    # Read in an updated config from the user. This will only append new websites and
    # conditions. It can't be used to remove anything from the config.
    def update_from_cfg(self, cfg_file):
        with open(cfg_file, "r+") as f:
            cfg = json.loads(f.read())
            for website in cfg["blocked_websites"]:
                if website not in self.config["blocked_websites"]:
                    self.config["blocked_websites"].append(website)
            self.config["conditions"] = {**cfg["conditions"], **self.config["conditions"]}

            # Write the current config back to the user's file so that they have an up to date
            # version of it.
            f.seek(0)
            f.write(json.dumps(self.config, indent=4))
            f.truncate()

        self.load_condition_scripts()
        self.dump_to_disk()

        return "Updated " + cfg_file

    def pause(self, num_days):
        if pause_con := self.config["pause_condition"]:
            max_days = pause_con.get("max_pause_days", 3)
            if num_days > max_days:
                self.pipe_out(f"You're not allowed to pause more than {max_days} days")
                return
            msg, unblocked = self.unblock()
            if not unblocked:
                self.pipe_out("Please finish your goals before requesting a longer pause.\n" + msg)
                return
            r = subprocess.run([pause_con["internal_script"], ] + pause_con["args"], capture_output=True)

            if r.returncode == 0:
                self.config["pause_until"] = from_now(days=num_days)
                self.pipe_out("Pause successful: " + r.stdout.decode("utf-8"))
            else:
                self.pipe_out("Pause failed: " + r.stdout.decode("utf-8"))


        else:
            self.pipe_out("Pausing is not enabled.")

    def purge_failed(self):
        msgs = []
        removed = []
        conditions_copy = {**self.config["conditions"]}
        for name, cfg in self.config["conditions"].items():
            if cfg.get("validated", False):
                msgs.append(f"[✓] {name}")
            else:
                msgs.append(f"[x] {name}")
                removed.append(name)
                del conditions_copy[name]
                del self.scripts[name]
        self.config["conditions"] = conditions_copy
        msg = "Status:\n"
        msg += '\n'.join(msgs)

        if removed:
            msg += "\n\nRemoved the following failed conditions:\n"
            msg += '\n'.join(removed)

        self.pipe_out(msg)

    # This is how the daemon receives commands from the client. We're using two named pipes.
    # There is an input pipe that this daemon listens to commands on and an output pipe that
    # it will send responses to. To avoid multiple theads, this will simply check the input
    # pipe every so often for commands. We don't really care about latency, so this is fine.
    def check_cmds(self):
        self.init_pipes(create_in=False)
        data = os.read(self.in_pipe, 4096).decode("utf-8")
        if len(data) > 0:
            logger.info("Received command: '" + data + "'")
            if data.startswith("unblock"):
                resp, _ = self.unblock()
                self.pipe_out(resp)
            elif data.startswith("disable_challenge"):
                self.pipe_out("Password")
            elif data.startswith("disable"):
                challenge_resp = data.split(":", maxsplit=1)[1]
                if hash(challenge_resp) == self.config["hashed_password"]:
                    self.clear_hosts()
                    self.delete_self()
                    self.kill_now = True
                    self.pipe_out("Shutting down")
                else:
                    self.pipe_out("Wrong password")
            elif data.startswith("update"):
                cfg = data.split(":", maxsplit=1)[1]
                self.pipe_out(self.update_from_cfg(cfg))
            elif data.startswith("pause"):
                days = int(data.split(":", maxsplit=1)[1])
                self.pause(days)
            elif data.startswith("purge"):
                self.purge_failed()
            else:
                self.pipe_out(str(data))

    def heartbeat(self):
        logger.debug("Heartbeat")

    def enforce(self):
        self.dump_to_disk()

        if pause := self.config.get("pause_until"):
            dt = datetime.datetime.fromisoformat(pause)
            if datetime.datetime.now() < dt:
                logger.debug("Pause detected.")
                return

        if file_hash(HOSTS_FILE) != self.config["hosts_sha"]:
            logger.info(HOSTS_FILE + " was changed. Fixing.")
            self.clear_hosts()
            self.set_hosts()
        else:
            logger.debug("No changes detected in hosts file.")


    def unblock(self):
        logger.info("Attempting unblock websites.")
        self.dump_to_disk()
        messages = []
        complete = True

        for name, script in self.config["conditions"].items():
            if WEEKDAYS[datetime.datetime.today().weekday()] not in script["require_on"]:
                messages.append(f"[✓] {name}: Not required today.")
                continue

            cmd = [script["internal_script"], ] + script["args"]
            r = subprocess.run(cmd, capture_output=True)
            msg = r.stdout.decode('utf-8').strip()

            if r.returncode == 0:
                check = "✓"
                self.config["conditions"][name]["validated"] = True
            elif r.returncode == 1:
                self.config["conditions"][name]["validated"] = False
                check = "x"
                msg = "This script failed with an unknown error. To purge it from the system 'run digital-carrot purge'"
                logger.error(f"command '{' '.join(cmd)}' failed")
                logger.error(r.stderr)
                logger.error(r.stdout)
                complete = False
            else:
                complete = False
                check = "x"

            messages.append(f"[{check}] {name}: {msg}")


        if complete:
            messages.append("You met all your goals! Well done.")

            self.config["pause_until"] = from_now(days=1)

            # test = datetime.datetime.today() + datetime.timedelta(seconds=10)
            # self.config["pause_until"] = test.isoformat()

            self.clear_hosts()
            logger.info("Websites unlocked")
        else:
            messages.append("Still missing some goals.")

        return ("\n".join(messages), complete)

    def init_pipes(self, create_in=True):
        if not os.path.exists(IN_PIPE):
            os.mkfifo(IN_PIPE, mode=0o644)
            create_in = True

        if not os.path.exists(OUT_PIPE):
            os.mkfifo(OUT_PIPE, mode=0o644)

        if create_in:
            self.in_pipe = os.open(IN_PIPE, os.O_RDONLY | os.O_NONBLOCK)

    def run(self):
        got_lock = False
        lockfile = None

        for i in range(6):
            if not is_file_locked(LOCK_FILE):
                got_lock = True
                break
            logger.info(f"waiting for lock")
            time.sleep(5)

        if got_lock:
            lockfile = open(LOCK_FILE, "a")
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
            logger.info(f"got lock")
        else:
            logger.info(f"lock timed out")
            self.delete_self()
            return

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.init_pipes()

        try:
            while not self.kill_now:
                self.heartbeat()

                if int(time.time()) % 5 == 0:
                    self.enforce()
                    self.check_cmds()

                time.sleep(1)
        except:
            self.delete_self()
            self.kill_now = True
            raise
        finally:
            os.close(self.in_pipe)
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)
            lockfile.close()

def main():
    if len(sys.argv) < 2:
        return

    AnnoyingScheduler(sys.argv[1]).run()

if __name__ == "__main__":
    main()
