import mailbox
import os

import pytest

from boltons.mboxutils import mbox_readonlydir


def _write_mbox(path, subjects=('one', 'two')):
    mb = mbox_readonlydir(path, create=True)
    for subject in subjects:
        mb.add('Subject: %s\n\nbody of %s' % (subject, subject))
    mb.flush()
    mb.close()
    return path


def _subjects(path, **kwargs):
    mb = mbox_readonlydir(path, **kwargs)
    try:
        return [mb[key]['subject'] for key in mb.keys()]
    finally:
        mb.close()


def test_add_and_read_roundtrip(tmp_path):
    path = str(tmp_path / 'mbox')
    _write_mbox(path, ('alpha', 'beta'))

    mb = mbox_readonlydir(path)
    try:
        assert len(mb) == 2
        assert list(mb.keys()) == [0, 1]
        assert mb[0]['subject'] == 'alpha'
        assert mb[1]['subject'] == 'beta'
    finally:
        mb.close()


def test_flush_without_pending_is_noop(tmp_path):
    path = _write_mbox(str(tmp_path / 'mbox'))
    before = os.path.getsize(path)

    mb = mbox_readonlydir(path)
    try:
        mb.flush()
        assert os.path.getsize(path) == before
        assert len(mb) == 2
    finally:
        mb.close()


def test_delete_truncates_and_rewrites(tmp_path):
    path = _write_mbox(str(tmp_path / 'mbox'), ('keep', 'remove'))
    before = os.path.getsize(path)

    mb = mbox_readonlydir(path)
    try:
        del mb[1]
        mb.flush()
        assert len(mb) == 1
        assert mb[0]['subject'] == 'keep'
    finally:
        mb.close()

    assert os.path.getsize(path) < before
    assert _subjects(path) == ['keep']


def test_delete_all_messages_leaves_empty_mailbox(tmp_path):
    path = _write_mbox(str(tmp_path / 'mbox'))

    mb = mbox_readonlydir(path)
    try:
        for key in list(mb.keys()):
            del mb[key]
        mb.flush()
        assert len(mb) == 0
    finally:
        mb.close()

    assert _subjects(path) == []


def test_delete_with_maxmem_streams_in_chunks(tmp_path):
    path = _write_mbox(str(tmp_path / 'mbox'), ('first', 'second', 'third'))

    mb = mbox_readonlydir(path, maxmem=0)
    try:
        del mb[1]
        mb.flush()
        assert [mb[key]['subject'] for key in mb.keys()] == ['first', 'third']
    finally:
        mb.close()

    assert _subjects(path) == ['first', 'third']


def test_flush_detects_external_file_change(tmp_path):
    path = _write_mbox(str(tmp_path / 'mbox'))

    mb = mbox_readonlydir(path)
    del mb[0]
    with open(path, 'ab') as f:
        f.write(b'From external\n\nappended\n')
    try:
        with pytest.raises(mailbox.ExternalClashError):
            mb.flush()
    finally:
        mb._file.close()
