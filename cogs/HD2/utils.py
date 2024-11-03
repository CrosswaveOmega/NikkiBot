from typing import *
import re


def split_and_cluster_strings(
    input_string: str, max_cluster_size: int, split_substring: str, length=len
) -> list[str]:
    """
    Split up the input_string by the split_substring
    and group the resulting substrings into
    clusters of about max_cluster_size length.
    Return the list of clusters.

    Args:
    input_string (str): The string to be split and clustered.
    max_cluster_size (int): The preferred maximum length of each cluster.
    split_substring (str): The substring used to split the input_string.
    length(Callable):  function to determine string length with.

    Returns:
    list[str]: A list of clusters.
    """
    clusters = []
    # There's no reason to split if input is already less than max_cluster_size
    if length(input_string) < max_cluster_size:
        return [input_string]

    split_by = split_substring

    is_regex = isinstance(split_substring, re.Pattern)
    if is_regex:
        result = split_substring.split(input_string)
        substrings = [r for r in result if r]
    else:
        if "%s" not in split_substring:
            split_by = "%s" + split_by
        split_character = split_by.replace("%s", "")

        # Split the input string based on the specified substring
        substrings = input_string.split(split_character)

    # No reason to run the loop if there's less than two
    # strings within the substrings list.  That means
    # it couldn't find anything to split up.
    if len(substrings) < 2:
        return [input_string]

    current_cluster = substrings[0]
    for substring in substrings[1:]:
        if not is_regex:
            new_string = split_by.replace("%s", substring, 1)
        else:
            new_string = substring
        sublength = length(new_string)
        if length(current_cluster) + sublength <= max_cluster_size:
            # Add the substring to the current cluster
            current_cluster += new_string
        else:
            # Adding to the current cluster will exceed the maximum size,
            # So start a new cluster.
            if current_cluster:
                # Don't add to clusters if current_cluster is empty.
                clusters.append(current_cluster)
            current_cluster = ""
            if substring:
                # Don't add to current_cluster if substring is empty.
                # Add the last cluster if not empty.
                current_cluster = new_string
    if current_cluster:
        clusters.append(current_cluster)  # Remove the trailing split_substring

    return clusters


def prioritized_string_split(
    input_string: str,
    substring_split_order: list[Union[str, tuple[str, int]]],
    default_max_len: int = 1024,
    trim=False,
    length=len,
) -> list[str]:
    """
    Segment the input string based on the delimiters specified in `substring_split_order`.
    Then, concatenate these segments to form a sequence of grouped strings,
    ensuring that no cluster surpasses a specified maximum length.
    The maximum length for each cluster addition
    can be individually adjusted along with the list of delimiters.


    Args:
        input_string (str): The string to be split.
        substring_split_order (list[Union[str, tuple[str, int]]]):
            A list of strings or tuples containing
            the delimiters to split by and their max lengths.
            If an argument here is "%s\\n", then the input string will be split by "\\n" and will
            place the relevant substrings in the position given by %s.
        default_max_len (int): The maximum length a string in a cluster may be if not given
            within a specific tuple for that delimiter.
        trim (bool): If True, trim leading and trailing whitespaces in each cluster. Default is False.

    Returns:
        list[str]: A list of clusters containing the split substrings.
    """

    # Initalize new cluster
    current_clusters = [input_string]
    for e, arg in enumerate(substring_split_order):
        if isinstance(arg, str):
            s, max_len = arg, None
        elif isinstance(arg, re.Pattern):
            s, max_len = arg, None
        elif len(arg) == 1:
            s, max_len = arg[0], None
        else:
            s, max_len = arg

        max_len = max_len or default_max_len  # Use default if not specified
        split_substring = s
        new_splits = []

        for cluster in current_clusters:
            result_clusters = split_and_cluster_strings(
                cluster, max_len, split_substring, length=length
            )
            new_splits.extend(result_clusters)
        # for c_num, cluster in enumerate(new_splits):
        #    print(f"Pass {e},  Cluster {c_num + 1}: {len(cluster)}, {len(cluster)}")
        current_clusters = new_splits

    # Optional trimming of leading and trailing whitespaces
    if trim:
        current_clusters = [cluster.strip() for cluster in current_clusters]

    return current_clusters


# def replaceTimestamp(timestamp):
#     isoformat_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?Z"
#     match = re.search(isoformat_pattern, timestamp)

#     if match:
#         fdt_result = fdt(match.group(0))
#         return fdt_result

#     return None
