# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class PayoutProbe(gl.Contract):
    note: str

    def __init__(self):
        self.note = ""

    @gl.public.write.payable
    def fund(self) -> None:
        self.note = "funded"

    @gl.public.write
    def pay(self, to: str, amount: u256) -> None:
        gl.get_contract_at(Address(to)).emit_transfer(value=amount)
        self.note = "paid"
