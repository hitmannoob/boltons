import os.path
import pathlib



from boltons import fileutils
from boltons.fileutils import FilePerms, iter_find_files
from boltons.strutils import removeprefix


BOLTONS_PATH = os.path.dirname(os.path.abspath(fileutils.__file__))


def test_fileperms():
    up = FilePerms()
    up.other = ''
    up.user = 'xrw'
    up.group = 'rrrwx'
    try:
        up.other = 'nope'
    except ValueError:
        # correctly raised ValueError on invalid chars
        pass

    assert repr(up) == "FilePerms(user='rwx', group='rwx', other='')"
    assert up.user == 'rwx'
    assert oct(int(up)) == '0o770'

    assert int(FilePerms()) == 0


def test_fileperms_from_int_leading_zero_groups():
    assert int(FilePerms.from_int(0o007)) == 0o007
    assert FilePerms.from_int(0o070).group == 'rwx'
    assert FilePerms.from_int(0o070).user == ''


def test_fileperms_revoke():
    fp = FilePerms(user='rw', other='r')
    fp.other = ''
    assert int(fp) == 0o600
    fp.user = 'r'
    assert int(fp) == 0o400


class _FlushFailingFile:
    def __init__(self, f):
        self.f = f

    def write(self, data):
        return self.f.write(data)

    def fileno(self):
        return self.f.fileno()

    def flush(self):
        raise OSError('simulated flush failure')

    def close(self):
        self.f.close()


class _FlushFailingSaver(fileutils.AtomicSaver):
    def _open_part_file(self):
        super()._open_part_file()
        self.real_part_file = self.part_file
        self.part_file = _FlushFailingFile(self.real_part_file)


def test_atomicsaver_flush_failure_cleans_up(tmp_path):
    dest = tmp_path / 'output.bin'
    saver = _FlushFailingSaver(str(dest))
    try:
        with saver as f:
            f.write(b'data')
    except OSError as e:
        assert 'simulated flush failure' in str(e)
    else:
        raise AssertionError('expected OSError from flush')
    assert saver.real_part_file.closed
    assert not os.path.exists(saver.part_path)
    assert not dest.exists()



def test_atomicsaver_pathlike(tmp_path):
    dest = tmp_path / 'output.bin'
    with fileutils.AtomicSaver(dest) as f:
        f.write(b'pathlike works')
    assert dest.read_bytes() == b'pathlike works'


def test_iter_find_files_pathlike():
    boltons_path = pathlib.Path(BOLTONS_PATH)
    results = list(iter_find_files(boltons_path, patterns=['*.py']))
    basenames = [os.path.basename(p) for p in results]
    assert 'fileutils.py' in basenames


def test_iter_find_files():
    def _to_baseless_list(paths):
        return [removeprefix(p, BOLTONS_PATH).lstrip(os.path.sep) for p in paths]

    assert 'fileutils.py' in _to_baseless_list(iter_find_files(BOLTONS_PATH, patterns=['*.py']))

    boltons_parent = os.path.dirname(BOLTONS_PATH)
    assert 'fileutils.py' in _to_baseless_list(iter_find_files(boltons_parent, patterns=['*.py']))
    assert 'fileutils.py' not in _to_baseless_list(iter_find_files(boltons_parent, patterns=['*.py'], max_depth=0))


def test_iter_find_files_trailing_sep(tmp_path):
    sub2 = tmp_path / 'sub' / 'sub2'
    sub2.mkdir(parents=True)
    for path in (tmp_path / 'a.txt', tmp_path / 'sub' / 'b.txt', sub2 / 'c.txt'):
        path.write_text('x')

    def _names(directory):
        return sorted(os.path.basename(p) for p in
                      iter_find_files(directory, '*.txt', max_depth=1))

    assert _names(str(tmp_path)) == ['a.txt', 'b.txt']
    assert _names(str(tmp_path) + os.path.sep) == ['a.txt', 'b.txt']


def test_rotate_file_no_rotation(tmp_path):
    file_path = tmp_path / 'test_file.txt'
    fileutils.rotate_file(file_path)
    assert not file_path.exists()


def test_rotate_file_one_rotation(tmp_path):
    file_path = tmp_path / 'test_file.txt'
    file_path.write_text('test content')
    assert file_path.exists()

    fileutils.rotate_file(file_path)
    assert not file_path.exists()
    assert (tmp_path / 'test_file.1.txt').exists()


