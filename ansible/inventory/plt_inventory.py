#!/usr/bin/env python3

import json
import boto3


def get_name_tag(tags):
    for tag in tags:
        if tag["Key"] == "EXTERNAL-FQDN":
            return tag["Value"].lower()
    for tag in tags:
        if tag["Key"] == "Name":
            return tag["Value"].lower() + ".mydomain.com"
    return None


def get_instances(account="Dev_Shared", inventory=[]):
    # Establishing a session using an AWS profile
    session = boto3.Session(profile_name=account)

    # Create a resource service client by name using the region name
    ec2 = session.resource(
        "ec2", region_name="us-west-2"
    )  # Replace 'us-west-2' with your region

    # Now you can use the instances attribute
    instances = ec2.instances.all()

    skip_these_names = [
        "exceptions"
    ]
    # Loop through each instance
    for instance in instances:
        identifier = get_name_tag(instance.tags)
        if identifier is None:
            continue  # Skip instances without a Name tag
        skip_host = False
        for skipname in skip_these_names:
            if skipname in identifier:
                skip_host = True
        if skip_host:
            continue

        if instance.state["Name"] == "terminated":
            continue

        # Sort running and stopped instances into their OS groups
        if instance.state["Name"] == "running" or instance.state["Name"] == "stopped":
            # Check the platform
            if instance.platform == "windows":
                inventory["windows"].append(identifier)
            else:
                inventory["linux"].append(identifier)

        # If stopped put in off group
        if instance.state["Name"] == "stopped":
            inventory["off"].append(identifier)

        # Check for specific tag
        found_buoy_tag = False
        found_complete_tag = False
        for tag in instance.tags:
            if tag["Key"] == "BUOY-ENABLED" or tag["Key"] == "BUOY-SERVER-NAME":
                inventory["buoy"].append(identifier)
                found_buoy_tag = True
            if tag["Key"] == "PROVISION-STATE" and tag["Value"] == "COMPLETE":
                found_complete_tag = True

        if found_complete_tag:
            inventory["complete"].append(identifier)
        if not found_buoy_tag:
            inventory["secure"].append(identifier)

        # Add hostvars
        inventory["_meta"]["hostvars"][identifier] = {
            "ansible_host": instance.private_ip_address,
            "instance_id": instance.id,
            "image_id": instance.image_id,
            "instance_type": instance.instance_type,
            "subnet_id": instance.subnet_id,
            "vpc_id": instance.vpc_id,
            "tags": instance.tags,
            "state": instance.state["Name"],
        }

    return inventory


def main():
    blank_inventory = {
        "windows": [],
        "linux": [],
        "buoy": [],
        "secure": [],
        "off": [],
        "complete": [],
        "_meta": {"hostvars": {}},
    }
    inventory = blank_inventory
    for account in [
        "Dev_Shared",
        "Shared_Services",
        "UAT_Shared",
        "Prod_Shared",
        "Networking",
    ]:
        account_inventory = get_instances(account, blank_inventory)
        for key in inventory.keys():
            if key != "_meta":
                inventory[key].extend(account_inventory[key])
            else:
                inventory["_meta"]["hostvars"].update(
                    account_inventory["_meta"]["hostvars"]
                )

    print(json.dumps(inventory, indent=2))


if __name__ == "__main__":
    main()
