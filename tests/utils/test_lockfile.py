"""Tests for InstanceLock - single-instance lock with stale reclamation (F-06)."""

import json

import pytest

from chinatxtbook.utils.lockfile import InstanceLock


@pytest.fixture
def lock_file(tmp_path):
    return tmp_path / "test.lock"


class TestInstanceLock:
    def test_first_acquire_succeeds(self, lock_file):
        lock = InstanceLock(lock_file)
        assert lock.acquire() is True
        assert lock_file.exists()
        lock.release()

    def test_second_acquire_fails(self, lock_file):
        lock1 = InstanceLock(lock_file)
        assert lock1.acquire() is True
        lock2 = InstanceLock(lock_file)
        assert lock2.acquire() is False
        lock1.release()

    def test_release_allows_reacquire(self, lock_file):
        lock = InstanceLock(lock_file)
        assert lock.acquire() is True
        lock.release()
        assert lock.acquire() is True
        lock.release()

    def test_release_idempotent(self, lock_file):
        lock = InstanceLock(lock_file)
        lock.acquire()
        lock.release()
        lock.release()  # must not raise
        lock.release()

    def test_stale_lock_reclaimed(self, lock_file):
        # A lock file whose PID is dead (large unused PID) must be reclaimed
        lock_file.write_text(json.dumps({"pid": 999999, "started": "2020-01-01"}))
        lock = InstanceLock(lock_file)
        assert lock.acquire() is True
        lock.release()

    def test_context_manager_acquires_and_releases(self, lock_file):
        with InstanceLock(lock_file) as lock:
            assert lock._acquired is True
            assert lock_file.exists()
        assert not lock_file.exists()

    def test_context_manager_blocks_second(self, lock_file):
        with InstanceLock(lock_file):
            second = InstanceLock(lock_file)
            with pytest.raises(RuntimeError):
                second.__enter__()
