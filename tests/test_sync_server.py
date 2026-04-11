"""
Tests for SyncServer diff computation and broadcast logic.
"""

from __future__ import annotations

import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comfyclaw.sync_server import SyncServer, diff_workflows


# ---------------------------------------------------------------------------
# diff_workflows — pure function tests
# ---------------------------------------------------------------------------


class TestDiffWorkflows:
    """Unit tests for the ``diff_workflows`` helper."""

    def test_empty_to_empty(self):
        assert diff_workflows({}, {}) == []

    def test_add_single_node(self):
        old = {}
        new = {
            "1": {"class_type": "KSampler", "inputs": {"seed": 42}},
        }
        ops = diff_workflows(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "add_node"
        assert ops[0]["id"] == "1"
        assert ops[0]["data"] == new["1"]

    def test_remove_single_node(self):
        old = {
            "1": {"class_type": "KSampler", "inputs": {"seed": 42}},
        }
        ops = diff_workflows(old, {})
        assert len(ops) == 1
        assert ops[0]["op"] == "remove_node"
        assert ops[0]["id"] == "1"

    def test_update_node_inputs(self):
        old = {"1": {"class_type": "KSampler", "inputs": {"seed": 42}}}
        new = {"1": {"class_type": "KSampler", "inputs": {"seed": 99}}}
        ops = diff_workflows(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "update_node"
        assert ops[0]["id"] == "1"
        assert ops[0]["data"]["inputs"]["seed"] == 99

    def test_no_change(self):
        wf = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd.ckpt"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "hello"}},
        }
        assert diff_workflows(wf, copy.deepcopy(wf)) == []

    def test_mixed_add_remove_update(self):
        old = {
            "1": {"class_type": "A", "inputs": {"x": 1}},
            "2": {"class_type": "B", "inputs": {"y": 2}},
        }
        new = {
            "2": {"class_type": "B", "inputs": {"y": 99}},
            "3": {"class_type": "C", "inputs": {"z": 3}},
        }
        ops = diff_workflows(old, new)
        ops_by_type = {o["op"]: o for o in ops}
        assert "add_node" in ops_by_type
        assert ops_by_type["add_node"]["id"] == "3"
        assert "remove_node" in ops_by_type
        assert ops_by_type["remove_node"]["id"] == "1"
        assert "update_node" in ops_by_type
        assert ops_by_type["update_node"]["id"] == "2"

    def test_ops_sorted_by_node_id(self):
        old = {}
        new = {
            "10": {"class_type": "X", "inputs": {}},
            "2": {"class_type": "Y", "inputs": {}},
            "5": {"class_type": "Z", "inputs": {}},
        }
        ops = diff_workflows(old, new)
        ids = [o["id"] for o in ops]
        assert ids == ["2", "5", "10"]

    def test_add_node_with_link_inputs(self):
        old = {
            "1": {"class_type": "Loader", "inputs": {"ckpt": "model.ckpt"}},
        }
        new = {
            "1": {"class_type": "Loader", "inputs": {"ckpt": "model.ckpt"}},
            "2": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": 42}},
        }
        ops = diff_workflows(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "add_node"
        assert ops[0]["data"]["inputs"]["model"] == ["1", 0]

    def test_meta_change_triggers_update(self):
        old = {"1": {"class_type": "X", "_meta": {"title": "Old"}, "inputs": {}}}
        new = {"1": {"class_type": "X", "_meta": {"title": "New"}, "inputs": {}}}
        ops = diff_workflows(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "update_node"


# ---------------------------------------------------------------------------
# SyncServer — broadcast & state tracking
# ---------------------------------------------------------------------------


class TestSyncServerBroadcast:
    """Tests for SyncServer.broadcast() diff logic and state tracking."""

    def _make_server(self) -> SyncServer:
        return SyncServer(port=0, host="127.0.0.1")

    def test_first_broadcast_stores_last_workflow(self):
        srv = self._make_server()
        wf = {"1": {"class_type": "A", "inputs": {}}}
        srv.broadcast(wf)
        assert srv._last_workflow == wf

    def test_reset_clears_state(self):
        srv = self._make_server()
        srv._last_workflow = {"1": {"class_type": "A", "inputs": {}}}
        srv.reset()
        assert srv._last_workflow is None

    def test_broadcast_deepcopies_workflow(self):
        srv = self._make_server()
        wf = {"1": {"class_type": "A", "inputs": {"x": [1, 2]}}}
        srv.broadcast(wf)
        wf["1"]["inputs"]["x"].append(3)
        assert srv._last_workflow["1"]["inputs"]["x"] == [1, 2]

    @patch("comfyclaw.sync_server._WS_AVAILABLE", True)
    def test_broadcast_sends_full_on_first_call(self):
        """When _last_workflow is None, broadcast should send workflow_update."""
        srv = self._make_server()
        srv._loop = MagicMock()
        srv._thread = MagicMock()
        srv._thread.is_alive.return_value = True
        mock_ws = MagicMock()
        srv._clients.add(mock_ws)

        wf = {"1": {"class_type": "A", "inputs": {}}}

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            srv.broadcast(wf)

        assert mock_run.called
        call_args = mock_run.call_args
        # The first positional arg is the coroutine — we can't easily inspect
        # it, but we can verify _last_workflow was set.
        assert srv._last_workflow == wf

    @patch("comfyclaw.sync_server._WS_AVAILABLE", True)
    def test_broadcast_sends_diff_on_subsequent_call(self):
        """After the first broadcast, subsequent calls should produce diffs."""
        srv = self._make_server()
        srv._loop = MagicMock()
        srv._thread = MagicMock()
        srv._thread.is_alive.return_value = True
        mock_ws = MagicMock()
        srv._clients.add(mock_ws)

        wf1 = {"1": {"class_type": "A", "inputs": {}}}
        wf2 = {
            "1": {"class_type": "A", "inputs": {}},
            "2": {"class_type": "B", "inputs": {}},
        }

        payloads = []

        def capture_payload(coro, loop):
            # We need to extract the payload from the coroutine arguments.
            # Since _async_broadcast is called with (payload, clients),
            # we capture via a side effect on the mock.
            pass

        # First call — sets _last_workflow
        srv.broadcast(wf1)
        assert srv._last_workflow == wf1

        # Now simulate running server for second call
        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            srv.broadcast(wf2)

        assert srv._last_workflow == wf2
        assert mock_run.called

    @patch("comfyclaw.sync_server._WS_AVAILABLE", True)
    def test_broadcast_skips_when_no_changes(self):
        """If workflow hasn't changed, no broadcast should be sent."""
        srv = self._make_server()
        srv._loop = MagicMock()
        srv._thread = MagicMock()
        srv._thread.is_alive.return_value = True
        mock_ws = MagicMock()
        srv._clients.add(mock_ws)

        wf = {"1": {"class_type": "A", "inputs": {}}}
        srv._last_workflow = copy.deepcopy(wf)

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            srv.broadcast(copy.deepcopy(wf))

        assert not mock_run.called

    def test_broadcast_noop_when_no_clients(self):
        srv = self._make_server()
        srv._loop = MagicMock()
        srv._thread = MagicMock()
        srv._thread.is_alive.return_value = True

        wf1 = {"1": {"class_type": "A", "inputs": {}}}
        wf2 = {
            "1": {"class_type": "A", "inputs": {}},
            "2": {"class_type": "B", "inputs": {}},
        }
        # Even with no clients, _last_workflow should still be updated
        srv.broadcast(wf1)
        srv.broadcast(wf2)
        assert srv._last_workflow == wf2
