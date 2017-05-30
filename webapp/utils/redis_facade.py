import json
from os.path import basename, splitext

import redis

from algoweb.settings import PACKAGE_URL, REDIS_POOL_CONFIG
from webapp.utils.main import get_package_link

connection_pool = redis.ConnectionPool(**REDIS_POOL_CONFIG)


def get_redis(**kwargs) -> redis.Redis:
    rs = redis.Redis(connection_pool=connection_pool, **kwargs)
    rs.ping()
    return rs


def upload_submission(submission):
    rs = get_redis()

    for file in submission.submissionfile_set.all():
        rs.hset("submission:%s" % submission.uuid, "file:%s" % file.name, file.contents.read())

    download_url = get_package_link(submission.task)

    if submission.queue_priority not in ['high', 'medium', 'low']:
        raise RuntimeError('Invalid queue_priority, expected one from: high, medium, low')

    submission.queue_seq_number = rs.incrby("queue:{}:counter".format(submission.queue_priority), 1)

    rs.zadd("queue:{}:order".format(submission.queue_priority), submission.uuid, submission.queue_seq_number)

    rs.rpush("queue:{}".format(submission.queue_priority), json.dumps({
        "uuid": submission.uuid,
        "package": {
            "name": splitext(basename(submission.task.package.name))[0],
            "version": submission.task.version,
            "url": PACKAGE_URL + download_url
        },
        "features": ["async_report"]
    }))

    submission.save()


def get_submission_status(uuid, queued_priority):
    rs = get_redis()

    status = rs.get('status:%s' % uuid)

    if status:
        return "processing", json.loads(status.decode('utf-8'))

    queue_pos = rs.zrank("queue:{}:order".format(queued_priority), uuid)

    if queue_pos is None:
        return "not-found", None

    if queued_priority == "medium" or queued_priority == "low":
        queue_pos += rs.zcard("queue:high:order")

    if queued_priority == "low":
        queue_pos += rs.zcard("queue:medium:order")

    return "queued", {"position": int(queue_pos) + 1}


def get_worker_list():
    rs = get_redis()

    worker_list = rs.keys("queue:alive_workers:*")
    state = {}

    for worker_key in worker_list:
        worker_name = worker_key.decode('utf-8').split(':')[2]
        state[worker_name] = json.loads(rs.get(worker_key).decode('utf-8'))

    return sorted(state.items())


def get_queue_contents():
    rs = get_redis()

    for queue_name in ["high", "medium", "low"]:
        queue_content = rs.lrange("queue:{}".format(queue_name), 0, -1)

        for queue_item in queue_content:
            item_data = json.loads(queue_item)
            item_data['priority'] = queue_name

            yield item_data
