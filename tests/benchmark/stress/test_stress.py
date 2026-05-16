"""
Stress tests replicating zk-unzen/tx-spammer/contracts/ZkGasStress.sol exactly,
matching Masaya production batch layout (per-block, 100M chain-zk-gas target).

Per-block layout: TPS txs, each calling stress function with iters specified below.
Source: zk-unzen/run-stress-suite, 100M-target column. Block time = 1s.

| Workload         | iters/tx | TPS (txs/block) |
| stressAdd        | 50,000   | 5               |
| stressMulmod     | 10,000   | 6               |
| stressKeccak     |  4,000   | 7               |
| stressEcrecover  |     70   | 4               |
| stressBlake2f    |      1   | 6               |
| stressModexp     |      1   | 9               |

Function selectors:
    stressAdd(uint256)       -> 0x0e428e84
    stressMulmod(uint256)    -> 0x190055be
    stressBlake2f(uint256)   -> 0x28395b0b
    stressKeccak(uint256)    -> 0x87ec07e8
    stressModexp(uint256)    -> 0xbaa05740
    stressEcrecover(uint256) -> 0xf617b4e6
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

# Runtime bytecode from forge build of ZkGasStress.sol (.deployedBytecode.object)
# This is EXACTLY what Masaya deploys.
_BYTECODE_PATH = Path("/tmp/stress_runtime.hex")
STRESS_RUNTIME = Bytes(_BYTECODE_PATH.read_text().strip())

SELECTORS = {
    "add":       bytes.fromhex("0e428e84"),
    "mulmod":    bytes.fromhex("190055be"),
    "blake2f":   bytes.fromhex("28395b0b"),
    "keccak":    bytes.fromhex("87ec07e8"),
    "modexp":    bytes.fromhex("baa05740"),
    "ecrecover": bytes.fromhex("f617b4e6"),
}

# Masaya 100M-target parameters: (iters_per_tx, txs_per_block)
WORKLOADS = {
    "add":       (50_000, 5),
    "mulmod":    (10_000, 6),
    "keccak":    ( 4_000, 7),
    "ecrecover": (    70, 4),
    "blake2f":   (     1, 6),
    "modexp":    (     1, 9),
}


@pytest.mark.benchmark
@pytest.mark.parametrize("func_name", list(SELECTORS.keys()))
def test_stress(
    blockchain_test: BlockchainTestFiller,
    pre: Alloc,
    func_name: str,
):
    """Build a single block with TPS txs, each calling stress function with iters."""
    iters, tps = WORKLOADS[func_name]
    selector = SELECTORS[func_name]
    calldata = selector + iters.to_bytes(32, "big")

    pre[STRESS_CONTRACT] = Account(code=STRESS_RUNTIME, balance=0)

    # One funded sender per tx (avoids nonce collisions, mirrors Masaya's spammer)
    txs = []
    for i in range(tps):
        sender = pre.fund_eoa()
        txs.append(
            Transaction(
                to=STRESS_CONTRACT,
                sender=sender,
                data=calldata,
                gas_limit=50_000_000,
            )
        )

    blockchain_test(
        genesis_environment=Environment(),
        pre=pre,
        blocks=[Block(txs=txs)],
        post={},
    )