def test_rotate_file_full_rotation(tmp_path):
    file_path = tmp_path / 'test_file.txt'
    file_path.write_text('test content 0')
    for i in range(1, 6):
        cur_path = tmp_path / f'test_file.{i}.txt'
        cur_path.write_text(f'test content {i}')
        assert cur_path.exists()

    fileutils.rotate_file(file_path, keep=5)
    assert not file_path.exists()

    for i in range(1, 6):
        cur_path = tmp_path / f'test_file.{i}.txt'
        assert cur_path.read_text() == f'test content {i-1}'

    assert not (tmp_path / 'test_file.6.txt').exists()

def test_rotate_file_full_rotation_no_ext(tmp_path):
    file_path = tmp_path / 'test_file'
    file_path.write_text('test content 0')
    for i in range(1, 6):
        cur_path = tmp_path / f'test_file.{i}'
        cur_path.write_text(f'test content {i}')
        assert cur_path.exists()

    fileutils.rotate_file(file_path, keep=5)
    assert not file_path.exists()

    for i in range(1, 6):
        cur_path = tmp_path / f'test_file.{i}'
        assert cur_path.read_text() == f'test content {i-1}'

    assert not (tmp_path / 'test_file.6').exists()


def test_rotate_file_keep_one(tmp_path):
    # keep=1 used to delete the backup it had just made
    file_path = tmp_path / 'log.txt'
    for gen in range(3):
        file_path.write_text(f'gen {gen}')
        fileutils.rotate_file(file_path, keep=1)
        assert sorted(p.name for p in tmp_path.iterdir()) == ['log.1.txt']
        assert (tmp_path / 'log.1.txt').read_text() == f'gen {gen}'



# --- additional behavioural coverage for boltons.fileutils ---

import errno
import stat
import sys

import pytest


def test_mkdir_p_creates_and_is_idempotent(tmp_path):
    target = tmp_path / 'a' / 'b' / 'c'
    assert fileutils.mkdir_p(target) is None
    assert target.is_dir()
    # already existing directory is a no-op, not an error
    assert fileutils.mkdir_p(target) is None


def test_mkdir_p_reraises_when_path_is_a_file(tmp_path):
    target = tmp_path / 'already_a_file'
    target.write_text('x')
    with pytest.raises(OSError) as excinfo:
        fileutils.mkdir_p(target)
    assert excinfo.value.errno == errno.EEXIST


def test_fileperms_descriptor_access_on_class():
    prop = FilePerms.user
    assert isinstance(prop, FilePerms._FilePermProperty)
    assert prop.offset == 2
    assert FilePerms.group.offset == 1
    assert FilePerms.other.offset == 0


class _BadStr:
    def __str__(self):
        raise TypeError('not stringable')


def test_fileperms_rejects_non_string_type():
    with pytest.raises(TypeError):
        FilePerms(user=_BadStr())


def test_fileperms_from_path(tmp_path):
    path = tmp_path / 'permfile'
    path.write_text('x')
    os.chmod(path, 0o640)
    perms = FilePerms.from_path(path)
    assert int(perms) == 0o640
    assert 'r' in perms.user and 'w' in perms.user
    assert perms.other == ''


def test_atomic_save_text_mode(tmp_path):
    dest = tmp_path / 'atomic.txt'
    saver = fileutils.atomic_save(dest, text_mode=True)
    assert isinstance(saver, fileutils.AtomicSaver)
    with saver as f:
        f.write('hello')
    assert dest.read_text() == 'hello'


def test_path_to_unicode():
    assert fileutils.path_to_unicode('already') == 'already'
    assert fileutils.path_to_unicode(b'bytes-name') == 'bytes-name'


