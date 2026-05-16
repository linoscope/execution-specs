"""
Multi-block variant of test_stress.py.

Each test produces N blocks, each block with TPS txs running iters of the stress
function — mimicking Masaya's batch structure (many blocks accumulating state).

Goal: isolate per-block state-tree / witness overhead from per-iter opcode cost.
If single-block cycles_per_block stays roughly the same when scaled to N blocks,
the marginal model is correct and the gap to Masaya is just SP1 prove
efficiency at scale. If per-block cycles drop sharply as N grows, per-block
overhead is the dominant gap.

Only stressAdd and stressModexp here — the two extremes from the 1-block
results (add was 0.39× Masaya c/zk-g, modexp was 0.83×).
"""

from pathlib import Path

import pytest
from execution_testing import (
    Account,
    Address,
    Alloc,
    Block,
    BlockchainTestFiller,
    Bytes,
    Environment,
    Transaction,
)

STRESS_CONTRACT = Address(0x1000)
_BYTECODE_PATH = Path("/tmp/stress_runtime.hex")
STRESS_RUNTIME = Bytes(_BYTECODE_PATH.read_text().strip())

SELECTORS = {
    "add":    bytes.fromhex("0e428e84"),
    "modexp": bytes.fromhex("baa05740"),
}

# (iters_per_tx, txs_per_block) — Masaya 100M target params
WORKLOADS = {
    "add":    (50_000, 5),
    "modexp": (     1, 9),
}

# Multi-block sizes: replicate the same block N times.
NUM_BLOCKS = 10


@pytest.mark.benchmark
@pytest.mark.parametrize("func_name", list(SELECTORS.keys()))
def test_stress_multi(
    blockchain_test: BlockchainTestFiller,
    pre: Alloc,
    func_name: str,
):
    """Build N identical blocks, each with TPS txs calling stress(iters)."""
    iters, tps = WORKLOADS[func_name]
    selector = SELECTORS[func_name]
    calldata = selector + iters.to_bytes(32, "big")

    pre[STRESS_CONTRACT] = Account(code=STRESS_RUNTIME, balance=0)

    # Fund enough senders for all blocks (each block needs `tps` senders)
    blocks = []
    for b in range(NUM_BLOCKS):
        block_txs = []
        for i in range(tps):
            sender = pre.fund_eoa()
            block_txs.append(
                Transaction(
                    to=STRESS_CONTRACT,
                    sender=sender,
                    data=calldata,
                    gas_limit=50_000_000,
                )
            )
        blocks.append(Block(txs=block_txs))

    blockchain_test(
        genesis_environment=Environment(),
        pre=pre,
        blocks=blocks,
        post={},
    )
