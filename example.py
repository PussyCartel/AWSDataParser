#!/bin/env python

from __future__ import division

import csv
import os
import re
import smtplib
import sys
from StringIO import StringIO
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

import boto
import xlsxwriter

instances_list = ec2_client.describe_instances().get('Reservations')

for i in range(instances_list.__len__()):
    current_instances = instances_list[i].get('Instances')
    print(current_instances[0].get("InstanceType"))

reload(sys)
sys.setdefaultencoding('utf8')

MAIL_TO = [
    "user@croc.ru",
]
MAIL_FROM = "c2-report@hosting.croc.ru"
MAIL_SUBJECT = "c2-report"
FILENAME = "c2-report22.xlsx"

EC2_URL = "https://api.cloud.croc.ru:443"
EC2_ACCESS_KEY = "vilyin:vilyin@cloud.croc.ru"
EC2_SECRET_KEY = "ZPhuMX1iQE6bchSp0weifw"

EC2conn = boto.connect_ec2_endpoint(
    EC2_URL,
    aws_access_key_id=EC2_ACCESS_KEY,
    aws_secret_access_key=EC2_SECRET_KEY
)

'''def send_mail(filename):
    msg = MIMEMultipart()
    with open(filename, "rb") as f:
        img = MIMEApplication(f.read(), _subtype="xlsx")
    img.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(img)

    msg["Subject"] = MAIL_SUBJECT
    msg["From"] = MAIL_FROM
    msg["To"] = ", ".join(MAIL_TO)

    server = smtplib.SMTP("localhost")
    server.sendmail(MAIL_FROM, MAIL_TO, msg.as_string())
    server.quit()
'''