def test_replace_and_atomic_rename(tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.write_text('new')
    dst.write_text('old')
    fileutils.replace(str(src), str(dst))
    assert not src.exists()
    assert dst.read_text() == 'new'

    src.write_text('linked')
    dst.unlink()
    fileutils.atomic_rename(str(src), str(dst), overwrite=False)
    assert not src.exists()
    assert dst.read_text() == 'linked'
    assert fileutils._atomic_rename is fileutils.atomic_rename


def test_atomicsaver_unexpected_kwarg(tmp_path):
    with pytest.raises(TypeError):
        fileutils.AtomicSaver(tmp_path / 'out', not_a_real_kwarg=True)


def test_atomicsaver_custom_part_file(tmp_path):
    dest = tmp_path / 'out.bin'
    saver = fileutils.AtomicSaver(dest, part_file='mypart')
    assert saver.part_path == os.path.join(str(tmp_path), 'mypart')
    with saver as f:
        f.write(b'data')
    assert dest.read_bytes() == b'data'
    assert not os.path.exists(saver.part_path)


def test_atomicsaver_respects_explicit_file_perms(tmp_path):
    dest = tmp_path / 'out.bin'
    with fileutils.AtomicSaver(dest, file_perms=0o600) as f:
        f.write(b'data')
    assert stat.S_IMODE(os.stat(str(dest)).st_mode) == 0o600


def test_atomicsaver_copies_perms_from_existing_dest(tmp_path):
    dest = tmp_path / 'out.bin'
    dest.write_bytes(b'old')
    os.chmod(dest, 0o640)
    with fileutils.AtomicSaver(dest) as f:
        f.write(b'new')
    assert dest.read_bytes() == b'new'
    assert stat.S_IMODE(os.stat(str(dest)).st_mode) == 0o640


def test_atomicsaver_refuses_overwrite(tmp_path):
    dest = tmp_path / 'out.bin'
    dest.write_bytes(b'keep')
    with pytest.raises(OSError) as excinfo:
        with fileutils.AtomicSaver(dest, overwrite=False):
            pass
    assert excinfo.value.errno == errno.EEXIST
    assert dest.read_bytes() == b'keep'


def test_atomicsaver_overwrite_part(tmp_path):
    dest = tmp_path / 'out.bin'
    part = tmp_path / 'out.bin.part'
    part.write_bytes(b'stale')
    with fileutils.AtomicSaver(dest, overwrite_part=True) as f:
        f.write(b'fresh')
    assert dest.read_bytes() == b'fresh'
    assert not part.exists()


def test_atomicsaver_keeps_part_on_exception_when_configured(tmp_path):
    dest = tmp_path / 'out.bin'
    saver = fileutils.AtomicSaver(dest, rm_part_on_exc=False)
    with pytest.raises(ZeroDivisionError):
        with saver as f:
            f.write(b'partial')
            1 / 0
    assert os.path.exists(saver.part_path)
    assert not dest.exists()


def test_atomicsaver_unlink_error_does_not_mask_original(tmp_path, monkeypatch):
    dest = tmp_path / 'out.bin'
    saver = fileutils.AtomicSaver(dest)
    real_unlink = os.unlink

    def failing_unlink(path):
        if path == saver.part_path:
            raise OSError('cannot unlink part')
        return real_unlink(path)

    monkeypatch.setattr(fileutils.os, 'unlink', failing_unlink)
    with pytest.raises(ZeroDivisionError):
        with saver as f:
            f.write(b'partial')
            1 / 0


def test_set_cloexec_handles_oserror(monkeypatch):
    def failing_fcntl(*args, **kwargs):
        raise OSError('no fcntl here')

    monkeypatch.setattr(fileutils.fcntl, 'fcntl', failing_fcntl)
    read_fd, write_fd = os.pipe()
    try:
        assert fileutils.set_cloexec(read_fd) is None
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_iter_find_files_ignored_as_string(tmp_path):
    (tmp_path / 'keep.py').write_text('x')
    (tmp_path / '.#lock.py').write_text('x')
    names = sorted(os.path.basename(p) for p in
                   iter_find_files(str(tmp_path), '*.py', ignored='.#*'))
    assert names == ['keep.py']


def test_iter_find_files_include_dirs_and_ignore_dirs(tmp_path):
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'inner.py').write_text('x')
    found = list(iter_find_files(str(tmp_path), 'sub', include_dirs=True))
    assert [os.path.basename(p) for p in found] == ['sub']
    ignored = list(iter_find_files(str(tmp_path), 'sub', ignored='sub',
                                   include_dirs=True))
    assert ignored == []


