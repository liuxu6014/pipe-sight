"""Kafka poll recovery uses a transport double, not a broker or production database."""

import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE_PATH = Path(__file__).resolve().parents[2] / 'src/app/intelligence/tasks/kafka_content_consumer.py'


@pytest.mark.asyncio
async def test_processing_configuration_error_rewinds_before_later_offsets_can_commit():
    path = SOURCE_PATH
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == '_consume_once'
    )
    message = SimpleNamespace(topic='content', partition=0, offset=5)
    later = SimpleNamespace(topic='content', partition=0, offset=6)
    seen, rewinds, commits = [], [], []

    class Consumer:
        polls = 0

        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            pass

        async def stop(self):
            pass

        async def getmany(self, **kwargs):
            self.polls += 1
            return {'partition': [message, later] if self.polls == 1 else [message]}

        def seek(self, partition, offset):
            rewinds.append((partition, offset))

        async def commit(self, offsets):
            commits.append(offsets)

    async def handle(msg, args):
        seen.append(msg.offset)
        return 'error' if len(seen) == 1 else 'inserted'

    scope = {
        'asyncio': asyncio,
        'AIOKafkaConsumer': Consumer,
        'KafkaConfig': SimpleNamespace(kafka_topic='content', kafka_bootstrap_servers='', kafka_group_id='test'),
        '_handle_message': handle,
        'TopicPartition': lambda topic, partition: (topic, partition),
        'OffsetAndMetadata': lambda offset, metadata: offset,
        'monotonic': lambda: 0,
        'STATS_LOG_INTERVAL_SECONDS': 10,
        'logger': logging.getLogger(__name__),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), scope)
    await scope['_consume_once'](asyncio.Event(), SimpleNamespace(from_earliest=False, limit=2, dry_run=False))
    assert seen == [5, 5]
    assert rewinds == [(('content', 0), 5)]
    assert commits == [{('content', 0): 6}]