class Instance(object):
    def __init__(self, instance, volumes, tags, network_interfaces, switches):
        self.id = instance.id
        self.devices = [{"volume_id": disk.volume_id} for _, disk in instance.block_device_mapping.iteritems()]
        self.disk_size = {}
        self.add_volumes(volumes)
        self.add_tags(tags)
        self.get_disk_size()
        self.status = instance._state.name
        self.create_time = instance.launch_time.replace("T", " ").replace("Z", "").replace("-", ".")
        self.az = instance._placement.zone
        self.placement_group = instance._placement.group_name or "NONE"
        self.type = instance.instance_type
        self.cpu, self.ram = Instance.instance_type_info(self.type)
        self.switch = []
        for i in instance.interfaces:
            for _, v in network_interfaces.items():
                if i.id == v.id:
                    self.switch.append(v.subnet_id or v.switchId)
        self.switches_name = []
        for s in self.switch:
            if switches.get(s):
                self.switches_name.append(switches[s].name)
            else:
                self.switches_name.append(s)

    def _print_header(self):
        return "n/n'id'tag_name'type'cpu'ram'switch'" \
               "'{devices}'az'placement_group".format(
            devices="io1_400'io1_1000'io1_3000'io1_5000'st2_500'gp2",
        )

    def __str__(self):
        info = "{id}'{tag_name}'{type}'{cpu}'{ram}'{os}'" \
               "{switch}'{devices}'{az}'{placement_group}".format(
            id=self.id,
            tag_name=self.tags.get("name", ""),
            type=self.type,
            cpu=self.cpu,
            ram=self.ram,
            switch=self.switch,
            devices=self._print_disk_size(),
            az=self.az,
            placement_group=self.placement_group,
        )
        return (info)

    def _print_disk_size(self):
        return "{io1_400}'{io1_1000}'{io1_3000}'{io1_5000}'" \
               "{st2_500}'{gp2}".format(**self.disk_size)

    @staticmethod
    def instance_type_info(instance_type):
        instance_type = str(instance_type)
        pool, size = instance_type.split(".")

        if re.findall(r"\d+", size):
            size_ratio = int(re.findall(r"\d+", size)[0])
        else:
            size_ratio = 1

        if pool.startswith("r") or pool.startswith("m2"):
            pool_ratio = 8
        elif pool.startswith("m"):
            pool_ratio = 4
        elif pool.startswith("c"):
            pool_ratio = 2
        elif pool.startswith("x"):
            pool_ratio = 15
        elif pool.startswith("x3l"):
            pool_ratio = 22.5

        if "micro" in size:
            cores = 1 / 32 * size_ratio
            memory = cores * pool_ratio
        elif "small" in size:
            cores = 1 / 2 * size_ratio
            memory = cores * pool_ratio
        elif "medium" in size:
            cores = 1 * size_ratio
            memory = cores * pool_ratio
        elif "large" in size:
            cores = 2 * size_ratio
            memory = cores * pool_ratio
        elif "xlarge" in size:
            cores = 3 * size_ratio
            memory = cores * pool_ratio
        else:
            cores = "None"
            memory = "None"

        return cores, memory

    def add_volumes(self, volumes):
        for device in self.devices:
            for v_id, volume in volumes.items():
                if v_id == device["volume_id"]:
                    device["size"] = volume.size
                    device["iops"] = volume.iops
                    device["volume_type"] = volume.type

    def add_tags(self, tags):
        self.tags = {}
        for res_id, t in tags.items():
            if res_id == self.id:
                if t.name == "Name":
                    self.tags["name"] = t.value

    def get_disk_size(self):
        st2 = 0
        gp2 = 0
        io2 = 0
        for device in self.devices:
            if device.get("volume_type") == "st2":
                st2 += device["size"]
            elif device.get("volume_type") == "gp2":
                gp2 += device["size"]
            elif device.get("volume_type") == "io2":
                io2 += device["size"]

        self.disk_size = {
            "st2": st2,
            "gp2": gp2,
            "io2": io2,
        }

    def get_info(self, number):
        return [
            number,
            self.create_time,
            self.id,
            self.type,
            self.status,
            self.tags.get("name", ""),
            self.placement_group,
            self.cpu,
            self.ram,
            self.disk_size["st2"],
            self.disk_size["gp2"],
            self.disk_size["io2"],
            ", ".join(self.switches_name),
            self.az,
        ]

    def csv(self, number, delimiter=";"):
        out = StringIO()
        writer = csv.writer(out, delimiter=delimiter, lineterminator='')
        row = self.get_info(number)
        writer.writerow(row)
        return out.getvalue()

    @staticmethod
    def get_header():
        return [
            "#",
            "Create Date",
            "VM ID",
            "VM Type",
            "State",
            "Tag Name",
            "Placement group",
            "CPU",
            "RAM",
            "st2",
            "gp2",
            "io2",
            "Switch",
            "Datacenter",
        ]

    @staticmethod
    def csv_header(delimiter=";"):
        """Return CSV Headers"""

        row = Instance.get_header()
        out = StringIO()
        writer = csv.writer(out, delimiter=delimiter, lineterminator='')
        writer.writerow(row)
        return out.getvalue()


class EC2Resources(object):

    def __init__(self):
        self.switches = dict((s.id, s) for s in EC2conn.get_all_virtual_switches())
        self.network_interfaces = dict((n.id, n) for n in EC2conn.get_all_network_interfaces())
        self.volumes = dict((v.id, v) for v in EC2conn.get_all_volumes())
        self.tags = dict((t.res_id, t) for t in EC2conn.get_all_tags())
        self.instances = [
            Instance(j, self.volumes, self.tags, self.network_interfaces, self.switches)
            for j in [i for r in EC2conn.get_all_instances()
                      for i in r.instances] if j.id
        ]
        self.sorted_instances = sorted(self.instances, key=lambda i: i.create_time)

    def __str__(self):
        number = 0
        info = Instance.csv_header() + "\n"
        for i in self.sorted_instances:
            number += 1
            info += i.csv(number) + "\n"
        return (info)

    def create_table(self):
        name = FILENAME
        workbook = xlsxwriter.Workbook(name)
        worksheet = workbook.add_worksheet()

        row = 0
        column = 0
        number = 0

        content = Instance.get_header()
        for item in content:
            worksheet.write(row, column, item)
            column += 1

        for i in self.sorted_instances:
            number += 1
            column = 0
            row += 1
            for item in i.get_info(number):
                worksheet.write(row, column, item)
                column += 1

        workbook.close()
        return name


def main():
    resources = EC2Resources()
    table = resources.create_table()
    # send_mail(table)


if __name__ == "__main__":
    main()