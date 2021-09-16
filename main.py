import os

import boto3
import pandas as pd
import re
import os

session = boto3.session.Session()

print(os.environ)

ec2_client = session.client(
    'ec2',
    aws_access_key_id='vilyin:vilyin@cloud.croc.ru',
    aws_secret_access_key='ZPhuMX1iQE6bchSp0weifw',
    endpoint_url='https://api.cloud.croc.ru',
    region_name='US'
)

# Возвращает два объекта: Reservation и ResponseMetadata
instances_list = ec2_client.describe_instances()

if instances_list['ResponseMetadata']['HTTPStatusCode'] != 200:
    raise ValueError('Ошибка на стадии отправки запроса к API https://api.cloud.croc.ru')

instances_list = instances_list.get('Reservations')

final_data = pd.DataFrame({"#": [i + 1 for i in range(instances_list.__len__())]})


class Instance:

    def __init__(self, date, instance_id, instance_type, state, name, device_list, group, switches, zone):
        self.date = date
        self.instance_id = instance_id
        self.instance_type = instance_type
        self.state = state
        self.name = name
        self.cpu = 0
        self.ram = 0
        self.device_list = device_list
        self.group = group
        self.switches = switches
        self.zone = zone
        self.st2 = 0
        self.gp2 = 0
        self.io2 = 0

    # Метод анализирует instance_type и на выходе выдаёт значения cpu и ram
    def convert_cpu_ram(self):
        # Разбиваем строку на две по точке к примеру "r5.xlarge" бьётся на ['r5', 'xlarge']
        array = self.instance_type.split('.')
        pool, size = array[0], array[1]

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
        self.cpu = cores
        self.ram = memory

    # Метод парсит полученный массив дисков и на выходе выдаёт объем каждого типа диска в ГБ
    def describe_disks_capacity(self):
        for disk in self.device_list:
            volume_list = []
            if not re.match('^cdrom', disk.get('DeviceName')):
                volume_list.append(disk.get('Ebs').get('VolumeId'))
                volume_data = ec2_client.describe_volumes(VolumeIds=volume_list)['Volumes'][0]
                if volume_data['VolumeType'] == 'st2':
                    self.st2 += int(volume_data['Size'])
                if volume_data['VolumeType'] == 'gp2':
                    self.gp2 += int(volume_data['Size'])
                if volume_data['VolumeType'] == 'io2':
                    self.io2 += int(volume_data['Size'])



def main():
    # Инициаилазурем массивы, которые в последствии будут добавлены в датафрейс final_data
    instances_id_list = []
    instances_types_list = []
    create_date_list = []
    states = []
    tag_name_list = []
    placement_group_list = []
    cpu_list = []
    ram_list = []
    st2_list = []
    gp2_list = []
    io2_list = []
    switches_list = []
    az_list = []

    for i in range(instances_list.__len__()):
        current_instances = instances_list[i].get('Instances')[0]
        instance_id = current_instances.get("InstanceId")
        instances_id_list.append(instance_id)
        instance_type = current_instances.get('InstanceType')
        instances_types_list.append(instance_type)
        create_date = current_instances.get('LaunchTime')
        create_date_list.append(str(create_date))
        state = current_instances['State']['Name']
        states.append(state)
        tag_name = current_instances['Tags'][0]['Value']
        tag_name_list.append(tag_name)
        placement_group = current_instances['Placement'].get('GroupName')
        placement_group_list.append(placement_group)
        device_list = current_instances['BlockDeviceMappings']
        switches = current_instances['SubnetId']
        switches_list.append(switches)
        aviable_zone = current_instances['Placement'].get('AvailabilityZone')
        az_list.append(aviable_zone)
        instance = Instance(create_date, instance_id, instance_type,
                            state, tag_name, device_list,
                            placement_group, switches, aviable_zone)
        instance.convert_cpu_ram()
        instance.describe_disks_capacity()
        cpu_list.append(instance.cpu)
        ram_list.append(instance.ram)
        st2_list.append(instance.st2)
        gp2_list.append(instance.gp2)
        io2_list.append(instance.io2)

    final_data.insert(1, "Create Date", create_date_list)
    final_data.insert(2, "VM ID", instances_id_list)
    final_data.insert(3, "VM Type", instances_types_list)
    final_data.insert(4, "State", states)
    final_data.insert(5, "Tag Name", tag_name_list)
    final_data.insert(6, "Placement Group", placement_group_list)
    final_data.insert(7, "CPU", cpu_list)
    final_data.insert(8, "RAM", ram_list)
    final_data.insert(9, "st2", st2_list)
    final_data.insert(10, "gp2", gp2_list)
    final_data.insert(11, "io2", io2_list)
    final_data.insert(12, "Switches", switches_list)
    final_data.insert(13, 'Datacenter', az_list)

    final_data.to_excel("goods.xlsx")


if __name__ == "__main__":
    main()
