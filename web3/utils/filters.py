import re
import random
import gevent

from .types import (
    is_string,
    is_array,
)
from .abi import (
    construct_event_topic_set,
    construct_event_data_set,
    exclude_indexed_event_inputs,
    exclude_indexed_event_inputs_types,
    get_indexed_event_inputs,
    get_indexed_event_inputs_types,
    abi_to_signature,
)
from web3.utils.string import force_bytes
from web3.utils.encoding import decode_hex, remove_0x_prefix

from sha3 import sha3_256
from ethereum.abi import decode_abi


def decodelogs(event_abi, log):
    event_non_indexed_args = exclude_indexed_event_inputs(event_abi)
    print('{} | {} | {}'.format(len(event_non_indexed_args), type(event_non_indexed_args), event_non_indexed_args))
   
    # see http://ethereum.stackexchange.com/questions/6297/python-eth-getfilterchanges-data-how-to-decode  

    print('=============================')
    print(log['data'])
    print(exclude_indexed_event_inputs_types(event_abi))
    print(decode_hex(remove_0x_prefix(log['data'])))
    data_decoded = decode_abi(exclude_indexed_event_inputs_types(event_abi), decode_hex(remove_0x_prefix(log['data'])))
    print(data_decoded)
    print('=============================')
    event_signature = abi_to_signature(event_abi)
    topics0_decoded = force_bytes("0x" + sha3_256(force_bytes(event_signature)).hexdigest())
    event_indexed_args = get_indexed_event_inputs(event_abi)
    print('{} | {} | {}'.format(len(event_indexed_args), type(event_indexed_args), event_indexed_args))

    topicsN_decoded = 0
    return data_decoded, topics0_decoded, topicsN_decoded


def construct_event_filter_params(event_abi,
                                  contract_address=None,
                                  argument_filters=None,
                                  topics=None,
                                  fromBlock=None,
                                  toBlock=None,
                                  address=None):
    filter_params = {}

    if topics is None:
        topic_set = construct_event_topic_set(event_abi, argument_filters)
    else:
        topic_set = [topics] + construct_event_topic_set(event_abi, argument_filters)

    if len(topic_set) == 1 and is_array(topic_set[0]):
        filter_params['topics'] = topic_set[0]
    else:
        filter_params['topics'] = topic_set

    if address and contract_address:
        if is_array(address):
            filter_params['address'] = address + [contract_address]
        elif is_string(address):
            filter_params['address'] = [address, contract_address]
        else:
            raise ValueError(
                "Unsupported type for `address` parameter: {0}".format(type(address))
            )
    elif address:
        filter_params['address'] = address
    elif contract_address:
        filter_params['address'] = contract_address

    if fromBlock is not None:
        filter_params['fromBlock'] = fromBlock

    if toBlock is not None:
        filter_params['toBlock'] = toBlock

    data_filters_set = construct_event_data_set(event_abi, argument_filters)

    return data_filters_set, filter_params


class BaseFilter(gevent.Greenlet):
    callbacks = None
    running = None
    stopped = False

    def __init__(self, web3, filter_id):
        self.web3 = web3
        self.filter_id = filter_id
        self.callbacks = []
        gevent.Greenlet.__init__(self)

    def __str__(self):
        return "Filter for {0}".format(self.filter_id)

    def _run(self):
        if self.stopped:
            raise ValueError("Cannot restart a Filter")
        self.running = True

        self.rejected_logs = []
        previous_logs = self.web3.eth.getFilterLogs(self.filter_id)
        if previous_logs:
            for entry in previous_logs:
                for callback_fn in self.callbacks:
                    if self.is_valid_entry(entry):
                        callback_fn(entry)
                    else:
                        self.rejected_logs.append(entry)

        while self.running:
            changes = self.web3.eth.getFilterChanges(self.filter_id)
            if changes:
                for entry in changes:
                    for callback_fn in self.callbacks:
                        if self.is_valid_entry(entry):
                            callback_fn(entry)
                        else:
                            self.rejected_logs.append(entry)
            gevent.sleep(random.random())

    def is_valid_entry(self, entry):
        """
        Hook for subclasses to implement additional filtering layers.
        """
        return True

    def watch(self, *callbacks):
        if self.stopped:
            raise ValueError("Cannot watch on a filter that has been stopped")
        self.callbacks.extend(callbacks)

        if not self.running:
            self.start()

    def stop_watching(self, timeout=0):
        self.running = False
        self.stopped = True
        self.web3.eth.uninstallFilter(self.filter_id)
        self.join(timeout)

    stopWatching = stop_watching


class BlockFilter(BaseFilter):
    pass


class TransactionFilter(BaseFilter):
    pass


ZERO_32BYTES = '[a-f0-9]{64}'


def construct_data_filter_regex(data_filter_set):
    return re.compile((
        '^' +
        '|'.join((
            '0x' + ''.join(
                (ZERO_32BYTES if v is None else v[2:] for v in data_filter)
            )
            for data_filter in data_filter_set
        )) +
        '$'
    ))


class LogFilter(BaseFilter):
    data_filter_set = None
    data_filter_set_regex = None

    def get(self, only_changes=True):
        if self.running:
            raise ValueError(
                "Cannot call `get` on a filter object which is actively watching"
            )
        if only_changes:
            return self.web3.eth.getFilterChanges(self.filter_id)
        else:
            return self.web3.eth.getFilterChanges(self.filter_id)

    def set_data_filters(self, data_filter_set):
        self.data_filter_set = data_filter_set
        if any(data_filter_set):
            self.data_filter_set_regex = construct_data_filter_regex(
                data_filter_set,
            )

    def is_valid_entry(self, entry):
        if not self.data_filter_set_regex:
            return True
        return bool(self.data_filter_set_regex.match(entry['data']))
