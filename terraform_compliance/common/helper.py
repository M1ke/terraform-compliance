import re
from netaddr import IPNetwork
from terraform_compliance.steps import resource_name
from collections.abc import Iterable
import json
from copy import deepcopy


class EmptyStash(object):
    pass


class Null(object):
    pass


def flatten_list(input):
    return list(flatten(input))


def flatten(items):
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            for sub_x in flatten(x):
                yield sub_x
        else:
            yield x


def check_if_cidr(value):
    regex = r'(1[0-9][0-9]|2[0-4][0-9]|25[0-5]|[0-9][0-9]|[0-9])' \
            r'\.' \
            r'(1[0-9][0-9]|2[0-4][0-9]|25[0-5]|[0-9][0-9]|[0-9])' \
            r'\.' \
            r'(1[0-9][0-9]|2[0-4][0-9]|25[0-5]|[0-9][0-9]|[0-9])' \
            r'\.' \
            r'(1[0-9][0-9]|2[0-4][0-9]|25[0-5]|[0-9][0-9]|[0-9])' \
            r'\/' \
            r'(3[0-2]|2[0-9]|1[0-9]|[0-9])'
    matches = re.match(regex, value)

    if matches is not None:
        return True

    return False


def is_ip_in_cidr(ip_cidr, cidr):
    for ip_network in cidr:
        if check_if_cidr(ip_cidr) and check_if_cidr(ip_network) and IPNetwork(ip_cidr) in IPNetwork(ip_network):
            return True

    return False


def are_networks_same(first_network, network_list):
    for second_network in network_list:
        if check_if_cidr(first_network) and check_if_cidr(second_network) and \
                IPNetwork(first_network) == IPNetwork(second_network):
            return True

    return False


def convert_resource_type(resource_type):
    '''
    Searchs given resource_type within resource_name array and returns the value if it is found

    :param resource_type: String of resource_type
    :return: converted or original resource_type
    '''
    if resource_type in resource_name.keys():
        resource_type = resource_name[resource_type]

    return resource_type


def seek_key_in_dict(haystack, needle):
    '''
    Searches needle in haystack ( could be dict, list, list of dicts, nested dicts, etc. ) and returns all findings
    as a list

    :param haystack: dict, list
    :param needle: search key
    :return: list of found keys & values
    '''
    found = list()
    if type(haystack) is dict:
        for key, value in haystack.items():
            if key.lower() == needle.lower():
                found.append({key: value})
            else:
                found.extend(seek_key_in_dict(value, needle))

    elif type(haystack) is list:
        for value in haystack:
            found.extend(seek_key_in_dict(value, needle))

    else:
        return []

    return found


def seek_regex_key_in_dict_values(haystack, key_name, needle, key_matched=None):
    '''
    Searches needle in haystack ( could be dict, list, list of dicts, nested dicts, etc. ) and returns all findings
    as a list. The only difference from seek_key_in_dict is, we are assuming needle is in regex format here and we
    are searching for values instead.

    :param haystack: dict, list
    :param key_name: string of the key
    :param needle: regex search for the value
    :param key_matched: Internal use
    :return: list of found keys & values
    '''
    regex = r'{}'.format(needle)
    found = list()
    if type(haystack) is dict:
        for key, value in haystack.items():
            if key.lower() == key_name.lower() or key_matched is not None:
                if type(value) is str:
                    matches = re.match(regex, value)

                    if matches is not None:
                        found.append(matches.group(0))
                    else:
                        found.extend(seek_regex_key_in_dict_values(value, key_name, needle, True))

                elif type(value) is dict:
                    found.extend(seek_regex_key_in_dict_values(value, key_name, needle, True))

                elif type(value) is list:
                    for v in value:
                        found.extend(seek_regex_key_in_dict_values(v, key_name, needle, True))

            else:
                found.extend(seek_regex_key_in_dict_values(value, key_name, needle, key_matched))

    elif type(haystack) is list:
        for value in haystack:
            found.extend(seek_regex_key_in_dict_values(value, key_name, needle, key_matched))

    else:
        return []

    return found


def find_root_by_key(haystack, needle, return_key=None, _inherited_key=None, _depth=0, _return_value=None):
    '''
    Searches needle in haystack ( could be dict, list, list of dicts, nested dicts, etc. ) and returns the root key
    that has this needle somewhere within it's children.

    :param haystack: dict, list
    :param needle: search key
    :param return_key: if this is given, then the result will be the root_key[return_key] instead of root_key
    :param _inherited_key: internal usage, do not pass this.
    :param _depth: internal usage, do not pass this.
    :param _return_value: internal usage, do not pass this.
    :return:
    '''
    found = list()
    if type(haystack) is dict:
        for key, value in haystack.items():
            if not _depth:
                _inherited_key = key
                _return_value = key if not return_key else haystack[_inherited_key].get(return_key, _inherited_key)

            if key.lower() == needle.lower():
                found.append(_return_value)
            else:
                found.extend(find_root_by_key(value, needle, return_key, _inherited_key, _depth+1, _return_value))

    elif type(haystack) is list and _inherited_key is not None:
        for value in haystack:
            found.extend(find_root_by_key(value, needle, return_key, _inherited_key, _depth+1, _return_value))

    else:
        return []

    return list(set(found))


def jsonify(string):
    if type(string) is not str:
        return string

    try:
        return json.loads(string)
    except json.decoder.JSONDecodeError:
        return string


def get_resource_name_from_stash(stash, alternative_stash=None, address=None):
    if address is not None:
        return {'address': address}

    if type(alternative_stash) is str or type(alternative_stash) is bool or alternative_stash is None:
        if type(stash) is list:

            # Get the first number, since this is usually due to `count` usage in terraform
            if 'address' in stash[0]:
                return {'address': stash[0]['address'].replace('[0]','')}
            else:
                return {'address': stash[0]}

        else:
            if 'address' in alternative_stash:
                return alternative_stash
            else:
                return {'address': alternative_stash}


def get_resource_address_list_from_stash(resource_list):
    address_list = []
    for resource in resource_list:
        if 'address' in resource and resource['address'] not in address_list:
            address_list.append(resource['address'])

    return address_list


def remove_mounted_resources(resource_list):
    if type(resource_list) is not list:
        return resource_list

    resources = deepcopy(resource_list)
    for resource in resources:
        if 'terraform-compliance.mounted_resources' in resource:
            for mounted_resource_type in resource['terraform-compliance.mounted_resources']:
                if mounted_resource_type in resource['values']:
                    del resource['values'][mounted_resource_type]

    return resources


def search_regex_in_list(regex, target_list):
    if type(target_list) is list:
        return list(filter(re.compile(r'{}'.format(regex)).match, target_list))

    return False
