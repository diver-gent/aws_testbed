__author__ = 'townsley'
import boto.ec2
import time
import os
import os.path
import yaml

conf_file='./aws.yaml'


def setup(conf=conf_file):
    # global variable to hold config data
    global C
    with open(conf, 'r') as stream:
        C = yaml.load(stream)

    # massage key_dir to make it OS friendly
    C['key_dir'] = os.path.expanduser(C['key_dir'])
    C['key_dir'] = os.path.expandvars(C['key_dir'])
    if not os.path.isdir(C['key_dir']):
                    os.mkdir(C['key_dir'], 0700)


def create_key_pair(ec2):
    try:
        key = ec2.get_all_key_pairs(keynames=[C['key_name']])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidKeyPair.NotFound':
            if C['debug']: print 'Creating keypair: %s' % C['key_name']
            key = ec2.create_key_pair(C['key_name'])
            key.save(C['key_dir'])
        else:
            raise
    if C['debug']: print 'Key Pair', key.name, 'is available'


def create_sec_group(ec2):
    try:
        group = ec2.get_all_security_groups(groupnames=[C['sec_group_id']])[0]
    except ec2.ResponseError, e:
        if e.code == 'InvalidGroup.NotFound':
            if C['debug']: print 'Creating Security Group: %s' % C['sec_group_id']
            group = ec2.create_security_group(C['sec_group_id'], 'group with ssh/http access')
        else:
            raise
    if C['debug']: print 'Security Group', group, 'is available'

    for port in [C['ssh_port'], C['http_port']]:
        try:
            group.authorize('tcp', port, port, C['cidr'])
        except ec2.ResponseError, e:
            if e.code == 'InvalidPermission.Duplicate':
                if C['debug']: print 'Security Group: %s already authorized for tcp port', port
            else:
                raise
        if C['debug']: print 'Security group %s authorized for tcp port', port


def create_instances(ec2, count=3):

    create_key_pair(ec2)
    create_sec_group(ec2)
    reservation = ec2.run_instances(C['drupal_ami'],
                                    key_name=C['key_name'],
                                    security_groups=[C['sec_group_id']],
                                    instance_type=C['instance_type'],
                                    user_data=C['user_data'],
                                    max_count=count)
    if C['debug']: print 'Reservation ID = ', reservation.id

    instance = reservation.instances[0]
    while instance.state != 'running':
        if C['debug']: print 'Instance ID', instance.id, 'is', instance.state, '...'
        time.sleep(5)
        instance.update()

    ec2.create_tags(instance.id, {'Name': C['tag_name']})

    if C['debug']: print 'Instance state is', instance.state
    if C['debug']: print 'Instance FQDN is', instance.public_dns_name


def print_instances(ec2, tag):
    instances = ec2.get_all_instances(filters={'tag:Name':'drupal_node'})
    for instance in instances:
        print instance.id



# ec2.terminate_instances(instance.id)
# while instance.state != 'terminated':
#     print 'Instance state is', instance.state, '...'
#     time.sleep(5)
#     instance.update()
# print 'Instance state is', instance.state, '!'

if __name__ == "__main__":
    setup()
    ec2 = boto.ec2.connect_to_region(C['region'])
    create_instances(ec2)
    print_instances(ec2, C['tag_name'])


