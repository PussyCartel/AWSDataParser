import boto3

session = boto3.session.Session()

ec2_client = session.client(
    'ec2',
    aws_access_key_id='vilyin:vilyin@cloud.croc.ru',
    aws_secret_access_key='ZPhuMX1iQE6bchSp0weifw',
    endpoint_url='https://api.cloud.croc.ru',
    region_name='US'
)

print(ec2_client.describe_volumes(VolumeIds=['vol-4F90CA21']))