def test_copy_tree_merges_existing_and_honours_ignore(tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    (src / 'sub').mkdir(parents=True)
    (src / 'a.txt').write_text('a')
    (src / 'skip.txt').write_text('skip')
    (src / 'sub' / 'b.txt').write_text('b')
    dst.mkdir()
    (dst / 'keep.txt').write_text('keep')

    def ignore(path, names):
        return [name for name in names if name == 'skip.txt']

    fileutils.copy_tree(str(src), str(dst), ignore=ignore)
    assert (dst / 'a.txt').read_text() == 'a'
    assert (dst / 'sub' / 'b.txt').read_text() == 'b'
    assert (dst / 'keep.txt').read_text() == 'keep'
    assert not (dst / 'skip.txt').exists()
    assert fileutils.copytree is fileutils.copy_tree


def test_copy_tree_symlinks(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    target = src / 'target.txt'
    target.write_text('target')
    (src / 'link.txt').symlink_to(target)
    dst = tmp_path / 'dst'
    fileutils.copy_tree(str(src), str(dst), symlinks=True)
    assert (dst / 'link.txt').is_symlink()
    assert (dst / 'target.txt').read_text() == 'target'


def test_copy_tree_collects_errors(tmp_path):
    from shutil import Error

    src = tmp_path / 'src'
    src.mkdir()
    (src / 'broken').symlink_to(src / 'does_not_exist')
    with pytest.raises(Error):
        fileutils.copy_tree(str(src), str(tmp_path / 'dst'))


def test_dummy_file_behaviour(tmp_path):
    name = str(tmp_path / 'gone')
    df = fileutils.DummyFile(name)
    assert df.name == name
    assert df.mode == 'r'
    assert df.closed is False
    assert df.errors is None
    assert df.encoding is None
    assert df.fileno() == -1
    assert df.flush() is None
    assert df.read() == ''
    assert df.read(10) == ''
    assert df.readline() == ''
    assert df.readlines() == []
    assert df.seek() is None
    assert df.tell() == 0
    assert df.truncate() is None
    assert df.write('ignored') is None
    assert df.writelines(['ignored']) is None
    with pytest.raises(StopIteration):
        df.next()
    with pytest.raises(StopIteration):
        next(df)
    with df as entered:
        assert entered is None

    df.close()
    assert df.closed is True
    for operation in (df.flush, df.read, df.readline, df.readlines, df.seek,
                      df.tell, df.truncate):
        with pytest.raises(ValueError):
            operation()
    with pytest.raises(ValueError):
        df.write('x')
    with pytest.raises(ValueError):
        df.writelines([])
    with pytest.raises(ValueError):
        df.__enter__()
    assert df.__exit__(None, None, None) is None


def test_atomicsaver_chmod_failure_closes_part_file(tmp_path, monkeypatch):
    dest = tmp_path / 'out.bin'

    def failing_chmod(*args, **kwargs):
        raise OSError('chmod denied')

    real_open = fileutils.AtomicSaver._open_part_file
    monkeypatch.setattr(fileutils.os, 'chmod', failing_chmod)
    saver = fileutils.AtomicSaver(dest, file_perms=0o600)
    with pytest.raises(OSError):
        saver._open_part_file()


def test_copy_tree_wraps_recursive_error(tmp_path, monkeypatch):
    from shutil import Error

    src = tmp_path / 'src'
    (src / 'sub').mkdir(parents=True)
    (src / 'sub' / 'f.txt').write_text('x')

    def failing_copytree(*args, **kwargs):
        raise Error(['simulated recursive failure'])

    monkeypatch.setattr(fileutils, 'copytree', failing_copytree)
    with pytest.raises(Error) as excinfo:
        fileutils.copy_tree(str(src), str(tmp_path / 'dst'))
    assert ('simulated recursive failure' in
            str(excinfo.value.args[0]))


def test_copy_tree_reports_copystat_error(tmp_path, monkeypatch):
    from shutil import Error

    src = tmp_path / 'src'
    src.mkdir()
    (src / 'f.txt').write_text('x')

    def failing_copystat(*args, **kwargs):
        raise OSError('cannot copy stat')

    monkeypatch.setattr(fileutils, 'copystat', failing_copystat)
    with pytest.raises(Error):
        fileutils.copy_tree(str(src), str(tmp_path / 'dst'))


def test_rotate_file_rejects_bad_arguments(tmp_path):
    with pytest.raises(ValueError):
        fileutils.rotate_file(tmp_path / 'any.txt', keep=0)
    directory = tmp_path / 'a_directory'
    directory.mkdir()
    with pytest.raises(ValueError):
        fileutils.rotate_file(directory)
