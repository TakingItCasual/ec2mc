from ec2mc.stuff import aws
from ec2mc.stuff.threader import Threader
from ec2mc.stuff import halt

def main(kwargs):
    """wrapper for probe_regions() which prints found instances to the CLI

    Requires ec2:DescribeRegions and ec2:DescribeInstances permissions.

    Quits out if no instances are found. This functionality is relied upon.

    Args:
        kwargs (dict):
            "region": list: AWS region(s) to probe. If None, probe all.
            "tagfilter": Instance tag key-value pair(s) to filter by. If None, 
                don't filter. If only a key is given, filter by key.

    Returns:
        list of dict(s): Found instance(s).
            "region": AWS region that an instance is in.
            "id": ID of instance.
            "tags": dict: Instance tag key-value pairs.
    """

    region_filter = kwargs["regions"]
    regions = aws.get_regions(region_filter)

    tag_filter = []
    if kwargs["tagfilter"]:
        # Convert dict(s) list to what describe_instances' Filters expects.
        for tag_kv_pair in kwargs["tagfilter"]:
            # Filter instances based on tag key-value(s) pair.
            if len(tag_kv_pair) > 1:
                tag_filter.append({
                    "Name": "tag:"+tag_kv_pair[0],
                    "Values": tag_kv_pair[1:]
                })
            # If filter tag value(s) not specified, filter by the tag key.
            else:
                tag_filter.append({
                    "Name": "tag-key",
                    "Values": [tag_kv_pair[0]]
                })
    if kwargs["namefilter"]:
        tag_filter.append({
            "Name": "tag:Name",
            "Values": kwargs["namefilter"]
        })

    print("")
    print("Probing " + str(len(regions)) + " AWS region(s) for instances...")

    all_instances = probe_regions(regions, tag_filter)

    for region in regions:
        instances = [instance for instance in all_instances
            if instance["region"] == region]
        if not instances:
            continue
        print(region + ": " + str(len(instances)) + " instance(s) found:")
        for instance in instances:
            print("  " + instance["id"])
            for tag_key, tag_value in instance["tags"].items():
                print("    " + tag_key + ": " + tag_value)

    if not all_instances:
        if region_filter and not tag_filter:
            halt.err(["No instances found from specified region(s).",
                "  Try removing the region filter."])
        if not region_filter and tag_filter:
            halt.err(["No instances with specified tag(s) found.",
                "  Try removing the tag filter."])
        if region_filter and tag_filter:
            halt.err([("No instances with specified tag(s) found "
                "from specified region(s)."),
                "  Try removing the region filter and/or the tag filter."])
        halt.err(["No instances found."])

    return all_instances


def probe_regions(regions, tag_filter=None):
    """probe EC2 region(s) for instances, and return dict(s) of instance(s)

    Uses multithreading to probe all regions simultaneously.

    Args:
        regions (list): List of EC2 regions to probe.
        tag_filter (dict): Passed to probe_region

    Returns:
        list of dict(s): Found instance(s).
            "region": AWS region that an instance is in.
            "id": ID of instance.
            "tags": dict: Instance tag key-value pairs.
    """

    threader = Threader()
    for region in regions:
        threader.add_thread(probe_region, (region, tag_filter))
    regions_info = threader.get_results()

    all_instances = []
    for region_info in regions_info:
        for instance in region_info["instances"]:
            all_instances.append({
                "region": region_info["region"],
                "id": instance["id"],
                "tags": instance["tags"]
            })

    return all_instances


def probe_region(region, tag_filter=None):
    """probe a single EC2 region for instances (threaded)

    Args:
        region (str): EC2 region to probe.
        tag_filter (dict): Filter out instances that don't have tags matching
            the filter. If None, filter not used.

    Returns:
        dict: Instance(s) found in region.
            "region": Probed EC2 region.
            "instances": list of dict(s): Instance(s) found.
                "id": ID of instance.
                "tags": Instance tags.
    """

    if tag_filter is None:
        tag_filter = []

    reservations = aws.ec2_client(
        region).describe_instances(Filters=tag_filter)["Reservations"]

    region_instances = {
        "region": region,
        "instances": []
    }

    for reservation in reservations:
        for instance in reservation["Instances"]:
            region_instances["instances"].append({
                "id": instance["InstanceId"],
                "tags": {
                    tag["Key"]: tag["Value"] for tag in instance["Tags"]
                }
            })

    return region_instances


def get_all_tags():
    """get instance tags from all instances in all regions"""
    tags = []
    all_instances = probe_regions(aws.get_regions())
    for instance in all_instances:
        tags.append(instance["tags"])
    return tags


def argparse_args(cmd_parser):
    """initialize arguments for argparse that verify_instances:main needs"""
    cmd_parser.add_argument(
        "-r", dest="regions", nargs="+", metavar="",
        help=("AWS EC2 region(s) to probe for instances. If not set, all "
            "regions will be probed."))
    cmd_parser.add_argument(
        "-t", dest="tagfilter", nargs="+", action="append", metavar="",
        help=("Instance tag value filter. First value is the tag key, with "
            "proceeding value(s) as the tag value(s). If not set, no filter "
            "will be applied. If only 1 value given, the tag key itself will "
            "be filtered for instead."))
    cmd_parser.add_argument(
        "-n", dest="namefilter", nargs="+", metavar="",
        help="Instance tag value filter for the tag key \"Name\".")
