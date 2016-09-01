from pprint import pprint
import random
import gevent
from flaky import flaky
from web3.utils.filters import (
    decodelogs
)
from web3.utils.abi import (
    filter_by_name,
    get_abi_input_types,
)


@flaky(max_runs=3)
def test_on_filter_with_only_event_name(web3_empty,
                                        emitter,
                                        wait_for_transaction,
                                        emitter_log_topics,
                                        emitter_event_ids,
                                        EMITTER_ABI):
    web3 = web3_empty

    seen_logs = []

    filter = emitter.on('LogNoArguments', {}, seen_logs.append)

    txn_hash = emitter.transact().logNoArgs(emitter_event_ids.LogNoArguments)
    txn_receipt = wait_for_transaction(web3, txn_hash)

    with gevent.Timeout(5):
        while not seen_logs:
            gevent.sleep(random.random())

    filter.stop_watching(10)

    assert len(seen_logs) == 1
    assert seen_logs[0]['transactionHash'] == txn_hash
    event_abi = filter_by_name('LogNoArguments', EMITTER_ABI)[0]
    pprint(event_abi)
    assert decodelogs(event_abi, seen_logs[0]) == (0, emitter_log_topics.LogNoArguments, 0 )

@flaky(max_runs=3)
def test_on_filter_with_event_name_and_single_argument(web3_empty,
                                                       emitter,
                                                       wait_for_transaction,
                                                       emitter_log_topics,
                                                       emitter_event_ids,
                                                       EMITTER_ABI):
    web3 = web3_empty

    seen_logs = []

    filter = emitter.on('LogTripleWithIndex', {'filter': {
        'arg1': 2,
    }}, seen_logs.append)

    txn_hashes = []
    txn_hashes.append(
        emitter.transact().logTriple(emitter_event_ids.LogTripleWithIndex, 2, 1, 3)
    )
    txn_hashes.append(
        emitter.transact().logTriple(emitter_event_ids.LogTripleWithIndex, 1, 2, 3)
    )
    txn_hashes.append(
        emitter.transact().logTriple(emitter_event_ids.LogTripleWithIndex, 12345, 2, 54321)
    )
    for txn_hash in txn_hashes:
        wait_for_transaction(web3, txn_hash)

    with gevent.Timeout(5):
        while not seen_logs:
            gevent.sleep(random.random())

    filter.stop_watching(10)

    assert len(seen_logs) == 2
    assert {l['transactionHash'] for l in seen_logs} == set(txn_hashes[1:])
    pprint('ALL ABI\n')
    pprint(EMITTER_ABI)
    event_abi = filter_by_name('LogTripleWithIndex', EMITTER_ABI)[0]
    pprint('EVENT ABI\n')
    pprint(event_abi)
    # 0-th seen_logs is the one with args 1, 2, 3
    # arg0 = 1 is not indexed so it should be in data
    # arg1 and arg2 are indexed so should be respectively in topics[1] and topics[2]
    # topics[0] is the keccak oif the evenbt signature
    # decodelogs returns data, topics0, topicsN
    pprint(seen_logs[0])
    assert decodelogs(event_abi, seen_logs[0]) == (1, emitter_log_topics.LogTripleWithIndex, [2, 3])
    pprint(seen_logs[1])
    assert decodelogs(event_abi, seen_logs[1]) == (12345, emitter_log_topics.LogTripleWithIndex, [2, 54321])

@flaky(max_runs=3)
def test_on_filter_with_event_name_and_non_indexed_argument(web3_empty,
                                                            emitter,
                                                            wait_for_transaction,
                                                            emitter_log_topics,
                                                            emitter_event_ids):
    web3 = web3_empty

    seen_logs = []

    filter = emitter.on('LogTripleWithIndex', {'filter': {
        'arg0': 1, 'arg1': 2,
    }}, seen_logs.append)

    txn_hashes = []
    txn_hashes.append(
        emitter.transact().logTriple(emitter_event_ids.LogTripleWithIndex, 2, 1, 3)
    )
    txn_hashes.append(
        emitter.transact().logTriple(emitter_event_ids.LogTripleWithIndex, 1, 2, 3)
    )
    txn_hashes.append(
        emitter.transact().logTriple(emitter_event_ids.LogTripleWithIndex, 12345, 2, 54321)
    )
    for txn_hash in txn_hashes:
        wait_for_transaction(web3, txn_hash)

    with gevent.Timeout(5):
        while not seen_logs:
            gevent.sleep(random.random())

    filter.stop_watching(10)

    assert len(seen_logs) == 1
    assert seen_logs[0]['transactionHash'] == txn_hashes[1]
