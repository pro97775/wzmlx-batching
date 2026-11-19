from importlib import import_module
from time import time
from uuid import uuid4

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

from ... import LOGGER, qbit_options, rss_dict, user_data
from ...core.config_manager import Config
from ...core.tg_client import TgClient, db_partition_id


def _bot_id():
    if TgClient.ID:
        return str(TgClient.ID)
    token = getattr(Config, "BOT_TOKEN", "") or ""
    return token.split(":", 1)[0] or "0"


def _part():
    if not TgClient.PARTITION:
        TgClient.PARTITION = db_partition_id(_bot_id())
    return TgClient.PARTITION


def _new_uuid():
    return uuid4().hex


class DbManager:
    def __init__(self):
        self._return = True
        self._conn = None
        self.db = None

    async def connect(self):
        try:
            if self._conn is not None:
                await self._conn.close()
            self._conn = AsyncMongoClient(
                Config.DATABASE_URL, server_api=ServerApi("1")
            )
            self.db = self._conn.wzmlx
            self._return = False
        except PyMongoError as e:
            LOGGER.error(f"Error in DB connection: {e}")
            self.db = None
            self._return = True
            self._conn = None

    async def disconnect(self):
        self._return = True
        if self._conn is not None:
            await self._conn.close()
        self._conn = None

    async def update_deploy_config(self):
        if self._return:
            return
        settings = import_module("config")
        config_file = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in vars(settings).items()
            if not key.startswith("__")
        }
        await self.db.settings.deployConfig.replace_one(
            {"_id": _part()}, config_file, upsert=True
        )

    async def update_config(self, dict_):
        if self._return:
            LOGGER.warning("update_config skipped: DB not connected")
            return
        await self.db.settings.config.update_one(
            {"_id": _part()}, {"$set": dict_}, upsert=True
        )

    async def update_aria2(self, key, value):
        if self._return:
            return
        await self.db.settings.aria2c.update_one(
            {"_id": _part()}, {"$set": {key: value}}, upsert=True
        )

    async def update_qbittorrent(self, key, value):
        if self._return:
            return
        await self.db.settings.qbittorrent.update_one(
            {"_id": _part()}, {"$set": {key: value}}, upsert=True
        )

    async def save_qbit_settings(self):
        if self._return:
            return
        await self.db.settings.qbittorrent.update_one(
            {"_id": _part()}, {"$set": qbit_options}, upsert=True
        )

    async def update_private_file(self, path):
        if self._return:
            return
        db_path = path.replace(".", "__")
        if await aiopath.exists(path):
            async with aiopen(path, "rb+") as pf:
                pf_bin = await pf.read()
            await self.db.settings.files.update_one(
                {"_id": _part()}, {"$set": {db_path: pf_bin}}, upsert=True
            )
            if path == "config.py":
                await self.update_deploy_config()
        else:
            await self.db.settings.files.update_one(
                {"_id": _part()}, {"$unset": {db_path: ""}}, upsert=True
            )

    async def update_user_data(self, user_id):
        if self._return:
            return
        data = user_data.get(user_id, {})
        data = data.copy()
        for key in ("THUMBNAIL", "RCLONE_CONFIG", "TOKEN_PICKLE", "USER_COOKIE_FILE"):
            data.pop(key, None)
        pipeline = [
            {
                "$replaceRoot": {
                    "newRoot": {
                        "$mergeObjects": [
                            data,
                            {
                                "$arrayToObject": {
                                    "$filter": {
                                        "input": {"$objectToArray": "$$ROOT"},
                                        "as": "field",
                                        "cond": {
                                            "$in": [
                                                "$$field.k",
                                                [
                                                    "THUMBNAIL",
                                                    "RCLONE_CONFIG",
                                                    "TOKEN_PICKLE",
                                                    "USER_COOKIE_FILE",
                                                ],
                                            ]
                                        },
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        ]
        await self.db.users[_part()].update_one(
            {"_id": user_id}, pipeline, upsert=True
        )

    async def update_user_doc(self, user_id, key, path=""):
        if self._return:
            return
        if path:
            async with aiopen(path, "rb+") as doc:
                doc_bin = await doc.read()
            await self.db.users[_part()].update_one(
                {"_id": user_id}, {"$set": {key: doc_bin}}, upsert=True
            )
        else:
            await self.db.users[_part()].update_one(
                {"_id": user_id}, {"$unset": {key: ""}}, upsert=True
            )

    async def rss_update_all(self):
        if self._return:
            return
        for user_id in list(rss_dict.keys()):
            await self.db.rss[_part()].replace_one(
                {"_id": user_id}, rss_dict[user_id], upsert=True
            )

    async def rss_update(self, user_id):
        if self._return:
            return
        await self.db.rss[_part()].replace_one(
            {"_id": user_id}, rss_dict[user_id], upsert=True
        )

    async def rss_delete(self, user_id):
        if self._return:
            return
        await self.db.rss[_part()].delete_one({"_id": user_id})

    async def add_incomplete_task(
        self,
        cid,
        link,
        tag,
        command="",
        user_id=0,
        reply_to_msg_id=0,
        message_thread_id=0,
    ):
        if self._return:
            return
        await self.db.tasks[_part()].update_one(
            {"link": link, "cid": cid, "user_id": user_id},
            {
                "$setOnInsert": {
                    "_id": _new_uuid(),
                    "cid": cid,
                    "tag": tag,
                    "link": link,
                    "command": command,
                    "user_id": user_id,
                    "reply_to_msg_id": reply_to_msg_id,
                    "message_thread_id": message_thread_id,
                }
            },
            upsert=True,
        )

    async def get_uploaded_file_keys(self, user_id, engine, torrent_hash):
        if self._return:
            return None
        cursor = self.db.batch_files[_part()].find(
            {
                "user_id": user_id,
                "engine": engine,
                "hash": torrent_hash,
                "uploaded": True,
            },
            {"_id": 1},
        )
        return {doc["_id"] async for doc in cursor}

    async def mark_batch_files_downloaded(
        self, user_id, engine, torrent_hash, files
    ):
        if self._return:
            return
        now = time()
        for file_info in files:
            index = int(file_info.get("index", 0))
            await self.db.batch_files[_part()].update_one(
                {
                    "_id": (
                        f"{user_id}:{engine}:{torrent_hash}:{index}"
                    )
                },
                {
                    "$set": {"downloaded": True, "downloaded_at": now},
                    "$setOnInsert": {
                        "user_id": user_id,
                        "engine": engine,
                        "hash": torrent_hash,
                        "index": index,
                        "name": str(file_info.get("name", "")),
                        "size": int(file_info.get("size") or 0),
                        "uploaded": False,
                    },
                },
                upsert=True,
            )

    async def mark_batch_file_uploaded(
        self,
        user_id,
        engine,
        torrent_hash,
        file_info,
        destination="",
        link="",
    ):
        if self._return:
            return
        index = int(file_info.get("index", 0))
        await self.db.batch_files[_part()].update_one(
            {"_id": f"{user_id}:{engine}:{torrent_hash}:{index}"},
            {
                "$set": {
                    "user_id": user_id,
                    "engine": engine,
                    "hash": torrent_hash,
                    "index": index,
                    "name": str(file_info.get("name", "")),
                    "size": int(file_info.get("size") or 0),
                    "uploaded": True,
                    "destination": destination,
                    "link": link,
                    "uploaded_at": time(),
                }
            },
            upsert=True,
        )

    async def clear_uploaded_files(self, user_id):
        if self._return:
            return 0
        result = await self.db.batch_files[_part()].delete_many(
            {"user_id": user_id}
        )
        return result.deleted_count

    async def get_pm_uids(self):
        if self._return:
            return
        return [doc["_id"] async for doc in self.db.pm_users[_part()].find({})]

    async def set_pm_users(self, user_id):
        if self._return:
            return
        if not bool(await self.db.pm_users[_part()].find_one({"_id": user_id})):
            await self.db.pm_users[_part()].insert_one({"_id": user_id})
            LOGGER.info(f"New PM User Added : {user_id}")

    async def rm_pm_user(self, user_id):
        if self._return:
            return
        await self.db.pm_users[_part()].delete_one({"_id": user_id})

    async def rm_complete_task(self, link, cid=None, user_id=None):
        if self._return:
            return
        query = {"link": link}
        if cid is not None:
            query["cid"] = cid
        if user_id is not None:
            query["user_id"] = user_id
        await self.db.tasks[_part()].delete_one(query)

    async def get_incomplete_tasks(self):
        notifier_dict = {}
        if self._return:
            return notifier_dict
        if await self.db.tasks[_part()].find_one():
            rows = self.db.tasks[_part()].find({})
            async for row in rows:
                link = row.get("link") or row.get("_id")
                if not link:
                    continue
                cid = row["cid"]
                tag = row["tag"]
                task_data = {
                    "link": link,
                    "command": row.get("command", ""),
                    "user_id": row.get("user_id", 0),
                    "reply_to_msg_id": row.get("reply_to_msg_id", 0),
                    "message_thread_id": row.get("message_thread_id", 0),
                }
                if cid in notifier_dict:
                    if tag in notifier_dict[cid]:
                        notifier_dict[cid][tag].append(task_data)
                    else:
                        notifier_dict[cid][tag] = [task_data]
                else:
                    notifier_dict[cid] = {tag: [task_data]}
        await self.db.tasks[_part()].drop()
        return notifier_dict

    async def trunc_table(self, name):
        if self._return:
            return
        await self.db[name][_part()].drop()


database = DbManager()
