# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from datetime import datetime, timezone
from genlayer import *


class ViewClock(gl.Contract):
    last_view_now: u256
    last_write_now: u256

    def __init__(self):
        self.last_view_now = u256(0)
        self.last_write_now = u256(0)

    @gl.public.view
    def view_now(self) -> int:
        return int(datetime.now(timezone.utc).timestamp())

    @gl.public.write
    def write_now(self) -> int:
        self.last_write_now = u256(int(datetime.now(timezone.utc).timestamp()))
        return int(self.last_write_now)
