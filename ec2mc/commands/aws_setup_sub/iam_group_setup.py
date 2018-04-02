import os
import json

from ec2mc import config
from ec2mc import update_template
from ec2mc.stuff import aws
from ec2mc.stuff import simulate_policy

import pprint
pp = pprint.PrettyPrinter(indent=2)

class IAMGroupSetup(update_template.BaseClass):

    def verify_component(self):
        """determine which groups need creating/updating, and which don't

        Returns:
            group_names (dict):
                "AWSExtra": Extra groups on AWS found under same namespace
                "ToCreate": Groups that do not (yet) exist on AWS
                "ToUpdate": Groups on AWS, but not the same as local versions
                "UpToDate": Groups on AWS and up-to-date with local versions
        """

        self.iam_client = aws.iam_client()
        self.path_prefix = "/" + config.NAMESPACE + "/"

        # Verify that aws_setup.json exists, and read it to a dict
        aws_setup_file = config.AWS_SETUP_DIR + "aws_setup.json"
        if not os.path.isfile(aws_setup_file):
            quit_out.err(["aws_setup.json not found from config."])
        with open(aws_setup_file) as f:
            self.iam_group_setup = json.loads(f.read())["IAM"]["Groups"]

        # Groups already present on AWS
        aws_groups = self.get_iam_groups()

        # Names of local policies described in aws_setup.json
        group_names = {
            "AWSExtra": [],
            "ToCreate": [group["Name"] for group in self.iam_group_setup],
            "ToUpdate": [],
            "UpToDate": []
        }

        # Check if group(s) described by aws_setup.json already on AWS
        for local_group in group_names["ToCreate"][:]:
            for aws_group in aws_groups:
                if local_group == aws_group["GroupName"]:
                    # Group already exists on AWS, so next check if to update
                    group_names["ToCreate"].remove(local_group)
                    group_names["ToUpdate"].append(local_group)
                    break

        # Check if group(s) on AWS need attachment(s) updated
        for local_group in group_names["ToUpdate"][:]:
            aws_attachments = [policy["PolicyName"] for policy in
                self.iam_client.list_attached_group_policies(
                    GroupName=local_group,
                    PathPrefix=self.path_prefix
                )["AttachedPolicies"]]

            local_attachments = next(group["Policies"] for group in
                self.iam_group_setup if group["Name"] == local_group)

            if aws_attachments == local_attachments:
                # Local group and AWS group match, so no need to update
                group_names["ToUpdate"].remove(local_group)
                group_names["UpToDate"].append(local_group)

        return group_names


    def notify_state(self, group_names):
        for group in group_names["AWSExtra"]:
            print("IAM group " + group + " found on AWS but not locally.")
        for group in group_names["ToCreate"]:
            print("Local IAM group " + group + " to be created on AWS.")
        for group in group_names["ToUpdate"]:
            print("Local IAM group " + group + " to be updated on AWS.")
        for group in group_names["UpToDate"]:
            print("IAM group " + group + " on AWS is up to date.")


    def upload_component(self, group_names):
        """create groups on AWS that don't exist, update groups that do

        Args:
            group_names (dict): See what verify_component returns
        """

        for local_group in group_names["ToCreate"]:
            self.iam_client.create_group(
                Path=self.path_prefix,
                GroupName=local_group
            )

            local_attachments = next(group["Policies"] for group in
                self.iam_group_setup if group["Name"] == local_group)
            aws_policies = self.iam_client.list_policies(
                Scope="Local",
                OnlyAttached=False,
                PathPrefix=self.path_prefix
            )["Policies"]
            pp.pprint(aws_policies)

            for attachment in local_attachments:
                aws_policy_arn = next(aws_policy["Arn"] for aws_policy in
                    aws_policies if aws_policy["PolicyName"] == attachment)
                self.iam_client.attach_group_policy(
                    GroupName=attachment,
                    PolicyArn=aws_policy_arn
                )

            print("IAM group " + local_group + " created on AWS.")

        for local_group in group_names["ToUpdate"]:
            # TODO
            print("IAM group " + local_group + " (not) updated on AWS.")

        for local_group in group_names["UpToDate"]:
            print("IAM group " + local_group + " on AWS already up to date.")


    def delete_component(self, _):
        """remove users and policys, then delete groups"""

        aws_groups = self.get_iam_groups()
        if not aws_groups:
            print("No IAM groups on AWS to delete.")

        for aws_group in aws_groups:

            aws_group_users = self.iam_client.get_group(
                GroupName=aws_group["GroupName"])["Users"]
            for aws_group_user in aws_group_users:
                self.iam_client.remove_user_from_group(
                    GroupName=aws_group["GroupName"],
                    UserName=aws_group_user["UserName"]
                )

            attached_policy_arns = [policy["PolicyArn"] for policy in
                self.iam_client.list_attached_group_policies(
                    GroupName=aws_group["GroupName"],
                    PathPrefix=self.path_prefix
                )["AttachedPolicies"]]
            for attached_policy_arn in attached_policy_arns:
                self.iam_client.detach_group_policy(
                    GroupName=aws_group["GroupName"],
                    PolicyArn=attached_policy_arn
                )

            self.iam_client.delete_group(GroupName=aws_group["GroupName"])

            print("IAM group " + aws_group["GroupName"] + " deleted from AWS.")


    def get_iam_groups(self):
        """returns group(s) on AWS under set namespace"""
        return self.iam_client.list_groups(
            PathPrefix=self.path_prefix)["Groups"]


    def blocked_actions(self, kwargs):
        self.check_actions = [
            "iam:ListGroups",
            "iam:ListAttachedGroupPolicies"
        ]
        self.upload_actions = [
            "iam:CreateGroup",
            "iam:ListPolicies",
            "iam:AttachGroupPolicy"
        ]
        self.delete_actions = [
            "iam:DeleteGroup",
            "iam:GetGroup",
            "iam:RemoveUserFromGroup",
            "iam:DetachGroupPolicy",
            "iam:DeleteGroup"
        ]
        return simulate_policy.blocked(actions=super().blocked_actions(kwargs))