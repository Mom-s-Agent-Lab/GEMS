"""Minimal ComfyUI HTTP client used by the GEMS ComfyUI line.

Nothing else in the package talks to ComfyUI directly — keep all network
code here so ``ComfyGEMS`` remains testable.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


class ComfyAPIError(Exception):
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"ComfyUI API error {status}: {body[:400]}")


class ComfyClient:
    """Submits workflows to ComfyUI and collects result images.

    Parameters
    ----------
    server_address : ``host:port`` of a running ComfyUI instance.
    client_id      : Optional stable UUID for queue tracking.
    """

    def __init__(
        self,
        server_address: str = "127.0.0.1:8188",
        client_id: str | None = None,
    ) -> None:
        if server_address.startswith("http://"):
            server_address = server_address[len("http://"):]
        elif server_address.startswith("https://"):
            server_address = server_address[len("https://"):]
        self.server_address = server_address.rstrip("/")
        self.client_id = client_id or str(uuid.uuid4())

    def queue_prompt(self, prompt: dict) -> dict:
        payload = json.dumps({"prompt": prompt, "client_id": self.client_id}).encode()
        req = urllib.request.Request(
            f"http://{self.server_address}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ComfyAPIError(exc.code, body) from exc

    def get_history(self, prompt_id: str) -> dict:
        url = f"http://{self.server_address}/history/{urllib.parse.quote(prompt_id)}"
        with urllib.request.urlopen(url) as resp:
            return json.loads(resp.read())

    def get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        params = urllib.parse.urlencode(
            {"filename": filename, "subfolder": subfolder, "type": folder_type}
        )
        with urllib.request.urlopen(
            f"http://{self.server_address}/view?{params}"
        ) as resp:
            return resp.read()

    def get_json(self, path: str, timeout: int = 10) -> Any:
        url = f"http://{self.server_address}{path}"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())

    def is_alive(self, timeout: int = 4) -> bool:
        for probe in ("/system_stats", "/object_info"):
            try:
                self.get_json(probe, timeout=timeout)
                return True
            except Exception:
                continue
        return False

    def wait_for_completion(
        self,
        prompt_id: str,
        timeout: int = 600,
        poll_interval: float = 2.0,
    ) -> dict:
        """Poll ``/history`` until completion or *timeout* seconds."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                history = self.get_history(prompt_id)
            except Exception as exc:
                return {"error": str(exc)}

            entry = history.get(prompt_id)
            if entry is None:
                time.sleep(poll_interval)
                continue

            status = entry.get("status", {})
            if status.get("status_str") == "error":
                err = "(unknown ComfyUI execution error)"
                for kind, data in status.get("messages", []):
                    if kind == "execution_error":
                        err = data.get("exception_message", err)
                        break
                return {"error": f"ComfyUI execution error: {err}"}

            return entry

        raise TimeoutError(f"Workflow {prompt_id!r} did not finish within {timeout}s")

    def collect_images(self, history_entry: dict) -> list[bytes]:
        """Return every output image from a history entry as raw bytes."""
        images: list[bytes] = []
        for node_output in history_entry.get("outputs", {}).values():
            for img in node_output.get("images", []):
                images.append(
                    self.get_image(img["filename"], img["subfolder"], img["type"])
                )
        return images

    def run_workflow(
        self,
        prompt: dict,
        timeout: int = 600,
        poll_interval: float = 2.0,
    ) -> bytes:
        """Submit a workflow and return the first output image's bytes.

        Raises
        ------
        ComfyAPIError
            If ComfyUI rejected the submission.
        RuntimeError
            If execution failed or no image was produced.
        TimeoutError
            If the workflow did not finish within *timeout*.
        """
        resp = self.queue_prompt(prompt)
        prompt_id = resp["prompt_id"]
        entry = self.wait_for_completion(
            prompt_id, timeout=timeout, poll_interval=poll_interval
        )
        if "error" in entry:
            raise RuntimeError(entry["error"])
        images = self.collect_images(entry)
        if not images:
            raise RuntimeError("ComfyUI produced no image for this workflow.")
        return images[0]
