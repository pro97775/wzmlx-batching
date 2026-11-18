from sys import exit
from hashlib import sha256
from importlib import import_module
from logging import (
    FileHandler,
    StreamHandler,
    INFO,
    basicConfig,
    error as log_error,
    info as log_info,
    getLogger,
    ERROR,
)
from os import path, environ
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from subprocess import run as srun, call as scall

getLogger("pymongo").setLevel(ERROR)

var_list = ['BOT_TOKEN', 'TELEGRAM_API', 'TELEGRAM_HASH', 'OWNER_ID', 'DATABASE_URL', 'BASE_URL', 'UPSTREAM_REPO', 'UPSTREAM_BRANCH']
DB_OVERRIDE_KEYS = ("UPSTREAM_REPO", "UPSTREAM_BRANCH", "UPDATE_PKGS")
DB_PARTITION_SALT = b"wzmlx_v3_db_partition_salt"


def db_partition_id(bot_id):
    raw = sha256(DB_PARTITION_SALT + str(bot_id).encode("utf-8")).hexdigest()
    return f"p_{raw[:24]}"

basicConfig(
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)
try:
    settings = import_module("config")
    config_file = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in vars(settings).items()
        if not key.startswith("__")
    }
except ModuleNotFoundError:
    log_info("Config.py file is not Added! Checking ENVs..")
    config_file = {}

env_updates = {key: value.strip() if isinstance(value, str) else value for key, value in environ.items() if key in var_list}
if env_updates:
    log_info("Config data is updated with ENVs!")
    config_file.update(env_updates)

BOT_TOKEN = config_file.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

BOT_ID = BOT_TOKEN.split(":", 1)[0]
DB_PART = db_partition_id(BOT_ID)

if DATABASE_URL := config_file.get("DATABASE_URL", "").strip():
    try:
        conn = MongoClient(DATABASE_URL, server_api=ServerApi("1"))
        db = conn.wzmlx
        config_dict = db.settings.config.find_one({"_id": DB_PART})
        if config_dict is None:
            config_dict = db.settings.config.find_one({"_id": BOT_ID})
        if config_dict is not None:
            for key in DB_OVERRIDE_KEYS:
                value = config_dict.get(key)
                if value is None:
                    continue
                if key == "UPSTREAM_REPO" and not str(value).strip():
                    continue
                config_file[key] = value
        conn.close()
    except Exception as e:
        log_error(f"Database ERROR: {e}")

UPSTREAM_REPO = config_file.get("UPSTREAM_REPO", "").strip()
UPSTREAM_BRANCH = config_file.get("UPSTREAM_BRANCH", "").strip() or "wzv3"

if UPSTREAM_REPO:
    if path.exists(".git"):
        srun(["rm", "-rf", ".git"])

    update = srun(
        [
            f"git init -q \
                     && git config --global user.email 105407900+SilentDemonSD@users.noreply.github.com \
                     && git config --global user.name SilentDemonSD \
                     && git add . \
                     && git commit -sm update -q \
                     && git remote add origin {UPSTREAM_REPO} \
                     && git fetch origin -q \
                     && git reset --hard origin/{UPSTREAM_BRANCH} -q"
        ],
        shell=True,
    )

    repo = UPSTREAM_REPO.split("/")
    UPSTREAM_REPO = f"https://github.com/{repo[-2]}/{repo[-1]}"
    if update.returncode == 0:
        log_info("Successfully updated with Latest Updates !")
    else:
        log_error("Something went Wrong ! Recheck your details or Ask Support !")
    log_info(f"UPSTREAM_REPO: {UPSTREAM_REPO} | UPSTREAM_BRANCH: {UPSTREAM_BRANCH}")


UPDATE_PKGS = config_file.get("UPDATE_PKGS", "True")
if (isinstance(UPDATE_PKGS, str) and UPDATE_PKGS.lower() == "true") or UPDATE_PKGS:
    scall("uv pip install -U -r requirements.txt", shell=True)
    log_info("Successfully Updated all the Packages !")
